//! Transport layer for communicating with Claude Code container

pub mod output;
pub mod pipe;

pub use output::OutputChunk;

use async_trait::async_trait;
use futures::Stream;
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
    fn recv_stream(&mut self) -> Pin<Box<dyn Stream<Item = OutputChunk> + Send>>;

    /// Interrupt the current response (Ctrl+C equivalent)
    async fn interrupt(&mut self) -> anyhow::Result<()>;

    /// Close the transport and cleanup resources
    async fn close(&mut self) -> anyhow::Result<()>;
}

/// Type alias for transport kind
pub type TransportKind = &'static str;
