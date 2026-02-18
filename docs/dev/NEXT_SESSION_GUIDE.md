# Next Session Guide

## Current Status

**Phase**: TUI UI 改进 ✅ 完成
**Date**: 2026-02-18
**Branch**: build-by-rust
**Tests**: 197 passing, zero clippy warnings

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
| 1 | 语法高亮 (syntect) - syntax.rs | ✅ |
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
- 历史搜索 UI（Ctrl+R 触发搜索）

**修改文件**:
- `Cargo.lock`
- `crates/ngb-tui/Cargo.toml` (添加 uuid 依赖)
- `crates/ngb-tui/src/app.rs` (集成 keymap/tree/engine)

**参考**:
- 设计文档: `docs/plans/2026-02-18-ngb-shell-tui.md`
- TUI 分析: `docs/design/RUST_TUI_PROJECTS_ANALYSIS.md`
- 可运行: `make shell WORKSPACE=xxx`
