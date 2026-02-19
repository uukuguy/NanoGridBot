//! Application state and main event loop

use anyhow::Result;
use futures::StreamExt;
use std::time::Instant;

use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout, Rect},
    prelude::Stylize,
    style::{Color, Modifier},
    text::{Line, Span},
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

use crate::engine::{create_history_engine, HistoryEngine, SearchResult};
use crate::keymap::{self, Action, EvalContext, KeyBinding};
use crate::tree::{Tree, TreeNode};
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

/// Application mode (normal or search)
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub enum AppMode {
    #[default]
    Normal,
    Search,
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
    /// Timestamp of last Ctrl+C press (for double-Ctrl+C to quit)
    last_ctrl_c_time: Option<Instant>,
    /// Conditional keybindings
    keybindings: Vec<KeyBinding>,
    /// Search results for history search
    search_results: Vec<String>,
    /// Current search query
    search_query: String,
    /// Application mode (normal or search)
    app_mode: AppMode,
    /// Search selection state
    search_selected: usize,
    /// Current input history index (for up/down navigation)
    history_index: Option<usize>,
    /// Tree structure for message threads
    message_tree: Tree,
    /// History engine for search
    history_engine: HistoryEngine,
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
    /// Parent message ID for tree view (threading/replies)
    pub parent_id: Option<String>,
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

/// 初始欢迎信息 - 方便后续修改
/// 初始欢迎信息 - 使用 Line 数组确保缩进正确
/// 从用户文件读取欢迎信息，如果文件不存在则返回空
fn welcome_lines_from_file(path: &std::path::Path) -> Vec<Line<'static>> {
    use ratatui::text::Line;
    use ratatui::style::Style;

    let content = match std::fs::read_to_string(path) {
        Ok(c) => c,
        Err(_) => return Vec::new(),
    };

    let style = Style::default().dim();
    content
        .lines()
        .map(|line| Line::from(vec![Span::raw(line.to_string())]).style(style))
        .collect()
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
            last_ctrl_c_time: None,
            keybindings: keymap::default_keybindings(),
            search_results: Vec::new(),
            search_query: String::new(),
            app_mode: AppMode::default(),
            search_selected: 0,
            history_index: None,
            message_tree: Tree::new(),
            history_engine: create_history_engine(),
        })
    }

    /// Set up transport after app creation (must be called from async context)
    pub async fn setup_transport(&mut self, config: &AppConfig) -> anyhow::Result<()> {
        if config.workspace.is_empty() {
            return Ok(());
        }

        // Create transport in async context
        self.transport = match create_transport(
            config.transport_kind,
            &config.workspace,
            &config.image,
            config.data_dir.clone(),
            config.ws_url.clone(),
        )
        .await
        {
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
                    parent_id: None,
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
                    parent_id: None,
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
                        parent_id: None,
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
                    parent_id: None,
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
                parent_id: None,
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
                parent_id: None,
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

    /// Build evaluation context for keymap condition checking
    fn build_eval_context(&self) -> EvalContext {
        EvalContext {
            cursor_position: self.cursor_position,
            input_width: unicode_width::UnicodeWidthStr::width(self.input.as_str()),
            input_byte_len: self.input.len(),
            selected_index: self.chat_state.selected().unwrap_or(0),
            results_len: self.search_results.len(),
            original_input_empty: self.input.is_empty(),
            in_search_mode: self.app_mode == AppMode::Search,
        }
    }

    /// Build tree structure from messages for threaded display
    fn build_message_tree(&mut self) {
        self.message_tree = Tree::new();

        // Build nodes for each message
        for (idx, msg) in self.messages.iter().enumerate() {
            let node = TreeNode::new(
                idx.to_string(),
                msg.parent_id.clone(),
                0,
                idx == self.messages.len() - 1,
            );
            self.message_tree.add_node(node);
        }
    }

    /// Get tree prefix for a message at index
    fn get_message_tree_prefix(&self, idx: usize) -> String {
        if let Some(node) = self.message_tree.get(&idx.to_string()) {
            node.prefix(&self.message_tree)
        } else {
            String::new()
        }
    }

    /// Add a user message to history
    fn add_to_history(&mut self, content: &str) {
        let result = SearchResult {
            id: uuid::Uuid::new_v4().to_string(),
            content: content.to_string(),
            timestamp: chrono::Utc::now().timestamp(),
            score: 1.0,
            metadata: None,
        };
        self.history_engine.add_result(result);
    }

    /// Search history (synchronous, without tokio runtime)
    fn search_history(&self, query: &str) -> Vec<String> {
        // Synchronous search without tokio runtime
        // This is a simple contains match implemented directly
        if query.is_empty() {
            return self.history_engine.results().iter().map(|r| r.content.clone()).collect();
        }

        let query_lower = query.to_lowercase();
        self.history_engine
            .results()
            .iter()
            .filter(|r| r.content.to_lowercase().contains(&query_lower))
            .map(|r| r.content.clone())
            .collect()
    }

    /// Handle action from keymap
    fn handle_action(&mut self, action: &Action) {
        match action {
            Action::CursorLeft => {
                if self.cursor_position > 0 {
                    self.cursor_position -= 1;
                }
            }
            Action::CursorRight => {
                let char_count = self.input.chars().count();
                if self.cursor_position < char_count {
                    self.cursor_position += 1;
                }
            }
            Action::CursorWordLeft => {
                // Move cursor to start of previous word
                let words: Vec<&str> = self.input.split_whitespace().collect();
                if words.is_empty() {
                    self.cursor_position = 0;
                    return;
                }
                let mut pos = 0;
                for word in words.iter() {
                    let word_start = self.input[pos..].find(word).map(|p| pos + p).unwrap_or(pos);
                    if word_start > self.cursor_position {
                        break;
                    }
                    pos = word_start;
                }
                self.cursor_position = pos;
            }
            Action::CursorWordRight => {
                // Move cursor to start of next word
                if let Some(next_word_pos) = self.input[self.cursor_position..].find(|c: char| c.is_whitespace()) {
                    let ws_start = self.cursor_position + next_word_pos;
                    if let Some(next_non_ws) = self.input[ws_start..].find(|c: char| !c.is_whitespace()) {
                        self.cursor_position = ws_start + next_non_ws;
                    }
                } else {
                    self.cursor_position = self.input.len();
                }
            }
            Action::CursorHome => {
                self.cursor_position = 0;
            }
            Action::CursorEnd => {
                self.cursor_position = self.input.chars().count();
            }
            Action::InsertChar(c) => {
                let char_idx = self.cursor_position.min(self.input.chars().count());
                let byte_idx = self.input.char_indices().nth(char_idx).map(|(i, _)| i).unwrap_or(self.input.len());
                self.input.insert(byte_idx, *c);
                self.cursor_position += 1;
            }
            Action::Delete => {
                if self.cursor_position < self.input.chars().count() {
                    let char_idx = self.cursor_position;
                    let byte_idx = self.input.char_indices().nth(char_idx).map(|(i, _)| i).unwrap_or(self.input.len());
                    self.input.remove(byte_idx);
                }
            }
            Action::DeleteWord => {
                // Delete from cursor to end of current word
                if let Some(word_end) = self.input[self.cursor_position..].find(|c: char| c.is_whitespace()) {
                    let end_pos = self.cursor_position + word_end;
                    self.input.drain(self.cursor_position..end_pos);
                } else {
                    self.input.drain(self.cursor_position..);
                }
            }
            Action::Backspace => {
                if self.cursor_position > 0 {
                    self.cursor_position -= 1;
                    let char_idx = self.cursor_position;
                    let byte_idx = self.input.char_indices().nth(char_idx).map(|(i, _)| i).unwrap_or(0);
                    self.input.remove(byte_idx);
                }
            }
            Action::Clear => {
                self.input.clear();
                self.cursor_position = 0;
            }
            Action::Submit => {
                if !self.input.is_empty() {
                    let msg_content = std::mem::take(&mut self.input);
                    // Add to history
                    self.add_to_history(&msg_content);
                    self.messages.push(Message {
                        role: MessageRole::User,
                        content: MessageContent::Text(msg_content),
                        timestamp: chrono::Local::now().format("%H:%M").to_string(),
                        parent_id: None,
                    });
                    self.cursor_position = 0;
                    self.input_mode = InputMode::SingleLine;
                    self.chat_state.select(Some(self.messages.len().saturating_sub(1)));
                }
            }
            Action::ScrollUp => {
                self.scroll_up();
            }
            Action::ScrollDown => {
                self.scroll_down();
            }
            Action::PageUp => {
                for _ in 0..5 {
                    self.scroll_up();
                }
            }
            Action::PageDown => {
                for _ in 0..5 {
                    self.scroll_down();
                }
            }
            Action::EnterNormalMode => {
                self.key_mode = KeyMode::Vim;
            }
            Action::EnterInsertMode => {
                self.key_mode = KeyMode::Emacs;
            }
            Action::Quit => {
                self.quit = true;
            }
            Action::Interrupt => {
                // Interrupt current operation
                self.chunk_receiver = None;
            }
            Action::ClearScreen => {
                self.chat_state.select(Some(self.messages.len().saturating_sub(1)));
            }
            // Search actions
            Action::OpenSearch => {
                self.app_mode = AppMode::Search;
                self.search_query.clear();
                self.search_selected = 0;
                // Load all history as initial results
                self.search_results = self.search_history("");
            }
            Action::ExitSearch => {
                self.app_mode = AppMode::Normal;
                self.search_query.clear();
                self.search_results.clear();
            }
            Action::SearchSelect => {
                if !self.search_results.is_empty() {
                    let selected = self.search_results[self.search_selected].clone();
                    self.input = selected;
                    self.cursor_position = self.input.len();
                }
                self.app_mode = AppMode::Normal;
                self.search_query.clear();
                self.search_results.clear();
            }
            Action::SearchUp => {
                if !self.search_results.is_empty() {
                    self.search_selected = self.search_selected.saturating_sub(1);
                }
            }
            Action::SearchDown => {
                if !self.search_results.is_empty() {
                    self.search_selected = (self.search_selected + 1).min(self.search_results.len() - 1);
                }
            }
            Action::NoOp => {
                // No operation - do nothing
            }
        }
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
                match event::read()? {
                    Event::Key(key) => {
                        self.handle_key(key);
                    }
                    Event::Mouse(mouse) => {
                        self.handle_mouse(mouse);
                    }
                    _ => {}
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

        // Calculate dynamic input height based on content
        // Input area: min 1 row, max 10 rows for content
        // Use actual area width - the Paragraph widget wraps at full width
        let input_text_width = area.width as usize;
        let input_text = &self.input;

        // Count lines: explicit newlines + wrap-based lines
        let explicit_newlines = input_text.chars().filter(|&c| c == '\n').count() as u16;

        // Calculate wrapped lines for each segment between newlines
        // Use unicode width for proper visual width calculation
        let mut wrapped_lines = 0u16;
        for line in input_text.split('\n') {
            let line_width = unicode_width::UnicodeWidthStr::width(line);
            if input_text_width > 0 && line_width > 0 {
                wrapped_lines += ((line_width as f32 / input_text_width as f32).ceil() as u16).max(1);
            } else if !line.is_empty() {
                wrapped_lines += 1;
            }
        }

        // Total lines = explicit newlines + wrapped content
        let total_lines = (explicit_newlines + 1).max(wrapped_lines);
        let min_input_lines = 1;
        let max_input_lines = 10;
        let input_lines = total_lines.clamp(min_input_lines, max_input_lines);
        let input_height = input_lines + 2; // +2 for top and bottom borders

        // Define layout with dynamic input height
        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Length(3), // Header
                Constraint::Min(0),    // Chat
                Constraint::Length(input_height), // Input (dynamic)
                Constraint::Length(2), // Status (2 rows)
            ])
            .split(area);

        self.draw_header(f, chunks[0]);
        self.draw_chat(f, chunks[1]);
        self.draw_input(f, chunks[2]);
        self.draw_status(f, chunks[3]);

        // Draw search overlay if in search mode
        if self.app_mode == AppMode::Search {
            self.draw_search_overlay(f, area);
        }
    }

    fn draw_header(&self, f: &mut Frame, area: Rect) {
        use ratatui::style::{Color, Modifier, Style};
        use ratatui::widgets::{Block, Paragraph};

        // 双行布局：第一行 Logo + 版本号，第二行当前目录
        let logo = Style::default().fg(self.theme.accent).add_modifier(Modifier::BOLD);
        let white = Style::default().fg(Color::White).add_modifier(Modifier::BOLD);
        let path_style = Style::default().fg(self.theme.secondary);

        // 第一行：🦑 NanoGridBot v0.1.0-alpha.1
        let version = env!("CARGO_PKG_VERSION");
        let version_num_style = Style::default().fg(self.theme.status).add_modifier(Modifier::BOLD);
        let line1 = Line::from(vec![
            Span::styled(" 🦑 Nano", logo),
            Span::styled("GridBot", white),
            Span::styled(" v", version_num_style),
            Span::styled(version, version_num_style),
        ]);

        // 第二行：当前目录路径（使用 ~ 风格，与 NanoGridBot 列对齐）
        let cwd = std::env::current_dir()
            .map(|p| {
                if let Ok(home) = std::env::var("HOME") {
                    let path_str = p.to_string_lossy().to_string();
                    path_str.replace(&home, "~")
                } else {
                    p.to_string_lossy().to_string()
                }
            })
            .unwrap_or_else(|_| "Unknown".to_string());
        let line2 = Line::from(vec![
            Span::styled("    ", path_style),
            Span::styled(cwd, path_style),
        ]);

        let block = Block::new().borders(ratatui::widgets::Borders::NONE);
        let paragraph = Paragraph::new(vec![line1, line2]).block(block);
        f.render_widget(paragraph, area);
    }

    fn draw_chat(&mut self, f: &mut Frame, area: Rect) {
        use ratatui::style::Style;
        use ratatui::widgets::{Block, Borders};

        let block = Block::new()
            .borders(Borders::NONE);

        // Build message tree for threaded display
        self.build_message_tree();

        // Build message items - collect messages first to avoid borrow issues
        let messages = self.messages.clone();
        let theme = self.theme.clone();
        let items: Vec<ListItem> = if messages.is_empty() {
            let dim = Style::default().fg(self.theme.secondary).dim();
            let welcome_path = std::path::Path::new("welcome.txt");
            let lines = welcome_lines_from_file(welcome_path);
            if lines.is_empty() {
                Vec::new()
            } else {
                vec![ListItem::new(lines).style(dim)]
            }
        } else {
            messages
                .iter()
                .enumerate()
                .map(|(idx, msg)| {
                    let tree_prefix = self.get_message_tree_prefix(idx);
                    Self::render_message_item(msg, self.is_message_collapsed(idx), &theme, &tree_prefix, area.width)
                })
                .collect()
        };

        let list = List::new(items)
            .block(block)
            .style(Style::default().fg(self.theme.foreground));

        f.render_stateful_widget(list, area, &mut self.chat_state);
    }

    /// Wrap long text to fit within specified width (for chat display)
    /// Returns lines with prefix prepended: first line has full_prefix, continuation has continuation_prefix
    fn wrap_message_text(text: &str, full_prefix: &str, continuation_prefix: &str, timestamp: &str, terminal_width: u16) -> Vec<String> {
        let mut result = Vec::new();

        // First, split by explicit newlines
        let explicit_lines: Vec<&str> = text.lines().collect();
        let is_single_line = explicit_lines.len() == 1;

        for (line_idx, line) in explicit_lines.iter().enumerate() {
            let line_width = line.len();

            // Determine available width for this line using actual terminal width
            let available_width = (terminal_width as usize).saturating_sub(continuation_prefix.len());

            if line_width == 0 {
                result.push(String::new());
            } else if line_width <= available_width {
                // Line fits, just add prefix
                if line_idx == 0 && is_single_line {
                    result.push(format!("{}{} {}", full_prefix, line, timestamp));
                } else if line_idx == 0 {
                    result.push(format!("{}{}", full_prefix, line));
                } else {
                    result.push(format!("{}{}", continuation_prefix, line));
                }
            } else {
                // Wrap long line word by word
                let mut current_line = String::new();
                let mut current_width = 0;
                let mut is_first_wrapped_line = true;
                for word in line.split_whitespace() {
                    let word_width = word.len();
                    if current_width + word_width + 1 > available_width {
                        if !current_line.is_empty() {
                            // First wrapped segment gets full_prefix, rest get nothing
                            if is_first_wrapped_line {
                                result.push(format!("{}{}", full_prefix, current_line.trim()));
                                is_first_wrapped_line = false;
                            } else {
                                result.push(current_line.trim().to_string());
                            }
                        }
                        current_line = word.to_string();
                        current_width = word_width;
                    } else {
                        if current_width > 0 {
                            current_line.push(' ');
                            current_width += 1;
                        }
                        current_line.push_str(word);
                        current_width += word_width;
                    }
                }
                if !current_line.is_empty() {
                    if is_first_wrapped_line {
                        result.push(format!("{}{}", full_prefix, current_line.trim()));
                    } else {
                        result.push(current_line.trim().to_string());
                    }
                }
            }
        }

        result
    }

    fn render_message_item<'a>(msg: &'a Message, collapsed: bool, theme: &'a Theme, tree_prefix: &str, terminal_width: u16) -> ListItem<'a> {
        use ratatui::style::Style;
        use ratatui::text::Line;

        let icons = &theme.icons;

        // Build prefix with tree structure
        let user_prefix = format!("{} {} ", tree_prefix, icons.user);
        let agent_prefix = format!("{} {} ", tree_prefix, icons.agent);

        match msg.role {
            MessageRole::User => {
                match &msg.content {
                    MessageContent::Text(text) => {
                        // Wrap long text: prefix for first line is user_prefix + timestamp, continuation uses user_prefix
                        let wrapped_lines = Self::wrap_message_text(text, &user_prefix, &user_prefix, &msg.timestamp, terminal_width);
                        let lines: Vec<Line> = wrapped_lines
                            .into_iter()
                            .map(Line::from)
                            .collect();
                        ListItem::new(lines)
                            .style(Style::default().fg(theme.user_message).italic())
                    }
                    _ => ListItem::new(user_prefix.clone()),
                }
            }
            MessageRole::Agent => {
                match &msg.content {
                    MessageContent::Text(text) => {
                        // Wrap long text: first line gets agent_prefix + timestamp, continuation gets agent_prefix
                        let wrapped_lines = Self::wrap_message_text(text, &agent_prefix, &agent_prefix, &msg.timestamp, terminal_width);
                        let lines: Vec<Line> = wrapped_lines
                            .into_iter()
                            .map(Line::from)
                            .collect();
                        ListItem::new(lines)
                            .style(Style::default().fg(theme.agent_message))
                    }
                    MessageContent::Thinking(text) => {
                        let preview = if collapsed {
                            format!("[{} collapsed, press Tab to expand]", text.lines().count())
                        } else {
                            text.clone()
                        };
                        let thinking_prefix = format!("{}{} ", tree_prefix, icons.spinner[0]);
                        let lines: Vec<Line> = preview
                            .lines()
                            .enumerate()
                            .map(|(i, line)| {
                                if i == 0 {
                                    Line::from(format!("{}{}", thinking_prefix, line))
                                } else {
                                    Line::from(format!("{}{}", tree_prefix, line))
                                }
                            })
                            .collect();
                        ListItem::new(lines)
                            .style(Style::default().fg(theme.thinking))
                    }
                    MessageContent::ToolCall { name, status } => {
                        let status_icon = match status {
                            ToolStatus::Running => format!(" {}", icons.tool_running),
                            ToolStatus::Success => format!(" {}", icons.tool_success),
                            ToolStatus::Error => format!(" {}", icons.tool_error),
                        };
                        let color = match status {
                            ToolStatus::Running => theme.tool_running,
                            ToolStatus::Success => theme.tool_success,
                            ToolStatus::Error => theme.tool_error,
                        };
                        let tool_line = format!("{}{} {}{}", tree_prefix, icons.arrow, name, status_icon);
                        ListItem::new(tool_line)
                            .style(Style::default().fg(color))
                    }
                    MessageContent::CodeBlock { language, code } => {
                        // Use syntax highlighting
                        let highlighted = crate::syntax::highlight_code(code, language);
                        let cb = icons.code_block;
                        let block_header = format!("{} {} {}", cb, language, cb);
                        let lines: Vec<Line> = vec![
                            Line::from(format!("{}{}", tree_prefix, block_header)),
                            Line::from(highlighted),
                        ];
                        ListItem::new(lines)
                            .style(Style::default().fg(theme.warning))
                    }
                    MessageContent::Error(err) => {
                        let error_line = format!("{}{} Error: {}", tree_prefix, icons.cross, err);
                        ListItem::new(error_line)
                            .style(Style::default().fg(theme.error))
                    }
                }
            }
        }
    }

    fn draw_input(&self, f: &mut Frame, area: Rect) {
        use ratatui::style::Style;
        use ratatui::widgets::{Block, Borders, Paragraph};

        // Threshold for long input warning
        const LONG_INPUT_THRESHOLD: usize = 500;
        const MAX_DISPLAY_CHARS: usize = 300;

        //上下细线
        let block = Block::new()
            .borders(Borders::TOP | Borders::BOTTOM)
            .border_style(Style::default().fg(self.theme.border));

        //添加 ❯ 前缀
        let prefix = "❯ ";

        // Handle long input: show warning for very long content
        let (text, _show_warning) = if self.input.len() > LONG_INPUT_THRESHOLD {
            // Show truncated content + warning
            let display_content: String = self.input.chars().take(MAX_DISPLAY_CHARS).collect();
            let warning = format!("\n[... {} characters, showing last {} ...]", self.input.len(), MAX_DISPLAY_CHARS);
            (format!("{}{}{}", prefix, display_content, warning), true)
        } else {
            let content = if self.input.is_empty() {
                String::new()
            } else {
                self.input.clone()
            };
            (format!("{}{}", prefix, content), false)
        };

        let paragraph = Paragraph::new(text)
            .block(block)
            .style(Style::default().fg(self.theme.input))
            .wrap(ratatui::widgets::Wrap { trim: true });

        f.render_widget(paragraph, area);

        // Render cursor at position
        #[allow(deprecated)]
        if area.width > 2 {
            let prefix_width = unicode_width::UnicodeWidthStr::width(prefix) as u16;
            let available_width = (area.width as usize).saturating_sub(prefix_width as usize);

            if self.input.is_empty() {
                // Empty input: show cursor at prefix end
                let x = area.x + prefix_width;
                let y = area.y + 1;
                f.set_cursor(x, y);
            } else {
                // Calculate cursor row and column based on content
                // Get characters before cursor position
                let cursor_pos = self.cursor_position;
                let chars_before_cursor: String = self.input.chars().take(cursor_pos).collect();

                // Find the content on the current line (after last explicit newline)
                let last_newline_idx = chars_before_cursor.rfind('\n');
                let current_line_content = if let Some(idx) = last_newline_idx {
                    &chars_before_cursor[idx + 1..]
                } else {
                    chars_before_cursor.as_str()
                };

                // Calculate visual width of text on current line
                let current_line_width = unicode_width::UnicodeWidthStr::width(current_line_content);

                // Calculate wrapped lines and position
                // Cursor at position N means: N characters have been typed
                // If N <= available_width, cursor is on line 0, at position N
                // If N > available_width, cursor wraps to subsequent lines
                let wrapped_offset = if available_width > 0 && current_line_width >= available_width {
                    // Use ceiling division to properly handle the wrap
                    ((current_line_width + available_width) - 1) / available_width - 1
                } else {
                    0
                };

                // Column position within current wrapped line
                let col_in_line = if available_width > 0 {
                    current_line_width % available_width
                } else {
                    current_line_width
                };

                // Count explicit newlines
                let explicit_newlines = chars_before_cursor.chars().filter(|&c| c == '\n').count() as u16;

                // Final cursor position
                let cursor_x = (prefix_width as usize + col_in_line).min(area.width as usize - 1) as u16;
                let cursor_y = (area.y + 1 + explicit_newlines + wrapped_offset as u16).min(area.bottom().saturating_sub(1));

                f.set_cursor(area.x + cursor_x, cursor_y);
            }
        }
    }

    fn draw_status(&self, f: &mut Frame, area: Rect) {
        use ratatui::style::Style;
        use ratatui::widgets::Paragraph;

        let icons = &self.theme.icons;
        let mode_str = match self.key_mode {
            KeyMode::Emacs => "emacs",
            KeyMode::Vim => "vim",
        };
        let theme_name = crate::theme::theme_display_name(self.theme.name);

        // 第一行: workspace | mode | theme
        let line1 = format!(
            " {} {} | {} mode | {} ",
            if self.workspace.is_empty() { icons.info } else { icons.agent },
            if self.workspace.is_empty() { "no workspace" } else { &self.workspace },
            mode_str,
            theme_name,
        );

        // 第二行: 操作提示
        let line2 = format!(
            " {} scroll | Tab expand/collapse | Ctrl+R history | Ctrl+C clear/interrupt | 2x Ctrl+C quit ",
            icons.arrow,
        );

        let text = format!("{}\n{}", line1, line2);

        let paragraph = Paragraph::new(text)
            .style(Style::default().fg(self.theme.status));
        f.render_widget(paragraph, area);
    }

    /// Draw search overlay (Ctrl+R history search)
    fn draw_search_overlay(&self, f: &mut Frame, area: Rect) {
        use ratatui::widgets::{Block, Borders, List, ListItem, Paragraph};
        use ratatui::style::Style;

        // Create a centered overlay box
        let overlay_width = 60.min(area.width.saturating_sub(4));
        let overlay_height = 15.min(area.height.saturating_sub(4));

        let overlay_x = (area.width - overlay_width) / 2;
        let overlay_y = (area.height - overlay_height) / 2;

        let overlay_area = Rect::new(
            overlay_x,
            overlay_y,
            overlay_x + overlay_width,
            overlay_y + overlay_height,
        );

        // Draw semi-transparent background
        let bg_block = Block::default()
            .style(Style::default().bg(Color::DarkGray))
            .borders(Borders::NONE);
        f.render_widget(bg_block, overlay_area);

        // Draw border box
        let box_area = Rect::new(
            overlay_area.x + 1,
            overlay_area.y + 1,
            overlay_area.x + overlay_width - 1,
            overlay_area.y + overlay_height - 1,
        );

        let search_block = Block::default()
            .title(" Search History (Ctrl+R) ")
            .borders(Borders::ALL)
            .border_style(Style::default().fg(self.theme.accent));
        f.render_widget(search_block, box_area);

        // Draw search input
        let input_area = Rect::new(
            box_area.x + 1,
            box_area.y + 1,
            box_area.right().saturating_sub(1),
            box_area.y + 3,
        );

        let input_text = format!("> {}", self.search_query);
        let input_para = Paragraph::new(input_text)
            .style(Style::default().fg(self.theme.input));
        f.render_widget(input_para, input_area);

        // Draw results list
        let results_area = Rect::new(
            box_area.x + 1,
            box_area.y + 3,
            box_area.right().saturating_sub(1),
            box_area.bottom().saturating_sub(1),
        );

        if self.search_results.is_empty() {
            let empty_text = Paragraph::new("No history found")
                .style(Style::default().fg(self.theme.status).dim());
            f.render_widget(empty_text, results_area);
        } else {
            let items: Vec<ListItem> = self.search_results
                .iter()
                .enumerate()
                .map(|(idx, result)| {
                    let prefix = if idx == self.search_selected { "▶" } else { " " };
                    let style = if idx == self.search_selected {
                        Style::default().fg(self.theme.accent).add_modifier(Modifier::BOLD)
                    } else {
                        Style::default().fg(self.theme.input)
                    };
                    ListItem::new(format!("{} {}", prefix, result)).style(style)
                })
                .collect();

            let results_list = List::new(items)
                .block(Block::default().borders(Borders::NONE));
            f.render_widget(results_list, results_area);
        }

        // Draw hint at bottom
        let hint_area = Rect::new(
            box_area.x + 1,
            box_area.bottom().saturating_sub(1),
            box_area.right().saturating_sub(1),
            box_area.bottom(),
        );
        let hint = Paragraph::new("↑↓ select | Enter use | Esc cancel")
            .style(Style::default().fg(self.theme.status).dim());
        f.render_widget(hint, hint_area);
    }

    fn handle_key(&mut self, key: event::KeyEvent) {
        if key.kind != KeyEventKind::Press {
            return;
        }

        // Search mode: handle character input and special keys
        if self.app_mode == AppMode::Search {
            match key.code {
                KeyCode::Char(c) => {
                    self.search_query.push(c);
                    // Real-time search
                    let query = self.search_query.clone();
                    self.search_results = self.search_history(&query);
                    self.search_selected = 0;
                    return;
                }
                KeyCode::Backspace => {
                    self.search_query.pop();
                    // Real-time search
                    let query = self.search_query.clone();
                    self.search_results = self.search_history(&query);
                    self.search_selected = 0;
                    return;
                }
                _ => {}
            }
        }

        // Vim mode specific handling (only when NOT in search mode)
        if self.key_mode == KeyMode::Vim && self.app_mode != AppMode::Search {
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
                    return;
                }
                KeyCode::Esc => {
                    self.quit = true;
                    return;
                }
                _ => {}
            }
        }

        // Build evaluation context for condition checking
        let ctx = self.build_eval_context();

        // Try to find a matching keybinding with satisfied condition
        // First collect matching actions to avoid borrow issues
        let mut action_to_handle: Option<Action> = None;
        for binding in &self.keybindings {
            if binding.matches(key.code, key.modifiers) && binding.is_condition_satisfied(&ctx) {
                action_to_handle = Some(binding.action.clone());
                break;
            }
        }

        // Now handle the action
        if let Some(action) = action_to_handle {
            match action {
                Action::Interrupt => {
                    // Ctrl+C special handling: similar to Claude Code behavior
                    let now = Instant::now();
                    let is_running = self.chunk_receiver.is_some();

                    if !self.input.is_empty() {
                        // Has input: clear it
                        self.input.clear();
                        self.cursor_position = 0;
                    } else if is_running {
                        // Running: interrupt
                        self.chunk_receiver = None;
                    } else {
                        // Not running: check for double-Ctrl+C
                        if let Some(last_time) = self.last_ctrl_c_time {
                            if now.duration_since(last_time) < Duration::from_secs(2) {
                                self.quit = true;
                            } else {
                                self.last_ctrl_c_time = Some(now);
                            }
                        } else {
                            self.last_ctrl_c_time = Some(now);
                        }
                    }
                }
                Action::Submit => {
                    // Submit needs to handle Shift+Enter for multiline
                    if key.modifiers.contains(KeyModifiers::SHIFT) {
                        // Shift+Enter: insert newline
                        let char_idx = self.cursor_position.min(self.input.chars().count());
                        let byte_idx = self.input.char_indices().nth(char_idx).map(|(i, _)| i).unwrap_or(self.input.len());
                        self.input.insert(byte_idx, '\n');
                        self.cursor_position += 1;
                        self.input_mode = InputMode::MultiLine;
                    } else if !self.input.is_empty() {
                        let msg_content = std::mem::take(&mut self.input);
                        // Add to history before pushing to messages
                        self.add_to_history(&msg_content);
                        self.messages.push(Message {
                            role: MessageRole::User,
                            content: MessageContent::Text(msg_content),
                            timestamp: chrono::Local::now().format("%H:%M").to_string(),
                            parent_id: None,
                        });
                        self.cursor_position = 0;
                        self.input_mode = InputMode::SingleLine;
                        self.chat_state.select(Some(self.messages.len().saturating_sub(1)));
                    }
                }
                Action::InsertChar(c) => {
                    let char_idx = self.cursor_position.min(self.input.chars().count());
                    let byte_idx = self.input.char_indices().nth(char_idx).map(|(i, _)| i).unwrap_or(self.input.len());
                    self.input.insert(byte_idx, c);
                    self.cursor_position += 1;
                }
                _ => {
                    self.handle_action(&action);
                }
            }
            return;
        }

        // Fallback: Tab for collapse toggle (not in keymap)
        if key.code == KeyCode::Tab {
            if let Some(selected) = self.chat_state.selected() {
                self.toggle_message_collapse(selected);
            }
        }

        // Arrow up/down and Ctrl+P/N for history navigation
        // Only when not in search mode and input is empty (or at boundaries)
        if self.app_mode != AppMode::Search {
            let history_count = self.history_engine.results().len();
            if history_count > 0 {
                if key.code == KeyCode::Up || (key.modifiers == KeyModifiers::CONTROL && key.code == KeyCode::Char('p')) {
                    // Navigate to previous history
                    let new_index = match self.history_index {
                        None => 0,
                        Some(i) if i < history_count - 1 => i + 1,
                        Some(i) => i,
                    };
                    if self.history_index != Some(new_index) || self.input.is_empty() {
                        self.history_index = Some(new_index);
                        let idx = history_count - 1 - new_index;
                        if let Some(result) = self.history_engine.results().get(idx) {
                            self.input = result.content.clone();
                            self.cursor_position = self.input.len();
                        }
                    }
                } else if key.code == KeyCode::Down || (key.modifiers == KeyModifiers::CONTROL && key.code == KeyCode::Char('n')) {
                    // Navigate to next history
                    if let Some(i) = self.history_index {
                        if i > 0 {
                            let new_index = i - 1;
                            self.history_index = Some(new_index);
                            let idx = history_count - 1 - new_index;
                            if let Some(result) = self.history_engine.results().get(idx) {
                                self.input = result.content.clone();
                                self.cursor_position = self.input.len();
                            }
                        } else {
                            // Go back to empty input
                            self.history_index = None;
                            self.input.clear();
                            self.cursor_position = 0;
                        }
                    }
                }
            }
        }

        // Fallback: Handle regular character input (not handled by keymap)
        // This is needed because keymap only handles Ctrl+key, not regular keys
        if let KeyCode::Char(c) = key.code {
            if key.modifiers.is_empty() || key.modifiers == KeyModifiers::SHIFT {
                // Insert character at cursor position
                let char_idx = self.cursor_position.min(self.input.chars().count());
                let byte_idx = self.input.char_indices().nth(char_idx).map(|(i, _)| i).unwrap_or(self.input.len());
                // For Shift+Char, convert to uppercase
                let char_to_insert = if key.modifiers == KeyModifiers::SHIFT {
                    c.to_ascii_uppercase()
                } else {
                    c
                };
                self.input.insert(byte_idx, char_to_insert);
                self.cursor_position += 1;
                // Reset history navigation when user starts typing
                self.history_index = None;
            }
        }
    }
}
