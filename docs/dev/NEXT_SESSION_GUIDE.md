# Next Session Guide

## Current Status

**Phase**: Workspace 架构重构 — 实施计划已完成，待执行
**Date**: 2026-02-18
**Branch**: build-by-rust
**Project Status**: 设计和计划完成，代码重构待开始

---

## 2026-02-18 - Workspace 架构设计 + Makefile + MVP 修复

### 本阶段成果

1. **Makefile 重写**: 37 个 target 覆盖 Rust/Python/Node.js/Docker 全部开发任务
2. **Agent Runner TS 修复**: `container/agent-runner/src/index.ts:426` 类型转换修复
3. **MVP 自动注册**: `router.rs` auto_register_group + `main.rs` Docker 镜像预检（临时方案）
4. **Workspace 架构设计**: brainstorming 完成，概念模型确定
5. **实施计划**: 11 个 task 的 TDD 实施计划

### 关键架构决策

**RegisteredGroup → Workspace + ChannelBinding + AccessToken**

- Workspace: 智能体开发项目的隔离工作环境（核心概念）
- ChannelBinding: IM chat → workspace 的映射（通过 token 建立）
- AccessToken: CLI 生成，IM 侧发送完成绑定
- 双模式: 私聊→个人 workspace，群聊→团队 workspace
- IM 引导: 未绑定 chat 主动回复使用说明
- MVP 不做用户管理，通过 sender_id 自然区分

### 设计文档

- `docs/plans/2026-02-18-workspace-architecture.md` — 完整设计（概念模型、关系图、数据库 schema、交互流程）
- `docs/plans/2026-02-18-workspace-refactor-plan.md` — 11 个 task 实施计划

---

## 下一阶段：执行 Workspace 重构

### 实施计划概览

**Phase A: 概念重构 (Task 1-8)**

| Task | 内容 | 关键文件 |
|------|------|----------|
| 1 | 新增 Workspace/ChannelBinding/AccessToken 类型 | `ngb-types/src/{workspace,binding}.rs` |
| 2 | 新增 DB 表和 Repository | `ngb-db/src/{workspaces,bindings,tokens}.rs` |
| 3 | Config: groups_dir → workspaces_dir | `ngb-config/src/config.rs` |
| 4 | Router: 两步查找 + RouteAction enum | `ngb-core/src/router.rs` |
| 5 | Orchestrator: 使用 Workspace + Binding | `ngb-core/src/orchestrator.rs` |
| 6 | GroupQueue → WorkspaceQueue | `ngb-core/src/workspace_queue.rs` |
| 7 | container_prep/runner/mount 重命名 | `ngb-core/src/container_*.rs` |
| 8 | 删除 RegisteredGroup 和 GroupRepository | `ngb-types/src/group.rs`, `ngb-db/src/groups.rs` |

**Phase B: Token 绑定机制 (Task 9-11)**

| Task | 内容 | 关键文件 |
|------|------|----------|
| 9 | CLI workspace create/list 命令 | `ngb-cli/src/main.rs` |
| 10 | IM token 识别 + 引导信息 | `ngb-core/src/orchestrator.rs` |
| 11 | Makefile + 文档更新 | `Makefile`, `CLAUDE.md` |

### 执行方式

建议用 **subagent-driven** 方式逐 task 执行，每个 task 之间做 code review。

### 注意事项

- 247 处 group 相关引用需要迁移，涉及 21 个 Rust 文件
- Task 1-7 逐步迁移，Task 8 最后清理旧类型
- 所有 test_config() 辅助函数需要加 workspaces_dir 字段
- 当前 auto_register_group 是临时方案，Task 4 会替换为引导信息机制
- DB schema 用 CREATE TABLE IF NOT EXISTS，新旧表共存过渡

### 验证清单

完成后需验证：
1. `cargo build --workspace` — 零错误
2. `cargo clippy --workspace -- -D warnings` — 零警告
3. `cargo test --workspace` — 全部通过
4. `make serve` — 正常启动
5. `make workspace-create NAME=test` — 创建成功并输出 token
6. Telegram 发消息 → 收到引导信息
7. Telegram 发 token → 绑定成功
8. Telegram 发正常消息 → agent 回复

---

## 项目历史

### Phase 1: Foundation Layer ✅
基础类型、配置、数据库、工具模块

### Phase 2: Core Runtime ✅
Orchestrator、Router、GroupQueue、ContainerRunner、IPC、TaskScheduler

### Phase 3: MVP (Telegram + Docker + CLI serve) ✅
Agent-runner、Dockerfile、Telegram channel、CLI serve、181 tests passing

### Phase 3.5: Workspace 架构设计 ✅ (当前)
Makefile 重写、概念模型设计、实施计划编写

### Phase 4: Workspace 重构 ← 下一步
执行 11 个 task 的实施计划
