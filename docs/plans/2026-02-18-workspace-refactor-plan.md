# Workspace 架构重构实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 NGB 从以 group/JID 为中心的模型重构为以 Workspace 为中心的模型，支持 token 绑定机制。

**Architecture:** RegisteredGroup 拆分为 Workspace + ChannelBinding + AccessToken 三个概念。Router 改为两步查找（先查 binding 找 workspace，未绑定则回复引导信息）。CLI 新增 workspace create/list 子命令。

**Tech Stack:** Rust (sqlx, clap, teloxide), SQLite, Docker

**设计文档:** `docs/plans/2026-02-18-workspace-architecture.md`

**影响范围:** 21 个 Rust 文件，247 处 group 相关引用

---

## Phase A: 概念重构

### Task 1: 新增 Workspace 和 ChannelBinding 类型 (ngb-types)

**Files:**
- Create: `crates/ngb-types/src/workspace.rs`
- Create: `crates/ngb-types/src/binding.rs`
- Modify: `crates/ngb-types/src/lib.rs`

**Step 1: 创建 workspace.rs**

```rust
// crates/ngb-types/src/workspace.rs
use std::collections::HashMap;
use serde::{Deserialize, Serialize};

/// Workspace — 智能体开发项目的隔离工作环境。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Workspace {
    pub id: String,
    pub name: String,
    pub owner: String,
    pub folder: String,
    #[serde(default)]
    pub shared: bool,
    #[serde(default)]
    pub container_config: Option<HashMap<String, serde_json::Value>>,
}
```

**Step 2: 创建 binding.rs**

```rust
// crates/ngb-types/src/binding.rs
use serde::{Deserialize, Serialize};

/// ChannelBinding — 将 IM chat 映射到 workspace。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChannelBinding {
    pub channel_jid: String,
    pub workspace_id: String,
}

/// AccessToken — 用于 IM 侧绑定 workspace。
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccessToken {
    pub token: String,
    pub workspace_id: String,
    pub used: bool,
}
```

**Step 3: 更新 lib.rs 导出**

在 `crates/ngb-types/src/lib.rs` 中添加模块声明和 re-export：
```rust
pub mod binding;
pub mod workspace;

pub use binding::{AccessToken, ChannelBinding};
pub use workspace::Workspace;
```

保留 `group.rs` 和 `RegisteredGroup` 暂不删除（后续 task 逐步迁移后再删）。

**Step 4: 编译验证**

Run: `cargo check -p ngb-types`
Expected: PASS

**Step 5: 写单元测试**

在 workspace.rs 和 binding.rs 中各加 serde roundtrip 测试。

Run: `cargo test -p ngb-types`
Expected: PASS (原有 22 + 新增测试)

**Step 6: Commit**

```bash
git add crates/ngb-types/src/{workspace,binding}.rs crates/ngb-types/src/lib.rs
git commit -m "feat(types): add Workspace, ChannelBinding, AccessToken types"
```

---

### Task 2: 新增数据库表和 Repository (ngb-db)

**Files:**
- Create: `crates/ngb-db/src/workspaces.rs`
- Create: `crates/ngb-db/src/bindings.rs`
- Create: `crates/ngb-db/src/tokens.rs`
- Modify: `crates/ngb-db/src/connection.rs` (添加新表到 initialize)
- Modify: `crates/ngb-db/src/lib.rs` (添加模块和 re-export)

**Step 1: 在 connection.rs initialize() 末尾添加三张新表**

在 sessions 表之后、`info!` 之前添加：

```rust
// Workspaces table
sqlx::query(
    "CREATE TABLE IF NOT EXISTS workspaces (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        owner TEXT NOT NULL DEFAULT '',
        folder TEXT NOT NULL,
        shared INTEGER NOT NULL DEFAULT 0,
        container_config TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )",
)
.execute(&self.pool)
.await
.map_err(|e| NanoGridBotError::Database(format!("Create workspaces table: {e}")))?;

// Channel bindings table
sqlx::query(
    "CREATE TABLE IF NOT EXISTS channel_bindings (
        channel_jid TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        bound_at TEXT NOT NULL DEFAULT (datetime('now'))
    )",
)
.execute(&self.pool)
.await
.map_err(|e| NanoGridBotError::Database(format!("Create channel_bindings table: {e}")))?;

// Access tokens table
sqlx::query(
    "CREATE TABLE IF NOT EXISTS access_tokens (
        token TEXT PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        expires_at TEXT,
        used INTEGER NOT NULL DEFAULT 0
    )",
)
.execute(&self.pool)
.await
.map_err(|e| NanoGridBotError::Database(format!("Create access_tokens table: {e}")))?;
```

更新 info 行：`"Database schema initialized (9 tables, 5 indexes)"`

**Step 2: 创建 workspaces.rs**

实现 `WorkspaceRepository`，方法：`save`, `get`, `get_all`, `delete`, `exists`。
参考 `groups.rs` 的模式，字段改为 Workspace 的字段。

**Step 3: 创建 bindings.rs**

实现 `BindingRepository`，方法：`bind`, `unbind`, `get_by_jid`, `get_by_workspace`, `exists`。

**Step 4: 创建 tokens.rs**

实现 `TokenRepository`，方法：`create_token`, `validate_and_consume`, `get_by_workspace`。
`create_token` 生成 `ngb-` 前缀的 12 位随机 hex token。

**Step 5: 更新 lib.rs**

```rust
pub mod bindings;
pub mod tokens;
pub mod workspaces;

pub use bindings::BindingRepository;
pub use tokens::TokenRepository;
pub use workspaces::WorkspaceRepository;
```

**Step 6: 写测试**

每个 repository 至少 5 个测试（CRUD + edge case）。

Run: `cargo test -p ngb-db`
Expected: PASS (原有 30 + 新增约 15 测试)

**Step 7: Commit**

```bash
git add crates/ngb-db/src/{workspaces,bindings,tokens,connection,lib}.rs
git commit -m "feat(db): add workspaces, channel_bindings, access_tokens tables and repositories"
```

---

### Task 3: 重构 Config — groups_dir → workspaces_dir (ngb-config)

**Files:**
- Modify: `crates/ngb-config/src/config.rs`

**Step 1: 在 Config struct 中添加 workspaces_dir，保留 groups_dir**

```rust
pub workspaces_dir: PathBuf,
```

在 `Config::load()` 中：
```rust
let workspaces_dir = env_path_or("WORKSPACES_DIR", || base.join("workspaces"));
```

同时保留 `groups_dir`（向后兼容，后续 task 迁移完再删）。

在 `create_directories()` 中添加 `self.workspaces_dir.clone()` 到 dirs 数组。

**Step 2: 更新测试中的 test_config()**

所有用到 `test_config()` 的地方（orchestrator.rs, router.rs 等）需要加 `workspaces_dir` 字段。
先只改 config 自身的测试。

Run: `cargo test -p ngb-config`
Expected: PASS

**Step 3: Commit**

```bash
git add crates/ngb-config/src/config.rs
git commit -m "feat(config): add workspaces_dir alongside groups_dir"
```

---

### Task 4: 重构 Router — 两步查找 + 引导信息 (ngb-core)

**Files:**
- Modify: `crates/ngb-core/src/router.rs`

**Step 1: 添加 BindingRepository 和 WorkspaceRepository 导入**

**Step 2: 重写 route_message()**

新逻辑：
1. 检查消息是否是 token 格式（`ngb-` 前缀）→ 返回特殊 RouteResult
2. 检查消息是否是内置命令（`/status`）→ 返回特殊 RouteResult
3. 查 channel_bindings 表 → 找到则路由到对应 workspace
4. 未找到 → 返回 unbound RouteResult（调用方回复引导信息）

**Step 3: 更新 RouteResult**

```rust
pub struct RouteResult {
    pub action: RouteAction,
    pub workspace_id: Option<String>,
    pub workspace_folder: Option<String>,
}

pub enum RouteAction {
    /// 路由到 workspace 容器处理
    Process,
    /// Token 绑定请求
    BindToken { token: String },
    /// 内置命令
    BuiltinCommand { command: String },
    /// 未绑定，需要回复引导信息
    Unbound,
}
```

**Step 4: 删除 auto_register_group()**

替换为返回 `RouteAction::Unbound`。

**Step 5: 更新测试**

更新所有 router 测试以适配新的 RouteResult 结构。

Run: `cargo test -p ngb-core -- router`
Expected: PASS

**Step 6: Commit**

```bash
git add crates/ngb-core/src/router.rs
git commit -m "refactor(router): two-step lookup with binding + workspace, add RouteAction enum"
```

---

### Task 5: 重构 Orchestrator — 使用 Workspace + Binding (ngb-core)

**Files:**
- Modify: `crates/ngb-core/src/orchestrator.rs`

**Step 1: 将 registered_groups 改为 workspaces + bindings**

```rust
workspaces: Mutex<HashMap<String, Workspace>>,  // workspace_id → Workspace
```

**Step 2: start() 加载 workspaces 和 bindings**

**Step 3: poll_messages() 处理新的 RouteAction**

- `Process` → 入队容器处理（同当前逻辑）
- `BindToken` → 验证 token，创建 binding，通过 channel 回复成功/失败
- `BuiltinCommand` → 处理 /status 等
- `Unbound` → 通过 channel 回复引导信息

**Step 4: 更新 register_group → register_workspace**

**Step 5: 更新测试**

Run: `cargo test -p ngb-core -- orchestrator`
Expected: PASS

**Step 6: Commit**

```bash
git add crates/ngb-core/src/orchestrator.rs
git commit -m "refactor(orchestrator): use Workspace + ChannelBinding instead of RegisteredGroup"
```

---

### Task 6: 重构 GroupQueue → WorkspaceQueue (ngb-core)

**Files:**
- Rename: `crates/ngb-core/src/group_queue.rs` → `crates/ngb-core/src/workspace_queue.rs`
- Modify: `crates/ngb-core/src/lib.rs`

**Step 1: 重命名文件和内部类型**

- `GroupQueue` → `WorkspaceQueue`
- `GroupState` → `WorkspaceState`
- 所有 `group_folder` 参数 → `workspace_folder`
- 所有 `jid` 参数 → `workspace_id`

**Step 2: 更新 lib.rs 导出**

**Step 3: 更新 orchestrator.rs 中的引用**

**Step 4: 运行测试**

Run: `cargo test -p ngb-core`
Expected: PASS (115 tests)

**Step 5: Commit**

```bash
git add crates/ngb-core/src/workspace_queue.rs crates/ngb-core/src/lib.rs crates/ngb-core/src/orchestrator.rs
git rm crates/ngb-core/src/group_queue.rs
git commit -m "refactor(core): rename GroupQueue to WorkspaceQueue"
```

---

### Task 7: 重构 container_prep, container_runner, mount_security (ngb-core)

**Files:**
- Modify: `crates/ngb-core/src/container_prep.rs`
- Modify: `crates/ngb-core/src/container_runner.rs`
- Modify: `crates/ngb-core/src/mount_security.rs`

**Step 1: container_prep.rs**

- `ensure_group_dirs` → `ensure_workspace_dirs`
- `config.groups_dir` → `config.workspaces_dir`
- `write_groups_snapshot` → `write_workspaces_snapshot`
- 参数类型 `&[RegisteredGroup]` → `&[Workspace]`

**Step 2: container_runner.rs**

- `group_folder` 参数 → `workspace_folder`
- `validate_group_mounts` → `validate_workspace_mounts`

**Step 3: mount_security.rs**

- `validate_group_mounts` → `validate_workspace_mounts`
- `get_allowed_mount_paths` 中 `groups_dir` → `workspaces_dir`

**Step 4: 更新 lib.rs re-exports**

**Step 5: 运行全部测试**

Run: `cargo test --workspace`
Expected: PASS

**Step 6: Commit**

```bash
git add crates/ngb-core/src/{container_prep,container_runner,mount_security,lib}.rs
git commit -m "refactor(core): rename group references to workspace in container modules"
```

---

### Task 8: 清理旧类型 — 删除 RegisteredGroup (ngb-types, ngb-db)

**Files:**
- Delete content: `crates/ngb-types/src/group.rs` (保留文件，标记 deprecated 或删除)
- Modify: `crates/ngb-types/src/lib.rs` (移除 group 模块)
- Delete content: `crates/ngb-db/src/groups.rs`
- Modify: `crates/ngb-db/src/lib.rs` (移除 GroupRepository)

**注意:** 只有在 Task 1-7 全部完成、所有引用都迁移后才执行此 task。

**Step 1: 删除 group.rs 和 groups.rs**

**Step 2: 更新 lib.rs**

**Step 3: 编译验证无残留引用**

Run: `cargo build --workspace`
Expected: PASS，无 warning

**Step 4: 运行全部测试**

Run: `cargo test --workspace`
Expected: PASS

**Step 5: Commit**

```bash
git rm crates/ngb-types/src/group.rs crates/ngb-db/src/groups.rs
git add crates/ngb-types/src/lib.rs crates/ngb-db/src/lib.rs
git commit -m "refactor: remove deprecated RegisteredGroup and GroupRepository"
```

---

## Phase B: Token 绑定机制

### Task 9: CLI workspace create 命令 (ngb-cli)

**Files:**
- Modify: `crates/ngb-cli/src/main.rs`

**Step 1: 添加 Workspace 子命令**

```rust
#[derive(Subcommand)]
enum Commands {
    Serve,
    Workspace {
        #[command(subcommand)]
        action: WorkspaceAction,
    },
}

#[derive(Subcommand)]
enum WorkspaceAction {
    /// Create a new workspace
    Create {
        /// Workspace name/ID
        name: String,
        /// Mark as shared (team workspace)
        #[arg(long)]
        shared: bool,
    },
    /// List all workspaces
    List,
}
```

**Step 2: 实现 workspace create**

- 创建 Workspace 记录到 DB
- 创建 `workspaces/{name}/` 目录和默认 CLAUDE.md
- 生成 AccessToken 并存入 DB
- 输出 token 供 IM 绑定

**Step 3: 实现 workspace list**

- 查询所有 workspace，表格输出

**Step 4: 测试**

手动测试：
```bash
cargo run -p ngb-cli -- workspace create test-agent
# 应输出 token
cargo run -p ngb-cli -- workspace list
# 应显示 test-agent
```

**Step 5: Commit**

```bash
git add crates/ngb-cli/src/main.rs
git commit -m "feat(cli): add workspace create and list commands with token generation"
```

---

### Task 10: Telegram Token 识别和引导信息 (ngb-channels + ngb-core)

**Files:**
- Modify: `crates/ngb-channels/src/telegram.rs`
- Modify: `crates/ngb-core/src/orchestrator.rs`

**Step 1: Telegram channel 存储所有消息（不变）**

消息照常存入 messages 表，由 orchestrator 轮询处理。

**Step 2: Orchestrator poll_messages 处理 RouteAction**

在 `poll_messages()` 中根据 `RouteAction` 分支处理：

```rust
match route_result.action {
    RouteAction::Process => {
        // 现有容器启动逻辑
    }
    RouteAction::BindToken { token } => {
        // 验证 token → 创建 binding → 回复成功/失败
        let token_repo = TokenRepository::new(&self.db);
        match token_repo.validate_and_consume(&token).await {
            Ok(Some(workspace_id)) => {
                let binding_repo = BindingRepository::new(&self.db);
                binding_repo.bind(&msg.chat_jid, &workspace_id).await?;
                self.router.send_response(&msg.chat_jid,
                    &format!("✅ 已绑定到工作区「{}」\n现在可以直接发消息与 agent 交互。", workspace_id)
                ).await?;
            }
            _ => {
                self.router.send_response(&msg.chat_jid,
                    "❌ Token 无效或已过期。请在 CLI 运行 `ngb workspace create <name>` 获取新 token。"
                ).await?;
            }
        }
    }
    RouteAction::Unbound => {
        self.router.send_response(&msg.chat_jid,
            "👋 欢迎使用 NanoGridBot！\n当前未绑定工作区。\n请在 CLI 运行 `ngb workspace create <name>` 创建工作区，然后将生成的 token 发送到这里完成绑定。"
        ).await?;
    }
    RouteAction::BuiltinCommand { command } => {
        // 处理 /status 等
    }
}
```

**Step 3: 测试**

端到端测试：
1. `ngb workspace create test-bot` → 获得 token
2. `ngb serve` → 启动
3. Telegram 发任意消息 → 收到引导信息
4. Telegram 发 token → 收到绑定成功
5. Telegram 发正常消息 → agent 处理并回复

**Step 4: Commit**

```bash
git add crates/ngb-core/src/orchestrator.rs crates/ngb-channels/src/telegram.rs
git commit -m "feat: token binding flow with IM guidance messages"
```

---

### Task 11: 更新 Makefile 和文档

**Files:**
- Modify: `Makefile` (添加 workspace 相关 target)
- Modify: `CLAUDE.md` (更新概念说明)
- Modify: `docs/dev/NEXT_SESSION_GUIDE.md`

**Step 1: Makefile 添加**

```makefile
workspace-create: ## Create a workspace (NAME=my-agent)
	@if [ -z "$(NAME)" ]; then echo "Usage: make workspace-create NAME=my-agent"; exit 1; fi
	$(CARGO) run -p $(CLI_CRATE) -- workspace create $(NAME)

workspace-list: ## List all workspaces
	$(CARGO) run -p $(CLI_CRATE) -- workspace list
```

**Step 2: 更新文档**

**Step 3: Commit**

```bash
git add Makefile CLAUDE.md docs/dev/NEXT_SESSION_GUIDE.md
git commit -m "docs: update for workspace architecture"
```

---

## 验证清单

完成所有 task 后：

1. `cargo build --workspace` — 零错误
2. `cargo clippy --workspace -- -D warnings` — 零警告
3. `cargo test --workspace` — 全部通过
4. `make serve` — 正常启动
5. `make workspace-create NAME=test` — 创建成功并输出 token
6. Telegram 发消息 → 收到引导信息
7. Telegram 发 token → 绑定成功
8. Telegram 发正常消息 → agent 回复
