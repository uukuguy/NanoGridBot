# NGB Shell TUI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建 NGB Shell TUI 交互界面 — 开发者在终端直接跟 workspace 里的 Claude Code 对话，类 Claude Code CLI 体验。

**Architecture:**
- 新建 `ngb-tui` crate，独立于 `ngb-cli`
- 三层架构：Transport（通信）→ App（状态机）→ UI（渲染）
- 三种通信方式可切换：Pipe（管道）、IPC（文件轮询）、WS（WebSocket）
- 渐进式交付：先核心对话，后续扩展主题/多面板

**Tech Stack:** ratatui + crossterm + tokio + syntect + pulldown-cmark

---

## 第一部分：设计文档

### 1.1 整体布局

```
┌─────────────────────────────────────────────────────┐
│  NGB Shell ◆ workspace: my-agent  ◇ pipe  ◇ 00:12  │  ← Header Bar
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────────────────────────┐                │
│  │ You                        14:03│                │  ← 用户消息（右对齐气泡）
│  │ 帮我检查 API 接口               │                │
│  └─────────────────────────────────┘                │
│                                                     │
│  ◆ Agent                                    14:03   │  ← Agent 回复（左对齐流式）
│  ▸ Thinking...                              ⌄       │  ← Thinking 折叠区
│  → Reading src/api/handler.rs...            ✓       │  ← 工具调用状态
│                                                     │
│  我检查了 `handler.rs`，发现以下问题：               │
│  ┌─ rust ──────────────────────────────────┐        │
│  │ 1 │ fn handle_request(req: Request) {   │        │  ← 语法高亮代码块
│  │ 2 │     // missing error handling       │        │
│  │ 3 │ }                                   │        │
│  └─────────────────────────────────────────┘        │
│                                                     │
├─────────────────────────────────────────────────────┤
│  ▎ 输入消息... (/ 命令)              Ctrl+? 帮助    │  ← 输入区
├─────────────────────────────────────────────────────┤
│  ◆ my-agent │ pipe │ session: abc123 │ ↑↓ scroll    │  ← Status Bar
└─────────────────────────────────────────────────────┘
```

**四个区域**：
- **Header Bar** — workspace 名、通信模式、会话时长
- **Chat Area** — 对话内容，支持滚动，混合模式渲染
- **Input Area** — 多行输入框，支持 `/` 命令补全
- **Status Bar** — workspace、通信模式、session ID、快捷键提示

### 1.2 通信层抽象

三种通信方式统一为一个 trait，运行时切换：

```rust
#[async_trait]
trait Transport: Send + Sync {
    async fn send(&self, msg: &str) -> Result<()>;
    fn recv_stream(&self) -> Pin<Box<dyn Stream<Item = OutputChunk>>>;
    async fn interrupt(&self) -> Result<()>;
    async fn close(&self) -> Result<()>;
}

enum OutputChunk {
    Text(String),
    ToolStart(String),
    ToolEnd(String, bool),
    ThinkingStart,
    ThinkingText(String),
    ThinkingEnd,
    Done,
    Error(String),
}
```

| Transport | 启动方式 | 延迟 | 适用场景 |
|-----------|---------|------|---------|
| `PipeTransport` | `docker run -i` pipe stdin/stdout | 实时 | `ngb shell`（默认） |
| `IpcTransport` | 复用 ipc_handler 文件轮询 | ~500ms | 兼容 serve 模式 |
| `WsTransport` | 容器内起 WebSocket server | 实时 | 远程/多客户端 |

CLI 选择方式：
```bash
ngb shell my-agent                    # 默认 pipe
ngb shell my-agent --transport ipc
ngb shell my-agent --transport ws
```

### 1.3 消息渲染规则

**混合模式**：
- 用户消息 → 精致气泡（`╭╮╰╯│` 圆角边框，右对齐）
- Agent 回复 → 前缀流式（`◆ Agent` + 时间戳，左对齐）

**CC 输出组件**：

| 组件 | 说明 |
|------|------|
| `ChatBubble` | 用户消息气泡，右对齐 |
| `AgentPrefix` | `◆ Agent` 前缀 + 时间戳 |
| `ThinkingBlock` | `▸ Thinking (2.1s)` 可折叠 |
| `ToolStatus` | `→ action... ✓/✗` |
| `CodeBlock` | 圆角边框 + 语言标签 + 行号 + syntect 高亮 |
| `StreamingCursor` | agent 输出时末尾 `▌` 闪烁 |

**图标选择**（精致现代 Unicode）：
```
◆ Agent 标识（实心菱形）
▸ 折叠箭头（收起）
▾ 折叠箭头（展开）
→ 工具调用
✓ 成功（绿色）
✗ 失败（红色）
▌ streaming 光标
⌄ 可展开提示
```

### 1.4 主题系统

**预置主题（8 个）**：
```
├── catppuccin-mocha    (默认) 柔和粉彩、深色
├── catppuccin-latte            柔和粉彩、浅色
├── kanagawa                    浮世绘风格、靛蓝/金
├── rose-pine                   柔和深色
├── rose-pine-dawn              柔和浅色
├── tokyo-night (obsidian)      经典深蓝
├── midnight                    纯黑高对比
└── terminal                   跟随终端 16 色
```

**Catppuccin Mocha 配色**：
```
背景:     #1e1e2e
前景:     #cdd6f4
强调:     #89b4fa (蓝)
成功:     #a6e3a1 (绿)
警告:     #f9e2af (琥珀)
错误:     #f38ba8 (玫红)
次要:     #6c7086 (灰)
气泡框:   #45475a
代码背:   #181825
```

### 1.5 输入系统

**内置命令**：
```
/help           显示帮助
/status         当前 workspace 状态
/clear          清屏
/theme <name>   切换主题
/transport <t>  切换通信模式
/session        显示/切换会话
/export         导出对话为 Markdown
/quit           退出
```

**快捷键（双模式）**：

| 操作 | Emacs | Vim |
|------|-------|-----|
| 发送 | Enter | Enter |
| 换行 | Shift+Enter | Shift+Enter |
| 中断 | Ctrl+C | Ctrl+C |
| 清屏 | Ctrl+L | :clear |
| 退出 | Ctrl+D | :q / Esc |
| 滚动上 | Ctrl+U / PageUp | k / Ctrl+U |
| 滚动下 | Ctrl+D / PageDown | j / Ctrl+D |
| 折叠/展开 | Tab | Tab |

### 1.6 Streaming 状态机

```
Idle → ThinkingStart → Thinking → ThinkingEnd → ToolCalls → Streaming → Done → Idle
```

- Thinking: braille spinner `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` 每 80ms 旋转
- 工具调用: 依次追加 `→ action ⠙` → `→ action ✓`
- 文本: 实时追加，末尾 `▌` 闪烁

---

## 第二部分：实施计划

### Phase 1: 骨架 + 管道通信

#### Task 1.1: 创建 ngb-tui crate 骨架

**Files:**
- Create: `crates/ngb-tui/Cargo.toml`
- Create: `crates/ngb-tui/src/lib.rs`
- Create: `crates/ngb-tui/src/app.rs`
- Modify: `Cargo.toml` (添加成员)
- Modify: `crates/ngb-cli/Cargo.toml` (添加依赖)

**Step 1: Create Cargo.toml**

```toml
[package]
name = "ngb-tui"
version.workspace = true
edition.workspace = true

[dependencies]
ngb-types = { workspace = true }
ngb-config = { workspace = true }
ngb-db = { workspace = true }
ngb-core = { workspace = true }
tokio = { workspace = true }
tracing = { workspace = true }
ratatui = "0.28"
crossterm = "0.28"
anyhow = "1"
thiserror = "2"

[dev-dependencies]
tempfile = "3"
```

**Step 2: Add to workspace**

Run: `echo '    "crates/ngb-tui",' | head -c 50`
Expected: Add to members array in root Cargo.toml

**Step 3: Write minimal lib.rs**

```rust
pub async fn run_shell() -> anyhow::Result<()> {
    Ok(())
}
```

**Step 4: Verify build**

Run: `cargo build -p ngb-tui`
Expected: SUCCESS

---

#### Task 1.2: 实现 Transport trait + PipeTransport

**Files:**
- Create: `crates/ngb-tui/src/transport/mod.rs`
- Create: `crates/ngb-tui/src/transport/pipe.rs`
- Create: `crates/ngb-tui/src/transport/output.rs`

**Step 1: Write OutputChunk enum**

```rust
// crates/ngb-tui/src/transport/output.rs
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum OutputChunk {
    Text(String),
    ToolStart { name: String, args: String },
    ToolEnd { name: String, success: bool },
    ThinkingStart,
    ThinkingText(String),
    ThinkingEnd,
    Done,
    Error(String),
}
```

**Step 2: Write Transport trait**

```rust
// crates/ngb-tui/src/transport/mod.rs
use async_trait::async_trait;
use futures::Stream;
use std::pin::Pin;

pub mod output;
pub mod pipe;

pub use output::OutputChunk;

#[async_trait]
pub trait Transport: Send + Sync + 'static {
    async fn send(&self, msg: &str) -> anyhow::Result<()>;
    fn recv_stream(&self) -> Pin<Box<dyn Stream<Item = OutputChunk> + Send>>;
    async fn interrupt(&self) -> anyhow::Result<()>;
    async fn close(&self) -> anyhow::Result<()>;
}

pub type TransportKind = &'static str;
```

**Step 3: Implement PipeTransport**

```rust
// crates/ngb-tui/src/transport/pipe.rs
use super::{OutputChunk, Transport};
use async_trait::async_trait;
use futures::stream::{self, StreamExt};
use std::pin::Pin;
use tokio::process::Command;
use tokio::io::{AsyncBufReadExt, BufReader};

pub struct PipeTransport {
    child: tokio::process::Child,
    reader: Option<BufReader<tokio::process::ChildStdout>>,
}

impl PipeTransport {
    pub async fn new(workspace_id: &str, image: &str) -> anyhow::Result<Self> {
        let mut child = Command::new("docker")
            .args([
                "run", "-i", "--rm",
                "--network", "host",
                "-e", &format!("WORKSPACE={}", workspace_id),
                image,
            ])
            .stdout(std::process::Stdio::piped())
            .stdin(std::process::Stdio::piped())
            .stderr(std::process::Stdio::null())
            .spawn()?;

        let reader = BufReader::new(child.stdout.take().unwrap());

        Ok(Self { child, reader: Some(reader) })
    }
}

#[async_trait]
impl Transport for PipeTransport {
    async fn send(&self, msg: &str) -> anyhow::Result<()> {
        // Implementation: write to stdin
        Ok(())
    }

    fn recv_stream(&self) -> Pin<Box<dyn Stream<Item = OutputChunk> + Send>> {
        // Implementation: parse stdout into OutputChunk stream
        Box::pin(stream::iter(vec![OutputChunk::Done]))
    }

    async fn interrupt(&self) -> anyhow::Result<()> {
        self.child.kill().await?;
        Ok(())
    }

    async fn close(&self) -> anyhow::Result<()> {
        self.child.wait().await?;
        Ok(())
    }
}
```

**Step 4: Add dependencies**

Run: `cargo add -p ngb-tui async-trait futures tokio --features tokio/process`
Expected: Dependencies added

**Step 5: Verify build**

Run: `cargo build -p ngb-tui`
Expected: SUCCESS

---

#### Task 1.3: 基础 TUI 框架（ratatui 初始化）

**Files:**
- Modify: `crates/ngb-tui/src/app.rs`
- Modify: `crates/ngb-tui/src/lib.rs`

**Step 1: Write App struct**

```rust
// crates/ngb-tui/src/app.rs
use ratatui::{Frame, Terminal, TerminalOptions, backend::CrosstermBackend};
use std::io;
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyEventKind},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};

pub struct App {
    pub quit: bool,
}

impl App {
    pub fn new() -> Self {
        Self { quit: false }
    }

    pub fn run(&mut self) -> anyhow::Result<()> {
        // Setup terminal
        enable_raw_mode()?;
        let mut stdout = io::stdout();
        execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
        let backend = CrosstermBackend::new(stdout);
        let mut terminal = Terminal::new(backend)?;

        // Main loop
        while !self.quit {
            terminal.draw(|f| self.draw(f))?;
            if let Event::Key(key) = event::read()? {
                self.handle_key(key);
            }
        }

        // Cleanup
        disable_raw_mode()?;
        execute!(terminal.backend(), LeaveAlternateScreen, DisableMouseCapture)?;
        Ok(())
    }

    fn draw(&self, f: &mut Frame) {
        use ratatui::widgets::Paragraph;
        let area = f.area();
        let text = "NGB Shell - Press 'q' to quit";
        f.render_widget(Paragraph::new(text), area);
    }

    fn handle_key(&mut self, key: event::KeyEvent) {
        if key.kind == KeyEventKind::Press {
            match key.code {
                KeyCode::Char('q') => self.quit = true,
                _ => {}
            }
        }
    }
}
```

**Step 2: Update lib.rs**

```rust
pub mod transport;
pub mod app;

pub use app::App;

pub async fn run_shell() -> anyhow::Result<()> {
    let mut app = App::new();
    app.run()
}
```

**Step 3: Verify build**

Run: `cargo build -p ngb-tui`
Expected: SUCCESS

---

### Phase 2: 渲染增强

#### Task 2.1: 四区域布局

**Step 1: Define layout areas**

```rust
// In app.rs
use ratatui::layout::{Constraint, Direction, Layout, Rect};

fn calculate_layout(area: Rect) -> Vec<Rect> {
    Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3),  // Header
            Constraint::Min(0),      // Chat
            Constraint::Length(3),  // Input
            Constraint::Length(1),  // Status
        ])
        .split(area)
}
```

#### Task 2.2: Chat Area + 滚动

#### Task 2.3: Input Area 多行编辑

#### Task 2.4: 代码高亮 (syntect)

---

### Phase 3: CC 状态感知

#### Task 3.1: OutputChunk 解析

#### Task 3.2: Thinking 折叠块

#### Task 3.3: 工具调用状态行

---

### Phase 4: 主题 + 键绑定

#### Task 4.1: 主题系统抽象

#### Task 4.2: 预置 8 主题

#### Task 4.3: Vim 模式键绑定

---

### Phase 5: 多通信模式

#### Task 5.1: IpcTransport 实现

#### Task 5.2: WsTransport 实现

#### Task 5.3: --transport 参数

---

### Phase 6: 打磨

#### Task 6.1: /export 导出

#### Task 6.2: 历史记录

#### Task 6.3: 命令补全

#### Task 6.4: 错误恢复

---

## 验证步骤

每个 Task 完成后执行：

```bash
# Build verification
cargo build -p ngb-tui

# Clippy check
cargo clippy -p ngb-tui -- -D warnings

# Format check
cargo fmt -p ngb-tui -- --check
```

---

## 执行方式

**Plan complete and saved to `docs/plans/2026-02-18-ngb-shell-tui.md`.**

**Two execution options:**

1. **Subagent-Driven (this session)** — I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** — Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
