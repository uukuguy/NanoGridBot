# Next Session Guide

## Current Status

**Phase**: Phase 25 Task 1 端到端集成测试 ✅ 完成
**Date**: 2026-02-21
**Branch**: build-by-rust
**Tests**: 175 passing (130 existing + 45 ngb-tui: 39 unit + 6 integration), zero clippy warnings

---

## 已完成的 Tasks

| Task | 内容 | 状态 |
|------|------|------|
| 1 | ngb-types: Workspace/ChannelBinding/AccessToken 类型 | ✅ |
| 2 | ngb-db: workspaces/bindings/tokens 表 + Repository | ✅ |
| 3 | ngb-config: workspaces_dir 字段 | ✅ |
| 4 | Router: RouteAction 枚举 + 两步绑定查找 | ✅ |
| 5 | Orchestrator: Workspace 模型 + token 绑定 + 引导消息 + 内置命令 | ✅ |
| 6 | workspace_queue.rs (WorkspaceQueue) | ✅ |
| 7 | container 模块函数重命名 (validate_workspace_mounts 等) | ✅ |
| 8 | 删除 RegisteredGroup/GroupRepository/GroupQueue 遗留代码 | ✅ |
| 9 | CLI workspace create/list 命令 | ✅ |
| 10 | Token 绑定流程 + 引导消息 (合并到 Task 5) | ✅ |
| 11 | Makefile + 文档更新 | ✅ |

## TUI 设计完成

**设计文档**: `docs/plans/2026-02-18-ngb-shell-tui.md`

### 核心设计决策
- **Agent**: 容器内运行 Claude Code，ngb shell 是 CC 的 TUI 前端
- **通信模式**: Pipe/IPC/WS 三种可切换，默认 Pipe（实时 streaming）
- **主题**: 8 个预置主题，默认 Catppuccin Mocha
- **消息渲染**: 混合模式 — 用户气泡 + Agent 前缀流式
- **快捷键**: Emacs + Vim 双模式

### 实施计划（6 Phase）
- Phase 1: 骨架 + 管道通信
- Phase 2: 渲染增强（Markdown/代码高亮）
- Phase 3: CC 状态感知（Thinking/工具调用）
- Phase 4: 主题 + 键绑定
- Phase 5: 多通信模式（IPC/WS）
- Phase 6: 打磨

## CLI 命令

```bash
# 创建 workspace 并获取 token
ngb workspace create <name>
# 或
make workspace-create NAME=<name>

# 列出所有 workspace
ngb workspace list
# 或
make workspace-list

# 启动 TUI shell
ngb shell <workspace>
ngb shell <workspace> --transport pipe
ngb shell <workspace> --transport ipc
ngb shell <workspace> --transport ws
ngb shell <workspace> --theme catppuccin-mocha
ngb shell <workspace> --theme kanagawa
ngb shell <workspace> --transport ws --theme tokyo-night
```

## 已完成 (Phase 1)

- ✅ Task 1.1: 创建 `ngb-tui` crate 骨架
- ✅ Task 1.2: Transport trait + PipeTransport 实现
- ✅ Task 1.3: 基础 TUI 框架（ratatui 初始化）
- ✅ Task 1.4: PipeTransport send/recv 实现（使用 tokio 异步 I/O）
- ✅ Task 1.5: OutputChunk JSONL 解析

**新增/修改文件**:
- `crates/ngb-tui/Cargo.toml` (添加 async-stream 依赖)
- `crates/ngb-tui/src/lib.rs`
- `crates/ngb-tui/src/app.rs`
- `crates/ngb-tui/src/transport/mod.rs`
- `crates/ngb-tui/src/transport/pipe.rs` (重写 send/recv_stream)
- `crates/ngb-tui/src/transport/output.rs`

## 已完成 (Phase 2)

- ✅ Task 2.1: 四区域布局 (Header/Chat/Input/Status)
- ✅ Task 2.2: Chat Area + 滚动 (ListState, 鼠标/键盘滚动)
- ✅ Task 2.3: Input Area 多行编辑 (Shift+Enter 换行, 光标移动)
- ✅ Task 2.4: 代码块渲染 (基本代码块显示，无 syntect 颜色)

**修改文件**:
- `crates/ngb-tui/Cargo.toml` (添加 pulldown-cmark 依赖)
- `crates/ngb-tui/src/app.rs` (完整重写，添加消息类型、滚动、输入处理)

## 已完成 (Phase 3)

- ✅ Task 3.1: OutputChunk 解析 (Transport stream 集成，mpsc channel 桥接)
- ✅ Task 3.2: Thinking 折叠块 (collapsed_thinking HashSet，Tab 键切换)
- ✅ Task 3.3: 工具调用状态行 (ToolStart 显示⠙，ToolEnd 更新为✓/✗)

**修改文件**:
- `crates/ngb-tui/src/app.rs` (添加 transport/stream/collapse 支持)

## 已完成 (Phase 4)

- ✅ Task 4.1: 主题系统抽象 (Theme/ThemeName 枚举)
- ✅ Task 4.2: 预置 8 主题 (catppuccin-mocha/latte, kanagawa, rose-pine/dawn, tokyo-night, midnight, terminal)
- ✅ Task 4.3: Vim 模式键绑定 (k/j 滚动, Esc 退出, : 命令模式预留)

**新增/修改文件**:
- `crates/ngb-tui/src/theme/mod.rs` (新建主题模块)
- `crates/ngb-tui/src/app.rs` (添加 theme/key_mode 字段和渲染支持)
- `crates/ngb-tui/src/lib.rs` (导出 theme/key_mode)

## 已完成 (Phase 5)

- ✅ Task 5.1: IpcTransport 实现 (文件轮询，~500ms 延迟)
- ✅ Task 5.2: WsTransport 实现 (WebSocket 实时通信)
- ✅ Task 5.3: create_transport 工厂函数 (支持 pipe/ipc/ws)

**新增/修改文件**:
- `crates/ngb-tui/Cargo.toml` (添加 tokio-tungstenite 依赖)
- `crates/ngb-tui/src/transport/ipc.rs` (新建 IPC 传输)
- `crates/ngb-tui/src/transport/ws.rs` (新建 WebSocket 传输)
- `crates/ngb-tui/src/transport/mod.rs` (添加工厂函数和常量)
- `crates/ngb-tui/src/lib.rs` (导出新传输类型)

## 已完成 (Phase 6)

- ✅ Task 6.1: CLI 参数集成 (ngb shell --transport --theme)
- ✅ Bug fixes: 事件循环双键输入、UTF-8字符边界、Unicode宽度计算
- ✅ UI改进: 图标系统IconSet、消息间距调整

**新增/修改文件**:
- `crates/ngb-tui/src/app.rs` (AppConfig、bug修复、图标、间距)
- `crates/ngb-tui/src/lib.rs` (导出 AppConfig, IconSet)
- `crates/ngb-tui/src/theme/mod.rs` (IconSet 结构体 + 4套图标)
- `crates/ngb-tui/Cargo.toml` (添加 unicode-width 依赖)
- `crates/ngb-cli/src/main.rs` (shell 命令)
- `Makefile` (install, shell 命令)

**CLI 命令示例**:
```bash
# 启动 TUI shell
ngb shell my-workspace

# 指定传输模式
ngb shell my-workspace --transport pipe
ngb shell my-workspace --transport ipc
ngb shell my-workspace --transport ws

# 指定主题
ngb shell my-workspace --theme catppuccin-mocha
ngb shell my-workspace --theme kanagawa

# Makefile
make shell WORKSPACE=my-workspace
make install
```

## TUI UI 改进 (本会话)

- ✅ Header 双行布局：
  - 第一行：🦑 NanoGridBot + 版本号（版本号使用状态区颜色）
  - 第二行：当前目录路径（~风格，与 NanoGridBot 列对齐）

- ✅ Ctrl+C 快捷键行为修改（参考 Claude Code）：
  - 有输入时：清空输入框
  - 正在运行：中断当前指令
  - 2秒内连续两次 Ctrl+C：退出 TUI

- ✅ 初始欢迎信息重构：
  - 从 welcome.txt 文件读取（纯用户文件方案）
  - 显示 Commands 和 Shortcuts 两部分
  - 方便后续修改

**修改文件**:
- `crates/ngb-tui/src/app.rs`
- `crates/ngb-tui/welcome.txt` (新建)

---

## Phase 17: TUI 功能框架增强 (本会话)

**日期**: 2026-02-19
**状态**: ✅ 完成
**测试**: 10 passing, zero clippy warnings

### 已完成

| Task | 内容 | 状态 |
|------|------|------|
| 1 | 语法高亮 (syntect) - syntax.rs | ✅ → 已被 tui-markdown 替代 (Phase 23) |
| 2 | 树形视图 (Tree) - tree.rs | ✅ 已集成 |
| 3 | 条件键绑定系统 - keymap.rs | ✅ 已集成 |
| 4 | Engine 抽象层 - engine.rs | ✅ 已集成 |
| 5 | unicode-width 验证 | ✅ |

### 本次集成更新

- **keymap.rs**: 添加 `keybindings` 字段，使用 `default_keybindings()` 初始化，重构 `handle_key` 使用 keymap 系统
- **tree.rs**: 添加 `message_tree` 字段，实现 `build_message_tree()` 和 `get_message_tree_prefix()` 方法
- **engine.rs**: 添加 `history_engine` 字段，实现 `add_to_history()` 和 `search_history()` 方法，提交消息时自动保存到历史

### 新增模块

- `crates/ngb-tui/src/syntax.rs` - 语法高亮
- `crates/ngb-tui/src/tree.rs` - 树形视图
- `crates/ngb-tui/src/keymap.rs` - 条件键绑定
- `crates/ngb-tui/src/engine.rs` - 搜索引擎抽象

### 分析文档

- `docs/design/RUST_TUI_PROJECTS_ANALYSIS.md` - 详细分析 Atuin、bat、eza 三个 Rust TUI 项目

---

## 下一步

**TUI 6 Phase 全部完成**，NGB Shell TUI MVP 已就绪！

**可选后续任务**:
- 与容器启动流程集成（真正的 agent 响应）
- 错误处理增强
- 状态栏完善

---

## Phase 18: Ctrl+R 历史搜索 UI (本会话新增)

**状态**: ✅ 完成

### 已完成

- **AppMode 枚举**: 添加 Normal/Search 模式切换
- **键绑定**: Ctrl+R 激活搜索，Esc 退出，Enter 选中，↑↓ 导航
- **搜索 UI**: 覆盖式搜索面板，实时过滤结果
- **历史引擎集成**: 使用 engine.rs 的 search_history 方法

### 修改文件

- `crates/ngb-tui/src/app.rs`: 添加搜索模式状态和 UI 渲染
- `crates/ngb-tui/src/keymap.rs`: 添加搜索相关 Action 和 Condition
- `crates/ngb-tui/src/lib.rs`: 导出 AppMode

### 使用方法

1. 按 **Ctrl+R** 打开历史搜索面板
2. 输入搜索词实时过滤历史记录
3. 使用 **↑↓** 选择结果
4. 按 **Enter** 填充到输入框
5. 按 **Esc** 退出搜索

**测试**: 10 passing, zero clippy warnings

**参考**:
- 设计文档: `docs/plans/2026-02-18-ngb-shell-tui.md`
- TUI 分析: `docs/design/RUST_TUI_PROJECTS_ANALYSIS.md`
- 可运行: `make shell WORKSPACE=xxx`

---

## Phase 20: TUI 输入组件重构 (本会话完成)

**状态**: ✅ 完成
**日期**: 2026-02-20

### 完成工作

1. **组件选型**: 调研 Rust TUI 生态
   - tui-textarea 0.7.0 ✅ (已支持 ratatui 0.29)
   - ratatui-textarea 0.4.x (与 ratatui 0.29 不兼容)
   - 决定使用 tui-textarea 0.7.0

2. **集成 tui-textarea**:
   - 添加 `textarea: TextArea<'static>` 字段到 App 结构体
   - 修改 `draw_input` 使用 TextArea widget 渲染
   - 修改 `handle_key` 使用 `textarea.input(key)` 处理输入
   - 保留 `input` 字段用于向后兼容

### 待完成任务

| 任务 | 内容 | 状态 |
|------|------|------|
| 1 | 优化 TextArea 配置（光标样式、占位符等） | ✅ |
| 2 | 添加 tui-markdown 依赖 | ✅ |
| 3 | 代码块使用 tui-markdown 渲染 | ⏸️ (已有 syntect) |
| 4 | 实现 Ctrl+R 历史搜索面板 | ✅ (Phase 18 已实现) |
| 5 | 添加确认对话框支持 | ⏸️ 可选 |

### 依赖版本

```toml
ratatui = "0.29"
tui-textarea = "0.7"
tui-markdown = "0.3"
```

### 参考

- tui-textarea: https://crates.io/crates/tui-textarea
- 设计文档: `docs/plans/2026-02-20-ngb-tui-refactor-design.md`

---

## Phase 21: TUI 输入框修复与键盘处理重构 (本会话完成)

**状态**: ✅ 完成
**日期**: 2026-02-20
**测试**: 10 passing, zero clippy warnings

### 完成工作

1. **优化 TextArea 配置**:
   - 添加占位符文本提示用户输入方式
   - 设置占位符样式为深灰色
   - 禁用默认的光标行下划线样式

2. **添加 tui-markdown 依赖**:
   - 添加 `tui-markdown = "0.3"` 用于 Markdown 渲染
   - 与 ratatui 0.29 兼容

3. **修复输入框问题** (用户反馈):
   - ✅ 修复上下键历史导航与光标移动冲突
   - ✅ 实现自动折行（通过 TextArea widget）
   - ✅ 启用快捷键文本编辑功能（Emacs 风格）

4. **键盘处理架构重构**:
   - **keybindings 简化**: 只保留应用级操作（Ctrl+C、Ctrl+R、搜索、滚动、PageUp/Down）
   - **移除所有编辑操作**: 删除 Ctrl+A/E/B/F/K/D/W、箭头键、Home/End、Backspace、Delete 等 93 行 keybindings
   - **textarea 优先**: 所有文本编辑操作交给 tui-textarea 处理
   - **handle_action 简化**: 移除所有光标/编辑操作（CursorLeft/Right/Home/End、InsertChar、Delete、Backspace、Clear 等）
   - **历史导航优化**: Ctrl+P/N 用于历史，上下键用于光标移动
   - **Submit 重构**: 从 textarea 获取内容而不是 self.input
   - **Ctrl+C 修复**: 清空 textarea 而不是 self.input

5. **辅助方法**:
   - `sync_input_from_textarea()`: 同步 textarea 到 input 字段
   - `set_textarea_content()`: 设置 textarea 内容并同步
   - `apply_textarea_config()`: 应用标准配置到 textarea

6. **draw_input 简化**:
   - 直接使用 TextArea widget 渲染
   - 移除手动 Paragraph + 光标计算
   - TextArea 自动处理光标、滚动、折行

### 架构改进

**Before**:
- keybindings 拦截所有编辑键 → handle_action 操作 self.input → textarea 只处理 fallback
- 两套状态不同步，快捷键不工作

**After**:
- keybindings 只处理应用级操作 → textarea 处理所有编辑 → sync_input_from_textarea
- 单一状态源，所有 Emacs 快捷键自动工作

### 修改文件

- `crates/ngb-tui/src/keymap.rs`: 93 行 keybindings 删除，只保留 9 个应用级绑定
- `crates/ngb-tui/src/app.rs`:
  - handle_action: 移除所有编辑操作（~100 行）
  - handle_key: 完全重写，textarea 优先
  - 添加 3 个辅助方法
  - draw_input: 简化为直接渲染 TextArea widget

### 依赖版本

```toml
ratatui = "0.29"
tui-textarea = "0.7"
tui-markdown = "0.3"
```

### 支持的快捷键

**tui-textarea 默认支持**:
- Ctrl+A: 行首
- Ctrl+E: 行尾
- Ctrl+B: 后退
- Ctrl+F: 前进
- Ctrl+K: 删除到行尾
- Ctrl+U: 删除整行
- Ctrl+W: 删除前一个词
- Ctrl+D: 删除当前字符
- Ctrl+H: Backspace
- Alt+B/F: 词移动
- Home/End: 行首/尾
- 箭头键: 光标移动
- Backspace/Delete: 删除字符

**应用级快捷键**:
- Ctrl+C: 清空输入/中断/退出
- Ctrl+R: 历史搜索
- Ctrl+P/N: 历史导航
- Enter: 提交
- Shift+Enter: 换行
- Tab: 折叠/展开
- PageUp/Down: 滚动

---

## Phase 22: 清理冗余字段 + 修复搜索覆盖层 Rect bug

**状态**: ✅ 完成
**日期**: 2026-02-20
**测试**: 编译通过, zero warnings

### 完成工作

1. **移除冗余字段**:
   - 删除 `App.input: String` 字段及初始化
   - 删除 `App.cursor_position: usize` 字段及初始化
   - 删除 `sync_input_from_textarea()` 方法及所有调用点
   - `build_eval_context()` 改为直接从 textarea 获取文本和光标位置
   - `draw_layout()` 中输入高度计算改为从 textarea 获取文本

2. **修复搜索覆盖层 Rect 构造 bug**:
   - `Rect::new(x, y, width, height)` 的第 3/4 参数应为宽高，之前错误传入了绝对坐标 (`overlay_x + overlay_width`)
   - 修复 5 处 Rect: overlay_area, box_area, input_area, results_area, hint_area

### 修改文件

- `crates/ngb-tui/src/app.rs`: -35 行, +26 行

---

## Phase 23: tui-markdown 统一渲染 + syntect 移除 + 代码重构

**状态**: ✅ 完成
**日期**: 2026-02-20
**测试**: 编译通过, zero clippy warnings

### 完成工作

1. **Agent 消息 Markdown 渲染** (fd0c39f):
   - 集成 `tui_markdown::from_str()` 渲染 agent 文本消息
   - 添加 `ratatui-core = "0.1.0"` 作为类型桥接
   - 添加 `convert_color()` 桥接函数（ratatui-core → ratatui 0.29）

2. **移除 syntect，统一用 tui-markdown** (1863d84):
   - 删除 `syntax.rs` 模块（116 行）
   - 移除 `syntect = "5.2"` 依赖
   - CodeBlock 渲染改用 `tui-markdown`（将代码包装为 markdown 代码块再渲染）

3. **提取公共方法，消除重复代码** (952f5da):
   - 新增 `convert_style()`: 将 ratatui-core Style 整体转换为 ratatui Style
   - 新增 `render_markdown_lines()`: 统一 Text 和 CodeBlock 的 markdown→Line 渲染逻辑
   - Text 渲染：25 行 → 4 行
   - CodeBlock 渲染：20 行 → 6 行
   - 净减 15 行

### 关键技术决策

- `tui-markdown` 0.3 依赖 `ratatui-core` 0.1.0，而项目用 `ratatui` 0.29，Color/Style 类型不兼容
- 通过 `convert_color`/`convert_style` 桥接函数解决类型差异
- 升级到 ratatui 0.30 的瓶颈：`tui-textarea` 0.7 尚未适配 0.30

### 修改文件

- `crates/ngb-tui/Cargo.toml`: +ratatui-core, -syntect
- `crates/ngb-tui/src/syntax.rs`: 删除
- `crates/ngb-tui/src/lib.rs`: 移除 `pub mod syntax`
- `crates/ngb-tui/src/app.rs`: markdown 渲染集成 + 公共方法提取

### 依赖版本

```toml
ratatui = "0.29"
tui-textarea = "0.7"
tui-markdown = "0.3"
ratatui-core = "0.1.0"
# syntect 已移除
```

---

## Phase 24: 容器启动流程集成

**状态**: ✅ 完成
**日期**: 2026-02-20
**测试**: 130 passing, zero clippy warnings

### 完成工作

| Task | 内容 | 状态 |
|------|------|------|
| 1 | MockTransport — 开发/演示模式 (mock.rs 新建) | ✅ |
| 2 | ContainerSession::from_existing() 构造器 | ✅ |
| 3 | SessionTransport — 持久化容器会话 (session.rs 新建) | ✅ |
| 4 | PipeTransport 安全挂载增强 | ✅ |
| 5 | Transport 模块 + AppConfig 更新 | ✅ |
| 6 | CLI 更新 (--mock, --session-id) | ✅ |

### 新增文件

- `crates/ngb-tui/src/transport/mock.rs` — MockTransport，3 组预设响应循环
- `crates/ngb-tui/src/transport/session.rs` — SessionTransport，包装 ContainerSession

### 修改文件

- `crates/ngb-core/src/container_session.rs` — 添加 from_existing() 构造器
- `crates/ngb-tui/src/transport/pipe.rs` — PipeTransport::new() 增加 config 参数，安全挂载
- `crates/ngb-tui/src/transport/mod.rs` — 添加 mock/session 模块，create_transport 扩展
- `crates/ngb-tui/src/app.rs` — AppConfig 添加 config/session_id 字段
- `crates/ngb-tui/src/lib.rs` — 导出新类型
- `crates/ngb-cli/src/main.rs` — Shell 命令添加 --mock, --session-id

### CLI 命令

```bash
# 开发/演示模式（无需 Docker）
ngb shell test --mock

# 持久化容器会话
ngb shell test --transport session
ngb shell test --session-id my-session-001

# 安全挂载管道模式（默认，需要 Docker）
ngb shell test --transport pipe

# 旧模式仍然兼容
ngb shell test
```

### 关键复用

| 已有代码 | 用途 |
|---------|------|
| `prepare_container_launch()` | 目录创建、settings.json、技能同步 |
| `validate_workspace_mounts()` | 构建安全挂载列表 |
| `filter_env_vars()` | 只传递 API key |
| `ContainerSession` | 持久容器管理 |
| `get_container_status()` | 检查容器状态 |

---

## Phase 25: 端到端集成测试

**状态**: Task 1 ✅ 完成
**日期**: 2026-02-21

### Task 1: ngb-tui 端到端集成测试 ✅

| 分类 | 测试数 | 内容 |
|------|--------|------|
| tests_chunk | 8 | OutputChunk 到 Message 转换（Text/Thinking/Tool/Error/Done） |
| tests_keys | 10 | 键盘输入（Ctrl+C/R、搜索、Vim j/k、PageUp/Down、历史、Submit） |
| tests_search | 5 | 历史搜索（空查询、过滤、大小写不敏感、无匹配、部分匹配） |
| tests_theme | 3 | 主题系统（默认、配置、所有主题不 panic） |
| integration | 6 | AppConfig builder、MockTransport 流式、App 构建 |

**修改文件**:
- `crates/ngb-tui/src/app.rs` — 添加 `#[cfg(test)]` helpers + 4 个测试模块（~250 行）
- `crates/ngb-tui/tests/integration_tests.rs` — 新建（106 行）
- `crates/ngb-tui/Cargo.toml` — 添加 tokio test-util dev-dependency

**测试结果**: 39 unit + 6 integration = 45 tests, zero clippy warnings

### 可能的后续 Tasks

- Task 2: 状态栏完善（运行状态 idle/streaming/thinking、消息计数、transport 类型）
- Task 3: 退出确认对话框（自行实现，tui-confirm-dialog crate 不存在）
- Task 4: 错误处理增强（transport 连接失败重试、超时处理）
- Task 5: Vim 模式键绑定增强
- Task 6: 版本兼容性升级追踪（等 tui-textarea 适配 ratatui 0.30）
