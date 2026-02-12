# NanoClaw 项目分析总结

## 执行摘要

本文档总结了对 NanoClaw 项目的全面分析，以及 Python 版本 NanoGridBot 的架构设计和实施方案。

---

## 1. NanoClaw 项目概览

### 1.1 核心特性

- **轻量级设计**: 约 5,077 行 TypeScript 代码，20 个核心文件
- **容器隔离**: 使用 Apple Container/Docker 实现 OS 级别安全隔离
- **多组隔离**: 每个 WhatsApp 群组拥有独立的文件系统、会话和容器
- **极简依赖**: 仅 7 个生产依赖，避免框架臃肿
- **AI 原生**: 使用 Claude Code 进行设置、调试和定制

### 1.2 技术栈

| 组件 | 技术 |
|------|------|
| 运行时 | Node.js 20+ |
| 语言 | TypeScript 5.7 |
| WhatsApp | @whiskeysockets/baileys |
| 数据库 | better-sqlite3 (SQLite) |
| 日志 | pino |
| 容器 | Apple Container / Docker |
| Agent SDK | @anthropic-ai/claude-code |

### 1.3 架构模式

1. **通道抽象**: 可插拔的通信通道接口
2. **依赖注入**: 函数接收依赖作为参数
3. **队列管理**: 每组队列 + 全局并发限制
4. **文件 IPC**: 基于文件系统的进程间通信
5. **双游标机制**: 消息读取游标 + Agent 处理游标
6. **流式输出**: 使用 sentinel 标记的实时输出

---

## 2. 核心模块分析

### 2.1 主编排器 (`src/index.ts`, 517 行)

**职责**:
- 全局状态管理（游标、会话、注册群组）
- 消息轮询循环（2 秒间隔）
- 群组注册和容器启动
- 崩溃恢复机制

**关键数据结构**:
```typescript
lastTimestamp: string                          // 全局消息游标
sessions: Record<string, string>               // 群组 -> 会话 ID
registeredGroups: Record<string, RegisteredGroup>
lastAgentTimestamp: Record<string, string>     // 群组 -> Agent 游标
```

### 2.2 容器运行器 (`src/container-runner.ts`, 658 行)

**职责**:
- 构建卷挂载列表（主群组 vs 普通群组）
- 安全验证额外挂载
- 启动容器并流式解析输出
- 超时管理（硬超时 + 空闲超时）

**挂载策略**:
- 主群组: 项目根目录 + 群组目录
- 普通群组: 仅群组目录 + 全局只读目录
- 所有群组: Claude 会话目录 + IPC 目录

### 2.3 群组队列 (`src/group-queue.ts`, 303 行)

**职责**:
- 每组串行处理（防止竞态）
- 全局并发限制（默认 5 个容器）
- 指数退避重试（最多 5 次）
- Follow-up 消息管道

**状态机**:
```typescript
interface GroupState {
  active: boolean           // 容器是否运行
  pendingMessages: boolean  // 是否有待处理消息
  pendingTasks: QueuedTask[]
  process: ChildProcess | null
  retryCount: number
}
```

### 2.4 数据库 (`src/db.ts`, 585 行)

**表结构**:
- `chats`: 聊天元数据
- `messages`: 消息内容
- `scheduled_tasks`: 定时任务
- `task_run_logs`: 任务执行日志
- `router_state`: 路由状态
- `sessions`: Claude 会话 ID
- `registered_groups`: 已注册群组

**关键操作**:
- `getNewMessages()`: 获取新消息（基于游标）
- `getMessagesSince()`: 获取特定时间后的消息
- `getDueTasks()`: 获取到期任务

### 2.5 IPC 通信 (`src/ipc.ts`, 382 行)

**协议**:
- 文件系统作为消息队列
- 原子写入（.tmp + rename）
- 轮询消费
- 信号机制（_close 文件）

**目录结构**:
```
data/ipc/{group}/
├── messages/    # 出站消息（容器 -> 主机）
├── tasks/       # 任务管理请求
└── input/       # 入站消息（主机 -> 容器）
```

**权限模型**:
- 主群组可向任何群组发送消息
- 普通群组只能向自己发送消息

### 2.6 任务调度器 (`src/task-scheduler.ts`, 219 行)

**调度类型**:
- `cron`: 标准 cron 表达式
- `interval`: 毫秒间隔
- `once`: 一次性任务

**上下文模式**:
- `group`: 使用群组会话上下文
- `isolated`: 全新会话

### 2.7 挂载安全 (`src/mount-security.ts`, 419 行)

**验证流程**:
1. 检查路径存在性
2. 解析符号链接
3. 检查黑名单模式
4. 验证在允许的根目录下
5. 确定读写权限

**白名单配置** (`~/.config/nanoclaw/mount-allowlist.json`):
```json
{
  "allowedRoots": [
    {"path": "~/projects", "allowReadWrite": true}
  ],
  "blockedPatterns": [".ssh", ".gnupg", ".aws"],
  "nonMainReadOnly": true
}
```

---

## 3. 容器内架构

### 3.1 Agent Runner (`container/agent-runner/src/index.ts`)

**职责**:
- 从 stdin 读取 JSON 配置
- 执行 Claude SDK 查询
- 轮询 IPC 目录获取 follow-up 消息
- 流式输出结果（带 sentinel 标记）

**查询循环**:
```typescript
while (true) {
  // 1. 运行 Claude SDK
  const result = await runQuery(prompt, sessionId);

  // 2. 检查关闭信号
  if (result.closedDuringQuery) break;

  // 3. 等待下一条 IPC 消息
  const nextMessage = await waitForIpcMessage();
  if (nextMessage === null) break;

  // 4. 继续查询
  prompt = nextMessage;
}
```

### 3.2 IPC MCP 服务器 (`container/agent-runner/src/ipc-mcp-stdio.ts`)

**提供的工具**:
1. `send_message`: 发送消息到用户/群组
2. `schedule_task`: 创建定时任务
3. `update_task`: 更新任务状态
4. `delete_task`: 删除任务
5. `list_tasks`: 列出任务
6. `register_group`: 注册新群组（仅主群组）
7. `list_available_groups`: 列出可用群组（仅主群组）
8. `sync_group_metadata`: 同步群组元数据（仅主群组）

---

## 4. 数据流分析

### 4.1 消息接收流程

```
WhatsApp 消息
  ↓
WhatsAppChannel.onMessage()
  ↓
storeMessage() → SQLite
  ↓
[主循环轮询 2s]
  ↓
getNewMessages() ← SQLite
  ↓
检查触发词 (@Andy)
  ↓
GroupQueue.enqueueMessageCheck()
  ↓
formatMessages() → XML
  ↓
runContainerAgent()
  ↓
agent-runner 执行 Claude SDK
  ↓
流式输出 → WhatsApp
```

### 4.2 IPC 消息流程

```
容器内 Claude SDK
  ↓
MCP 工具 (send_message)
  ↓
writeIpcFile() → data/ipc/{group}/messages/*.json
  ↓
[主机 IPC 轮询]
  ↓
processIpcFiles() ← 读取 JSON
  ↓
权限检查
  ↓
WhatsAppChannel.sendMessage()
  ↓
发送到 WhatsApp
```

### 4.3 Follow-up 消息流程

```
新消息到达（容器已活跃）
  ↓
GroupQueue.sendMessage()
  ↓
写入 data/ipc/{group}/input/*.json
  ↓
[容器内轮询]
  ↓
drainIpcInput() ← 读取 JSON
  ↓
MessageStream.push(text)
  ↓
注入到活跃的 Claude SDK 查询
  ↓
继续对话（无需重启容器）
```

---

## 5. Python 移植设计

### 5.1 技术栈映射

| TypeScript | Python | 说明 |
|------------|--------|------|
| Node.js | Python 3.12+ | 使用最新特性 |
| @whiskeysockets/baileys | Baileys 桥接 | Node.js 子进程 |
| better-sqlite3 | aiosqlite | 异步 SQLite |
| pino | loguru | 结构化日志 |
| zod | pydantic | 运行时验证 |
| cron-parser | croniter | Cron 解析 |
| N/A | FastAPI | Web 监控 |

### 5.2 项目结构

```
nanogridbot/
├── src/nanogridbot/
│   ├── core/              # 核心模块
│   │   ├── orchestrator.py
│   │   ├── container_runner.py
│   │   ├── group_queue.py
│   │   ├── task_scheduler.py
│   │   ├── ipc_handler.py
│   │   └── mount_security.py
│   ├── database/          # 数据库
│   │   ├── db.py
│   │   └── models.py
│   ├── channels/          # 通道
│   │   ├── base.py
│   │   ├── whatsapp.py
│   │   └── telegram.py
│   ├── plugins/           # 插件系统
│   │   ├── base.py
│   │   └── loader.py
│   └── web/               # Web 监控
│       └── app.py
├── container/             # Agent 容器
│   └── agent_runner/
├── bridge/                # Baileys 桥接
│   └── whatsapp-bridge.js
└── tests/                 # 测试
```

### 5.3 核心设计

**异步架构**:
- 基于 asyncio 的事件循环
- 所有 I/O 操作异步化
- 使用 aiofiles 处理文件

**类型安全**:
- Pydantic 数据模型
- 完整的类型注解
- mypy 静态检查

**通道抽象**:
```python
class Channel(ABC):
    @abstractmethod
    async def connect(self) -> None: ...
    @abstractmethod
    async def send_message(self, jid: str, text: str) -> None: ...
    @abstractmethod
    def is_connected(self) -> bool: ...
    @abstractmethod
    def owns_jid(self, jid: str) -> bool: ...
```

---

## 6. 扩展功能设计

### 6.1 插件系统

**插件基类**:
```python
class Plugin(ABC):
    @abstractmethod
    async def initialize(self, config: Dict): ...

    async def on_message_received(self, message: Message) -> Optional[Message]: ...
    async def on_message_sent(self, jid: str, text: str) -> Optional[str]: ...
    async def on_container_start(self, group: str, prompt: str) -> Optional[str]: ...
```

**示例插件**:
- 速率限制
- 消息过滤
- 日志增强
- 指标收集

### 6.2 Web 监控面板

**功能**:
- 实时群组状态
- 任务管理界面
- 消息历史搜索
- 系统指标展示
- WebSocket 实时更新

**技术栈**:
- FastAPI 后端
- Vue.js 前端
- WebSocket 通信

### 6.3 多通道支持

**Telegram 通道**:
```python
class TelegramChannel(Channel):
    def __init__(self, token: str, db: Database):
        self.app = Application.builder().token(token).build()

    async def connect(self):
        await self.app.start()
        await self.app.updater.start_polling()
```

**Slack 通道**:
- 使用 slack-sdk
- 支持 Socket Mode
- 事件订阅

### 6.4 高级功能

- **消息历史搜索**: SQLite FTS5 全文搜索
- **健康检查**: `/api/health` 端点
- **指标导出**: Prometheus 格式
- **速率限制**: 基于令牌桶算法
- **Webhook 支持**: 外部系统集成

---

## 7. 实施计划

### 7.1 开发阶段（14 周）

| 阶段 | 周数 | 内容 |
|------|------|------|
| 1 | 1-2 | 基础架构搭建 |
| 2 | 2-3 | 数据库层实现 |
| 3 | 3-5 | WhatsApp 集成 |
| 4 | 5-7 | 容器运行器 |
| 5 | 7-8 | 队列和并发 |
| 6 | 8-9 | 任务调度器 |
| 7 | 9-10 | 主编排器集成 |
| 8 | 10-12 | 扩展功能 |
| 9 | 12-13 | 文档和部署 |
| 10 | 13-14 | 测试和发布 |

### 7.2 技术选型

**WhatsApp 集成**: Baileys 桥接（推荐）
- 通过 Node.js 子进程运行 Baileys
- JSON-RPC 通信
- 复用成熟实现

**容器运行时**: Docker
- 广泛支持
- 丰富生态

**异步框架**: asyncio
- Python 标准库
- 生态最丰富

### 7.3 质量保证

**测试策略**:
- 单元测试覆盖率 > 80%
- 集成测试（Docker Compose）
- 端到端测试
- 性能测试

**代码质量**:
- Black 格式化
- Ruff Linter
- mypy 类型检查
- pre-commit 钩子

---

## 8. 性能目标

| 指标 | 目标 |
|------|------|
| 消息处理延迟 | < 2 秒 |
| 容器启动时间 | < 5 秒 |
| 并发容器数 | 5-10 个 |
| 内存占用 | < 500MB |
| 数据库查询 | < 100ms (p95) |

---

## 9. 安全考虑

### 9.1 容器安全

- 非 root 用户运行
- 资源限制（CPU、内存）
- 只读挂载敏感目录
- 定期更新基础镜像

### 9.2 数据安全

- 加密存储敏感配置
- 定期备份数据库
- 访问日志审计
- 挂载请求审计

### 9.3 网络安全

- HTTPS 加密
- API 认证授权
- 速率限制
- 输入验证

---

## 10. 风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| WhatsApp 协议变更 | 高 | 中 | 使用 Baileys 桥接 |
| 容器性能问题 | 中 | 低 | 性能测试优化 |
| 并发 Bug | 高 | 中 | 充分测试 |
| 开发延期 | 中 | 中 | 分阶段交付 |

---

## 11. 成功标准

### 11.1 功能完整性

- [ ] 所有核心功能与 TypeScript 版本对等
- [ ] 通过所有端到端测试
- [ ] 文档完整且准确

### 11.2 性能指标

- [ ] 消息处理延迟 < 2 秒
- [ ] 容器启动时间 < 5 秒
- [ ] 支持 5+ 并发容器

### 11.3 质量指标

- [ ] 单元测试覆盖率 > 80%
- [ ] 无已知严重 Bug
- [ ] 代码通过所有检查

---

## 12. 下一步行动

### 立即开始

1. **创建项目仓库**
2. **设置项目结构**
3. **实现基础模块** (config, logger, types)
4. **设置 CI/CD**
5. **开始第一周开发**

### 第一周目标

- [ ] 完成项目骨架
- [ ] 实现配置和日志模块
- [ ] 定义所有 Pydantic 模型
- [ ] 编写基础文档
- [ ] 设置开发环境

---

## 13. 相关文档

- [架构设计文档](./NANOGRIDBOT_DESIGN.md) - 详细的模块设计和代码示例
- [实施方案](./IMPLEMENTATION_PLAN.md) - 开发阶段和任务分解
- [NanoClaw 原项目](https://github.com/nanoclaw/nanoclaw) - TypeScript 原版

---

## 14. 总结

NanoGridBot 是 NanoClaw 的完整 Python 移植，具有以下优势：

1. **功能对等**: 1:1 复制所有核心功能
2. **Python 生态**: 利用丰富的 Python 库
3. **异步架构**: 基于 asyncio 的高性能设计
4. **可扩展性**: 插件系统、多通道支持、Web 监控
5. **类型安全**: Pydantic 数据验证
6. **易于部署**: Docker 容器化
7. **向后兼容**: 可与 TypeScript 版本共存

通过 14 周的开发周期，我们将交付一个生产就绪的 Python 版本，同时保持与原版的完全兼容性。

---

**文档版本**: 1.0
**最后更新**: 2026-02-13
**分析完成**: ✅
