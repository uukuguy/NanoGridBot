//! Application state and main event loop

use anyhow::Result;
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

pub struct App {
    /// Whether to quit the application
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
    pub fn new() -> Result<Self> {
        let mut chat_state = ListState::default();
        chat_state.select(Some(0));
        Ok(Self {
            quit: false,
            workspace: String::new(),
            messages: Vec::new(),
            input: String::new(),
            scroll: 0,
            chat_state,
            cursor_position: 0,
            input_mode: InputMode::SingleLine,
        })
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
            .title_style(Style::default().fg(ratatui::style::Color::Cyan));

        let paragraph = Paragraph::new(text).block(block);
        f.render_widget(paragraph, area);
    }

    fn draw_chat(&mut self, f: &mut Frame, area: Rect) {
        use ratatui::style::{Color, Style, Stylize};
        use ratatui::widgets::{Block, Borders};

        let block = Block::new()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray));

        // Build message items - collect messages first to avoid borrow issues
        let messages = self.messages.clone();
        let items: Vec<ListItem> = if messages.is_empty() {
            vec![ListItem::new(
                "  Start chatting with Claude Code...\n\n  Press Enter to send message, Ctrl+C to quit.",
            )
            .style(Style::default().dim())]
        } else {
            messages
                .iter()
                .map(|msg| Self::render_message_item_static(msg))
                .collect()
        };

        let list = List::new(items)
            .block(block)
            .style(Style::default().fg(Color::White));

        f.render_stateful_widget(list, area, &mut self.chat_state);
    }

    fn render_message_item_static(msg: &Message) -> ListItem<'_> {
        use ratatui::style::Style;

        match msg.role {
            MessageRole::User => {
                // User message: cyan colored
                let content = match &msg.content {
                    MessageContent::Text(text) => format!("{}  {}", text, msg.timestamp),
                    _ => msg.timestamp.clone(),
                };
                ListItem::new(content)
                    .style(Style::default().fg(ratatui::style::Color::Cyan).italic())
            }
            MessageRole::Agent => {
                // Agent message: green colored with prefix
                let prefix = format!("◆ Agent  {}", msg.timestamp);
                match &msg.content {
                    MessageContent::Text(text) => ListItem::new(format!("{}\n{}", prefix, text))
                        .style(Style::default().fg(ratatui::style::Color::LightGreen)),
                    MessageContent::Thinking(text) => {
                        ListItem::new(format!("{} ▸ Thinking... {}", prefix, text))
                            .style(Style::default().fg(ratatui::style::Color::Yellow))
                    }
                    MessageContent::ToolCall { name, status } => {
                        let status_icon = match status {
                            ToolStatus::Running => " ⠙",
                            ToolStatus::Success => " ✓",
                            ToolStatus::Error => " ✗",
                        };
                        let color = match status {
                            ToolStatus::Running => ratatui::style::Color::Yellow,
                            ToolStatus::Success => ratatui::style::Color::Green,
                            ToolStatus::Error => ratatui::style::Color::Red,
                        };
                        ListItem::new(format!("{} → {} {}", prefix, name, status_icon))
                            .style(Style::default().fg(color))
                    }
                    MessageContent::CodeBlock { language, code } => {
                        ListItem::new(format!("{}\n  ┌─ {} ──\n{}\n  └─", prefix, language, code))
                            .style(Style::default().fg(ratatui::style::Color::LightYellow))
                    }
                    MessageContent::Error(err) => {
                        ListItem::new(format!("{} ✗ Error: {}", prefix, err))
                            .style(Style::default().fg(ratatui::style::Color::Red))
                    }
                }
            }
        }
    }

    fn draw_input(&self, f: &mut Frame, area: Rect) {
        use ratatui::widgets::{Block, Borders};

        let block = Block::new()
            .borders(Borders::ALL)
            .title(match self.input_mode {
                InputMode::SingleLine => " Input ",
                InputMode::MultiLine => " Input (Shift+Enter for newline) ",
            });

        let text = if self.input.is_empty() {
            " Type a message..."
        } else {
            self.input.as_str()
        };

        let paragraph = ratatui::widgets::Paragraph::new(text)
            .block(block)
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
        use ratatui::widgets::Paragraph;

        let text = format!(
            " {} | pipe | ↑↓ scroll | Ctrl+C quit ",
            if self.workspace.is_empty() {
                "no workspace"
            } else {
                &self.workspace
            }
        );

        let paragraph = Paragraph::new(text)
            .style(ratatui::style::Style::default().fg(ratatui::style::Color::DarkGray));
        f.render_widget(paragraph, area);
    }

    fn handle_key(&mut self, key: event::KeyEvent) {
        if key.kind != KeyEventKind::Press {
            return;
        }

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
