//! NGB Shell TUI - Terminal User Interface for NanoGridBot
//!
//! Provides an interactive shell interface for chatting with Claude Code
//! running in workspace containers.

pub mod app;
pub mod theme;
pub mod transport;
pub mod syntax;
pub mod tree;
pub mod keymap;
pub mod engine;

pub use app::{App, AppConfig, AppMode, InputMode, KeyMode, Message, MessageContent, MessageRole, ToolStatus};
pub use theme::{all_theme_names, theme_display_name, IconSet, Theme, ThemeName};
pub use transport::{
    create_transport, IpcTransport, IpcTransportConfig, OutputChunk, PipeTransport,
    Transport, TransportKind, WsTransport, WsTransportConfig,
    IPC_TRANSPORT, PIPE_TRANSPORT, WS_TRANSPORT,
    DEFAULT_WS_PORT, DEFAULT_IPC_POLL_MS,
};

/// Entry point for running the NGB Shell TUI
pub fn run_shell() -> anyhow::Result<()> {
    let mut app = App::new()?;
    app.run()
}
