//! Session transport - persistent container sessions via IPC.
//!
//! Wraps `ngb_core::ContainerSession` to provide a `Transport` implementation
//! that manages a named Docker container. The container persists between
//! send/receive cycles and can be resumed across TUI restarts.

use super::{OutputChunk, Transport};
use async_trait::async_trait;
use futures::stream::Stream;
use ngb_config::Config;
use ngb_core::ContainerSession;
use std::pin::Pin;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

/// Configuration for creating a SessionTransport.
pub struct SessionTransportConfig {
    /// Workspace / group folder name
    pub workspace_id: String,
    /// Session identifier (generated if not provided)
    pub session_id: String,
    /// Full Config for mount validation, env filtering, etc.
    pub config: Config,
    /// How often to poll the IPC output directory (ms)
    pub poll_interval_ms: u64,
}

/// Transport backed by a persistent `ContainerSession`.
///
/// The container is started in detached mode and communicates via
/// file-based IPC (input/output JSON files).
pub struct SessionTransport {
    session: ContainerSession,
    poll_interval_ms: u64,
    done: Arc<AtomicBool>,
}

impl SessionTransport {
    /// Create and start a new session transport.
    ///
    /// 1. Prepares directories/config via `prepare_container_launch` (in spawn_blocking)
    /// 2. Creates a `ContainerSession` and calls `session.start()`
    pub async fn new(tc: SessionTransportConfig) -> anyhow::Result<Self> {
        // Prepare container launch in blocking context
        let cfg = tc.config.clone();
        let ws_id = tc.workspace_id.clone();
        tokio::task::spawn_blocking(move || {
            ngb_core::prepare_container_launch(&cfg, &ws_id, false, &[], &[])
        })
        .await??;

        let mut session = ContainerSession::new(&tc.workspace_id, &tc.session_id, &tc.config);
        session.start(&tc.config).await.map_err(|e| {
            anyhow::anyhow!("Failed to start container session: {e}")
        })?;

        Ok(Self {
            session,
            poll_interval_ms: tc.poll_interval_ms,
            done: Arc::new(AtomicBool::new(false)),
        })
    }

    /// Resume an existing session by reconnecting to a running container.
    ///
    /// Checks the container status via `get_container_status()`, then
    /// reconstructs the `ContainerSession` with `from_existing()`.
    pub async fn resume(tc: SessionTransportConfig) -> anyhow::Result<Self> {
        // Derive the container name pattern and look for running containers
        // We search for containers matching the session pattern
        let container_name = format!("ngb-shell-{}", tc.workspace_id);

        // Check if any container with this prefix is running
        let status = ngb_core::get_container_status(&container_name).await?;
        if status != "running" {
            anyhow::bail!(
                "No running container found for session '{}' (status: {})",
                tc.session_id,
                status
            );
        }

        let session = ContainerSession::from_existing(
            &tc.workspace_id,
            &tc.session_id,
            &container_name,
            &tc.config,
        );

        Ok(Self {
            session,
            poll_interval_ms: tc.poll_interval_ms,
            done: Arc::new(AtomicBool::new(false)),
        })
    }

    /// Get the session ID.
    pub fn session_id(&self) -> &str {
        &self.session.session_id
    }

    /// Get the container name.
    pub fn container_name(&self) -> &str {
        &self.session.container_name
    }
}

#[async_trait]
impl Transport for SessionTransport {
    async fn send(&mut self, msg: &str) -> anyhow::Result<()> {
        self.session.send(msg).await.map_err(|e| {
            anyhow::anyhow!("Session send failed: {e}")
        })
    }

    fn recv_stream(&mut self) -> Pin<Box<dyn Stream<Item = OutputChunk> + Send + '_>> {
        let done = self.done.clone();
        let poll_ms = self.poll_interval_ms;

        Box::pin(async_stream::stream! {
            loop {
                if done.load(Ordering::SeqCst) {
                    yield OutputChunk::Done;
                    break;
                }

                // Poll for output from the container session
                match self.session.receive().await {
                    Ok(lines) => {
                        for line in lines {
                            if let Some(chunk) = OutputChunk::parse_line(&line) {
                                yield chunk;
                            } else if !line.is_empty() {
                                yield OutputChunk::Text(line);
                            }
                        }
                    }
                    Err(e) => {
                        yield OutputChunk::Error(format!("Session receive error: {e}"));
                        done.store(true, Ordering::SeqCst);
                        break;
                    }
                }

                // Wait before next poll
                tokio::time::sleep(Duration::from_millis(poll_ms)).await;
            }
        })
    }

    async fn interrupt(&mut self) -> anyhow::Result<()> {
        // For session transport, we don't kill the container on interrupt —
        // we just signal the stream to stop. The container keeps running.
        self.done.store(true, Ordering::SeqCst);
        Ok(())
    }

    async fn close(&mut self) -> anyhow::Result<()> {
        self.done.store(true, Ordering::SeqCst);
        self.session.close().await.map_err(|e| {
            anyhow::anyhow!("Session close failed: {e}")
        })
    }
}
