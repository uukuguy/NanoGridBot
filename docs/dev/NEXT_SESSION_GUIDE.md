# Next Session Guide

## Current Status

**Phase**: Rust 重写 - Phase 2 核心运行时 🚀
**Date**: 2026-02-17
**Branch**: build-by-rust
**Project Status**: Phase 1 基础层已完成，准备开始 Phase 2 核心运行时实现

---

## 2026-02-17 - Phase 1 基础层完成 ✅

### 本阶段成果

成功创建 Cargo workspace 并实现 4 个基础 crate + 4 个 stub crate：

| Crate | 内容 | 测试数 |
|-------|------|--------|
| `ngb-types` | 4 枚举 + 7 结构体 + 错误类型 | 22 |
| `ngb-config` | Config (40+ 字段) + ConfigWatcher | 10 |
| `ngb-db` | Database + 4 个 Repository (messages, groups, tasks, metrics) | 27 |
| `ngb-core` | retry, circuit_breaker, shutdown, rate_limiter, security, formatting, logging | 32 |
| `ngb-channels` | Stub (Phase 4) | 0 |
| `ngb-plugins` | Stub (Phase 5) | 0 |
| `ngb-web` | Stub (Phase 3) | 0 |
| `ngb-cli` | Stub (Phase 3) | 0 |

**验证结果**：
- `cargo build` ✅
- `cargo test` — 91 个测试全部通过 ✅
- `cargo clippy -- -D warnings` — 零警告 ✅
- `cargo fmt -- --check` — 格式一致 ✅

### 关键技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| SQL 查询方式 | `sqlx::query()` 运行时检查 | 避免编译时需要 DATABASE_URL |
| 时间戳格式 | RFC 3339 字符串 | 与 Python SQLite 数据兼容 |
| Config 单例 | `OnceLock<RwLock<Config>>` | 线程安全 + 支持热重载 |
| LRU 缓存 | `Mutex<lru::LruCache>` | 快速操作，无 I/O |
| 文件监控 | notify v7 独立线程 | 不与 tokio 事件循环冲突 |
| Default derive | `#[derive(Default)]` + `#[default]` | clippy 推荐，比手写 impl 更惯用 |

---

## 下一阶段：Phase 2 核心运行时实现

### 目标

实现 `ngb-core` 的核心运行时模块，完成容器管理、消息路由、任务调度等功能。

### 模块清单

#### 1. container_runner — Docker 容器运行器
- 使用 `tokio::process::Command` 调用 Docker
- 挂载验证、环境变量注入、资源限制 (CPU/内存)
- 输出解析 (JSON/纯文本)
- 超时处理、状态查询、容器清理
- **参考**: `src/nanogridbot/core/container_runner.py` (374 行)

#### 2. container_session — 交互式容器会话
- 命名容器（非 `--rm`）支持会话恢复
- 文件系统 IPC 输入/输出交换
- 会话生命周期管理 (start/send/receive/close)
- **参考**: `src/nanogridbot/core/container_session.py` (162 行)

#### 3. mount_security — 路径安全校验
- 注意：Phase 1 的 `security.rs` 已包含基础路径验证
- Phase 2 需扩展为完整的挂载安全模块
- 安全前缀白名单、遍历防护、主组限制
- **参考**: `src/nanogridbot/core/mount_security.py` (142 行)

#### 4. ipc_handler — 文件 IPC 处理器
- notify 监控 IPC 目录
- 输入/输出文件处理
- 通道响应路由
- **参考**: `src/nanogridbot/core/ipc_handler.py` (245 行)

#### 5. group_queue — 群组队列管理
- 状态机 + `tokio::sync::Mutex` 并发控制
- 消息/任务队列
- 指数退避重试
- 并发容器管理
- **参考**: `src/nanogridbot/core/group_queue.py` (353 行)
- **收益最高**：Rust 并发安全在此模块价值最大

#### 6. task_scheduler — 任务调度器
- CRON/INTERVAL/ONCE 三种调度类型
- 使用 `croner` crate 替代 Python croniter
- 任务生命周期管理
- **参考**: `src/nanogridbot/core/task_scheduler.py` (293 行)

#### 7. router — 消息路由
- 消息路由到注册群组
- 触发器模式匹配
- 群组广播
- **参考**: `src/nanogridbot/core/router.py` (139 行)

#### 8. orchestrator — 总协调器
- 全局状态管理
- 通道连接/断开
- 消息轮询循环
- 群组注册
- 健康状态跟踪
- **参考**: `src/nanogridbot/core/orchestrator.py` (366 行)

### 新增依赖（预估）

| 依赖 | 用途 |
|------|------|
| `croner` | CRON 表达式解析 |
| `bollard` 或 `tokio::process` | Docker 交互 |
| `uuid` | 会话/请求 ID 生成 |

### 验证标准
- 容器启动/停止测试
- 消息队列并发测试
- 调度器定时触发测试
- `cargo test` + `cargo clippy -- -D warnings` 全部通过

### 关键注意事项

1. **Phase 1 已有基础设施**：retry、circuit_breaker、shutdown、rate_limiter、security、formatting 已在 `ngb-core` 实现，Phase 2 直接使用
2. **避免过度设计**：先实现核心功能，channel trait 和插件系统留给后续 Phase
3. **Docker 交互方式**：优先使用 `tokio::process::Command` 直接调用 docker CLI（与 Python 版本一致），暂不引入 bollard SDK
4. **IPC 模式**：保持文件系统 IPC 设计（与 Python 版本兼容）
5. **参考 ZeroClaw**：`RuntimeAdapter` trait 和 `DockerRuntime` 可作为参考（约 233 行 Rust 代码）

### 依赖图更新

```
ngb-types (zero deps)
    ↓
ngb-config (← ngb-types)
    ↓           ↓
ngb-db      ngb-core [Phase 1: utils/security/formatting/logging]
(← types     ↓
 + config)  ngb-core [Phase 2: container_runner, ipc_handler, group_queue,
            task_scheduler, router, orchestrator]
            (← types + config + db)
```

注意：Phase 2 的 ngb-core 需要新增对 ngb-db 的依赖（orchestrator 需要数据库操作）。

---

## 历史记录

<details>
<summary>Phase 1 之前的历史（点击展开）</summary>

### 2026-02-17 - Rust 重写可行性评估完成

完成了 NanoGridBot Python→Rust 重写的全面可行性评估，产出设计文档 `docs/design/RUST_REWRITE_DESIGN.md`。

### 2026-02-17 - GitHub About & Topics 优化完成

更新 pyproject.toml 和 GitHub 仓库设置。

### 2026-02-16 - README.md 修订完成 / 功能框架增强完成

CLI 重构、容器环境变量、配置热重载、日志会话增强、监控指标。

### Python 版本完成状态

- 16 个开发阶段全部完成
- 8,854 行源码、640+ 测试、80%+ 覆盖率
- 8 个消息平台、5 个 CLI 模式

</details>

---

**Created**: 2026-02-13
**Updated**: 2026-02-17
**Project Status**: Phase 1 基础层完成 — 准备进入 Phase 2 核心运行时
