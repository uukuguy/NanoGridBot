# NanoGridBot Workspace 架构设计

## 背景

NGB 定位为企业内多个 AI 工程师开发调试智能体的工具。当前实现中 `RegisteredGroup` 混合了工作环境和通道路由两个职责，导致概念混乱。本设计将核心概念重构为以 Workspace 为中心的模型。

## 核心概念

### 1. Workspace（工作区）

智能体开发项目的隔离环境，是 NGB 的核心工作单元。

```
Workspace:
  id: string          # 唯一标识，如 "chatbot-v2"
  name: string        # 显示名，如 "客服机器人 v2"
  owner: string       # 创建者标识
  folder: string      # 磁盘目录名（通常等于 id）
  shared: bool        # 是否团队共享
  container_config: json  # 容器配置覆盖
```

每个 workspace 对应独立的：
- 文件目录（CLAUDE.md、skills、sessions）
- Docker 容器实例（按需启动）
- 环境变量（私有 + 全局合并）

### 2. ChannelBinding（通道绑定）

将 IM 的 chat 映射到 workspace。通过 access token 建立绑定。

```
ChannelBinding:
  channel_jid: string     # 如 "telegram:123456"（私聊）或 "telegram:-100999"（群聊）
  workspace_id: string    # 绑定的目标工作区
  bound_at: datetime      # 绑定时间
```

### 3. AccessToken（访问令牌）

CLI 创建 workspace 时生成，用于 IM 侧绑定。

```
AccessToken:
  token: string           # 如 "ngb-a3f8c2e1b7d4"
  workspace_id: string    # 对应的工作区
  created_at: datetime
  expires_at: datetime?   # 可选过期时间
  used: bool              # 是否已使用
```

### 4. User（用户）

MVP 阶段不做独立用户管理。身份通过以下方式自然识别：
- CLI：系统用户名或 `--user` 参数
- Telegram：消息中的 sender_id + sender_name
- 群聊中多人通过 sender_id 自然区分

## 关系图

```
                    ┌─────────────────────────────────────────────┐
                    │              NGB Server                      │
                    │                                             │
  Telegram Bot ─────┤  channel_bindings 表                        │
  (1个 token,       │  ┌────────────────────┬──────────────────┐ │
   服务所有用户)    │  │ telegram:111       │→ chatbot-v2      │ │
                    │  │ telegram:222       │→ data-agent      │ │
  Slack Bot ────────┤  │ slack:C_team       │→ chatbot-v2      │ │
                    │  │ telegram:-100999   │→ team-qa (群聊)  │ │
  CLI ──────────────┤  └────────────────────┴──────────────────┘ │
  (直接指定         │                           │                 │
   workspace 名)    │                           ▼                 │
                    │  workspaces 表                              │
                    │  ┌──────────────┬────────┬───────────────┐ │
                    │  │ chatbot-v2   │ alice  │ shared=false  │ │
                    │  │ data-agent   │ bob    │ shared=false  │ │
                    │  │ team-qa      │ alice  │ shared=true   │ │
                    │  └──────────────┴────────┴───────────────┘ │
                    │         │                                   │
                    │         ▼                                   │
                    │  Docker Container (按 workspace 启动)       │
                    │  挂载: workspaces/{id}/ + _shared/          │
                    └─────────────────────────────────────────────┘
```

## 目录结构

```
workspaces/
  ├── chatbot-v2/          # 工程师 Alice 的私有工作区
  │   ├── CLAUDE.md        # agent 指令
  │   ├── skills/          # 私有技能
  │   └── sessions/        # 会话历史
  ├── team-qa/             # 团队共享工作区
  │   ├── CLAUDE.md
  │   └── skills/
  └── _shared/             # 全局共享资源（只读挂载到容器）
      ├── skills/          # 所有 workspace 可用的技能
      └── knowledge/       # 全局知识库
```

## 交互流程

### CLI 侧（日常工作，无 token）

```bash
ngb workspace create my-agent    # 创建工作区，输出 access token
ngb workspace list               # 列出所有工作区
ngb shell my-agent               # 进入交互式 shell
ngb serve                        # 启动服务（Telegram listener + orchestrator）
```

### IM 侧（首次连接）

```
用户 → bot: 你好
bot → 用户: 👋 欢迎使用 NanoGridBot！
             当前未绑定工作区。
             请在 CLI 运行 `ngb workspace create <name>` 创建工作区，
             然后将生成的 token 发送到这里完成绑定。

用户 → bot: ngb-a3f8c2e1b7d4
bot → 用户: ✅ 已绑定到工作区「my-agent」
             现在可以直接发消息与 agent 交互。
             发送新 token 可切换工作区，发送 /status 查看当前状态。
```

### IM 侧（已绑定后）

```
用户 → bot: 帮我检查一下 API 接口
bot → 用户: [agent 回复，来自 my-agent workspace 的容器]

用户 → bot: /status
bot → 用户: 当前工作区: my-agent
             Owner: alice
             类型: 私有
```

### 双模式

| 场景 | chat_id | 绑定方式 | 适用 |
|------|---------|----------|------|
| 私聊 | 正数（用户 ID） | 个人在私聊窗口发 token | 个人 workspace |
| 群聊 | 负数（群 ID） | 任意成员在群里发 token | 团队 workspace |

群聊中所有成员共享同一个 workspace，agent 能看到所有人的消息（通过 sender_name 区分）。

## 消息路由流程

```
收到 IM 消息
  │
  ├─ 消息内容匹配 token 格式（ngb-*）？
  │   ├─ 是 → 验证 token → 创建/更新 binding → 回复绑定成功
  │   └─ token 无效 → 回复错误提示
  │
  ├─ 查 channel_bindings 表
  │   ├─ 找到 binding → 路由到对应 workspace → 启动容器处理
  │   └─ 未找到 → 回复引导信息（如何创建 workspace 和绑定）
  │
  └─ /status 等内置命令 → 直接处理，不进容器
```

## 数据库 Schema

### workspaces 表（替代 groups 表）

```sql
CREATE TABLE workspaces (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    owner       TEXT NOT NULL DEFAULT '',
    folder      TEXT NOT NULL,
    shared      INTEGER NOT NULL DEFAULT 0,
    container_config TEXT,  -- JSON
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### channel_bindings 表（新增）

```sql
CREATE TABLE channel_bindings (
    channel_jid  TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    bound_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### access_tokens 表（新增）

```sql
CREATE TABLE access_tokens (
    token        TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at   TEXT,
    used         INTEGER NOT NULL DEFAULT 0
);
```

## 对当前 Rust 代码的影响

### 类型层（ngb-types）

| 当前 | 变更 |
|------|------|
| `RegisteredGroup` | → `Workspace`（去掉 jid, trigger_pattern, requires_trigger） |
| — | + `ChannelBinding`（新类型） |
| — | + `AccessToken`（新类型） |

### 数据库层（ngb-db）

| 当前 | 变更 |
|------|------|
| `groups.rs` / `GroupRepository` | → `workspaces.rs` / `WorkspaceRepository` |
| — | + `bindings.rs` / `BindingRepository` |
| — | + `tokens.rs` / `TokenRepository` |
| DB schema `groups` 表 | → `workspaces` + `channel_bindings` + `access_tokens` |

### 核心层（ngb-core）

| 当前 | 变更 |
|------|------|
| `router.rs` route_message | → 两步查找：先查 binding，再查 workspace |
| `router.rs` auto_register_group | → 删除，改为回复引导信息 |
| `group_queue.rs` GroupQueue | → `workspace_queue.rs` WorkspaceQueue |
| `orchestrator.rs` registered_groups | → workspaces + bindings |
| `container_prep.rs` | → 路径从 groups_dir 改为 workspaces_dir |

### Channel 层（ngb-channels）

| 当前 | 变更 |
|------|------|
| `telegram.rs` 只存消息 | + 识别 token 消息和内置命令（/status） |

### CLI 层（ngb-cli）

| 当前 | 变更 |
|------|------|
| 只有 `serve` 命令 | + `workspace create/list/delete` |
| — | + `shell` 命令 |

### 配置层（ngb-config）

| 当前 | 变更 |
|------|------|
| `groups_dir` | → `workspaces_dir` |

## 实施阶段

### Phase A：概念重构（最小改动）
1. `RegisteredGroup` → `Workspace`，去掉路由字段
2. `groups` 表 → `workspaces` 表
3. 新增 `channel_bindings` 表和 `access_tokens` 表
4. Router 改为两步查找
5. `groups_dir` → `workspaces_dir`

### Phase B：Token 绑定机制
1. CLI `workspace create` 命令 + token 生成
2. Telegram channel 识别 token 消息并执行绑定
3. 未绑定 chat 回复引导信息
4. `/status` 内置命令

### Phase C：共享层
1. `_shared/` 目录结构
2. 容器启动时合并挂载（私有读写 + 共享只读）
3. 全局 skills 同步

### Phase D：CLI 增强
1. `workspace list/delete` 命令
2. `shell` 交互模式
3. workspace 配置管理
