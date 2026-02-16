# NanoGridBot Rust 重写可行性评估与实施计划

## Context

NanoGridBot 是一个 AI Agent 开发控制台与轻量级运行时，支持 8 个消息平台、Docker 容器隔离、插件系统和 Web 仪表板。Python 版本已完成 16 个开发阶段，代码成熟（8,854 行源码、640+ 测试、80%+ 覆盖率）。

当前处于 v0.1.0-alpha 阶段，是进行 Rust 重写的最佳时机——用户 API 尚未固化，没有第三方插件生态负担。

---

## 一、可行性评估结论

**结论：可行，推荐执行。** 但需采用分阶段策略，优先重写核心模块。

### 1.1 各模块重写难度评估

| 模块 | Python LOC | Rust 难度 | Rust 收益 | 优先级 |
|------|-----------|----------|----------|--------|
| types（类型系统） | 119 | ⭐ 简单 | 中 | P0 |
| config（配置管理） | 285 | ⭐ 简单 | 中 | P0 |
| database（数据库层） | 1,121 | ⭐ 简单 | 中 | P0 |
| utils（工具函数） | 804 | ⭐⭐ 中等 | 高 | P0 |
| core/router | 139 | ⭐ 简单 | 中 | P1 |
| core/mount_security | 142 | ⭐ 简单 | 高 | P1 |
| core/container_runner | 374 | ⭐⭐ 中等 | 高 | P1 |
| core/container_session | 162 | ⭐⭐ 中等 | 高 | P1 |
| core/group_queue | 353 | ⭐⭐ 中等 | **很高** | P1 |
| core/task_scheduler | 293 | ⭐⭐ 中等 | 中 | P1 |
| core/orchestrator | 366 | ⭐⭐ 中等 | 高 | P1 |
| core/ipc_handler | 245 | ⭐⭐ 中等 | 中 | P1 |
| cli（命令行） | 533 | ⭐⭐ 中等 | 高 | P2 |
| web（仪表板） | 702 | ⭐⭐ 中等 | 中 | P2 |
| channels/base + factory | 336 | ⭐⭐ 中等 | 中 | P3 |
| channels/telegram | 195 | ⭐⭐ 中等 | 中 | P3 |
| channels/discord | 179 | ⭐⭐ 中等 | 中 | P3 |
| channels/wecom | 244 | ⭐⭐ 中等 | 中 | P3 |
| channels/slack | 238 | ⭐⭐⭐ 较难 | 低 | P3 |
| channels/dingtalk | 218 | ⭐⭐⭐ 较难 | 低 | P4 |
| channels/feishu | 201 | ⭐⭐⭐ 较难 | 低 | P4 |
| channels/qq | 205 | ⭐⭐⭐ 较难 | 低 | P4 |
| channels/whatsapp | 220 | ⭐⭐⭐⭐ 困难 | 低 | P4 |
| plugins（插件系统） | 667 | ⭐⭐⭐⭐ 困难 | 中 | P5 |

### 1.2 依赖生态映射

| Python 依赖 | Rust 替代 | 成熟度 | 差距 |
|-------------|----------|--------|------|
| asyncio | tokio | ✅ 优秀 | 无 |
| aiosqlite | sqlx (sqlite) | ✅ 优秀 | 无 |
| aiofiles | tokio::fs | ✅ 优秀 | 无 |
| fastapi | axum | ✅ 优秀 | 无 |
| pydantic | serde + validator | ✅ 优秀 | 无 |
| pydantic-settings | config + dotenvy | ✅ 良好 | 嵌套分隔符需手动处理 |
| loguru | tracing | ✅ 优秀 | 无 |
| croniter | croner | ✅ 良好 | 无 |
| httpx | reqwest | ✅ 优秀 | 无 |
| pyyaml | serde_yaml | ✅ 优秀 | 无 |
| watchdog | notify | ✅ 优秀 | 无 |
| argparse | clap | ✅ 优秀（更好） | 无 |
| python-telegram-bot | reqwest（直接调 Bot API，复用 ZeroClaw 实现） | ✅ 优秀 | 无 |
| discord.py | tokio-tungstenite + reqwest（复用 ZeroClaw 实现） | ✅ 优秀 | 无 |
| slack-sdk | reqwest（复用 ZeroClaw 实现） | ✅ 优秀 | 无 |
| pywa (WhatsApp) | reqwest（复用 ZeroClaw Business Cloud API 实现） | ✅ 优秀 | 无 |
| dingtalk-stream | reqwest + tokio-tungstenite（参考 Nanobot HTTP API 实现） | ✅ 可行 | 无 SDK，需实现 Stream 协议 |
| lark-oapi (Feishu) | reqwest + tokio-tungstenite（参考 Nanobot WebSocket 实现） | ✅ 可行 | 无 SDK，需实现 WS 长连接 |
| nonebot2 (QQ) | reqwest（QQ Bot HTTP API） | ✅ 可行 | 参考 Nanobot qq-botpy 实现 |
| importlib (动态加载) | libloading / wasmtime | ⚠️ 范式不同 | 需重新设计插件架构 |

### 1.3 核心收益

| 收益 | 影响程度 | 说明 |
|------|---------|------|
| 单二进制分发 | **极高** | 无需 Python/pip/venv，下载即用 |
| 启动速度 | 高 | ~10ms vs Python ~500ms+ |
| 内存占用 | 高 | ~10-30MB vs Python ~80-150MB |
| 并发安全 | 高 | 编译期防止数据竞争，GroupQueue 受益最大 |
| 跨平台编译 | 高 | 一台机器构建 Linux/macOS/Windows/ARM |
| 无 GIL 限制 | 中 | 插件 hook 可真正并行执行 |
| 依赖安全 | 中 | 比 PyPI 更少的供应链攻击面 |

### 1.4 主要风险

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| 4 个平台无 Rust SDK | 高 | 直接对接 HTTP/WebSocket API（WeCom 已验证此模式） |
| 插件系统范式转换 | 高 | 先用静态编译插件，后期引入 WASM |
| 重写期间功能冻结 | 中 | 分阶段迁移，Python 版本保持可用 |
| 测试重写工作量 | 中 | 640+ 测试需逐步移植 |
| Rust 学习曲线 | 中 | 从简单模块（types/config）开始 |

---

## 二、Rust 项目架构设计

### 2.1 Cargo Workspace 结构

```
nanogridbot/
├── Cargo.toml                    # Workspace 根配置
├── crates/
│   ├── ngb-types/                # 类型定义（serde structs）
│   │   └── src/lib.rs
│   ├── ngb-config/               # 配置管理 + 热重载
│   │   └── src/lib.rs
│   ├── ngb-db/                   # 数据库层（sqlx SQLite）
│   │   └── src/{lib,connection,groups,messages,tasks,metrics}.rs
│   ├── ngb-core/                 # 核心运行时
│   │   └── src/{lib,orchestrator,router,group_queue,task_scheduler,
│   │           container/runner,container/session,container/security,
│   │           ipc,utils/retry,utils/circuit_breaker,utils/rate_limiter,
│   │           utils/shutdown}.rs
│   ├── ngb-channels/             # 消息通道实现
│   │   └── src/{lib,traits,events,factory,
│   │           telegram,wecom,discord,slack,dingtalk,feishu,qq,whatsapp}.rs
│   ├── ngb-plugins/              # 插件系统
│   │   └── src/{lib,traits,loader,builtin/*}.rs
│   ├── ngb-web/                  # Web 仪表板（axum）
│   │   └── src/{lib,routes,websocket,models}.rs
│   └── ngb-cli/                  # CLI 二进制入口（clap）
│       └── src/main.rs
└── tests/
    ├── unit/
    └── integration/
```

### 2.2 核心依赖选型

```toml
[workspace.dependencies]
# 异步运行时
tokio = { version = "1", default-features = false, features = [
    "rt-multi-thread", "macros", "time", "net", "io-util",
    "sync", "process", "io-std", "fs", "signal"
] }

# Web 框架
axum = { version = "0.7", default-features = false, features = ["http1", "json", "tokio", "query"] }
tower = { version = "0.5", default-features = false }
tower-http = { version = "0.6", default-features = false, features = ["limit", "timeout", "cors", "trace"] }

# 数据库
sqlx = { version = "0.8", features = ["runtime-tokio", "sqlite"] }

# 序列化
serde = { version = "1", default-features = false, features = ["derive"] }
serde_json = { version = "1", default-features = false, features = ["std"] }
toml = "0.8"

# HTTP 客户端（所有 channel 统一使用 reqwest，复用 ZeroClaw 模式）
reqwest = { version = "0.12", default-features = false, features = ["json", "rustls-tls", "multipart", "stream"] }

# CLI
clap = { version = "4.5", features = ["derive"] }

# 配置
dotenvy = "0.15"

# 日志
tracing = { version = "0.1", default-features = false }
tracing-subscriber = { version = "0.3", default-features = false, features = ["fmt", "ansi", "env-filter"] }

# 调度
cron = "0.12"

# 文件监控
notify = "7"

# WebSocket（Discord gateway、DingTalk stream、Feishu 长连接）
tokio-tungstenite = { version = "0.24", features = ["rustls-tls-webpki-roots"] }
futures-util = { version = "0.3", default-features = false, features = ["sink"] }

# 错误处理
thiserror = "2"
anyhow = "1"

# 异步 trait
async-trait = "0.1"

# 工具
uuid = { version = "1", default-features = false, features = ["v4", "std"] }
chrono = { version = "0.4", default-features = false, features = ["clock", "std", "serde"] }
regex = "1"
base64 = "0.22"

# 安全（webhook 签名验证）
hmac = "0.12"
sha2 = "0.10"
hex = "0.4"
```

### 2.3 预估代码量

| 模块 | Python LOC | Rust 倍率 | 预估 Rust LOC |
|------|-----------|----------|--------------|
| Types/Config | 404 | 1.5x | ~600 |
| Core 运行时 | 2,074 | 2.0x | ~4,150 |
| Database | 1,121 | 1.5x | ~1,680 |
| Channels (8个) | 2,198 | 2.0x | ~4,400 |
| Web 仪表板 | 702 | 1.8x | ~1,260 |
| CLI | 533 | 1.3x | ~690 |
| Plugins | 667 | 2.5x | ~1,670 |
| Utils | 804 | 1.5x | ~1,200 |
| 样板代码 | — | — | ~800 |
| **合计** | **8,854** | **~1.8x** | **~16,450** |

测试代码预估：~16,000-18,000 行

---

## 三、分阶段实施计划

### Phase 1：基础层（Foundation）
- 创建 Cargo workspace 结构
- `ngb-types`：移植所有 Pydantic 模型为 serde structs
  - 参考：`src/nanogridbot/types.py`
- `ngb-config`：配置管理 + ConfigWatcher
  - 参考：`src/nanogridbot/config.py`
- `ngb-db`：sqlx SQLite 连接池 + 4 个 Repository
  - 参考：`src/nanogridbot/database/*.py`
- 工具模块：error types (thiserror)、retry、circuit breaker、rate limiter、graceful shutdown
  - 参考：`src/nanogridbot/utils/*.py`
- 日志模块：tracing 配置
  - 参考：`src/nanogridbot/logger.py`

### Phase 2：核心运行时（Core Runtime）
- `ngb-core`：
  - container_runner（tokio::process::Command 调用 Docker）
    - 参考：`src/nanogridbot/core/container_runner.py`
  - container_session（交互式容器会话）
    - 参考：`src/nanogridbot/core/container_session.py`
  - mount_security（路径安全校验）
    - 参考：`src/nanogridbot/core/mount_security.py`
  - ipc_handler（文件 IPC + notify 监控）
    - 参考：`src/nanogridbot/core/ipc_handler.py`
  - group_queue（状态机 + tokio::sync::Mutex 并发控制）
    - 参考：`src/nanogridbot/core/group_queue.py`
  - task_scheduler（croner 定时任务）
    - 参考：`src/nanogridbot/core/task_scheduler.py`
  - router（消息路由）
    - 参考：`src/nanogridbot/core/router.py`
  - orchestrator（总协调器）
    - 参考：`src/nanogridbot/core/orchestrator.py`

### Phase 3：CLI + Web
- `ngb-cli`：clap 实现 5 种模式（serve/shell/run/logs/session）
  - 参考：`src/nanogridbot/cli.py`
- `ngb-web`：axum REST API + WebSocket + 仪表板
  - 参考：`src/nanogridbot/web/app.py`

### Phase 4：消息通道（Channels）— 先 Telegram + WeCom

**关键发现：ZeroClaw 项目可直接复用**

ZeroClaw（`github.com/zeroclaw/`）是一个成熟的 Rust AI Agent 运行时，包含 8 个 channel 实现（~7,269 LOC）、Docker runtime、Gateway 等，代码质量高（1,017 测试）。

**ZeroClaw 可复用资源清单**：

| ZeroClaw 组件 | 路径 | LOC | 复用度 | NanoGridBot 用途 |
|--------------|------|-----|--------|-----------------|
| Channel trait | `src/channels/traits.rs` | 40 | **95%** | `ngb-channels` trait 基础 |
| Telegram | `src/channels/telegram.rs` | 869 | **90%** | 直接引入，改 import 路径 |
| WhatsApp | `src/channels/whatsapp.rs` | 1,110 | **85%** | Business Cloud API，改 JID 格式 |
| Discord | `src/channels/discord.rs` | 691 | **85%** | WebSocket + REST，改 JID 格式 |
| Slack | `src/channels/slack.rs` | 255 | **85%** | HTTP polling，改 JID 格式 |
| RuntimeAdapter trait | `src/runtime/traits.rs` | 33 | **90%** | `ngb-core` 容器抽象 |
| DockerRuntime | `src/runtime/docker.rs` | 200 | **80%** | 容器管理基础，扩展 IPC/Session |
| Gateway (axum) | `src/gateway/mod.rs` | 150+ | **70%** | Web 仪表板 + Webhook 接收 |

**Nanobot 项目可复用资源（Python，作为 Rust 移植参考）**

Nanobot（`github.com/nanobot/`）是 Python 实现，但其中国平台 channel 实现质量极高，是 ZeroClaw 没有覆盖的关键补充：

| Nanobot 组件 | 路径 | LOC | 价值 | 用途 |
|-------------|------|-----|------|------|
| DingTalk | `nanobot/channels/dingtalk.py` | 245 | **⭐⭐⭐⭐⭐** | Stream Mode + HTTP API 发送，token 生命周期管理 |
| Feishu | `nanobot/channels/feishu.py` | 310 | **⭐⭐⭐⭐⭐** | WebSocket 长连接，Markdown 表格→飞书卡片，emoji 反应 |
| QQ | `nanobot/channels/qq.py` | 134 | **⭐⭐⭐⭐** | qq-botpy SDK，C2C 私聊，消息去重 |
| Mochat | `nanobot/channels/mochat.py` | 895 | **⭐⭐⭐⭐⭐** | Socket.IO 双模式（WS+轮询），状态持久化，消息缓冲 |
| BaseChannel | `nanobot/channels/base.py` | 127 | **⭐⭐⭐⭐** | 消息总线模式，allowlist 权限检查 |
| ChannelManager | `nanobot/channels/manager.py` | 227 | **⭐⭐⭐⭐** | 工厂模式，懒加载 SDK，异步调度 |

**Nanobot 中国平台关键实现细节（Rust 移植参考）**：

1. **DingTalk**（reqwest 直接移植）：
   - 接收：dingtalk-stream SDK WebSocket → Rust 用 tokio-tungstenite 实现
   - 发送：HTTP API `POST /v1.0/robot/oToMessages/batchSend`（Markdown 格式）
   - Token：`POST /v1.0/oauth2/accessToken`，带 60s 提前过期刷新
   - 参考：`github.com/nanobot/nanobot/channels/dingtalk.py`

2. **Feishu**（reqwest + tokio-tungstenite 移植）：
   - 接收：lark-oapi WebSocket 长连接 → Rust 用 tokio-tungstenite
   - 发送：REST API `POST /open-apis/im/v1/messages`（飞书卡片格式）
   - 特色：Markdown 表格解析为飞书 table 元素，emoji 反应
   - ID 格式：`oc_` 前缀为群聊，`ou_` 前缀为用户
   - 参考：`github.com/nanobot/nanobot/channels/feishu.py`

3. **QQ**（OneBot 协议移植）：
   - qq-botpy SDK 封装 → Rust 用 HTTP/WebSocket 实现 QQ Bot API
   - C2C 私聊消息，deque 去重
   - 参考：`github.com/nanobot/nanobot/channels/qq.py`

**ZeroClaw Channel trait 设计**（简洁优雅，直接采用）：
```rust
#[async_trait]
pub trait Channel: Send + Sync {
    fn name(&self) -> &str;
    async fn send(&self, message: &str, recipient: &str) -> anyhow::Result<()>;
    async fn listen(&self, tx: mpsc::Sender<ChannelMessage>) -> anyhow::Result<()>;
    async fn health_check(&self) -> bool { true }
    async fn start_typing(&self, _recipient: &str) -> anyhow::Result<()> { Ok(()) }
    async fn stop_typing(&self, _recipient: &str) -> anyhow::Result<()> { Ok(()) }
}
```

需要扩展的部分：
- 添加 `disconnect()` 方法（ZeroClaw 的 listen 是长运行的，NanoGridBot 需要显式断开）
- 添加 JID 解析/构建方法（`parse_jid`/`build_jid`）以支持统一寻址
- 添加 `receive_message()` 用于 webhook 模式的消息解析

**实施顺序**（综合 ZeroClaw Rust 代码 + Nanobot Python 参考）：

| 批次 | 平台 | 来源 | 方式 | 预估 LOC |
|------|------|------|------|---------|
| 1 | Telegram | ZeroClaw `src/channels/telegram.rs` | 直接引入，改 JID 格式 | ~900 |
| 1 | WeCom | NanoGridBot `src/nanogridbot/channels/wecom.py` | reqwest 重写（已是纯 HTTP） | ~300 |
| 2 | Discord | ZeroClaw `src/channels/discord.rs` | 直接引入 | ~700 |
| 2 | Slack | ZeroClaw `src/channels/slack.rs` | 直接引入 | ~300 |
| 3 | DingTalk | Nanobot `nanobot/channels/dingtalk.py` | reqwest + tokio-tungstenite 移植 | ~350 |
| 3 | Feishu | Nanobot `nanobot/channels/feishu.py` | reqwest + tokio-tungstenite 移植 | ~400 |
| 4 | QQ | Nanobot `nanobot/channels/qq.py` | QQ Bot HTTP API 实现 | ~250 |
| 4 | WhatsApp | ZeroClaw `src/channels/whatsapp.rs` | 直接引入（Business Cloud API） | ~1,100 |

**ZeroClaw DockerRuntime 复用**（`src/runtime/docker.rs`）：
- `build_shell_command()` 构建 Docker CLI 参数 — 直接复用
- workspace 路径校验 + allowlist — 对应 NanoGridBot 的 `mount_security.py`
- 内存/CPU 限制 — 直接复用
- 需扩展：IPC handler、ContainerSession（交互式会话）、GroupQueue 集成

### Phase 5：插件系统（Rust 最佳实践，不复现 Python importlib）

**设计思路**：NanoGridBot 的核心价值是容器封装 Claude Code。Python 的 `importlib` 动态加载主要服务于方便操控容器内的 Claude Code，而 Rust 对容器的操控能力（tokio::process、直接 Docker API）本身就是最强的，完全不需要死板复现 Python 的动态加载范式。

**Python 版插件系统回顾**（仅作参考，不复现）：
- `importlib` 动态加载 + watchdog 热重载 + 6 个生命周期 Hook
- PluginAPI 安全接口 + JSON 配置
- 参考：`src/nanogridbot/plugins/{base,loader,api}.py`

**Rust 实施策略**：

**Phase 5a — 静态编译插件（首选）**：
- 定义 Plugin trait（保留 6 个 Hook 接口语义）
- 3 个内置插件（rate_limiter、auto_reply、mention）编译进二进制
- 零运行时开销，类型安全，编译期检查
- Feature flags 控制插件启用/禁用

**Phase 5b — WASM 插件（后期升级，可选）**：
- wasmtime 加载 `.wasm` 文件
- 沙箱隔离 + 多语言支持 + 安全热重载
- 比 Python importlib **全面升级**：安全性、跨平台、多语言

**Phase 5c — 容器操控增强（核心价值）**：
- 利用 Rust 的 tokio::process 直接管理 Docker 容器
- 复用 ZeroClaw 的 `RuntimeAdapter` trait + `DockerRuntime`
- 扩展 ContainerSession 支持交互式多轮对话
- IPC 通过文件系统 JSON 或 Unix socket（比 Python 版更高效）

### Phase 6：测试 + 打磨
- 移植 640+ 测试到 Rust
- 集成测试、E2E 测试
- 性能基准测试（vs Python 版本）
- CI/CD 流水线（跨平台编译）
- 文档更新

---

## 五、架构决策：NGB vs ZeroClaw 关系定位

### 5.1 核心架构差异

| 维度 | ZeroClaw | NanoGridBot |
|------|----------|------------|
| 定位 | 单 Agent 自治运行时 | 多组 Agent 开发控制台 + 运行时 |
| Agent 模型 | 单 Agent，进程内直接调 LLM | 多组 Agent，容器封装 Claude Code |
| 并发 | 单 Agent 循环处理所有消息 | 每组独立容器，GroupQueue 并发管理 |
| LLM 调用 | 进程内 Provider 路由（22+ 提供商） | 委托给容器内 Claude Code |
| 状态管理 | 文件系统 + workspace 文件 | SQLite 数据库中心化 |
| Web UI | 无（CLI only） | FastAPI 完整仪表板 + WebSocket |
| 多租户 | 无（单 Agent） | 有（Group + JID 统一寻址） |
| IPC | 无（进程内执行） | 文件 JSON IPC + 容器 stdin/stdout |
| CLI 模式 | daemon/gateway/agent | serve/shell/run/logs/session |
| 调度 | cron 单一类型 | CRON + INTERVAL + ONCE 三种 |

### 5.2 决策：只引入 ZeroClaw 部分模块，不向其架构倾斜

**理由**：
1. NGB 的核心价值是**容器封装 Claude Code + 多组并发管理 + Web 仪表板**，ZeroClaw 完全没有这些
2. ZeroClaw 的 Agent Loop（进程内调 LLM）与 NGB 的容器委托模式是根本不同的架构范式
3. NGB 的 GroupQueue 状态机、ContainerSession、IPC、多类型调度器是差异化能力
4. 向 ZeroClaw 倾斜会丢失 NGB 的多租户和开发控制台定位

### 5.3 从 ZeroClaw 引入的模块（仅基础设施层）

| ✅ 引入 | ❌ 不引入 | 原因 |
|---------|----------|------|
| Channel trait + 4 个 channel | Agent Loop | NGB 用容器模式，不在进程内调 LLM |
| DockerRuntime（命令构建） | Provider 系统（22+ LLM） | NGB 委托给容器内 Claude Code |
| Gateway webhook 模式 | Memory 系统 | NGB 用 SQLite 数据库 |
| HMAC 签名验证工具 | Skills 系统 | NGB 用 Plugin trait |
| 依赖版本选型 | Security Policy | NGB 有容器隔离 + mount 校验 |
| release profile 优化 | Daemon/Service 模式 | NGB 有自己的 5 种 CLI 模式 |
| Cargo.toml default-features 优化 | Observability (OTel) | 后期按需引入 |

### 5.4 存储架构决策：NGB SQLite vs ZeroClaw Memory

**两者存储内容完全不同，不是替代关系**：

| | NGB SQLite | ZeroClaw Memory |
|---|-----------|----------------|
| 存储内容 | 运营数据（消息、群组、任务、指标） | Agent 知识（记忆、会话、向量嵌入） |
| 查询方式 | 结构化（JID + 时间戳索引） | 语义搜索（FTS5 + 向量余弦混合） |
| 语义搜索 | ❌ 无 | ✅ 混合搜索（0.7 向量 + 0.3 关键词） |
| 适合场景 | 仪表板、调度、指标 | "Agent 之前学到了什么？" |

**决策：Phase 1 用 NGB SQLite，后期可选引入 ZeroClaw Memory 设计**
- 运营层（NGB SQLite）：群组管理、任务调度、消息历史、容器指标 — 核心需求
- 智能层（ZeroClaw Memory 思路）：Agent 知识记忆、语义搜索 — Phase 6+ 增强功能

### 5.5 扩展性决策：Plugin trait vs Skills

**ZeroClaw Skills ≠ Agent Skills（Claude/MCP），是 Prompt 模板注入**：

| | ZeroClaw Skills | NGB Plugins |
|---|----------------|-------------|
| 本质 | Prompt 模板（SKILL.md）+ 工具元数据 | 消息/容器生命周期 Hook |
| 执行者 | Agent 自主决定是否使用 | 框架主动调用 |
| 用途 | 扩展 Agent 知识和能力 | 控制消息流程（限流、过滤、变换） |
| 与 MCP | ❌ 不兼容 | N/A（不同层面） |
| 热重载 | ❌ 手动 git pull | ✅ watchdog 自动 |

**决策：保留 Plugin trait，Skills 作为可选增强**
- Plugin trait（Phase 5a 必须）：NGB 核心是编排控制，Hook 机制不可替代
- Skills 概念（Phase 6+ 可选）：如需扩展容器内 Claude Code 能力，可参考 ZeroClaw SKILL.md 模式

### 5.6 NGB 独有架构（必须自行实现）

- `ngb-core/orchestrator` — 多组协调器（ZeroClaw 无对应）
- `ngb-core/group_queue` — 并发状态机（ZeroClaw 无对应）
- `ngb-core/container_session` — 交互式容器会话（ZeroClaw 无对应）
- `ngb-core/ipc_handler` — 容器 IPC 通信（ZeroClaw 无对应）
- `ngb-core/task_scheduler` — 多类型调度器（ZeroClaw 仅 cron）
- `ngb-web` — 完整 Web 仪表板（ZeroClaw 无对应）
- `ngb-db` — SQLite 数据库层（ZeroClaw 用文件系统）
- `ngb-plugins` — Plugin trait + 生命周期 Hook（ZeroClaw 用 Skills）

---

## 六、验证方案

### 6.1 每阶段验证
- Phase 1：`cargo test` 通过所有类型序列化/反序列化测试，数据库 CRUD 测试
- Phase 2：容器启动/停止测试，消息队列并发测试，调度器定时触发测试
- Phase 3：`nanogridbot serve` 启动成功，Web API 响应正确，CLI 各模式可用
- Phase 4：每个通道的 connect/send/receive 集成测试
- Phase 5：插件加载/卸载/hook 执行测试
- Phase 6：全量回归测试，性能对比报告

### 6.2 功能对等验证
- 对比 Python 版本的 640+ 测试用例，确保 Rust 版本覆盖相同场景
- 使用相同的 SQLite 数据库 schema，验证数据兼容性
- 使用相同的 Docker 命令格式，验证容器交互兼容性

### 6.3 性能基准
- 启动时间对比
- 内存占用对比
- 并发消息处理吞吐量对比
- 容器启动延迟对比
