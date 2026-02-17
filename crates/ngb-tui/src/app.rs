//! Application state and main event loop

use anyhow::Result;
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout, Rect},
    Frame,
};
use std::io;
use std::time::Duration;

use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEventKind},
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
}

pub struct Message {
    pub role: MessageRole,
    pub content: String,
    pub timestamp: String,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum MessageRole {
    User,
    Agent,
}

impl App {
    pub fn new() -> Result<Self> {
        Ok(Self {
            quit: false,
            workspace: String::new(),
            messages: Vec::new(),
            input: String::new(),
            scroll: 0,
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

    fn run_loop(&mut self, terminal: &mut ratatui::Terminal<CrosstermBackend<io::Stdout>>) -> Result<()> {
        loop {
            terminal.draw(|f| self.draw(f))?;

            if event::poll(Duration::from_millis(250))? {
                if let Event::Key(key) = event::read()? {
                    self.handle_key(key);
                }
            }

            if self.quit {
                break;
            }
        }
        Ok(())
    }

    fn draw(&self, f: &mut Frame) {
        let area = f.area();

        // Define layout: Header(3) + Chat(*) + Input(3) + Status(1)
        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Length(3),  // Header
                Constraint::Min(0),      // Chat
                Constraint::Length(3),  // Input
                Constraint::Length(1),  // Status
            ])
            .split(area);

        self.draw_header(f, chunks[0]);
        self.draw_chat(f, chunks[1]);
        self.draw_input(f, chunks[2]);
        self.draw_status(f, chunks[3]);
    }

    fn draw_header(&self, f: &mut Frame, area: Rect) {
        use ratatui::widgets::{Block, Borders, Paragraph};
        use ratatui::style::Style;

        let text = format!(" NGB Shell ◆ workspace: {} ", self.workspace);
        let block = Block::new()
            .borders(Borders::ALL)
            .title("NanoGridBot")
            .title_style(Style::default().fg(ratatui::style::Color::Cyan));

        let paragraph = Paragraph::new(text).block(block);
        f.render_widget(paragraph, area);
    }

    fn draw_chat(&self, f: &mut Frame, area: Rect) {
        use ratatui::widgets::{Block, Borders, Paragraph};

        let block = Block::new()
            .borders(Borders::ALL)
            .border_style(ratatui::style::Style::default().fg(
                ratatui::style::Color::DarkGray,
            ));

        // Simple placeholder for now
        let content = if self.messages.is_empty() {
            "  Start chatting with Claude Code...\n\n  Press Enter to send message, Ctrl+C to quit."
        } else {
            "  Chat messages will appear here..."
        };

        let paragraph = Paragraph::new(content).block(block);
        f.render_widget(paragraph, area);
    }

    fn draw_input(&self, f: &mut Frame, area: Rect) {
        use ratatui::widgets::{Block, Borders, Paragraph};

        let block = Block::new()
            .borders(Borders::ALL)
            .title(" Input ");

        let text = if self.input.is_empty() {
            " Type a message..."
        } else {
            self.input.as_str()
        };

        let paragraph = Paragraph::new(text)
            .block(block)
            .wrap(ratatui::widgets::Wrap { trim: true });
        f.render_widget(paragraph, area);
    }

    fn draw_status(&self, f: &mut Frame, area: Rect) {
        use ratatui::widgets::{Paragraph};

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

        match key.code {
            KeyCode::Char('q') if key.modifiers.contains(event::KeyModifiers::CONTROL) => {
                self.quit = true;
            }
            KeyCode::Char('c') if key.modifiers.contains(event::KeyModifiers::CONTROL) => {
                self.quit = true;
            }
            KeyCode::Char(c) => {
                self.input.push(c);
            }
            KeyCode::Backspace => {
                self.input.pop();
            }
            KeyCode::Enter => {
                if !self.input.is_empty() {
                    // Send message
                    let msg = std::mem::take(&mut self.input);
                    self.messages.push(Message {
                        role: MessageRole::User,
                        content: msg,
                        timestamp: chrono::Local::now().format("%H:%M").to_string(),
                    });
                }
            }
            _ => {}
        }
    }
}
