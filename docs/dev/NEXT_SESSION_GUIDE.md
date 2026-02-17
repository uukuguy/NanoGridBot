# Next Session Guide

## Current Status

**Phase**: Workspace 架构重构 — Phase A 基本完成 (8/11 tasks)
**Date**: 2026-02-18
**Branch**: build-by-rust
**Tests**: 214 passing, zero clippy warnings

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
| 10 | Token 绑定流程 + 引导消息 (合并到 Task 5) | ✅ |

## 剩余 Tasks (下一会话)

### Task 8: 删除 RegisteredGroup 和 GroupRepository
- 删除 `crates/ngb-types/src/group.rs`
- 删除 `crates/ngb-db/src/groups.rs`
- 从 `lib.rs` 移除导出
- 检查并修复所有残留引用 (container_prep.rs 的 `write_workspaces_snapshot` 仍接受 `&[RegisteredGroup]` 参数)
- 注意: task_scheduler.rs 可能引用 GroupRepository

### Task 9: CLI workspace create/list 命令
- 在 ngb-cli 添加 `Workspace` 子命令
- `create <name>`: 创建 workspace + 生成 token
- `list`: 列出所有 workspace 及其绑定状态
- 需要读 `crates/ngb-cli/src/main.rs` 了解 CLI 结构

### Task 11: Makefile + 文档更新
- Makefile 添加 workspace-create/workspace-list target
- 更新 CLAUDE.md 和设计文档

## 架构决策 (已实施)

- **RegisteredGroup** → 拆分为 **Workspace + ChannelBinding + AccessToken**
- Router 使用 **RouteAction** 枚举: Process / BindToken / BuiltinCommand / Unbound
- Token 格式: `ngb-` + 12位 hex (uuid v4 截取)
- 内置命令: `/status` `/help` `/unbind`
- Orchestrator 的 `poll_messages()` 处理所有 4 种 RouteAction

## 注意事项

- `group_queue.rs` 和 `workspace_queue.rs` 共存，orchestrator 仍使用 GroupQueue
- `RegisteredGroup` 和 `GroupRepository` 仍存在，等 Task 8 清理
- `HealthStatus.registered_groups` 字段名保持不变 (JSON API 兼容)
- 所有 test_config() helper 已包含 workspaces_dir 字段
