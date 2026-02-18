//! NGB Shell TUI - Terminal User Interface for NanoGridBot
//!
//! Provides an interactive shell interface for chatting with Claude Code
//! running in workspace containers.

pub mod app;
pub mod transport;

pub use app::{
    App, InputMode, Message, MessageContent, MessageRole, ToolStatus,
};
pub use transport::{OutputChunk, Transport, IPC_TRANSPORT, PIPE_TRANSPORT, WS_TRANSPORT};

/// Entry point for running the NGB Shell TUI
pub fn run_shell() -> anyhow::Result<()> {
    let mut app = App::new()?;
    app.run()
}
