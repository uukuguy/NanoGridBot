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
use tui_textarea::TextArea;
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
use ngb_config::Config;
use std::path::PathBuf;
use tokio::sync::mpsc;

/// Configuration for the TUI application
#[derive(Debug, Clone)]
pub struct AppConfig {
    /// Workspace name to connect to
    pub workspace: String,
    /// Transport kind (pipe, ipc, ws, mock, or session)
    pub transport_kind: TransportKind,
    /// Container image name
    pub image: String,
    /// Data directory for IPC/WS
    pub data_dir: PathBuf,
    /// WebSocket URL (for ws transport)
    pub ws_url: Option<String>,
    /// Theme name
    pub theme_name: ThemeName,
    /// Full Config for secure mounts and session transport
    pub config: Option<Config>,
    /// Session ID for resuming a persistent container session
    pub session_id: Option<String>,
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
            config: None,
            session_id: None,
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

    /// Set the full Config for secure mount validation and session transport
    pub fn with_config(mut self, config: Config) -> Self {
        self.config = Some(config);
        self
    }

    /// Set session ID for resuming a persistent container session
    pub fn with_session_id(mut self, id: impl Into<String>) -> Self {
        self.session_id = Some(id.into());
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

/// Application runtime state — drives status bar icon and spinner
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub enum AppState {
    /// No active processing
    #[default]
    Idle,
    /// Receiving streaming text from agent
    Streaming,
    /// Agent is thinking / reasoning
    Thinking,
    /// A tool call is in progress
    ToolRunning,
    /// Transport is disconnected / failed to connect
    Offline,
}

pub struct App {
    /// Whether to quit the application
    #[allow(dead_code)]
    pub quit: bool,
    /// Current workspace name
    pub workspace: String,
    /// Chat messages
    pub messages: Vec<Message>,
    /// TextArea widget for input handling
    textarea: TextArea<'static>,
    /// Scroll offset for chat area
    pub scroll: u16,
    /// List state for chat scrolling
    pub chat_state: ListState,
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
    /// Runtime state (drives status bar)
    app_state: AppState,
    /// Transport kind label for status bar display
    transport_label: String,
    /// Frame counter for spinner animation
    spinner_tick: usize,
    /// Pending quit confirmation (true = waiting for second press)
    pending_quit: bool,
    /// Vim: pending 'g' key for 'gg' command
    vim_pending_g: bool,
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

        // Initialize TextArea widget with optimized configuration
        let mut textarea = TextArea::default();
        // Config will be applied after Self is created; set inline for now
        textarea.set_placeholder_text("Type a message... (Enter to send, Shift+Enter for new line)");
        textarea.set_placeholder_style(ratatui::style::Style::default().fg(ratatui::style::Color::DarkGray));
        textarea.set_cursor_line_style(ratatui::style::Style::default());

        Ok(Self {
            quit: false,
            workspace: config.workspace,
            messages: Vec::new(),
            textarea,
            scroll: 0,
            chat_state,
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
            app_state: AppState::default(),
            transport_label: config.transport_kind.to_string(),
            spinner_tick: 0,
            pending_quit: false,
            vim_pending_g: false,
        })
    }

    /// Set up transport after app creation (must be called from async context)
    pub async fn setup_transport(&mut self, config: &AppConfig) -> anyhow::Result<()> {
        if config.workspace.is_empty() {
            return Ok(());
        }

        self.transport_label = config.transport_kind.to_string();

        // Create transport in async context
        self.transport = match create_transport(
            config.transport_kind,
            &config.workspace,
            &config.image,
            config.data_dir.clone(),
            config.ws_url.clone(),
            config.config.as_ref(),
            config.session_id.clone(),
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
                self.app_state = AppState::Offline;
                self.messages.push(Message {
                    role: MessageRole::Agent,
                    content: MessageContent::Error(format!(
                        "Transport connection failed ({}): {}",
                        config.transport_kind, e
                    )),
                    timestamp: chrono::Local::now().format("%H:%M").to_string(),
                    parent_id: None,
                });
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
                self.app_state = AppState::Streaming;
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
                self.app_state = AppState::Thinking;
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
                self.app_state = AppState::ToolRunning;
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
                self.app_state = AppState::Idle;
                self.finalize_thinking();
                self.finalize_tool();
            }
            OutputChunk::Error(err) => {
                self.app_state = AppState::Idle;
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
        let input_text = self.textarea.lines().join("\n");
        let cursor_col = self.textarea.cursor().1;
        EvalContext {
            cursor_position: cursor_col,
            input_width: unicode_width::UnicodeWidthStr::width(input_text.as_str()),
            input_byte_len: input_text.len(),
            selected_index: self.chat_state.selected().unwrap_or(0),
            results_len: self.search_results.len(),
            original_input_empty: input_text.is_empty(),
            in_search_mode: self.app_mode == AppMode::Search,
        }
    }

    /// Set textarea content
    fn set_textarea_content(&mut self, content: &str) {
        let lines: Vec<String> = content.lines().map(String::from).collect();
        let lines = if lines.is_empty() { vec![String::new()] } else { lines };
        self.textarea = TextArea::from(lines);
        self.apply_textarea_config();
    }

    /// Apply standard configuration to textarea
    fn apply_textarea_config(&mut self) {
        self.textarea.set_placeholder_text("Type a message... (Enter to send, Shift+Enter for new line)");
        self.textarea.set_placeholder_style(ratatui::style::Style::default().fg(ratatui::style::Color::DarkGray));
        self.textarea.set_cursor_line_style(ratatui::style::Style::default());
    }

    /// Get current spinner frame character based on app state
    fn spinner_frame(&self) -> &str {
        match self.app_state {
            AppState::Thinking | AppState::Streaming | AppState::ToolRunning => {
                let frames = &self.theme.icons.spinner;
                frames[self.spinner_tick % frames.len()]
            }
            AppState::Idle => "✓",
            AppState::Offline => "⚠",
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
                    // Set textarea content to selected history item
                    self.set_textarea_content(&selected);
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
            // Editing actions are handled by tui-textarea, not here
            _ => {}
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
            // Advance spinner for animated status
            self.spinner_tick = self.spinner_tick.wrapping_add(1);

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
        let input_text = self.textarea.lines().join("\n");

        // Count lines: explicit newlines + wrap-based lines
        let explicit_newlines = input_text.chars().filter(|&c| c == '\n').count() as u16;

        // Calculate wrapped lines for each segment between newlines
        // Use unicode width for proper visual width calculation
        let mut wrapped_lines = 0u16;
        for line in input_text.split('\n') {
            let line_width = unicode_width::UnicodeWidthStr::width(line);
            if input_text_width > 0 && line_width > 0 {
                // Use (line_width - 1) to handle boundary: when content exactly fills a line,
                // it needs 2 rows (the last char wraps to next line)
                wrapped_lines += (((line_width.saturating_sub(1)) / input_text_width) + 1) as u16;
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

    /// Convert ratatui_core::style::Color to ratatui::style::Color
    fn convert_color(c: ratatui_core::style::Color) -> ratatui::style::Color {
        match c {
            ratatui_core::style::Color::Reset => ratatui::style::Color::Reset,
            ratatui_core::style::Color::Black => ratatui::style::Color::Black,
            ratatui_core::style::Color::Red => ratatui::style::Color::Red,
            ratatui_core::style::Color::Green => ratatui::style::Color::Green,
            ratatui_core::style::Color::Yellow => ratatui::style::Color::Yellow,
            ratatui_core::style::Color::Blue => ratatui::style::Color::Blue,
            ratatui_core::style::Color::Magenta => ratatui::style::Color::Magenta,
            ratatui_core::style::Color::Cyan => ratatui::style::Color::Cyan,
            ratatui_core::style::Color::Gray => ratatui::style::Color::Gray,
            ratatui_core::style::Color::DarkGray => ratatui::style::Color::DarkGray,
            ratatui_core::style::Color::LightRed => ratatui::style::Color::LightRed,
            ratatui_core::style::Color::LightGreen => ratatui::style::Color::LightGreen,
            ratatui_core::style::Color::LightYellow => ratatui::style::Color::LightYellow,
            ratatui_core::style::Color::LightBlue => ratatui::style::Color::LightBlue,
            ratatui_core::style::Color::LightMagenta => ratatui::style::Color::LightMagenta,
            ratatui_core::style::Color::LightCyan => ratatui::style::Color::LightCyan,
            ratatui_core::style::Color::White => ratatui::style::Color::White,
            ratatui_core::style::Color::Rgb(r, g, b) => ratatui::style::Color::Rgb(r, g, b),
            ratatui_core::style::Color::Indexed(i) => ratatui::style::Color::Indexed(i),
        }
    }

    /// Convert ratatui_core::style::Style to ratatui::style::Style
    fn convert_style(s: ratatui_core::style::Style) -> ratatui::style::Style {
        ratatui::style::Style {
            fg: s.fg.map(Self::convert_color),
            bg: s.bg.map(Self::convert_color),
            add_modifier: ratatui::style::Modifier::from_bits_truncate(s.add_modifier.bits()),
            sub_modifier: ratatui::style::Modifier::from_bits_truncate(s.sub_modifier.bits()),
            ..Default::default()
        }
    }

    /// Render markdown source into Lines with prefixes via tui-markdown.
    /// `first_prefix` is used for the first line, `rest_prefix` for subsequent lines.
    fn render_markdown_lines(md_src: &str, first_prefix: &str, rest_prefix: &str) -> Vec<Line<'static>> {
        let md_text = tui_markdown::from_str(md_src);
        md_text.lines.into_iter().enumerate().map(|(i, md_line)| {
            let prefix = if i == 0 { first_prefix } else { rest_prefix };
            let mut spans = vec![Span::raw(prefix.to_string())];
            for s in md_line.spans {
                spans.push(Span::styled(s.content.into_owned(), Self::convert_style(s.style)));
            }
            Line::from(spans)
        }).collect()
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
                        let first = format!("{}{} ", &agent_prefix, &msg.timestamp);
                        let lines = Self::render_markdown_lines(text, &first, &agent_prefix);
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
                        let md_src = format!("```{}\n{}\n```", language, code);
                        let first = format!("{}{} ", tree_prefix, icons.code_block);
                        let rest = format!("{}  ", tree_prefix);
                        let lines = Self::render_markdown_lines(&md_src, &first, &rest);
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
        use ratatui::widgets::Borders;

        let block = ratatui::widgets::Block::new()
            .borders(Borders::TOP | Borders::BOTTOM)
            .border_style(Style::default().fg(self.theme.border));

        // Clone textarea and set block for rendering
        let mut textarea = self.textarea.clone();
        textarea.set_block(block);
        textarea.set_style(Style::default().fg(self.theme.input));

        // tui-textarea handles rendering, cursor positioning, and scrolling
        f.render_widget(&textarea, area);
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
        let msg_count = self.messages.len();
        let spinner = self.spinner_frame();

        // 第一行: [spinner] workspace | transport | N msgs | mode | theme
        let line1 = format!(
            " {} {} | {} | {} msgs | {} | {} ",
            spinner,
            if self.workspace.is_empty() { "no workspace" } else { &self.workspace },
            self.transport_label,
            msg_count,
            mode_str,
            theme_name,
        );

        // 第二行: 操作提示 or quit confirmation
        let line2 = if self.pending_quit {
            format!(
                " {} Press Ctrl+C or Esc again to quit, any other key to cancel ",
                icons.warning,
            )
        } else {
            format!(
                " {} scroll | Tab expand/collapse | Ctrl+R history | Ctrl+P/N history | Ctrl+A/E line | Ctrl+K/U delete | Ctrl+C clear/interrupt | 2x Ctrl+C quit ",
                icons.arrow,
            )
        };

        let text = format!("{}\n{}", line1, line2);

        let status_style = if self.pending_quit {
            Style::default().fg(self.theme.warning)
        } else {
            Style::default().fg(self.theme.status)
        };

        let paragraph = Paragraph::new(text).style(status_style);
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
            overlay_width,
            overlay_height,
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
            overlay_width.saturating_sub(2),
            overlay_height.saturating_sub(2),
        );

        let search_block = Block::default()
            .title(" Search History (Ctrl+R) ")
            .borders(Borders::ALL)
            .border_style(Style::default().fg(self.theme.accent));
        f.render_widget(search_block, box_area);

        // Draw search input (inside box, 2 rows for input)
        let inner_width = box_area.width.saturating_sub(2);
        let input_area = Rect::new(
            box_area.x + 1,
            box_area.y + 1,
            inner_width,
            2,
        );

        let input_text = format!("> {}", self.search_query);
        let input_para = Paragraph::new(input_text)
            .style(Style::default().fg(self.theme.input));
        f.render_widget(input_para, input_area);

        // Draw results list (below input, above hint)
        let results_y = box_area.y + 3;
        let results_height = box_area.height.saturating_sub(5); // 1 border + 2 input + 1 hint + 1 border
        let results_area = Rect::new(
            box_area.x + 1,
            results_y,
            inner_width,
            results_height,
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

        // Draw hint at bottom of box
        let hint_area = Rect::new(
            box_area.x + 1,
            box_area.bottom().saturating_sub(2),
            inner_width,
            1,
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
                    self.pending_quit = false;
                    self.vim_pending_g = false;
                    self.scroll_up();
                    return;
                }
                KeyCode::Char('j') => {
                    self.pending_quit = false;
                    self.vim_pending_g = false;
                    self.scroll_down();
                    return;
                }
                KeyCode::Char('G') => {
                    // Jump to bottom
                    self.pending_quit = false;
                    self.vim_pending_g = false;
                    if !self.messages.is_empty() {
                        let max_offset = self.messages.len().saturating_sub(1);
                        *self.chat_state.offset_mut() = max_offset;
                    }
                    return;
                }
                KeyCode::Char('g') => {
                    self.pending_quit = false;
                    if self.vim_pending_g {
                        // gg: jump to top
                        *self.chat_state.offset_mut() = 0;
                        self.vim_pending_g = false;
                    } else {
                        self.vim_pending_g = true;
                    }
                    return;
                }
                KeyCode::Char('/') => {
                    // Open search (same as Ctrl+R)
                    self.pending_quit = false;
                    self.vim_pending_g = false;
                    self.app_mode = AppMode::Search;
                    self.search_query.clear();
                    self.search_selected = 0;
                    self.search_results = self.search_history("");
                    return;
                }
                KeyCode::Char(':') => {
                    self.pending_quit = false;
                    self.vim_pending_g = false;
                    return;
                }
                KeyCode::Esc => {
                    self.vim_pending_g = false;
                    let has_input = !self.textarea.lines().iter().all(|s| s.is_empty());
                    let is_busy = self.app_state != AppState::Idle && self.app_state != AppState::Offline;
                    if (has_input || is_busy) && !self.pending_quit {
                        self.pending_quit = true;
                    } else {
                        self.quit = true;
                    }
                    return;
                }
                _ => {
                    // Any other key resets vim_pending_g
                    self.vim_pending_g = false;
                }
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
                    let has_input = !self.textarea.lines().iter().all(|s| s.is_empty());
                    let is_busy = self.app_state != AppState::Idle && self.app_state != AppState::Offline;

                    if has_input {
                        // Has input: clear it
                        self.set_textarea_content("");
                        self.pending_quit = false;
                    } else if is_running {
                        // Running: interrupt
                        self.chunk_receiver = None;
                        self.pending_quit = false;
                    } else if is_busy && !self.pending_quit {
                        // Busy but no pending quit yet: set pending
                        self.pending_quit = true;
                    } else if self.pending_quit {
                        // Already pending: quit immediately
                        self.quit = true;
                    } else {
                        // Not running, not busy: check for double-Ctrl+C
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
                    // Submit: get content from textarea and send
                    let msg_content = self.textarea.lines().join("\n");
                    if !msg_content.is_empty() {
                        self.add_to_history(&msg_content);
                        self.messages.push(Message {
                            role: MessageRole::User,
                            content: MessageContent::Text(msg_content),
                            timestamp: chrono::Local::now().format("%H:%M").to_string(),
                            parent_id: None,
                        });
                        // Reset textarea
                        self.set_textarea_content("");
                        self.input_mode = InputMode::SingleLine;
                        self.chat_state.select(Some(self.messages.len().saturating_sub(1)));
                        self.history_index = None;
                    }
                }
                _ => {
                    self.handle_action(&action);
                }
            }
            return;
        }

        // Tab: collapse toggle (not in keymap)
        if key.code == KeyCode::Tab {
            if let Some(selected) = self.chat_state.selected() {
                self.toggle_message_collapse(selected);
            }
            return;
        }

        // Ctrl+P/Ctrl+N for history navigation
        if self.app_mode != AppMode::Search {
            let history_count = self.history_engine.results().len();
            if history_count > 0 {
                if key.modifiers == KeyModifiers::CONTROL && key.code == KeyCode::Char('p') {
                    let new_index = match self.history_index {
                        None => 0,
                        Some(i) if i < history_count - 1 => i + 1,
                        Some(i) => i,
                    };
                    self.history_index = Some(new_index);
                    let idx = history_count - 1 - new_index;
                    if let Some(result) = self.history_engine.results().get(idx) {
                        self.set_textarea_content(&result.content.clone());
                    }
                    return;
                }
                if key.modifiers == KeyModifiers::CONTROL && key.code == KeyCode::Char('n') {
                    if let Some(i) = self.history_index {
                        if i > 0 {
                            let new_index = i - 1;
                            self.history_index = Some(new_index);
                            let idx = history_count - 1 - new_index;
                            if let Some(result) = self.history_engine.results().get(idx) {
                                self.set_textarea_content(&result.content.clone());
                            }
                        } else {
                            self.history_index = None;
                            self.set_textarea_content("");
                        }
                    }
                    return;
                }
            }
        }

        // All other keys: delegate to tui-textarea
        // tui-textarea handles: character input, Ctrl+A/E/B/F/K/D/H/W, arrows,
        // Home/End, Backspace, Delete, word movement, undo/redo, etc.
        self.textarea.input(key);

        // Any non-quit key cancels pending quit confirmation
        self.pending_quit = false;

        // Reset history navigation when user types
        if matches!(key.code, KeyCode::Char(_)) {
            self.history_index = None;
        }
    }
}

// ---------------------------------------------------------------------------
// Test helpers & inline test modules
// ---------------------------------------------------------------------------

#[cfg(test)]
impl App {
    /// Expose process_chunk for tests
    pub(crate) fn test_process_chunk(&mut self, chunk: OutputChunk) {
        self.process_chunk(chunk);
    }

    /// Expose handle_key for tests
    pub(crate) fn test_handle_key(&mut self, key: event::KeyEvent) {
        self.handle_key(key);
    }

    /// Get textarea content as a single string
    pub(crate) fn test_textarea_content(&self) -> String {
        self.textarea.lines().join("\n")
    }

    /// Get current app mode
    pub(crate) fn test_app_mode(&self) -> AppMode {
        self.app_mode
    }

    /// Get current search query
    pub(crate) fn test_search_query(&self) -> &str {
        &self.search_query
    }

    /// Get quit flag
    pub(crate) fn test_quit(&self) -> bool {
        self.quit
    }

    /// Get current app state
    pub(crate) fn test_app_state(&self) -> AppState {
        self.app_state
    }

    /// Get pending quit flag
    pub(crate) fn test_pending_quit(&self) -> bool {
        self.pending_quit
    }

    /// Get vim pending g flag
    pub(crate) fn test_vim_pending_g(&self) -> bool {
        self.vim_pending_g
    }

}

/// Helper: build a KeyEvent with Press kind
#[cfg(test)]
fn key_event(code: KeyCode, modifiers: KeyModifiers) -> event::KeyEvent {
    event::KeyEvent {
        code,
        modifiers,
        kind: KeyEventKind::Press,
        state: event::KeyEventState::empty(),
    }
}

// ── Chunk processing tests ──────────────────────────────────────────────────

#[cfg(test)]
mod tests_chunk {
    use super::*;

    fn app() -> App {
        App::with_config(AppConfig::default()).unwrap()
    }

    #[test]
    fn test_chunk_text_creates_message() {
        let mut app = app();
        app.test_process_chunk(OutputChunk::Text("hello".into()));

        assert_eq!(app.messages.len(), 1);
        assert_eq!(app.messages[0].role, MessageRole::Agent);
        assert!(matches!(&app.messages[0].content, MessageContent::Text(t) if t == "hello"));
    }

    #[test]
    fn test_chunk_text_appends() {
        let mut app = app();
        app.test_process_chunk(OutputChunk::Text("hello".into()));
        app.test_process_chunk(OutputChunk::Text(" world".into()));

        // Should still be a single message with concatenated text
        assert_eq!(app.messages.len(), 1);
        assert!(matches!(&app.messages[0].content, MessageContent::Text(t) if t == "hello world"));
    }

    #[test]
    fn test_chunk_thinking_lifecycle() {
        let mut app = app();
        app.test_process_chunk(OutputChunk::ThinkingStart);
        app.test_process_chunk(OutputChunk::ThinkingText("reasoning...".into()));
        app.test_process_chunk(OutputChunk::ThinkingEnd);

        // ThinkingEnd itself doesn't flush; a subsequent Text or Done does
        app.test_process_chunk(OutputChunk::Text("answer".into()));

        // Should have 2 messages: Thinking + Text
        assert_eq!(app.messages.len(), 2);
        assert!(matches!(&app.messages[0].content, MessageContent::Thinking(t) if t.contains("reasoning")));
        assert!(matches!(&app.messages[1].content, MessageContent::Text(t) if t == "answer"));
    }

    #[test]
    fn test_chunk_tool_lifecycle() {
        let mut app = app();
        app.test_process_chunk(OutputChunk::ToolStart {
            name: "Read".into(),
            args: "{}".into(),
        });

        assert_eq!(app.messages.len(), 1);
        assert!(matches!(
            &app.messages[0].content,
            MessageContent::ToolCall { name, status: ToolStatus::Running } if name == "Read"
        ));

        app.test_process_chunk(OutputChunk::ToolEnd {
            name: "Read".into(),
            success: true,
        });

        // The running message should be updated to Success
        assert_eq!(app.messages.len(), 1);
        assert!(matches!(
            &app.messages[0].content,
            MessageContent::ToolCall { name, status: ToolStatus::Success } if name == "Read"
        ));
    }

    #[test]
    fn test_chunk_tool_failure() {
        let mut app = app();
        app.test_process_chunk(OutputChunk::ToolStart {
            name: "Bash".into(),
            args: "{}".into(),
        });
        app.test_process_chunk(OutputChunk::ToolEnd {
            name: "Bash".into(),
            success: false,
        });

        assert_eq!(app.messages.len(), 1);
        assert!(matches!(
            &app.messages[0].content,
            MessageContent::ToolCall { name, status: ToolStatus::Error } if name == "Bash"
        ));
    }

    #[test]
    fn test_chunk_error() {
        let mut app = app();
        app.test_process_chunk(OutputChunk::Error("something broke".into()));

        assert_eq!(app.messages.len(), 1);
        assert!(matches!(
            &app.messages[0].content,
            MessageContent::Error(e) if e == "something broke"
        ));
    }

    #[test]
    fn test_chunk_done_finalizes() {
        let mut app = app();
        // Start thinking but don't manually end it
        app.test_process_chunk(OutputChunk::ThinkingStart);
        app.test_process_chunk(OutputChunk::ThinkingText("deep thought".into()));
        app.test_process_chunk(OutputChunk::Done);

        // Done should have finalized the pending thinking
        assert_eq!(app.messages.len(), 1);
        assert!(matches!(&app.messages[0].content, MessageContent::Thinking(_)));
    }

    #[test]
    fn test_chunk_mixed_sequence() {
        let mut app = app();

        // Full cycle 0 sequence: thinking → text → done
        app.test_process_chunk(OutputChunk::ThinkingStart);
        app.test_process_chunk(OutputChunk::ThinkingText("analyzing…".into()));
        app.test_process_chunk(OutputChunk::ThinkingEnd);
        app.test_process_chunk(OutputChunk::Text("Here is the answer.".into()));
        app.test_process_chunk(OutputChunk::Done);

        assert_eq!(app.messages.len(), 2);
        assert!(matches!(&app.messages[0].content, MessageContent::Thinking(_)));
        assert!(matches!(&app.messages[1].content, MessageContent::Text(t) if t == "Here is the answer."));
    }
}

// ── Key handling tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod tests_keys {
    use super::*;

    fn app() -> App {
        App::with_config(AppConfig::default()).unwrap()
    }

    #[test]
    fn test_key_ctrl_c_clears_input() {
        let mut app = app();
        // Type something first
        app.test_handle_key(key_event(KeyCode::Char('h'), KeyModifiers::NONE));
        app.test_handle_key(key_event(KeyCode::Char('i'), KeyModifiers::NONE));
        assert!(!app.test_textarea_content().is_empty());

        // Ctrl+C should clear input
        app.test_handle_key(key_event(KeyCode::Char('c'), KeyModifiers::CONTROL));
        assert!(app.test_textarea_content().is_empty());
    }

    #[test]
    fn test_key_double_ctrl_c_quits() {
        let mut app = app();
        // Ensure textarea is empty so Ctrl+C enters "double-press" path
        assert!(app.test_textarea_content().is_empty());

        // First Ctrl+C — sets last_ctrl_c_time
        app.test_handle_key(key_event(KeyCode::Char('c'), KeyModifiers::CONTROL));
        assert!(!app.test_quit());

        // Second Ctrl+C within 2 seconds — should quit
        app.test_handle_key(key_event(KeyCode::Char('c'), KeyModifiers::CONTROL));
        assert!(app.test_quit());
    }

    #[test]
    fn test_key_ctrl_r_opens_search() {
        let mut app = app();
        assert_eq!(app.test_app_mode(), AppMode::Normal);

        app.test_handle_key(key_event(KeyCode::Char('r'), KeyModifiers::CONTROL));
        assert_eq!(app.test_app_mode(), AppMode::Search);
    }

    #[test]
    fn test_key_esc_exits_search() {
        let mut app = app();
        // Enter search mode first
        app.test_handle_key(key_event(KeyCode::Char('r'), KeyModifiers::CONTROL));
        assert_eq!(app.test_app_mode(), AppMode::Search);

        // Esc should exit search
        app.test_handle_key(key_event(KeyCode::Esc, KeyModifiers::NONE));
        assert_eq!(app.test_app_mode(), AppMode::Normal);
    }

    #[test]
    fn test_key_search_typing() {
        let mut app = app();
        // Enter search mode
        app.test_handle_key(key_event(KeyCode::Char('r'), KeyModifiers::CONTROL));

        // Type in search
        app.test_handle_key(key_event(KeyCode::Char('h'), KeyModifiers::NONE));
        app.test_handle_key(key_event(KeyCode::Char('i'), KeyModifiers::NONE));

        assert_eq!(app.test_search_query(), "hi");
    }

    #[test]
    fn test_key_vim_k_scrolls() {
        let mut app = app();
        app.set_key_mode(KeyMode::Vim);

        // Add some messages for scrolling
        for i in 0..5 {
            app.messages.push(Message {
                role: MessageRole::Agent,
                content: MessageContent::Text(format!("msg {}", i)),
                timestamp: "00:00".into(),
                parent_id: None,
            });
        }

        // Scroll down first so we can scroll up
        *app.chat_state.offset_mut() = 3;

        let offset_before = app.chat_state.offset();
        app.test_handle_key(key_event(KeyCode::Char('k'), KeyModifiers::NONE));
        assert!(app.chat_state.offset() < offset_before);
    }

    #[test]
    fn test_key_vim_j_scrolls() {
        let mut app = app();
        app.set_key_mode(KeyMode::Vim);

        // Add messages
        for i in 0..5 {
            app.messages.push(Message {
                role: MessageRole::Agent,
                content: MessageContent::Text(format!("msg {}", i)),
                timestamp: "00:00".into(),
                parent_id: None,
            });
        }

        let offset_before = app.chat_state.offset();
        app.test_handle_key(key_event(KeyCode::Char('j'), KeyModifiers::NONE));
        assert!(app.chat_state.offset() > offset_before);
    }

    #[test]
    fn test_key_page_up_down() {
        let mut app = app();

        // Add messages to enable scrolling
        for i in 0..20 {
            app.messages.push(Message {
                role: MessageRole::Agent,
                content: MessageContent::Text(format!("msg {}", i)),
                timestamp: "00:00".into(),
                parent_id: None,
            });
        }

        // PageDown should increase offset
        app.test_handle_key(key_event(KeyCode::PageDown, KeyModifiers::NONE));
        assert!(app.chat_state.offset() > 0);

        let offset_after_down = app.chat_state.offset();

        // PageUp should decrease offset
        app.test_handle_key(key_event(KeyCode::PageUp, KeyModifiers::NONE));
        assert!(app.chat_state.offset() < offset_after_down);
    }

    #[test]
    fn test_key_ctrl_p_history() {
        let mut app = app();

        // Add history entries
        app.add_to_history("first command");
        app.add_to_history("second command");

        // Ctrl+P should navigate to most recent history
        app.test_handle_key(key_event(KeyCode::Char('p'), KeyModifiers::CONTROL));
        assert_eq!(app.test_textarea_content(), "second command");

        // Another Ctrl+P should go to older entry
        app.test_handle_key(key_event(KeyCode::Char('p'), KeyModifiers::CONTROL));
        assert_eq!(app.test_textarea_content(), "first command");
    }

    #[test]
    fn test_key_submit() {
        let mut app = app();

        // Type a message
        app.test_handle_key(key_event(KeyCode::Char('h'), KeyModifiers::NONE));
        app.test_handle_key(key_event(KeyCode::Char('i'), KeyModifiers::NONE));
        assert_eq!(app.test_textarea_content(), "hi");

        // Press Enter to submit
        app.test_handle_key(key_event(KeyCode::Enter, KeyModifiers::NONE));

        // Message should appear in messages list
        assert_eq!(app.messages.len(), 1);
        assert_eq!(app.messages[0].role, MessageRole::User);
        assert!(matches!(&app.messages[0].content, MessageContent::Text(t) if t == "hi"));

        // Textarea should be cleared
        assert!(app.test_textarea_content().is_empty());
    }
}

// ── Search tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests_search {
    use super::*;

    fn app_with_history() -> App {
        let mut app = App::with_config(AppConfig::default()).unwrap();
        app.add_to_history("git status");
        app.add_to_history("git diff");
        app.add_to_history("cargo test");
        app.add_to_history("cargo build");
        app.add_to_history("ls -la");
        app
    }

    #[test]
    fn test_search_empty_returns_all() {
        let app = app_with_history();
        let results = app.search_history("");
        assert_eq!(results.len(), 5);
    }

    #[test]
    fn test_search_filters() {
        let app = app_with_history();
        let results = app.search_history("git");
        assert_eq!(results.len(), 2);
        assert!(results.iter().all(|r| r.contains("git")));
    }

    #[test]
    fn test_search_case_insensitive() {
        let app = app_with_history();
        let results = app.search_history("GIT");
        assert_eq!(results.len(), 2);
    }

    #[test]
    fn test_search_no_match() {
        let app = app_with_history();
        let results = app.search_history("python");
        assert!(results.is_empty());
    }

    #[test]
    fn test_search_partial_match() {
        let app = app_with_history();
        let results = app.search_history("cargo");
        assert_eq!(results.len(), 2);
        assert!(results.iter().any(|r| r.contains("test")));
        assert!(results.iter().any(|r| r.contains("build")));
    }
}

// ── Theme tests ─────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests_theme {
    use super::*;
    use crate::theme::{all_theme_names, Theme, ThemeName};

    #[test]
    fn test_theme_default() {
        let app = App::with_config(AppConfig::default()).unwrap();
        assert_eq!(app.theme.name, ThemeName::CatppuccinMocha);
    }

    #[test]
    fn test_theme_config() {
        let config = AppConfig::default().with_theme(ThemeName::TokyoNight);
        let app = App::with_config(config).unwrap();
        assert_eq!(app.theme.name, ThemeName::TokyoNight);
    }

    #[test]
    fn test_all_themes_valid() {
        for name in all_theme_names() {
            // Should not panic
            let _theme = Theme::from_name(name);
            let config = AppConfig::default().with_theme(name);
            let _app = App::with_config(config).unwrap();
        }
    }
}

// ── AppState tests ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests_app_state {
    use super::*;

    fn app() -> App {
        App::with_config(AppConfig::default()).unwrap()
    }

    #[test]
    fn test_app_state_default_idle() {
        let app = app();
        assert_eq!(app.test_app_state(), AppState::Idle);
    }

    #[test]
    fn test_app_state_thinking() {
        let mut app = app();
        app.test_process_chunk(OutputChunk::ThinkingStart);
        assert_eq!(app.test_app_state(), AppState::Thinking);
    }

    #[test]
    fn test_app_state_streaming() {
        let mut app = app();
        app.test_process_chunk(OutputChunk::Text("hello".into()));
        assert_eq!(app.test_app_state(), AppState::Streaming);
    }

    #[test]
    fn test_app_state_tool() {
        let mut app = app();
        app.test_process_chunk(OutputChunk::ToolStart {
            name: "Read".into(),
            args: "{}".into(),
        });
        assert_eq!(app.test_app_state(), AppState::ToolRunning);
    }

    #[test]
    fn test_app_state_done_resets() {
        let mut app = app();
        app.test_process_chunk(OutputChunk::ThinkingStart);
        assert_eq!(app.test_app_state(), AppState::Thinking);
        app.test_process_chunk(OutputChunk::Done);
        assert_eq!(app.test_app_state(), AppState::Idle);
    }

    #[test]
    fn test_app_state_error_resets() {
        let mut app = app();
        app.test_process_chunk(OutputChunk::Text("streaming".into()));
        assert_eq!(app.test_app_state(), AppState::Streaming);
        app.test_process_chunk(OutputChunk::Error("fail".into()));
        assert_eq!(app.test_app_state(), AppState::Idle);
    }
}

// ── Quit confirmation tests ─────────────────────────────────────────────────

#[cfg(test)]
mod tests_quit_confirm {
    use super::*;

    fn app() -> App {
        App::with_config(AppConfig::default()).unwrap()
    }

    #[test]
    fn test_quit_confirm_with_input() {
        let mut app = app();
        // Type something to have non-empty input
        app.test_handle_key(key_event(KeyCode::Char('x'), KeyModifiers::NONE));
        assert!(!app.test_textarea_content().is_empty());

        // Ctrl+C should clear input, not set pending_quit
        app.test_handle_key(key_event(KeyCode::Char('c'), KeyModifiers::CONTROL));
        assert!(app.test_textarea_content().is_empty());
        assert!(!app.test_pending_quit());
        assert!(!app.test_quit());
    }

    #[test]
    fn test_quit_confirm_cancel() {
        let mut app = app();
        // Put app in busy state
        app.test_process_chunk(OutputChunk::ThinkingStart);
        assert_eq!(app.test_app_state(), AppState::Thinking);

        // First Ctrl+C sets pending
        app.test_handle_key(key_event(KeyCode::Char('c'), KeyModifiers::CONTROL));
        assert!(app.test_pending_quit());
        assert!(!app.test_quit());

        // Any other key cancels pending
        app.test_handle_key(key_event(KeyCode::Char('a'), KeyModifiers::NONE));
        assert!(!app.test_pending_quit());
        assert!(!app.test_quit());
    }

    #[test]
    fn test_quit_direct_when_idle() {
        let mut app = app();
        // Idle, no input: double Ctrl+C quits directly
        assert_eq!(app.test_app_state(), AppState::Idle);
        assert!(app.test_textarea_content().is_empty());

        app.test_handle_key(key_event(KeyCode::Char('c'), KeyModifiers::CONTROL));
        assert!(!app.test_quit());

        app.test_handle_key(key_event(KeyCode::Char('c'), KeyModifiers::CONTROL));
        assert!(app.test_quit());
    }

    #[test]
    fn test_quit_confirm_busy_double_ctrl_c() {
        let mut app = app();
        // Put app in busy state
        app.test_process_chunk(OutputChunk::ThinkingStart);

        // First Ctrl+C sets pending
        app.test_handle_key(key_event(KeyCode::Char('c'), KeyModifiers::CONTROL));
        assert!(app.test_pending_quit());

        // Second Ctrl+C while pending → quit
        app.test_handle_key(key_event(KeyCode::Char('c'), KeyModifiers::CONTROL));
        assert!(app.test_quit());
    }
}

// ── Vim mode enhancement tests ──────────────────────────────────────────────

#[cfg(test)]
mod tests_vim_enhanced {
    use super::*;

    fn vim_app() -> App {
        let mut app = App::with_config(AppConfig::default()).unwrap();
        app.set_key_mode(KeyMode::Vim);
        // Add messages for scrolling tests
        for i in 0..10 {
            app.messages.push(Message {
                role: MessageRole::Agent,
                content: MessageContent::Text(format!("msg {}", i)),
                timestamp: "00:00".into(),
                parent_id: None,
            });
        }
        app
    }

    #[test]
    fn test_vim_g_bottom() {
        let mut app = vim_app();
        // Start at top
        *app.chat_state.offset_mut() = 0;

        // G should jump to bottom
        app.test_handle_key(key_event(KeyCode::Char('G'), KeyModifiers::SHIFT));
        assert_eq!(app.chat_state.offset(), 9); // 10 messages, max offset = 9
    }

    #[test]
    fn test_vim_gg_top() {
        let mut app = vim_app();
        // Start at bottom
        *app.chat_state.offset_mut() = 9;

        // gg should jump to top
        app.test_handle_key(key_event(KeyCode::Char('g'), KeyModifiers::NONE));
        assert!(app.test_vim_pending_g());

        app.test_handle_key(key_event(KeyCode::Char('g'), KeyModifiers::NONE));
        assert!(!app.test_vim_pending_g());
        assert_eq!(app.chat_state.offset(), 0);
    }

    #[test]
    fn test_vim_slash_search() {
        let mut app = vim_app();
        assert_eq!(app.test_app_mode(), AppMode::Normal);

        // / should open search
        app.test_handle_key(key_event(KeyCode::Char('/'), KeyModifiers::NONE));
        assert_eq!(app.test_app_mode(), AppMode::Search);
    }

    #[test]
    fn test_vim_g_reset() {
        let mut app = vim_app();

        // Press g once
        app.test_handle_key(key_event(KeyCode::Char('g'), KeyModifiers::NONE));
        assert!(app.test_vim_pending_g());

        // Press a different key - should reset
        app.test_handle_key(key_event(KeyCode::Char('j'), KeyModifiers::NONE));
        assert!(!app.test_vim_pending_g());
    }
}
