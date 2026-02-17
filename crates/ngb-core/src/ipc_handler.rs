use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use ngb_config::Config;
use ngb_types::{NanoGridBotError, Result};
use tokio::task::JoinHandle;
use tracing::{debug, error, info, warn};

/// Trait for channel adapters that can send outbound messages.
///
/// Defined here in the IPC handler because it is the primary consumer:
/// the IPC watcher routes container output to channels via this trait.
pub trait ChannelSender: Send + Sync {
    /// Return true if this sender handles the given JID.
    fn owns_jid(&self, jid: &str) -> bool;

    /// Send a text message to the specified JID.
    fn send_message(
        &self,
        jid: &str,
        text: &str,
    ) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<()>> + Send + '_>>;
}

/// File-based IPC handler that bridges containers and channel adapters.
///
/// For each watched group JID, a background task polls
/// `{data_dir}/ipc/{jid}/output/*.json` and routes results to channels.
pub struct IpcHandler {
    running: Arc<AtomicBool>,
    watchers: HashMap<String, JoinHandle<()>>,
    channels: Arc<Vec<Box<dyn ChannelSender>>>,
    data_dir: PathBuf,
    poll_interval_ms: u64,
}

impl IpcHandler {
    /// Create a new IPC handler.
    pub fn new(channels: Arc<Vec<Box<dyn ChannelSender>>>, config: &Config) -> Self {
        Self {
            running: Arc::new(AtomicBool::new(false)),
            watchers: HashMap::new(),
            channels,
            data_dir: config.data_dir.clone(),
            poll_interval_ms: 500,
        }
    }

    /// Start watching IPC output directories for the given JIDs.
    pub fn start(&mut self, jids: &[String]) {
        self.running.store(true, Ordering::SeqCst);
        info!(count = jids.len(), "Starting IPC watchers");

        for jid in jids {
            if self.watchers.contains_key(jid) {
                continue;
            }
            let output_dir = self.data_dir.join("ipc").join(jid).join("output");
            let running = self.running.clone();
            let channels = self.channels.clone();
            let jid_clone = jid.clone();
            let interval = self.poll_interval_ms;

            let handle = tokio::spawn(async move {
                watcher_loop(&jid_clone, &output_dir, &running, &channels, interval).await;
            });

            self.watchers.insert(jid.clone(), handle);
        }
    }

    /// Stop all IPC watchers.
    pub fn stop(&mut self) {
        self.running.store(false, Ordering::SeqCst);
        for (jid, handle) in self.watchers.drain() {
            handle.abort();
            debug!(jid, "Stopped IPC watcher");
        }
        info!("All IPC watchers stopped");
    }

    /// Check if the handler is running.
    pub fn is_running(&self) -> bool {
        self.running.load(Ordering::SeqCst)
    }

    /// Write an input file for a container to consume.
    ///
    /// Uses atomic write (tmp file + rename) to prevent partial reads.
    pub async fn write_input(&self, jid: &str, data: &serde_json::Value) -> Result<()> {
        let input_dir = self.data_dir.join("ipc").join(jid).join("input");
        tokio::fs::create_dir_all(&input_dir).await.map_err(|e| {
            NanoGridBotError::Container(format!("Failed to create IPC input dir: {e}"))
        })?;

        let ts = chrono::Utc::now().timestamp_millis();
        let filename = format!("input-{ts}.json");
        let tmp_path = input_dir.join(format!(".tmp-{filename}"));
        let final_path = input_dir.join(&filename);

        tokio::fs::write(&tmp_path, serde_json::to_vec_pretty(data)?)
            .await
            .map_err(|e| NanoGridBotError::Container(format!("Failed to write IPC input: {e}")))?;
        tokio::fs::rename(&tmp_path, &final_path)
            .await
            .map_err(|e| NanoGridBotError::Container(format!("Failed to rename IPC input: {e}")))?;

        debug!(jid, filename, "Wrote IPC input file");
        Ok(())
    }

    /// Write an output file (typically called by containers or tests).
    pub async fn write_output(&self, jid: &str, data: &serde_json::Value) -> Result<()> {
        let output_dir = self.data_dir.join("ipc").join(jid).join("output");
        tokio::fs::create_dir_all(&output_dir).await.map_err(|e| {
            NanoGridBotError::Container(format!("Failed to create IPC output dir: {e}"))
        })?;

        let ts = chrono::Utc::now().timestamp_millis();
        let filename = format!("output-{ts}.json");
        let tmp_path = output_dir.join(format!(".tmp-{filename}"));
        let final_path = output_dir.join(&filename);

        tokio::fs::write(&tmp_path, serde_json::to_vec_pretty(data)?)
            .await
            .map_err(|e| NanoGridBotError::Container(format!("Failed to write IPC output: {e}")))?;
        tokio::fs::rename(&tmp_path, &final_path)
            .await
            .map_err(|e| {
                NanoGridBotError::Container(format!("Failed to rename IPC output: {e}"))
            })?;

        debug!(jid, filename, "Wrote IPC output file");
        Ok(())
    }

    /// Number of active watchers.
    pub fn watcher_count(&self) -> usize {
        self.watchers.len()
    }
}

/// Background loop that polls a JID's output directory and routes messages.
async fn watcher_loop(
    jid: &str,
    output_dir: &PathBuf,
    running: &AtomicBool,
    channels: &[Box<dyn ChannelSender>],
    interval_ms: u64,
) {
    debug!(jid, dir = %output_dir.display(), "IPC watcher started");

    while running.load(Ordering::SeqCst) {
        tokio::time::sleep(std::time::Duration::from_millis(interval_ms)).await;

        let mut entries = match tokio::fs::read_dir(output_dir).await {
            Ok(e) => e,
            Err(_) => continue,
        };

        let mut files = Vec::new();
        while let Ok(Some(entry)) = entries.next_entry().await {
            let path = entry.path();
            if path.extension().is_some_and(|ext| ext == "json")
                && !path
                    .file_name()
                    .is_some_and(|n| n.to_string_lossy().starts_with('.'))
            {
                files.push(path);
            }
        }

        files.sort();

        for path in files {
            match tokio::fs::read_to_string(&path).await {
                Ok(content) => {
                    let text = extract_text(&content);
                    if !text.is_empty() {
                        route_to_channels(jid, &text, channels).await;
                    }
                    let _ = tokio::fs::remove_file(&path).await;
                }
                Err(e) => {
                    warn!(jid, path = %path.display(), error = %e, "Failed to read IPC output");
                }
            }
        }
    }

    debug!(jid, "IPC watcher stopped");
}

/// Extract text from a JSON output file.
fn extract_text(content: &str) -> String {
    if let Ok(val) = serde_json::from_str::<serde_json::Value>(content) {
        // Try common field names
        for field in ["text", "result", "message", "response"] {
            if let Some(t) = val.get(field).and_then(|v| v.as_str()) {
                return t.to_string();
            }
        }
    }
    // Fallback: return raw content if not empty JSON
    content.trim().to_string()
}

/// Send text to the first channel that owns the JID.
async fn route_to_channels(jid: &str, text: &str, channels: &[Box<dyn ChannelSender>]) {
    for channel in channels {
        if channel.owns_jid(jid) {
            if let Err(e) = channel.send_message(jid, text).await {
                error!(jid, error = %e, "Failed to send via channel");
            }
            return;
        }
    }
    warn!(jid, "No channel found for JID");
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::sync::atomic::AtomicU32;

    /// Mock channel sender for testing.
    struct MockChannel {
        prefix: String,
        send_count: Arc<AtomicU32>,
        last_message: Arc<tokio::sync::Mutex<String>>,
    }

    impl MockChannel {
        fn new(prefix: &str) -> Self {
            Self {
                prefix: prefix.to_string(),
                send_count: Arc::new(AtomicU32::new(0)),
                last_message: Arc::new(tokio::sync::Mutex::new(String::new())),
            }
        }
    }

    impl ChannelSender for MockChannel {
        fn owns_jid(&self, jid: &str) -> bool {
            jid.starts_with(&self.prefix)
        }

        fn send_message(
            &self,
            _jid: &str,
            text: &str,
        ) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<()>> + Send + '_>> {
            let text = text.to_string();
            Box::pin(async move {
                self.send_count.fetch_add(1, Ordering::SeqCst);
                *self.last_message.lock().await = text;
                Ok(())
            })
        }
    }

    fn test_config(base: &std::path::Path) -> Config {
        Config {
            project_name: "test".to_string(),
            version: "0.0.1".to_string(),
            debug: false,
            base_dir: base.to_path_buf(),
            data_dir: base.join("data"),
            store_dir: base.join("store"),
            groups_dir: base.join("groups"),
            workspaces_dir: base.join("workspaces"),
            db_path: base.join("store/messages.db"),
            whatsapp_session_path: base.join("store/whatsapp_session"),
            openai_api_key: None,
            anthropic_api_key: None,
            telegram_bot_token: None,
            slack_bot_token: None,
            slack_signing_secret: None,
            discord_bot_token: None,
            qq_host: "127.0.0.1".to_string(),
            qq_port: 20000,
            feishu_app_id: None,
            feishu_app_secret: None,
            wecom_corp_id: None,
            wecom_agent_id: None,
            wecom_secret: None,
            dingtalk_app_key: None,
            dingtalk_app_secret: None,
            claude_api_url: "https://api.anthropic.com".to_string(),
            claude_api_version: "2023-06-01".to_string(),
            claude_model: "claude-sonnet-4-20250514".to_string(),
            claude_max_tokens: 4096,
            cli_default_group: "cli".to_string(),
            container_timeout: 300,
            container_max_output_size: 100_000,
            container_max_concurrent: 5,
            container_image: "nanogridbot-agent:latest".to_string(),
            assistant_name: "Andy".to_string(),
            trigger_pattern: None,
            poll_interval: 2000,
            max_messages_per_minute: 10,
            message_cache_size: 1000,
            batch_size: 100,
            db_connection_pool_size: 5,
            ipc_file_buffer_size: 8192,
            log_level: "INFO".to_string(),
            log_format: "default".to_string(),
            log_rotation: "10 MB".to_string(),
            log_retention: "7 days".to_string(),
            web_host: "0.0.0.0".to_string(),
            web_port: 8080,
        }
    }

    #[test]
    fn extract_text_json_text_field() {
        let content = r#"{"text": "hello world"}"#;
        assert_eq!(extract_text(content), "hello world");
    }

    #[test]
    fn extract_text_json_result_field() {
        let content = r#"{"result": "done"}"#;
        assert_eq!(extract_text(content), "done");
    }

    #[test]
    fn extract_text_plain_string() {
        assert_eq!(extract_text("just text"), "just text");
    }

    #[tokio::test]
    async fn write_input_creates_file() {
        let tmp = tempfile::tempdir().unwrap();
        let cfg = test_config(tmp.path());
        let channels: Arc<Vec<Box<dyn ChannelSender>>> = Arc::new(vec![]);
        let handler = IpcHandler::new(channels, &cfg);

        handler
            .write_input("telegram:123", &json!({"prompt": "hi"}))
            .await
            .unwrap();

        let input_dir = tmp.path().join("data/ipc/telegram:123/input");
        let mut entries = tokio::fs::read_dir(&input_dir).await.unwrap();
        let mut count = 0;
        while let Ok(Some(_)) = entries.next_entry().await {
            count += 1;
        }
        assert_eq!(count, 1);
    }

    #[tokio::test]
    async fn write_output_creates_file() {
        let tmp = tempfile::tempdir().unwrap();
        let cfg = test_config(tmp.path());
        let channels: Arc<Vec<Box<dyn ChannelSender>>> = Arc::new(vec![]);
        let handler = IpcHandler::new(channels, &cfg);

        handler
            .write_output("slack:C1", &json!({"text": "response"}))
            .await
            .unwrap();

        let output_dir = tmp.path().join("data/ipc/slack:C1/output");
        let mut entries = tokio::fs::read_dir(&output_dir).await.unwrap();
        let mut count = 0;
        while let Ok(Some(_)) = entries.next_entry().await {
            count += 1;
        }
        assert_eq!(count, 1);
    }

    #[tokio::test]
    async fn start_and_stop_watchers() {
        let tmp = tempfile::tempdir().unwrap();
        let cfg = test_config(tmp.path());
        let channels: Arc<Vec<Box<dyn ChannelSender>>> = Arc::new(vec![]);
        let mut handler = IpcHandler::new(channels, &cfg);

        assert!(!handler.is_running());
        assert_eq!(handler.watcher_count(), 0);

        handler.start(&["telegram:1".to_string(), "slack:2".to_string()]);
        assert!(handler.is_running());
        assert_eq!(handler.watcher_count(), 2);

        handler.stop();
        assert!(!handler.is_running());
        assert_eq!(handler.watcher_count(), 0);
    }

    #[tokio::test]
    async fn route_to_correct_channel() {
        let tg = MockChannel::new("telegram:");
        let sl = MockChannel::new("slack:");
        let tg_count = tg.send_count.clone();
        let sl_count = sl.send_count.clone();

        let channels: Vec<Box<dyn ChannelSender>> = vec![Box::new(tg), Box::new(sl)];

        route_to_channels("telegram:123", "hello", &channels).await;
        assert_eq!(tg_count.load(Ordering::SeqCst), 1);
        assert_eq!(sl_count.load(Ordering::SeqCst), 0);

        route_to_channels("slack:C1", "world", &channels).await;
        assert_eq!(tg_count.load(Ordering::SeqCst), 1);
        assert_eq!(sl_count.load(Ordering::SeqCst), 1);
    }
}
