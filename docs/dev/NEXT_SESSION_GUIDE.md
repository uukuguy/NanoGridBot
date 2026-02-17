# Next Session Guide

## Current Status

**Phase**: Workspace 架构重构 — Phase A 完成 (11/11 tasks)
**Date**: 2026-02-18
**Branch**: build-by-rust
**Tests**: 194 passing, zero clippy warnings

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

## 架构决策 (已实施)

- **RegisteredGroup** → 拆分为 **Workspace + ChannelBinding + AccessToken**
- Router 使用 **RouteAction** 枚举: Process / BindToken / BuiltinCommand / Unbound
- Token 格式: `ngb-` + 12位 hex (uuid v4 截取)
- 内置命令: `/status` `/help` `/unbind`
- Orchestrator 的 `poll_messages()` 处理所有 4 种 RouteAction
- GroupQueue 已完全替换为 WorkspaceQueue
- container_prep 使用 Workspace 类型替代 RegisteredGroup

## 清理完成

- `crates/ngb-types/src/group.rs` — 已删除
- `crates/ngb-db/src/groups.rs` — 已删除
- `crates/ngb-core/src/group_queue.rs` — 已删除
- 所有 `RegisteredGroup`、`GroupRepository`、`GroupQueue` 引用已清除

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
```

## 下一步建议

Phase A (Workspace 架构重构) 已全部完成。可能的后续方向：

1. **Phase B: 端到端集成测试** — 验证完整的 token 绑定 → 消息路由 → 容器执行流程
2. **Web Dashboard 适配** — 更新 web API 使用 Workspace 模型
3. **多用户支持** — 基于 Workspace owner 的权限控制
4. **生产部署准备** — Docker Compose、环境变量配置、日志优化
