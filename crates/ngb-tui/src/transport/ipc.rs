//! IPC transport - communicates with Claude Code via file polling
//!
//! This transport uses file-based IPC similar to ngb-core's IpcHandler:
//! - Write input to {data_dir}/ipc/{workspace_id}/input/input-{timestamp}.json
//! - Poll output from {data_dir}/ipc/{workspace_id}/output/
//!
//! Latency: ~500ms (polling interval)

use super::{OutputChunk, Transport};
use async_trait::async_trait;
use futures::Stream;
use std::path::PathBuf;
use std::pin::Pin;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tokio::fs;
use tokio::sync::Mutex as TokioMutex;

/// IPC transport configuration
#[derive(Clone)]
pub struct IpcTransportConfig {
    /// Workspace ID (used as JID)
    pub workspace_id: String,
    /// Base data directory
    pub data_dir: PathBuf,
    /// Polling interval in milliseconds
    pub poll_interval_ms: u64,
}

impl Default for IpcTransportConfig {
    fn default() -> Self {
        Self {
            workspace_id: String::new(),
            data_dir: PathBuf::from("./data"),
            poll_interval_ms: 500,
        }
    }
}

/// IPC transport - file polling based communication
pub struct IpcTransport {
    /// Configuration
    config: IpcTransportConfig,
    /// Flag to indicate stream is done
    done: Arc<AtomicBool>,
    /// Last processed output file timestamp (using tokio Mutex for Send safety)
    last_output_ts: Arc<TokioMutex<i64>>,
}

impl IpcTransport {
    /// Create a new IPC transport
    pub fn new(config: IpcTransportConfig) -> Self {
        Self {
            config,
            done: Arc::new(AtomicBool::new(false)),
            last_output_ts: Arc::new(TokioMutex::new(0)),
        }
    }

    /// Get the input directory path
    fn input_dir(&self) -> PathBuf {
        self.config
            .data_dir
            .join("ipc")
            .join(&self.config.workspace_id)
            .join("input")
    }

    /// Get the output directory path
    #[allow(dead_code)]
    fn output_dir(&self) -> PathBuf {
        self.config
            .data_dir
            .join("ipc")
            .join(&self.config.workspace_id)
            .join("output")
    }

    /// Mark the transport as done
    pub fn set_done(&self) {
        self.done.store(true, Ordering::SeqCst);
    }

    /// Check if done
    pub fn is_done(&self) -> bool {
        self.done.load(Ordering::SeqCst)
    }
}

#[async_trait]
impl Transport for IpcTransport {
    async fn send(&mut self, msg: &str) -> anyhow::Result<()> {
        let input_dir = self.input_dir();

        // Ensure input directory exists
        fs::create_dir_all(&input_dir).await?;

        // Create input JSON
        let ts = chrono::Utc::now().timestamp_millis();
        let filename = format!("input-{ts}.json");
        let tmp_path = input_dir.join(format!(".tmp-{filename}"));
        let final_path = input_dir.join(&filename);

        let input_data = serde_json::json!({
            "prompt": msg,
            "timestamp": ts
        });

        // Atomic write: temp file then rename
        fs::write(&tmp_path, serde_json::to_vec_pretty(&input_data)?).await?;
        fs::rename(&tmp_path, &final_path).await?;

        tracing::debug!(workspace = %self.config.workspace_id, file = %filename, "Wrote IPC input");
        Ok(())
    }

    fn recv_stream(&mut self) -> Pin<Box<dyn Stream<Item = OutputChunk> + Send>> {
        let config = self.config.clone();
        let done = self.done.clone();
        let last_output_ts = self.last_output_ts.clone();

        Box::pin(async_stream::stream! {
            let poll_interval = std::time::Duration::from_millis(config.poll_interval_ms);

            loop {
                if done.load(Ordering::SeqCst) {
                    yield OutputChunk::Done;
                    break;
                }

                // Poll output directory
                let output_dir = config.data_dir.join("ipc")
                    .join(&config.workspace_id)
                    .join("output");

                let mut entries = match fs::read_dir(&output_dir).await {
                    Ok(e) => e,
                    Err(_) => {
                        // Directory doesn't exist yet, wait and retry
                        tokio::time::sleep(poll_interval).await;
                        continue;
                    }
                };

                let mut files = Vec::new();
                while let Ok(Some(entry)) = entries.next_entry().await {
                    let path = entry.path();
                    if path.extension().is_some_and(|ext| ext == "json")
                        && !path.file_name()
                            .is_some_and(|n| n.to_string_lossy().starts_with('.'))
                    {
                        // Get modification time for sorting
                        if let Ok(metadata) = entry.metadata().await {
                            if let Ok(modified) = metadata.modified() {
                                let ts = modified
                                    .duration_since(std::time::UNIX_EPOCH)
                                    .map(|d| d.as_millis() as i64)
                                    .unwrap_or(0);
                                files.push((path, ts));
                            }
                        }
                    }
                }

                // Sort by timestamp and process new files
                files.sort_by_key(|(_, ts)| *ts);

                // Drop lock before async operations
                {
                    let mut last_ts = last_output_ts.lock().await;

                    for (path, ts) in files {
                        if ts > *last_ts {
                            *last_ts = ts;
                            match fs::read_to_string(&path).await {
                                Ok(content) => {
                                    // Parse as OutputChunk
                                    if let Some(chunk) = OutputChunk::parse_line(&content) {
                                        yield chunk;
                                    } else if !content.trim().is_empty() {
                                        yield OutputChunk::Text(content);
                                    }
                                    // Delete processed file
                                    let _ = fs::remove_file(&path).await;
                                }
                                Err(e) => {
                                    tracing::warn!(path = %path.display(), error = %e, "Failed to read IPC output");
                                }
                            }
                        }
                    }
                }

                tokio::time::sleep(poll_interval).await;
            }
        })
    }

    async fn interrupt(&mut self) -> anyhow::Result<()> {
        self.set_done();
        Ok(())
    }

    async fn close(&mut self) -> anyhow::Result<()> {
        self.set_done();
        Ok(())
    }
}
