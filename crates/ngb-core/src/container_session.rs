use std::path::PathBuf;

use ngb_config::Config;
use ngb_types::{NanoGridBotError, Result};
use serde_json::json;
use tokio::process::{Child, Command};
use tracing::{debug, info, warn};

use crate::container_runner::cleanup_container;
use crate::mount_security::validate_workspace_mounts;

/// An interactive container session for CLI shell mode.
///
/// Uses file-based IPC via input/output directories under `ipc_dir`.
/// The container reads JSON files from `input/` and writes responses to `output/`.
pub struct ContainerSession {
    pub group_folder: String,
    pub session_id: String,
    pub container_name: String,
    ipc_dir: PathBuf,
    process: Option<Child>,
}

impl ContainerSession {
    /// Create a new session (does not start the container).
    pub fn new(group_folder: &str, session_id: &str, config: &Config) -> Self {
        let container_name = format!(
            "ngb-shell-{}-{}",
            group_folder,
            uuid::Uuid::new_v4()
                .to_string()
                .split('-')
                .next()
                .unwrap_or("0000")
        );
        let ipc_dir = config
            .data_dir
            .join("ipc")
            .join(format!("session-{session_id}"));

        Self {
            group_folder: group_folder.to_string(),
            session_id: session_id.to_string(),
            container_name,
            ipc_dir,
            process: None,
        }
    }

    /// Reconstruct a session from known parameters without starting a new container.
    ///
    /// Used to reconnect to an existing running container. The `process` field is
    /// set to `None` since communication happens via IPC directories, not a process handle.
    pub fn from_existing(
        group_folder: &str,
        session_id: &str,
        container_name: &str,
        config: &Config,
    ) -> Self {
        let ipc_dir = config
            .data_dir
            .join("ipc")
            .join(format!("session-{session_id}"));

        Self {
            group_folder: group_folder.to_string(),
            session_id: session_id.to_string(),
            container_name: container_name.to_string(),
            ipc_dir,
            process: None,
        }
    }

    /// Start the container in detached mode.
    ///
    /// Creates the IPC directories, validates mounts, and spawns a named
    /// container (without `--rm` so it persists between sends).
    pub async fn start(&mut self, config: &Config) -> Result<()> {
        // Create IPC directories
        let input_dir = self.ipc_dir.join("input");
        let output_dir = self.ipc_dir.join("output");
        tokio::fs::create_dir_all(&input_dir).await.map_err(|e| {
            NanoGridBotError::Container(format!("Failed to create IPC input dir: {e}"))
        })?;
        tokio::fs::create_dir_all(&output_dir).await.map_err(|e| {
            NanoGridBotError::Container(format!("Failed to create IPC output dir: {e}"))
        })?;

        // Validate mounts
        let mounts = validate_workspace_mounts(
            &self.group_folder,
            &format!("session:{}", self.session_id),
            false,
            &[],
            config,
        )?;

        // Build docker args — no --rm, use --name for persistence
        let mut args = vec![
            "run".to_string(),
            "-d".to_string(), // detached
            "--name".to_string(),
            self.container_name.clone(),
            "--network=none".to_string(),
            "--memory=2g".to_string(),
            "--cpus=1.0".to_string(),
        ];

        for mount in &mounts {
            args.push("-v".to_string());
            args.push(mount.to_docker_arg());
        }

        // Mount IPC directory
        args.push("-v".to_string());
        args.push(format!("{}:/workspace/ipc:rw", self.ipc_dir.display()));

        args.push(config.container_image.clone());

        debug!(
            container_name = %self.container_name,
            group_folder = %self.group_folder,
            "Starting interactive container session"
        );

        let child = Command::new("docker")
            .args(&args)
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .spawn()
            .map_err(|e| {
                NanoGridBotError::Container(format!("Failed to start session container: {e}"))
            })?;

        self.process = Some(child);
        info!(
            container_name = %self.container_name,
            "Container session started"
        );

        Ok(())
    }

    /// Send a text message to the container via IPC.
    ///
    /// Writes a JSON file to `ipc_dir/input/input-{timestamp}.json`.
    pub async fn send(&self, text: &str) -> Result<()> {
        let ts = chrono::Utc::now().timestamp_millis();
        let filename = format!("input-{ts}.json");
        let input_path = self.ipc_dir.join("input").join(&filename);
        let tmp_path = self.ipc_dir.join("input").join(format!(".tmp-{filename}"));

        let payload = json!({
            "text": text,
            "timestamp": ts,
            "sessionId": self.session_id,
        });

        // Atomic write: write to temp file, then rename
        tokio::fs::write(&tmp_path, serde_json::to_vec_pretty(&payload)?)
            .await
            .map_err(|e| NanoGridBotError::Container(format!("Failed to write IPC input: {e}")))?;
        tokio::fs::rename(&tmp_path, &input_path)
            .await
            .map_err(|e| NanoGridBotError::Container(format!("Failed to rename IPC input: {e}")))?;

        debug!(filename, "Sent input to container session");
        Ok(())
    }

    /// Poll for output messages from the container.
    ///
    /// Reads and deletes JSON files from `ipc_dir/output/`.
    pub async fn receive(&self) -> Result<Vec<String>> {
        let output_dir = self.ipc_dir.join("output");
        let mut results = Vec::new();

        let mut entries = match tokio::fs::read_dir(&output_dir).await {
            Ok(e) => e,
            Err(_) => return Ok(results),
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

        // Sort by name (timestamp-based) to preserve order
        files.sort();

        for path in files {
            match tokio::fs::read_to_string(&path).await {
                Ok(content) => {
                    if let Ok(val) = serde_json::from_str::<serde_json::Value>(&content) {
                        if let Some(text) = val.get("text").and_then(|v| v.as_str()) {
                            results.push(text.to_string());
                        } else {
                            results.push(content);
                        }
                    } else {
                        results.push(content);
                    }
                    // Delete processed file
                    let _ = tokio::fs::remove_file(&path).await;
                }
                Err(e) => {
                    warn!(path = %path.display(), error = %e, "Failed to read output file");
                }
            }
        }

        Ok(results)
    }

    /// Close the session: write sentinel, kill process, cleanup container.
    pub async fn close(&mut self) -> Result<()> {
        // Write a sentinel file to signal the container to stop
        let sentinel = self.ipc_dir.join("input").join("_shutdown.json");
        let _ = tokio::fs::write(&sentinel, b"{\"shutdown\":true}").await;

        // Kill the child process if we still hold it
        if let Some(mut child) = self.process.take() {
            let _ = child.kill().await;
        }

        // Force-remove the container
        cleanup_container(&self.container_name).await?;

        // Clean up IPC directory
        let _ = tokio::fs::remove_dir_all(&self.ipc_dir).await;

        info!(
            container_name = %self.container_name,
            "Container session closed"
        );
        Ok(())
    }

    /// Check if the container process is still alive.
    pub fn is_alive(&mut self) -> bool {
        match &mut self.process {
            Some(child) => child.try_wait().ok().flatten().is_none(),
            None => false,
        }
    }

    /// Get the IPC directory path.
    pub fn ipc_dir(&self) -> &PathBuf {
        &self.ipc_dir
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_config() -> Config {
        let base = PathBuf::from("/tmp/ngb-session-test");
        Config {
            project_name: "test".to_string(),
            version: "0.0.1".to_string(),
            debug: false,
            base_dir: base.clone(),
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
    fn new_session_sets_fields() {
        let cfg = test_config();
        let session = ContainerSession::new("test_group", "sess-001", &cfg);
        assert_eq!(session.group_folder, "test_group");
        assert_eq!(session.session_id, "sess-001");
        assert!(session.container_name.starts_with("ngb-shell-test_group-"));
        assert!(session
            .ipc_dir
            .to_string_lossy()
            .contains("session-sess-001"));
    }

    #[test]
    fn new_session_not_alive() {
        let cfg = test_config();
        let mut session = ContainerSession::new("g1", "s1", &cfg);
        assert!(!session.is_alive());
    }

    #[test]
    fn from_existing_preserves_fields() {
        let cfg = test_config();
        let session =
            ContainerSession::from_existing("test_group", "sess-002", "ngb-shell-test-abc", &cfg);
        assert_eq!(session.group_folder, "test_group");
        assert_eq!(session.session_id, "sess-002");
        assert_eq!(session.container_name, "ngb-shell-test-abc");
        assert!(session
            .ipc_dir
            .to_string_lossy()
            .contains("session-sess-002"));
        // process should be None — not alive
        assert!(session.process.is_none());
    }

    #[test]
    fn from_existing_not_alive() {
        let cfg = test_config();
        let mut session =
            ContainerSession::from_existing("g1", "s1", "ngb-shell-g1-xyz", &cfg);
        assert!(!session.is_alive());
    }

    #[tokio::test]
    async fn send_creates_input_file() {
        let tmp = tempfile::tempdir().unwrap();
        let mut cfg = test_config();
        cfg.data_dir = tmp.path().to_path_buf().join("data");

        let session = ContainerSession::new("g1", "s1", &cfg);

        // Create IPC dirs manually for test
        let input_dir = session.ipc_dir().join("input");
        tokio::fs::create_dir_all(&input_dir).await.unwrap();

        session.send("hello").await.unwrap();

        let mut entries = tokio::fs::read_dir(&input_dir).await.unwrap();
        let mut count = 0;
        while let Ok(Some(entry)) = entries.next_entry().await {
            let name = entry.file_name().to_string_lossy().to_string();
            if name.starts_with("input-") && name.ends_with(".json") {
                count += 1;
                let content = tokio::fs::read_to_string(entry.path()).await.unwrap();
                let val: serde_json::Value = serde_json::from_str(&content).unwrap();
                assert_eq!(val["text"], "hello");
                assert_eq!(val["sessionId"], "s1");
            }
        }
        assert_eq!(count, 1);
    }

    #[tokio::test]
    async fn receive_reads_and_deletes_output_files() {
        let tmp = tempfile::tempdir().unwrap();
        let mut cfg = test_config();
        cfg.data_dir = tmp.path().to_path_buf().join("data");

        let session = ContainerSession::new("g1", "s1", &cfg);
        let output_dir = session.ipc_dir().join("output");
        tokio::fs::create_dir_all(&output_dir).await.unwrap();

        // Write test output files
        tokio::fs::write(output_dir.join("out-001.json"), r#"{"text": "response 1"}"#)
            .await
            .unwrap();
        tokio::fs::write(output_dir.join("out-002.json"), r#"{"text": "response 2"}"#)
            .await
            .unwrap();

        let results = session.receive().await.unwrap();
        assert_eq!(results.len(), 2);
        assert_eq!(results[0], "response 1");
        assert_eq!(results[1], "response 2");

        // Files should be deleted
        let mut entries = tokio::fs::read_dir(&output_dir).await.unwrap();
        let mut count = 0;
        while let Ok(Some(_)) = entries.next_entry().await {
            count += 1;
        }
        assert_eq!(count, 0);
    }

    #[tokio::test]
    async fn receive_empty_dir() {
        let tmp = tempfile::tempdir().unwrap();
        let mut cfg = test_config();
        cfg.data_dir = tmp.path().to_path_buf().join("data");

        let session = ContainerSession::new("g1", "s1", &cfg);
        let output_dir = session.ipc_dir().join("output");
        tokio::fs::create_dir_all(&output_dir).await.unwrap();

        let results = session.receive().await.unwrap();
        assert!(results.is_empty());
    }

    #[tokio::test]
    async fn receive_nonexistent_dir() {
        let cfg = test_config();
        let session = ContainerSession::new("g1", "s1", &cfg);
        // Don't create the output dir — should return empty, not error
        let results = session.receive().await.unwrap();
        assert!(results.is_empty());
    }
}
