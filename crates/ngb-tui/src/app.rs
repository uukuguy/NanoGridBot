//! Application state and main event loop

use anyhow::Result;
use futures::StreamExt;
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout, Rect},
    prelude::Stylize,
    widgets::{List, ListItem, ListState},
    Frame,
};
use std::io;
use std::time::Duration;

use crossterm::{
    event::{
        self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEventKind, KeyModifiers,
    },
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};

use crate::theme::{Theme, ThemeName};
use crate::transport::{create_transport, OutputChunk, Transport, PIPE_TRANSPORT, TransportKind};
use std::path::PathBuf;
use tokio::sync::mpsc;

/// Configuration for the TUI application
#[derive(Debug, Clone)]
pub struct AppConfig {
    /// Workspace name to connect to
    pub workspace: String,
    /// Transport kind (pipe, ipc, or ws)
    pub transport_kind: TransportKind,
    /// Container image name
    pub image: String,
    /// Data directory for IPC/WS
    pub data_dir: PathBuf,
    /// WebSocket URL (for ws transport)
    pub ws_url: Option<String>,
    /// Theme name
    pub theme_name: ThemeName,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            workspace: String::new(),
            transport_kind: PIPE_TRANSPORT,
            image: "claude-code:latest".to_string(),
            data_dir: PathBuf::from("./data"),
            ws_url: None,
            theme_name: ThemeName::CatppuccinMocha,
        }
    }
}

impl AppConfig {
    /// Create a new config with required workspace
    pub fn new(workspace: impl Into<String>) -> Self {
        Self {
            workspace: workspace.into(),
            ..Default::default()
        }
    }

    /// Set transport kind
    pub fn with_transport(mut self, kind: TransportKind) -> Self {
        self.transport_kind = kind;
        self
    }

    /// Set theme
    pub fn with_theme(mut self, name: ThemeName) -> Self {
        self.theme_name = name;
        self
    }

    /// Set container image
    pub fn with_image(mut self, image: impl Into<String>) -> Self {
        self.image = image.into();
        self
    }

    /// Set data directory
    pub fn with_data_dir(mut self, dir: PathBuf) -> Self {
        self.data_dir = dir;
        self
    }

    /// Set WebSocket URL
    pub fn with_ws_url(mut self, url: impl Into<String>) -> Self {
        self.ws_url = Some(url.into());
        self
    }
}

/// Key input mode (Emacs or Vim)
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub enum KeyMode {
    #[default]
    Emacs,
    Vim,
}

pub struct App {
    /// Whether to quit the application
    #[allow(dead_code)]
    pub quit: bool,
    /// Current workspace name
    pub workspace: String,
    /// Chat messages
    pub messages: Vec<Message>,
    /// Current input text
    pub input: String,
    /// Scroll offset for chat area
    pub scroll: u16,
    /// List state for chat scrolling
    pub chat_state: ListState,
    /// Input cursor position
    pub cursor_position: usize,
    /// Input mode (single line or multiline)
    pub input_mode: InputMode,
    /// Transport for communicating with Claude Code (used for sending messages)
    #[allow(dead_code)]
    transport: Option<Box<dyn Transport>>,
    /// Current thinking text (accumulated while thinking)
    thinking_text: String,
    /// Whether thinking is currently collapsed
    thinking_collapsed: bool,
    /// Current tool call being tracked
    current_tool: Option<ToolCallInfo>,
    /// Timestamp for current agent message
    agent_timestamp: String,
    /// Channel receiver for transport output chunks
    chunk_receiver: Option<mpsc::Receiver<OutputChunk>>,
    /// Set of message indices that have thinking collapsed
    collapsed_thinking: std::collections::HashSet<usize>,
    /// Current theme
    pub theme: Theme,
    /// Key input mode (Emacs or Vim)
    pub key_mode: KeyMode,
}

struct ToolCallInfo {
    name: String,
    status: ToolStatus,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Message {
    pub role: MessageRole,
    pub content: MessageContent,
    pub timestamp: String,
}

#[derive(Debug, Clone, PartialEq)]
pub enum MessageContent {
    Text(String),
    Thinking(String),
    ToolCall { name: String, status: ToolStatus },
    CodeBlock { language: String, code: String },
    Error(String),
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum MessageRole {
    User,
    Agent,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum InputMode {
    SingleLine,
    MultiLine,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ToolStatus {
    Running,
    Success,
    Error,
}

impl App {
    /// Create a new app with default configuration (no transport)
    pub fn new() -> Result<Self> {
        Self::with_config(AppConfig::default())
    }

    /// Create a new app with custom configuration (no transport)
    pub fn with_config(config: AppConfig) -> Result<Self> {
        let mut chat_state = ListState::default();
        chat_state.select(Some(0));

        Ok(Self {
            quit: false,
            workspace: config.workspace,
            messages: Vec::new(),
            input: String::new(),
            scroll: 0,
            chat_state,
            cursor_position: 0,
            input_mode: InputMode::SingleLine,
            transport: None,
            thinking_text: String::new(),
            thinking_collapsed: false,
            current_tool: None,
            agent_timestamp: chrono::Local::now().format("%H:%M").to_string(),
            chunk_receiver: None,
            collapsed_thinking: std::collections::HashSet::new(),
            theme: Theme::from_name(config.theme_name),
            key_mode: KeyMode::default(),
        })
    }

    /// Set up transport after app creation (must be called from async context)
    pub fn setup_transport(&mut self, config: &AppConfig) -> anyhow::Result<()> {
        if config.workspace.is_empty() {
            return Ok(());
        }

        // Use tokio runtime to create transport
        let rt = tokio::runtime::Handle::current();
        self.transport = match rt.block_on(async {
            create_transport(
                config.transport_kind,
                &config.workspace,
                &config.image,
                config.data_dir.clone(),
                config.ws_url.clone(),
            )
            .await
        }) {
            Ok(t) => Some(t),
            Err(e) => {
                tracing::warn!(
                    workspace = %config.workspace,
                    transport = ?config.transport_kind,
                    error = %e,
                    "Failed to create transport, running in offline mode"
                );
                None
            }
        };
        Ok(())
    }

    /// Create a new app with a specific theme (deprecated, use with_config)
    pub fn with_theme(theme_name: ThemeName) -> Result<Self> {
        Self::with_config(AppConfig::default().with_theme(theme_name))
    }

    /// Set the theme
    pub fn set_theme(&mut self, theme_name: ThemeName) {
        self.theme = Theme::from_name(theme_name);
    }

    /// Set the key mode
    pub fn set_key_mode(&mut self, mode: KeyMode) {
        self.key_mode = mode;
    }

    /// Toggle key mode between Emacs and Vim
    pub fn toggle_key_mode(&mut self) {
        self.key_mode = match self.key_mode {
            KeyMode::Emacs => KeyMode::Vim,
            KeyMode::Vim => KeyMode::Emacs,
        };
    }

    /// Set the transport for communicating with Claude Code and start processing
    pub fn set_transport(&mut self, transport: Box<dyn Transport>) {
        // Create a channel for passing chunks from async transport to sync event loop
        let (tx, rx) = mpsc::channel(100);
        self.chunk_receiver = Some(rx);

        // Spawn a task to process the transport stream
        let transport = transport;
        tokio::spawn(async move {
            let mut transport = transport;
            let mut stream = transport.recv_stream();

            while let Some(chunk) = stream.next().await {
                if tx.send(chunk).await.is_err() {
                    // Receiver dropped, stop processing
                    break;
                }
            }
        });
    }

    /// Process a single OutputChunk and update app state
    fn process_chunk(&mut self, chunk: OutputChunk) {
        match chunk {
            OutputChunk::Text(text) => {
                // Finalize any pending thinking/tool states
                self.finalize_thinking();
                self.finalize_tool();

                // Add text to current agent message or create new one
                if let Some(last_msg) = self.messages.last_mut() {
                    if last_msg.role == MessageRole::Agent {
                        if let MessageContent::Text(existing) = &mut last_msg.content {
                            existing.push_str(&text);
                            return;
                        }
                    }
                }

                // Create new agent message
                self.messages.push(Message {
                    role: MessageRole::Agent,
                    content: MessageContent::Text(text),
                    timestamp: self.agent_timestamp.clone(),
                });
            }
            OutputChunk::ThinkingStart => {
                self.thinking_text.clear();
                self.agent_timestamp = chrono::Local::now().format("%H:%M").to_string();
            }
            OutputChunk::ThinkingText(text) => {
                self.thinking_text.push_str(&text);
                self.thinking_text.push('\n');
            }
            OutputChunk::ThinkingEnd => {
                // Keep thinking text for display, user can collapse it
            }
            OutputChunk::ToolStart { name, args: _ } => {
                self.finalize_thinking();
                // Show running tool immediately so user sees progress
                self.messages.push(Message {
                    role: MessageRole::Agent,
                    content: MessageContent::ToolCall {
                        name: name.clone(),
                        status: ToolStatus::Running,
                    },
                    timestamp: self.agent_timestamp.clone(),
                });
                // Track for potential updates
                self.current_tool = Some(ToolCallInfo {
                    name,
                    status: ToolStatus::Running,
                });
            }
            OutputChunk::ToolEnd { name, success } => {
                // Find and update the last running tool message with matching name
                let mut updated = false;
                if let Some(tool_name) = self.current_tool.as_ref().map(|t| t.name.clone()) {
                    if tool_name == name {
                        // Update the last running message
                        for msg in self.messages.iter_mut().rev() {
                            if let MessageContent::ToolCall { name: n, status } = &mut msg.content {
                                if *n == name && *status == ToolStatus::Running {
                                    *status = if success {
                                        ToolStatus::Success
                                    } else {
                                        ToolStatus::Error
                                    };
                                    updated = true;
                                    break;
                                }
                            }
                        }
                    }
                }

                // If we didn't update an existing message, create a new one
                if !updated {
                    self.messages.push(Message {
                        role: MessageRole::Agent,
                        content: MessageContent::ToolCall {
                            name,
                            status: if success {
                                ToolStatus::Success
                            } else {
                                ToolStatus::Error
                            },
                        },
                        timestamp: self.agent_timestamp.clone(),
                    });
                }
                self.current_tool = None;
            }
            OutputChunk::Done => {
                self.finalize_thinking();
                self.finalize_tool();
            }
            OutputChunk::Error(err) => {
                self.finalize_thinking();
                self.finalize_tool();
                self.messages.push(Message {
                    role: MessageRole::Agent,
                    content: MessageContent::Error(err),
                    timestamp: self.agent_timestamp.clone(),
                });
            }
        }
    }

    /// Finalize any pending thinking as a message
    fn finalize_thinking(&mut self) {
        if !self.thinking_text.is_empty() {
            let idx = self.messages.len();
            self.messages.push(Message {
                role: MessageRole::Agent,
                content: MessageContent::Thinking(self.thinking_text.clone()),
                timestamp: self.agent_timestamp.clone(),
            });
            // Default to collapsed for thinking messages
            self.collapsed_thinking.insert(idx);
            self.thinking_text.clear();
        }
    }

    /// Toggle collapse state for a specific message (if it's a thinking message)
    pub fn toggle_message_collapse(&mut self, index: usize) {
        if index < self.messages.len() {
            if let MessageContent::Thinking(_) = &self.messages[index].content {
                if self.collapsed_thinking.contains(&index) {
                    self.collapsed_thinking.remove(&index);
                } else {
                    self.collapsed_thinking.insert(index);
                }
            }
        }
    }

    /// Check if a message is collapsed
    pub fn is_message_collapsed(&self, index: usize) -> bool {
        self.collapsed_thinking.contains(&index)
    }

    /// Finalize any pending tool call
    fn finalize_tool(&mut self) {
        if let Some(tool) = self.current_tool.take() {
            self.messages.push(Message {
                role: MessageRole::Agent,
                content: MessageContent::ToolCall {
                    name: tool.name,
                    status: tool.status,
                },
                timestamp: self.agent_timestamp.clone(),
            });
        }
    }

    /// Toggle thinking block collapse state
    pub fn toggle_thinking_collapse(&mut self) {
        self.thinking_collapsed = !self.thinking_collapsed;
    }

    /// Check if thinking is collapsed
    pub fn is_thinking_collapsed(&self) -> bool {
        self.thinking_collapsed
    }

    pub fn run(&mut self) -> Result<()> {
        // Setup terminal
        enable_raw_mode()?;
        let mut stdout = io::stdout();
        execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
        let backend = CrosstermBackend::new(stdout);
        let mut terminal = ratatui::Terminal::new(backend)?;

        // Run the main loop
        let result = self.run_loop(&mut terminal);

        // Cleanup
        disable_raw_mode()?;
        let _ = execute!(io::stdout(), LeaveAlternateScreen, DisableMouseCapture);

        result
    }

    fn run_loop(
        &mut self,
        terminal: &mut ratatui::Terminal<CrosstermBackend<io::Stdout>>,
    ) -> Result<()> {
        loop {
            terminal.draw(|f| self.draw(f))?;

            // Process any available chunks from the transport
            let chunks: Vec<OutputChunk> = if let Some(rx) = self.chunk_receiver.as_mut() {
                let mut collected = Vec::new();
                while let Ok(chunk) = rx.try_recv() {
                    collected.push(chunk);
                }
                collected
            } else {
                Vec::new()
            };

            for chunk in chunks {
                self.process_chunk(chunk);
            }

            if event::poll(Duration::from_millis(250))? {
                if let Event::Key(key) = event::read()? {
                    self.handle_key(key);
                }
                // Handle mouse events for scrolling
                if let Event::Mouse(mouse) = event::read()? {
                    self.handle_mouse(mouse);
                }
            }

            if self.quit {
                break;
            }
        }
        Ok(())
    }

    fn handle_mouse(&mut self, mouse: crossterm::event::MouseEvent) {
        match mouse.kind {
            crossterm::event::MouseEventKind::ScrollUp => {
                self.scroll_up();
            }
            crossterm::event::MouseEventKind::ScrollDown => {
                self.scroll_down();
            }
            _ => {}
        }
    }

    fn scroll_up(&mut self) {
        if !self.messages.is_empty() {
            let new_offset = self.chat_state.offset().saturating_sub(1);
            *self.chat_state.offset_mut() = new_offset;
        }
    }

    fn scroll_down(&mut self) {
        if !self.messages.is_empty() {
            let max_offset = self.messages.len().saturating_sub(1);
            let new_offset = (self.chat_state.offset() + 1).min(max_offset);
            *self.chat_state.offset_mut() = new_offset;
        }
    }

    fn draw(&mut self, f: &mut Frame) {
        let area = f.area();

        // Define layout: Header(3) + Chat(*) + Input(3) + Status(1)
        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Length(3), // Header
                Constraint::Min(0),    // Chat
                Constraint::Length(3), // Input
                Constraint::Length(1), // Status
            ])
            .split(area);

        self.draw_header(f, chunks[0]);
        self.draw_chat(f, chunks[1]);
        self.draw_input(f, chunks[2]);
        self.draw_status(f, chunks[3]);
    }

    fn draw_header(&self, f: &mut Frame, area: Rect) {
        use ratatui::style::Style;
        use ratatui::widgets::{Block, Borders, Paragraph};

        let text = format!(" NGB Shell ◆ workspace: {} ", self.workspace);
        let block = Block::new()
            .borders(Borders::ALL)
            .title("NanoGridBot")
            .title_style(Style::default().fg(self.theme.accent));

        let paragraph = Paragraph::new(text)
            .block(block)
            .style(Style::default().fg(self.theme.foreground));
        f.render_widget(paragraph, area);
    }

    fn draw_chat(&mut self, f: &mut Frame, area: Rect) {
        use ratatui::style::Style;
        use ratatui::widgets::{Block, Borders};

        let block = Block::new()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(self.theme.border));

        // Build message items - collect messages first to avoid borrow issues
        let messages = self.messages.clone();
        let theme = self.theme.clone();
        let items: Vec<ListItem> = if messages.is_empty() {
            vec![ListItem::new(
                "  Start chatting with Claude Code...\n\n  Press Enter to send message, Ctrl+C to quit.",
            )
            .style(Style::default().fg(self.theme.secondary).dim())]
        } else {
            messages
                .iter()
                .enumerate()
                .map(|(idx, msg)| Self::render_message_item(msg, self.is_message_collapsed(idx), &theme))
                .collect()
        };

        let list = List::new(items)
            .block(block)
            .style(Style::default().fg(self.theme.foreground));

        f.render_stateful_widget(list, area, &mut self.chat_state);
    }

    fn render_message_item<'a>(msg: &'a Message, collapsed: bool, theme: &'a Theme) -> ListItem<'a> {
        use ratatui::style::Style;

        match msg.role {
            MessageRole::User => {
                let content = match &msg.content {
                    MessageContent::Text(text) => format!("{}  {}", text, msg.timestamp),
                    _ => msg.timestamp.clone(),
                };
                ListItem::new(content)
                    .style(Style::default().fg(theme.user_message).italic())
            }
            MessageRole::Agent => {
                let prefix = format!("◆ Agent  {}", msg.timestamp);
                match &msg.content {
                    MessageContent::Text(text) => ListItem::new(format!("{}\n{}", prefix, text))
                        .style(Style::default().fg(theme.agent_message)),
                    MessageContent::Thinking(text) => {
                        let arrow = if collapsed { "▸" } else { "▾" };
                        let preview = if collapsed {
                            format!("[{} collapsed, press Tab to expand]", text.lines().count())
                        } else {
                            text.clone()
                        };
                        ListItem::new(format!("{} {} Thinking...\n{}", prefix, arrow, preview))
                            .style(Style::default().fg(theme.thinking))
                    }
                    MessageContent::ToolCall { name, status } => {
                        let status_icon = match status {
                            ToolStatus::Running => " ⠙",
                            ToolStatus::Success => " ✓",
                            ToolStatus::Error => " ✗",
                        };
                        let color = match status {
                            ToolStatus::Running => theme.tool_running,
                            ToolStatus::Success => theme.tool_success,
                            ToolStatus::Error => theme.tool_error,
                        };
                        ListItem::new(format!("{} → {} {}", prefix, name, status_icon))
                            .style(Style::default().fg(color))
                    }
                    MessageContent::CodeBlock { language, code } => {
                        ListItem::new(format!("{}\n  ┌─ {} ──\n{}\n  └─", prefix, language, code))
                            .style(Style::default().fg(theme.warning))
                    }
                    MessageContent::Error(err) => {
                        ListItem::new(format!("{} ✗ Error: {}", prefix, err))
                            .style(Style::default().fg(theme.error))
                    }
                }
            }
        }
    }

    fn draw_input(&self, f: &mut Frame, area: Rect) {
        use ratatui::style::Style;
        use ratatui::widgets::{Block, Borders};

        let block = Block::new()
            .borders(Borders::ALL)
            .title(match self.input_mode {
                InputMode::SingleLine => " Input ",
                InputMode::MultiLine => " Input (Shift+Enter for newline) ",
            })
            .border_style(Style::default().fg(self.theme.border))
            .title_style(Style::default().fg(self.theme.accent));

        let text = if self.input.is_empty() {
            " Type a message..."
        } else {
            self.input.as_str()
        };

        let paragraph = ratatui::widgets::Paragraph::new(text)
            .block(block)
            .style(Style::default().fg(self.theme.input))
            .wrap(ratatui::widgets::Wrap { trim: true });

        f.render_widget(paragraph, area);

        // Render cursor at position
        #[allow(deprecated)]
        if !self.input.is_empty() && area.width > 2 {
            let cursor_x = (self.cursor_position as u16).min(area.width - 2);
            let x = area.x + 1 + cursor_x;
            let y = area.y + 1;
            f.set_cursor(x, y);
        }
    }

    fn draw_status(&self, f: &mut Frame, area: Rect) {
        use ratatui::style::Style;
        use ratatui::widgets::Paragraph;

        let mode_str = match self.key_mode {
            KeyMode::Emacs => "emacs",
            KeyMode::Vim => "vim",
        };
        let theme_name = crate::theme::theme_display_name(self.theme.name);

        let text = format!(
            " {} | pipe | {} mode | {} | ↑↓ scroll | Ctrl+C quit ",
            if self.workspace.is_empty() {
                "no workspace"
            } else {
                &self.workspace
            },
            mode_str,
            theme_name
        );

        let paragraph = Paragraph::new(text)
            .style(Style::default().fg(self.theme.status));
        f.render_widget(paragraph, area);
    }

    fn handle_key(&mut self, key: event::KeyEvent) {
        if key.kind != KeyEventKind::Press {
            return;
        }

        // Vim mode specific handling
        if self.key_mode == KeyMode::Vim {
            // Vim mode: k/j for scroll, :command for commands, Esc to quit
            match key.code {
                KeyCode::Char('k') => {
                    self.scroll_up();
                    return;
                }
                KeyCode::Char('j') => {
                    self.scroll_down();
                    return;
                }
                KeyCode::Char(':') => {
                    // Command mode - could implement command input
                    return;
                }
                KeyCode::Esc => {
                    self.quit = true;
                    return;
                }
                _ => {}
            }
        }

        // Common handling for both modes
        // Handle scrolling with arrow keys
        if key.modifiers.contains(KeyModifiers::CONTROL) {
            match key.code {
                KeyCode::Up | KeyCode::Char('k') => {
                    self.scroll_up();
                    return;
                }
                KeyCode::Down | KeyCode::Char('j') => {
                    self.scroll_down();
                    return;
                }
                KeyCode::Char('q') => {
                    self.quit = true;
                    return;
                }
                _ => {}
            }
        }

        match key.code {
            KeyCode::Tab => {
                // Tab: toggle collapse on selected message
                if let Some(selected) = self.chat_state.selected() {
                    self.toggle_message_collapse(selected);
                }
            }
            KeyCode::Char('q') => {
                self.quit = true;
            }
            KeyCode::Char('c') if key.modifiers.contains(event::KeyModifiers::CONTROL) => {
                // Ctrl+C: interrupt or quit
                if self.input.is_empty() {
                    self.quit = true;
                }
            }
            KeyCode::Char('l') if key.modifiers.contains(event::KeyModifiers::CONTROL) => {
                // Ctrl+L: clear screen (scroll to bottom)
                self.chat_state
                    .select(Some(self.messages.len().saturating_sub(1)));
            }
            // Arrow keys for cursor movement
            KeyCode::Left => {
                if self.cursor_position > 0 {
                    self.cursor_position -= 1;
                }
            }
            KeyCode::Right => {
                if self.cursor_position < self.input.len() {
                    self.cursor_position += 1;
                }
            }
            KeyCode::Home => {
                self.cursor_position = 0;
            }
            KeyCode::End => {
                self.cursor_position = self.input.len();
            }
            // Character input
            KeyCode::Char(c) => {
                let pos = self.cursor_position.min(self.input.len());
                self.input.insert(pos, c);
                self.cursor_position += 1;
            }
            KeyCode::Backspace => {
                if self.cursor_position > 0 {
                    self.cursor_position -= 1;
                    let pos = self.cursor_position;
                    self.input.remove(pos);
                }
            }
            KeyCode::Delete => {
                if self.cursor_position < self.input.len() {
                    self.input.remove(self.cursor_position);
                }
            }
            KeyCode::Enter => {
                if key.modifiers.contains(KeyModifiers::SHIFT) {
                    // Shift+Enter: insert newline
                    let pos = self.cursor_position.min(self.input.len());
                    self.input.insert(pos, '\n');
                    self.cursor_position += 1;
                    self.input_mode = InputMode::MultiLine;
                } else if !self.input.is_empty() {
                    // Send message
                    let msg_content = std::mem::take(&mut self.input);
                    self.messages.push(Message {
                        role: MessageRole::User,
                        content: MessageContent::Text(msg_content),
                        timestamp: chrono::Local::now().format("%H:%M").to_string(),
                    });
                    self.cursor_position = 0;
                    self.input_mode = InputMode::SingleLine;
                    // Scroll to bottom after sending
                    self.chat_state
                        .select(Some(self.messages.len().saturating_sub(1)));
                }
            }
            // Page up/down for scrolling
            KeyCode::PageUp => {
                for _ in 0..5 {
                    self.scroll_up();
                }
            }
            KeyCode::PageDown => {
                for _ in 0..5 {
                    self.scroll_down();
                }
            }
            // Arrow up/down for history (placeholder)
            KeyCode::Up => {
                // Could implement command history here
            }
            KeyCode::Down => {
                // Could implement command history here
            }
            _ => {}
        }
    }
}
