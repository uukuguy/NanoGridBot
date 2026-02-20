//! Transport layer for communicating with Claude Code container

pub mod ipc;
pub mod mock;
pub mod output;
pub mod pipe;
pub mod session;
pub mod ws;

pub use ipc::{IpcTransport, IpcTransportConfig};
pub use mock::MockTransport;
pub use output::OutputChunk;
pub use pipe::PipeTransport;
pub use session::{SessionTransport, SessionTransportConfig};
pub use ws::{WsTransport, WsTransportConfig};

use async_trait::async_trait;
use futures::Stream;
use ngb_config::Config;
use std::path::PathBuf;
use std::pin::Pin;

/// Transport kind identifiers
pub const PIPE_TRANSPORT: &str = "pipe";
pub const IPC_TRANSPORT: &str = "ipc";
pub const WS_TRANSPORT: &str = "ws";
pub const MOCK_TRANSPORT: &str = "mock";
pub const SESSION_TRANSPORT: &str = "session";

/// Transport trait for communicating with Claude Code
#[async_trait]
pub trait Transport: Send + Sync + 'static {
    /// Send a message to Claude Code
    async fn send(&mut self, msg: &str) -> anyhow::Result<()>;

    /// Get a stream of output chunks from Claude Code
    fn recv_stream(&mut self) -> Pin<Box<dyn Stream<Item = OutputChunk> + Send + '_>>;

    /// Interrupt the current response (Ctrl+C equivalent)
    async fn interrupt(&mut self) -> anyhow::Result<()>;

    /// Close the transport and cleanup resources
    async fn close(&mut self) -> anyhow::Result<()>;
}

/// Type alias for transport kind
pub type TransportKind = &'static str;

/// Default WebSocket port
pub const DEFAULT_WS_PORT: u16 = 8080;

/// Default IPC poll interval in milliseconds
pub const DEFAULT_IPC_POLL_MS: u64 = 500;

/// Create a transport based on the transport kind
///
/// # Arguments
/// * `kind` - Transport kind ("pipe", "ipc", "ws", "mock", or "session")
/// * `workspace_id` - Workspace identifier
/// * `image` - Docker image for pipe transport
/// * `data_dir` - Data directory for IPC transport
/// * `ws_url` - WebSocket URL for WS transport (optional)
/// * `config` - Optional Config for secure mounts (pipe/session transports)
/// * `session_id` - Optional session ID for session transport resume
pub async fn create_transport(
    kind: TransportKind,
    workspace_id: &str,
    image: &str,
    data_dir: PathBuf,
    ws_url: Option<String>,
    config: Option<&Config>,
    session_id: Option<String>,
) -> anyhow::Result<Box<dyn Transport>> {
    match kind {
        PIPE_TRANSPORT => {
            let transport = PipeTransport::new(workspace_id, image, config).await?;
            Ok(Box::new(transport))
        }
        IPC_TRANSPORT => {
            let ipc_config = IpcTransportConfig {
                workspace_id: workspace_id.to_string(),
                data_dir,
                poll_interval_ms: DEFAULT_IPC_POLL_MS,
            };
            Ok(Box::new(IpcTransport::new(ipc_config)))
        }
        WS_TRANSPORT => {
            let url = ws_url.unwrap_or_else(|| {
                format!("ws://localhost:{}/ws", DEFAULT_WS_PORT)
            });
            let ws_config = WsTransportConfig {
                url,
                timeout_secs: 10,
            };
            Ok(Box::new(WsTransport::new(ws_config)))
        }
        MOCK_TRANSPORT => {
            Ok(Box::new(MockTransport::new()))
        }
        SESSION_TRANSPORT => {
            let cfg = config
                .ok_or_else(|| anyhow::anyhow!("Session transport requires a Config"))?;
            let make_sid = || {
                format!(
                    "s-{}",
                    uuid::Uuid::new_v4()
                        .to_string()
                        .split('-')
                        .next()
                        .unwrap_or("0000")
                )
            };
            let sid = session_id.clone().unwrap_or_else(make_sid);

            let tc = SessionTransportConfig {
                workspace_id: workspace_id.to_string(),
                session_id: sid.clone(),
                config: cfg.clone(),
                poll_interval_ms: DEFAULT_IPC_POLL_MS,
            };

            // Try to resume first, fall back to new
            match SessionTransport::resume(tc).await {
                Ok(t) => Ok(Box::new(t)),
                Err(_) => {
                    let tc = SessionTransportConfig {
                        workspace_id: workspace_id.to_string(),
                        session_id: sid,
                        config: cfg.clone(),
                        poll_interval_ms: DEFAULT_IPC_POLL_MS,
                    };
                    let t = SessionTransport::new(tc).await?;
                    Ok(Box::new(t))
                }
            }
        }
        _ => anyhow::bail!("Unknown transport kind: {}", kind),
    }
}
