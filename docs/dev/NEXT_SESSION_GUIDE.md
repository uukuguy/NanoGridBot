# Next Session Guide

## Current Status

**Phase**: Rust 重写 - Phase 3 MVP 实现完成 ✅
**Date**: 2026-02-17
**Branch**: build-by-rust
**Project Status**: Phase 3 MVP 全部 8 个 Task 实现完成，181 tests passing

---

## 2026-02-17 - Phase 3 MVP 实现完成 ✅

### 本阶段成果

实现了最小可运行的智能体系统：Telegram 接收消息 → Docker 容器运行 Claude Code → 回复用户

| Task | 内容 | 文件 | 新增测试 |
|------|------|------|----------|
| 1 | agent-runner 从 nanoclaw 适配 | `container/agent-runner/src/{index,ipc-mcp-stdio}.ts` | — |
| 2 | Dockerfile + build.sh | `container/{Dockerfile,build.sh}` | — |
| 3 | format_messages() 消息格式化 | `crates/ngb-core/src/router.rs` | 3 |
| 4 | Session ID 持久化 | `crates/ngb-db/src/sessions.rs` | 3 |
| 5 | 容器启动准备 | `crates/ngb-core/src/container_prep.rs` | 9 |
| 6 | Telegram Channel 适配器 | `crates/ngb-channels/src/telegram.rs` | 4 |
| 7 | CLI serve 子命令 | `crates/ngb-cli/src/main.rs` | — |
| 8 | 集成验证 | 全 workspace | — |

**测试统计**：
| Crate | 测试数 |
|-------|--------|
| `ngb-channels` | 4 (新) |
| `ngb-config` | 10 |
| `ngb-core` | 115 (103 + 12 新) |
| `ngb-db` | 30 (27 + 3 新) |
| `ngb-types` | 22 |
| **总计** | **181** |

**验证结果**：
- `cargo build --workspace` ✅
- `cargo test --workspace` — 181 个测试全部通过 ✅
- `cargo clippy --workspace -- -D warnings` — 零警告 ✅
- `cargo fmt --all -- --check` — 格式一致 ✅
- `ngb --help` — CLI 正常输出 ✅

### 新增依赖

| 依赖 | 用途 |
|------|------|
| `teloxide = "0.13"` | Telegram Bot API |
| `clap = "4"` | CLI 参数解析 |
| `anyhow = "1"` | CLI 错误处理 |
| `dotenvy = "0.15"` | CLI 环境变量加载 |

---

## 下一阶段：端到端验证 + P1 增强

### 优先级 1：端到端验证（用户手动执行）

1. 构建 Docker 镜像：`cd container && ./build.sh`
2. 配置 `.env`：
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   TELEGRAM_BOT_TOKEN=123456:ABC...
   ```
3. 创建 `groups/main/CLAUDE.md`（agent 指令文件）
4. 注册 Telegram group 到数据库
5. 运行：`cargo run -p ngb-cli -- serve`
6. 在 Telegram 中发送 `@Andy hello`，验证收到回复

### 优先级 2：P1 增强（MVP 跑通后）

| Gap | 内容 | 影响 |
|-----|------|------|
| Gap 1 | 流式输出解析（实时 marker-based） | 用户更快看到回复 |
| Gap 2 | Idle timeout + _close sentinel | 容器保活，减少启动开销 |
| Gap 3 | 消息管道到活跃容器 | 多轮对话不需新容器 |

### 优先级 3：Web API + 更多 CLI 子命令

- `ngb-web`：axum REST API + WebSocket 监控
- CLI 扩展：`shell`, `run`, `logs`, `session` 子命令

### 依赖图

```
ngb-types (零依赖)
    ↓
ngb-config (← ngb-types)
    ↓           ↓
ngb-db      ngb-core [Phase 1 utils + Phase 2 runtime + Phase 3 container_prep]
(← types    (← types + config + db)
 + config)      ↓
            ngb-channels (← ngb-types + ngb-core + ngb-db + ngb-config + teloxide)
                ↓
            ngb-cli (← ngb-channels + ngb-core + ngb-db + ngb-config + clap)
```

---

## 历史记录

<details>
<summary>Phase 2 之前的历史（点击展开）</summary>

### 2026-02-17 - Phase 2 核心运行时完成

在 `ngb-core` 中实现了 8 个核心运行时模块（container_runner, container_session, ipc_handler, group_queue, task_scheduler, router, orchestrator, mount_security），162 tests passing。

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
**Project Status**: Phase 3 MVP 实现完成 — 准备端到端验证
