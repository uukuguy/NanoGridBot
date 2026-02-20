# NanoGridBot TUI 功能增强实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 NanoGridBot TUI 引入五个关键功能增强：语法高亮、树形视图、条件键绑定、Engine 抽象层

**Architecture:**
- 5 个独立模块分散在现有 crate 中
- 每个功能可独立使用，不相互依赖
- 参考 atuin/bat/eza 三个项目的最佳实践

**Tech Stack:**
- ratatui 0.29, crossterm 0.28 (现有)
- syntect 5.2 (新增: 语法高亮)
- unicode-width 0.2 (现有: 已有依赖)
- 内部抽象: 条件键绑定、Engine trait

---

## Task 1: 代码语法高亮增强 (syntect)

**Files:**
- Modify: `crates/ngb-tui/Cargo.toml:26` - 添加 syntect 依赖
- Modify: `crates/ngb-tui/src/app.rs:661-750` - render_message_item 函数
- Modify: `crates/ngb-tui/src/theme/mod.rs` - 添加高亮主题配置

**Step 1: 添加 syntect 依赖**

```toml
# Cargo.toml 第26行后添加
# Syntax highlighting
syntect = "5.2"
```

Run: `cargo build --package ngb-tui`
Expected: 编译成功

**Step 2: 创建语法高亮模块**

Create: `crates/ngb-tui/src/syntax.rs`

```rust
use syntect::highlighting::ThemeSet;
use syntect::parsing::SyntaxSet;
use std::sync::LazyLock;

pub static SYNTAX_SET: LazyLock<SyntaxSet> = LazyLock::new(|| SyntaxSet::load_defaults_newlines());
pub static THEME_SET: LazyLock<ThemeSet> = LazyLock::new(|| ThemeSet::load_defaults());

pub fn highlight_code(code: &str, language: &str) -> String {
    use syntect::easy::HighlightLines;
    use syntect::highlighting::Theme;
    use syntect::html::highlighted_html_for_string;
    use syntect::parsing::SyntaxReference;

    let syntax = SYNTAX_SET
        .find_syntax_by_token(language)
        .unwrap_or_else(|| SYNTAX_SET.find_syntax_plain_text());

    let theme = &THEME_SET.themes["base16-ocean.dark"];
    let mut highlighter = HighlightLines::new(syntax, theme);

    // 返回 ANSI 转义后的字符串
    // ... 简化实现
}
```

Run: `cargo build --package ngb-tui`
Expected: 编译成功

**Step 3: 在 MessageContent 中添加高亮支持**

Modify: `crates/ngb-tui/src/app.rs:163-169`

```rust
pub enum MessageContent {
    Text(String),
    Thinking(String),
    ToolCall { name: String, status: ToolStatus },
    CodeBlock { language: String, code: String },  // 已有
    Error(String),
}
```

Run: `cargo build --package ngb-tui`
Expected: 编译成功

**Step 4: 修改 render_message_item 使用高亮**

Modify: `crates/ngb-tui/src/app.rs:720-750` - 在处理 CodeBlock 时调用 syntect

```rust
MessageContent::CodeBlock { language, code } => {
    let highlighted = syntax::highlight_code(code, language);
    ListItem::new(highlighted).style(Style::default().fg(theme.foreground))
}
```

Run: `cargo build --package ngb-tui`
Expected: 编译成功

**Step 5: 提交**

```bash
git add crates/ngb-tui/Cargo.toml crates/ngb-tui/src/syntax.rs crates/ngb-tui/src/app.rs
git commit -m "feat: add syntax highlighting for code blocks using syntect"
```

---

## Task 2: Tree 树形视图 (对话线程)

**Files:**
- Create: `crates/ngb-tui/src/tree.rs`
- Modify: `crates/ngb-tui/src/app.rs:156-175` - Message 结构扩展
- Modify: `crates/ngb-tui/src/app.rs:661-750` - render_message_item

**Step 1: 创建 Tree 模块**

Create: `crates/ngb-tui/src/tree.rs`

```rust
/// 树形视图部件 - 用于显示对话线程/引用
#[derive(Debug, Clone)]
pub enum TreePart {
    Edge,    // ├──
    Line,    // │
    Corner,  // └──
    Blank,   // (space)
}

impl TreePart {
    pub fn ascii_art(&self) -> &'static str {
        match self {
            Self::Edge => "├── ",
            Self::Line => "│   ",
            Self::Corner => "└── ",
            Self::Blank => "    ",
        }
    }
}

/// 树节点 - 用于对话消息
#[derive(Debug, Clone)]
pub struct TreeNode {
    pub id: String,
    pub parent_id: Option<String>,
    pub children: Vec<String>,
    pub depth: usize,
}

impl TreeNode {
    pub fn new(id: String, parent_id: Option<String>, depth: usize) -> Self {
        Self { id, parent_id, children: Vec::new(), depth }
    }

    /// 获取用于渲染的前缀
    pub fn prefix(&self, is_last: bool) -> String {
        if self.depth == 0 {
            return String::new();
        }

        // 构建树前缀
        // ... 简化实现
        "  ".repeat(self.depth)
    }
}
```

Run: `cargo build --package ngb-tui`
Expected: 编译成功

**Step 2: 扩展 Message 支持回复**

Modify: `crates/ngb-tui/src/app.rs:156-175`

```rust
pub struct Message {
    pub role: MessageRole,
    pub content: MessageContent,
    pub timestamp: String,
    pub parent_id: Option<String>,  // 新增: 用于树形视图
}
```

Run: `cargo build --package ngb-tui`
Expected: 编译成功

**Step 3: 在 render_message_item 中使用 TreeNode**

Modify: `crates/ngb-tui/src/app.rs:720-750`

```rust
fn render_message_item<'a>(msg: &'a Message, collapsed: bool, theme: &'a Theme) -> ListItem<'a> {
    use ratatui::style::Style;
    use ratatui::widgets::ListItem;

    // 如果有 parent_id，渲染树形前缀
    let prefix = if let Some(parent_id) = &msg.parent_id {
        // 从某个 TreeNode 映射获取前缀
        format!("{} ", "│".repeat(2))  // 简化
    } else {
        String::new()
    };

    // ... 现有渲染逻辑
}
```

Run: `cargo build --package ngb-tui`
Expected: 编译成功

**Step 4: 提交**

```bash
git add crates/ngb-tui/src/tree.rs crates/ngb-tui/src/app.rs
git commit -m "feat: add tree view support for message threads"
```

---

## Task 3: 条件键绑定系统

**Files:**
- Create: `crates/ngb-tui/src/keymap.rs`
- Modify: `crates/ngb-tui/src/app.rs:799-900` - handle_key 函数

**Step 1: 创建 keymap 模块**

Create: `crates/ngb-tui/src/keymap.rs`

```rust
use crossterm::event::{KeyCode, KeyModifiers};

/// 键绑定动作
#[derive(Debug, Clone, PartialEq)]
pub enum Action {
    // 光标移动
    CursorLeft,
    CursorRight,
    CursorWordLeft,
    CursorWordRight,
    CursorHome,
    CursorEnd,

    // 编辑
    InsertChar(char),
    Delete,
    DeleteWord,
    Backspace,
    Clear,

    // 发送
    Submit,

    // 滚动
    ScrollUp,
    ScrollDown,

    // 模式切换
    EnterNormalMode,
    EnterInsertMode,

    // 应用级
    Quit,
    Interrupt,
    ClearScreen,
}

/// 条件原子 - 用于条件键绑定
#[derive(Debug, Clone, PartialEq)]
pub enum ConditionAtom {
    CursorAtStart,
    CursorAtEnd,
    InputEmpty,
    InputNotEmpty,
    ListAtEnd,
    ListAtStart,
    HasResults,
    NoResults,
}

/// 条件上下文
#[derive(Debug, Clone)]
pub struct EvalContext {
    pub cursor_position: usize,
    pub input_width: usize,
    pub input_byte_len: usize,
    pub selected_index: usize,
    pub results_len: usize,
    pub original_input_empty: bool,
}

impl EvalContext {
    pub fn evaluate(&self, cond: &ConditionAtom) -> bool {
        match cond {
            ConditionAtom::CursorAtStart => self.cursor_position == 0,
            ConditionAtom::CursorAtEnd => self.cursor_position >= self.input_byte_len,
            ConditionAtom::InputEmpty => self.input_byte_len == 0,
            ConditionAtom::InputNotEmpty => self.input_byte_len > 0,
            ConditionAtom::ListAtEnd => self.selected_index >= self.results_len.saturating_sub(1),
            ConditionAtom::ListAtStart => self.selected_index == 0,
            ConditionAtom::HasResults => self.results_len > 0,
            ConditionAtom::NoResults => self.results_len == 0,
        }
    }
}

/// 键绑定定义
#[derive(Debug, Clone)]
pub struct KeyBinding {
    pub key: (KeyCode, KeyModifiers),
    pub action: Action,
    pub condition: Option<ConditionAtom>,
}

/// 默认键绑定
pub fn default_keybindings() -> Vec<KeyBinding> {
    vec![
        // Ctrl+C: 有输入时清空，否则中断
        KeyBinding { key: (KeyCode::Char('c'), KeyModifiers::CONTROL), action: Action::Interrupt, condition: Some(ConditionAtom::InputNotEmpty) },
        KeyBinding { key: (KeyCode::Char('c'), KeyModifiers::CONTROL), action: Action::Clear, condition: Some(ConditionAtom::InputEmpty) },

        // Enter: 发送
        KeyBinding { key: (KeyCode::Enter, KeyModifiers::NONE), action: Action::Submit, condition: Some(ConditionAtom::InputNotEmpty) },

        // 方向键
        KeyBinding { key: (KeyCode::Left, KeyModifiers::CONTROL), action: Action::CursorWordLeft, condition: None },
        KeyBinding { key: (KeyCode::Right, KeyModifiers::CONTROL), action: Action::CursorWordRight, condition: None },
    ]
}
```

Run: `cargo build --package ngb-tui`
Expected: 编译成功

**Step 2: 在 App 中使用条件键绑定**

Modify: `crates/ngb-tui/src/app.rs:799-900`

```rust
// 在 App 结构体中添加
struct App {
    // ... existing fields
    pending_vim_key: Option<char>,
}

// 修改 handle_key 函数
fn handle_key(&mut self, key: event::KeyEvent) {
    use crate::keymap::{Action, ConditionAtom, EvalContext, default_keybindings};

    if key.kind != KeyEventKind::Press {
        return;
    }

    // 构建上下文
    let ctx = EvalContext {
        cursor_position: self.input_cursor,
        input_width: unicode_width::UnicodeWidthStr::width(self.input.as_str()),
        input_byte_len: self.input.len(),
        selected_index: self.chat_state.selected().unwrap_or(0),
        results_len: self.messages.len(),
        original_input_empty: self.input.is_empty(),
    };

    // 查找匹配的键绑定
    let bindings = default_keybindings();
    if let Some(action) = bindings.iter()
        .find(|b| b.key == (key.code, key.modifiers))
        .and_then(|b| b.condition.as_ref().filter(|c| ctx.evaluate(c)).map(|_| &b.action))
    {
        match action {
            Action::Submit => { /* 发送逻辑 */ }
            Action::Interrupt => { /* 中断逻辑 */ }
            Action::Clear => { /* 清空输入 */ }
            // ... 其他动作
            _ => {}
        }
        return;
    }

    // 回退到现有逻辑
    // ... existing handling
}
```

Run: `cargo build --package ngb-tui`
Expected: 编译成功

**Step 3: 提交**

```bash
git add crates/ngb-tui/src/keymap.rs crates/ngb-tui/src/app.rs
git commit -m "feat: add conditional keybinding system"
```

---

## Task 4: Engine 抽象层 (命令历史搜索)

**Files:**
- Create: `crates/ngb-tui/src/engine.rs`
- Modify: `crates/ngb-tui/src/lib.rs` - 导出新模块

**Step 1: 创建 Engine trait**

Create: `crates/ngb-tui/src/engine.rs`

```rust
use async_trait::async_trait;
use serde::{Deserialize, Serialize};

/// 搜索引擎 trait - 支持命令历史搜索
#[async_trait]
pub trait SearchEngine: Send + Sync {
    /// 执行搜索
    async fn search(&self, query: &str) -> Vec<SearchResult>;

    /// 过滤结果
    async fn filter(&mut self, filter: SearchFilter);

    /// 获取总数
    fn count(&self) -> usize;
}

/// 搜索结果
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    pub id: String,
    pub content: String,
    pub timestamp: i64,
    pub score: f64,
    pub metadata: Option<SearchMetadata>,
}

/// 搜索元数据
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchMetadata {
    pub command: Option<String>,
    pub exit_code: Option<i32>,
    pub duration_ms: Option<u64>,
}

/// 搜索过滤器
#[derive(Debug, Clone, Default)]
pub struct SearchFilter {
    pub query: Option<String>,
    pub date_from: Option<i64>,
    pub date_to: Option<i64>,
    pub exit_code: Option<i32>,
    pub limit: Option<usize>,
}

/// 历史引擎 - 从本地存储加载命令历史
pub struct HistoryEngine {
    // 内部存储
}

impl HistoryEngine {
    pub fn new() -> Self {
        Self {}
    }

    pub async fn load_history(&mut self, _path: &std::path::Path) -> Result<(), Box<dyn std::error::Error>> {
        // 从文件加载历史
        // 简化实现
        Ok(())
    }
}

#[async_trait]
impl SearchEngine for HistoryEngine {
    async fn search(&self, query: &str) -> Vec<SearchResult> {
        // 简单实现: 包含匹配
        vec![]
    }

    async fn filter(&mut self, _filter: SearchFilter) {
        // 实现过滤逻辑
    }

    fn count(&self) -> usize {
        0
    }
}
```

Run: `cargo build --package ngb-tui`
Expected: 编译成功

**Step 2: 导出模块**

Modify: `crates/ngb-tui/src/lib.rs`

```rust
pub mod app;
pub mod theme;
pub mod transport;
pub mod engine;  // 新增
```

Run: `cargo build --package ngb-tui`
Expected: 编译成功

**Step 3: 提交**

```bash
git add crates/ngb-tui/src/engine.rs crates/ngb-tui/src/lib.rs
git commit -m "feat: add SearchEngine trait for command history"
```

---

## Task 5: unicode-width 验证和使用增强

**Files:**
- Modify: `crates/ngb-tui/src/app.rs:745-770` - draw_input 光标计算

**Note:** unicode-width 已经在 Cargo.toml 中，且 app.rs 已在使用。验证并增强使用。

**Step 1: 验证当前使用**

Run: `grep -n "unicode_width" crates/ngb-tui/src/app.rs`

Expected: 找到第 747 行和 757 行的使用

**Step 2: 增强光标计算**

Modify: `crates/ngb-tui/src/app.rs:745-770`

```rust
// 当前 draw_input 中的光标位置计算
// 确保正确使用 unicode-width

use unicode_width::UnicodeWidthStr;

// 计算显示宽度（考虑全角字符）
let display_width = UnicodeWidthStr::width(input_before_cursor.as_str()) as u16;

// 光标 X 位置 = 前缀宽度 + 输入宽度 + 1
let cursor_x = (prefix_width + display_width + 1).min(area.width - 1);
```

Run: `cargo build --package ngb-tui`
Expected: 编译成功

**Step 3: 提交**

```bash
git add crates/ngb-tui/src/app.rs
git commit -m "refactor: ensure unicode-width usage in cursor positioning"
```

---

## 实施顺序

1. **Task 5** - unicode-width 验证（最快，确认现有功能）
2. **Task 1** - 语法高亮（用户最可见的改进）
3. **Task 2** - Tree 视图（为后续功能预留）
4. **Task 3** - 条件键绑定（提升交互体验）
5. **Task 4** - Engine 抽象（基础设施）

---

## 验证步骤

每个 Task 完成后:
1. `cargo build --package ngb-tui` - 编译成功
2. `cargo clippy --package ngb-tui` - 无警告
3. 运行 TUI 手动测试相关功能

---

## Plan complete and saved to `docs/plans/2026-02-19-tui-feature-enhancements.md`.

**Two execution options:**

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
