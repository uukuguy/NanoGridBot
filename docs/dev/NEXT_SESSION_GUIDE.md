# Next Session Guide

## Current Status

**Phase**: NGB Shell TUI Phase 1 实施中
**Date**: 2026-02-18
**Branch**: build-by-rust
**Tests**: 197 passing (新增 3 个), zero clippy warnings

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

# 启动 TUI shell（待实现）
ngb shell <workspace>
ngb shell <workspace> --transport pipe|ipc|ws
ngb shell <workspace> --theme catppuccin-mocha|kanagawa|...
```

## 已完成 (Phase 1)

- ✅ Task 1.1: 创建 `ngb-tui` crate 骨架
- ✅ Task 1.2: Transport trait + PipeTransport 实现
- ✅ Task 1.3: 基础 TUI 框架（ratatui 初始化）

**新增文件**:
- `crates/ngb-tui/Cargo.toml`
- `crates/ngb-tui/src/lib.rs`
- `crates/ngb-tui/src/app.rs`
- `crates/ngb-tui/src/transport/mod.rs`
- `crates/ngb-tui/src/transport/pipe.rs`
- `crates/ngb-tui/src/transport/output.rs`

## 下一步

**Phase 1 剩余**:
- 实现真正的 stdout 读取逻辑
- 完善 PipeTransport 的 send/recv 实现

**Phase 2: 渲染增强**:
- Task 2.1: 四区域布局
- Task 2.2: Chat Area + 滚动
- Task 2.3: Input Area 多行编辑
- Task 2.4: 代码高亮 (syntect)

**参考**:
- 设计文档: `docs/plans/2026-02-18-ngb-shell-tui.md`
- 现有 crate: `crates/ngb-cli/`
