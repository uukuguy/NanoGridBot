# Next Session Guide

## Current Status

**Phase**: Rust 重写 - Phase 3 准备中 🚀
**Date**: 2026-02-17
**Branch**: build-by-rust
**Project Status**: Phase 2 核心运行时已完成，准备开始 Phase 3

---

## 2026-02-17 - Phase 2 核心运行时完成 ✅

### 本阶段成果

在 `ngb-core` 中实现了 8 个核心运行时模块，将 ngb-core 从工具库转变为完整的容器编排运行时：

| 模块 | 功能 | 测试数 |
|------|------|--------|
| `mount_security.rs` | Docker 挂载验证、路径白名单 | 6 |
| `container_runner.rs` | Docker 容器执行、输出解析 | 10 |
| `container_session.rs` | 交互式容器会话、文件 IPC | 6 |
| `ipc_handler.rs` | ChannelSender trait + 文件 IPC 处理 | 7 |
| `group_queue.rs` | 并发容器管理、状态机、重试 | 12 |
| `task_scheduler.rs` | CRON/INTERVAL/ONCE 调度 | 13 |
| `router.rs` | 消息路由、触发器匹配 | 7 |
| `orchestrator.rs` | 总协调器、消息循环、健康状态 | 10 |

**测试统计**：
| Crate | 测试数 |
|-------|--------|
| `ngb-core` | 103 (32 Phase 1 + 71 Phase 2) |
| `ngb-db` | 27 |
| `ngb-types` | 22 |
| `ngb-config` | 10 |
| **总计** | **162** |

**验证结果**：
- `cargo build` ✅
- `cargo test` — 162 个测试全部通过 ✅
- `cargo clippy -- -D warnings` — 零警告 ✅
- `cargo fmt -- --check` — 格式一致 ✅

### 关键技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| ChannelSender trait 异步方法 | `Pin<Box<dyn Future>>` | MSRV Rust 1.75 不支持原生 async fn in traits |
| CRON 解析 | `cron` 0.12 (7-field 格式) | 5-field 转 7-field: prepend "0", append "*" |
| Docker 交互 | `tokio::process::Command` | 与 Python 版一致，无需额外 SDK |
| 并发锁策略 | `tokio::sync::Mutex` + `tokio::spawn` | 避免 hold lock across await |
| 群组队列状态机 | 辅助函数 `ensure_state`/`try_activate` | 解决 HashMap borrow checker 冲突 |
| IPC 写入 | 原子写入 (tmp + rename) | 避免文件竞争 |
| 重试策略 | 指数退避 `5 * 2^(n-1)` 秒, 最多 5 次 | 平衡响应速度和系统负载 |

### 新增依赖

| 依赖 | 用途 |
|------|------|
| `cron = "0.12"` | CRON 表达式解析 |
| `ngb-db` (内部) | ngb-core 依赖 ngb-db (orchestrator 等需要数据库操作) |
| `tempfile = "3"` (dev) | IPC 和容器会话测试 |

---

## 下一阶段：Phase 3 Web API + CLI

### 目标

实现 `ngb-web` (REST API + WebSocket) 和 `ngb-cli` (命令行接口)。

### 模块清单

#### 1. ngb-web — Web API 和监控面板
- 使用 `axum` 框架 (async, tower-compatible)
- REST API 端点:
  - `GET /api/health` — 健康检查
  - `GET /api/groups` — 群组列表
  - `GET /api/tasks` — 任务列表
  - `GET /api/messages` — 最近消息
  - `GET /api/metrics/containers` — 容器统计
  - `POST /api/groups` — 注册群组
  - `DELETE /api/groups/{jid}` — 注销群组
- WebSocket `/ws` — 实时状态更新
- 静态文件服务 (Vue.js 前端)
- **参考**: `src/nanogridbot/web/app.py`

#### 2. ngb-cli — 命令行接口
- 使用 `clap` 框架 (derive API)
- 子命令: `serve`, `shell`, `run`, `logs`, `session`
- `serve` — 启动 orchestrator + web server
- `shell` — 交互式容器 shell (ContainerSession)
- `run` — 一次性容器执行
- `logs` — 查看日志
- `session` — 管理会话 (ls/kill)
- **参考**: `src/nanogridbot/cli.py`

### 新增依赖（预估）

| 依赖 | 用途 |
|------|------|
| `axum` | Web 框架 |
| `tower` / `tower-http` | 中间件 (CORS, logging) |
| `clap` | CLI 参数解析 |
| `tokio-tungstenite` | WebSocket |

### 验证标准
- Web API 端点可访问
- CLI 子命令正常执行
- `cargo test` + `cargo clippy -- -D warnings` 全部通过

### 关键注意事项

1. **Phase 2 已有的核心运行时**：Orchestrator, GroupQueue, TaskScheduler 等均已实现，Phase 3 只需在 Web/CLI 层调用
2. **Orchestrator 是核心入口**：Web API 和 CLI 都通过 Orchestrator 操作
3. **ChannelSender trait**：使用 `Pin<Box<dyn Future>>` 风格，非原生 async fn in traits
4. **测试策略**：Web API 测试使用 axum::test_helpers，CLI 测试使用 assert_cmd

### 依赖图更新

```
ngb-types (零依赖)
    ↓
ngb-config (← ngb-types)
    ↓           ↓
ngb-db      ngb-core [Phase 1: utils + Phase 2: runtime]
(← types    (← types + config + db)
 + config)      ↓
            ngb-web (← ngb-core + ngb-db + ngb-types + ngb-config)
            ngb-cli (← ngb-web + ngb-core + ngb-db + ngb-types + ngb-config)
```

---

## 历史记录

<details>
<summary>Phase 2 之前的历史（点击展开）</summary>

### 2026-02-17 - Phase 1 基础层完成

成功创建 Cargo workspace 并实现 4 个基础 crate + 4 个 stub crate：
- ngb-types: 22 测试
- ngb-config: 10 测试
- ngb-db: 27 测试
- ngb-core (utils): 32 测试
- 总计 91 测试

### 2026-02-17 - Rust 重写可行性评估完成

完成了 NanoGridBot Python→Rust 重写的全面可行性评估，产出设计文档 `docs/design/RUST_REWRITE_DESIGN.md`。

### Python 版本完成状态

- 16 个开发阶段全部完成
- 8,854 行源码、640+ 测试、80%+ 覆盖率
- 8 个消息平台、5 个 CLI 模式

</details>

---

**Created**: 2026-02-13
**Updated**: 2026-02-17
**Project Status**: Phase 2 核心运行时完成 — 准备进入 Phase 3 Web API + CLI
