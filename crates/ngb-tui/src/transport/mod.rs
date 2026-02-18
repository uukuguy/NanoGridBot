//! Transport layer for communicating with Claude Code container

pub mod ipc;
pub mod output;
pub mod pipe;
pub mod ws;

pub use ipc::{IpcTransport, IpcTransportConfig};
pub use output::OutputChunk;
pub use pipe::PipeTransport;
pub use ws::{WsTransport, WsTransportConfig};

use async_trait::async_trait;
use futures::Stream;
use std::path::PathBuf;
use std::pin::Pin;

/// Transport kind identifiers
pub const PIPE_TRANSPORT: &str = "pipe";
pub const IPC_TRANSPORT: &str = "ipc";
pub const WS_TRANSPORT: &str = "ws";

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
/// * `kind` - Transport kind ("pipe", "ipc", or "ws")
/// * `workspace_id` - Workspace identifier
/// * `image` - Docker image for pipe transport
/// * `data_dir` - Data directory for IPC transport
/// * `ws_url` - WebSocket URL for WS transport (optional)
///
/// # Returns
/// * PipeTransport for "pipe"
/// * IpcTransport for "ipc"
/// * WsTransport for "ws"
pub fn create_transport(
    kind: TransportKind,
    workspace_id: &str,
    image: &str,
    data_dir: PathBuf,
    ws_url: Option<String>,
) -> anyhow::Result<Box<dyn Transport>> {
    match kind {
        PIPE_TRANSPORT => {
            let rt = tokio::runtime::Handle::current();
            let transport = rt.block_on(async {
                PipeTransport::new(workspace_id, image).await
            })?;
            Ok(Box::new(transport))
        }
        IPC_TRANSPORT => {
            let config = IpcTransportConfig {
                workspace_id: workspace_id.to_string(),
                data_dir,
                poll_interval_ms: DEFAULT_IPC_POLL_MS,
            };
            Ok(Box::new(IpcTransport::new(config)))
        }
        WS_TRANSPORT => {
            let url = ws_url.unwrap_or_else(|| {
                format!("ws://localhost:{}/ws", DEFAULT_WS_PORT)
            });
            let config = WsTransportConfig {
                url,
                timeout_secs: 10,
            };
            Ok(Box::new(WsTransport::new(config)))
        }
        _ => anyhow::bail!("Unknown transport kind: {}", kind),
    }
}
