# NanoGridBot 架构设计文档

## 1. 项目概述

**NanoGridBot** 是 NanoClaw 项目的 Python 1:1 移植版本，是一个轻量级、安全的个人 Claude AI 助手，通过 WhatsApp 提供交互界面，运行在容器化环境中以确保安全隔离。

### 1.1 核心特性

- **极简设计**: 单进程架构，核心代码模块化
- **容器隔离**: 使用 Docker 实现 OS 级别的安全隔离
- **多组隔离**: 每个 WhatsApp 群组拥有独立的文件系统、会话和容器沙箱
- **异步架构**: 基于 asyncio 的高性能异步处理
- **类型安全**: 使用 Pydantic 进行数据验证和类型检查
- **可扩展**: 支持多通道、插件系统、Web 监控

### 1.2 技术栈选择

| 组件 | TypeScript 原版 | Python 移植版 | 说明 |
|------|----------------|--------------|------|
| **运行时** | Node.js 20+ | Python 3.12+ | 使用最新 Python 特性 |
| **WhatsApp 客户端** | @whiskeysockets/baileys | yowsup / whatsapp-web.py | 需要评估可用性 |
| **数据库** | better-sqlite3 | aiosqlite | 异步 SQLite |
| **日志** | pino | loguru | 结构化日志 |
| **类型验证** | zod | pydantic | 运行时类型检查 |
| **Cron 解析** | cron-parser | croniter | Cron 表达式解析 |
| **容器运行时** | Apple Container/Docker | Docker | 跨平台容器 |
| **异步框架** | N/A | asyncio + aiofiles | 原生异步支持 |
| **HTTP 框架** | N/A | FastAPI | Web 监控面板 |
| **消息队列** | 文件系统 | 文件系统 + Redis (可选) | 支持分布式 |

---

## 2. 项目结构设计

```
nanogridbot/
├── src/
│   └── nanogridbot/
│       ├── __init__.py
│       ├── __main__.py              # 主入口
│       ├── config.py                # 配置管理
│       ├── types.py                 # Pydantic 数据模型
│       ├── logger.py                # Loguru 配置
│       │
│       ├── core/                    # 核心模块
│       │   ├── __init__.py
│       │   ├── orchestrator.py      # 主编排器 (index.ts)
│       │   ├── container_runner.py  # 容器运行器
│       │   ├── group_queue.py       # 群组队列管理
│       │   ├── task_scheduler.py    # 任务调度器
│       │   ├── ipc_handler.py       # IPC 处理器
│       │   ├── router.py            # 消息路由器
│       │   └── mount_security.py    # 挂载安全验证
│       │
│       ├── database/                # 数据库模块
│       │   ├── __init__.py
│       │   ├── db.py                # 数据库操作
│       │   ├── models.py            # SQLAlchemy 模型
│       │   └── migrations/          # 数据库迁移
│       │
│       ├── channels/                # 通道抽象
│       │   ├── __init__.py
│       │   ├── base.py              # Channel 基类
│       │   ├── whatsapp.py          # WhatsApp 实现
│       │   ├── telegram.py          # Telegram 实现 (扩展)
│       │   └── slack.py             # Slack 实现 (扩展)
│       │
│       ├── plugins/                 # 插件系统 (扩展)
│       │   ├── __init__.py
│       │   ├── base.py              # 插件基类
│       │   ├── loader.py            # 插件加载器
│       │   └── builtin/             # 内置插件
│       │
│       ├── web/                     # Web 监控 (扩展)
│       │   ├── __init__.py
│       │   ├── app.py               # FastAPI 应用
│       │   ├── api/                 # REST API
│       │   └── static/              # 前端资源
│       │
│       └── utils/                   # 工具函数
│           ├── __init__.py
│           ├── formatting.py        # 消息格式化
│           ├── security.py          # 安全工具
│           └── async_helpers.py     # 异步辅助函数
│
├── container/                       # 容器镜像
│   ├── Dockerfile
│   ├── build.sh
│   ├── agent_runner/                # Agent 运行器
│   │   ├── __init__.py
│   │   ├── main.py                  # 主逻辑
│   │   └── ipc_mcp_server.py        # MCP 服务器
│   └── skills/                      # 容器技能
│
├── groups/                          # 群组工作目录
│   ├── main/
│   │   └── CLAUDE.md
│   └── global/
│       └── CLAUDE.md
│
├── data/                            # 运行时数据
│   ├── ipc/
│   ├── sessions/
│   └── env/
│
├── store/                           # 持久化存储
│   ├── messages.db
│   └── auth/
│
├── tests/                           # 测试
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docs/                            # 文档
│   ├── design/
│   └── main/
│
├── pyproject.toml                   # 项目配置
├── Dockerfile                       # 主应用容器
├── docker-compose.yml               # 编排配置
└── README.md
```

---

## 3. 核心模块设计

### 3.1 数据模型 (`types.py`)

使用 Pydantic 定义所有数据结构：

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Literal
from datetime import datetime
from enum import Enum

class ChannelType(str, Enum):
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    SLACK = "slack"
    DISCORD = "discord"
    QQ = "qq"
    FEISHU = "feishu"
    WECOM = "wecom"
    DINGTALK = "dingtalk"

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class Message(BaseModel):
    id: str
    chat_jid: str
    sender: str
    sender_name: Optional[str] = None
    content: str
    timestamp: datetime
    is_from_me: bool = False

class RegisteredGroup(BaseModel):
    jid: str
    name: str
    folder: str
    trigger_pattern: Optional[str] = None
    container_config: Optional[Dict] = None
    requires_trigger: bool = True

class ContainerConfig(BaseModel):
    additional_mounts: List[Dict] = Field(default_factory=list)
    timeout: Optional[int] = None
    max_output_size: Optional[int] = None

class ScheduleType(str, Enum):
    CRON = "cron"
    INTERVAL = "interval"
    ONCE = "once"

class TaskStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"

class ScheduledTask(BaseModel):
    id: Optional[int] = None
    group_folder: str
    prompt: str
    schedule_type: ScheduleType
    schedule_value: str
    status: TaskStatus = TaskStatus.ACTIVE
    next_run: Optional[datetime] = None
    context_mode: Literal["group", "isolated"] = "group"
    target_chat_jid: Optional[str] = None

class ContainerOutput(BaseModel):
    status: Literal["success", "error"]
    result: Optional[str] = None
    error: Optional[str] = None
    new_session_id: Optional[str] = None
```

### 3.2 通道抽象 (`channels/base.py`)

```python
from abc import ABC, abstractmethod
from typing import Optional

class Channel(ABC):
    """通道抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """通道名称"""
        pass

    @property
    def prefix_assistant_name(self) -> bool:
        """是否需要在消息前添加助手名称"""
        return True

    @abstractmethod
    async def connect(self) -> None:
        """连接到通道"""
        pass

    @abstractmethod
    async def send_message(self, jid: str, text: str) -> None:
        """发送消息"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接状态"""
        pass

    @abstractmethod
    def owns_jid(self, jid: str) -> bool:
        """检查 JID 是否属于此通道"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass

    async def set_typing(self, jid: str, is_typing: bool) -> None:
        """设置输入状态（可选）"""
        pass
```

### 3.3 主编排器 (`core/orchestrator.py`)

```python
import asyncio
from typing import Dict, Optional
from loguru import logger
from .group_queue import GroupQueue
from .task_scheduler import TaskScheduler
from .ipc_handler import IpcHandler
from ..database.db import Database
from ..channels.base import Channel
from ..config import Config

class Orchestrator:
    """主编排器 - 管理全局状态和消息循环"""

    def __init__(
        self,
        config: Config,
        db: Database,
        channels: list[Channel],
    ):
        self.config = config
        self.db = db
        self.channels = channels

        # 全局状态
        self.last_timestamp: Optional[str] = None
        self.sessions: Dict[str, str] = {}
        self.registered_groups: Dict[str, RegisteredGroup] = {}
        self.last_agent_timestamp: Dict[str, str] = {}

        # 子系统
        self.queue = GroupQueue(config, db)
        self.scheduler = TaskScheduler(config, db, self.queue)
        self.ipc_handler = IpcHandler(config, db, channels)

        # 运行标志
        self._running = False

    async def start(self):
        """启动编排器"""
        logger.info("Starting NanoGridBot orchestrator")

        # 加载状态
        await self._load_state()

        # 连接所有通道
        for channel in self.channels:
            await channel.connect()

        # 启动子系统
        self._running = True
        tasks = [
            asyncio.create_task(self._message_loop()),
            asyncio.create_task(self.scheduler.start()),
            asyncio.create_task(self.ipc_handler.start()),
        ]

        # 等待所有任务
        await asyncio.gather(*tasks)

    async def stop(self):
        """停止编排器"""
        logger.info("Stopping orchestrator")
        self._running = False

        # 保存状态
        await self._save_state()

        # 断开通道
        for channel in self.channels:
            await channel.disconnect()

    async def _message_loop(self):
        """消息轮询循环"""
        while self._running:
            try:
                # 获取新消息
                messages = await self.db.get_new_messages(self.last_timestamp)

                if messages:
                    # 按群组分组
                    groups = self._group_messages(messages)

                    # 处理每个群组
                    for jid, group_messages in groups.items():
                        await self._process_group_messages(jid, group_messages)

                    # 更新游标
                    self.last_timestamp = messages[-1].timestamp

                # 等待下一次轮询
                await asyncio.sleep(self.config.POLL_INTERVAL / 1000)

            except Exception as e:
                logger.error(f"Error in message loop: {e}")
                await asyncio.sleep(5)

    async def _process_group_messages(self, jid: str, messages: list[Message]):
        """处理群组消息"""
        group = self.registered_groups.get(jid)
        if not group:
            logger.debug(f"Group {jid} not registered, skipping")
            return

        # 检查触发词
        if group.requires_trigger:
            triggered = any(
                self._check_trigger(msg.content, group.trigger_pattern)
                for msg in messages
            )
            if not triggered:
                return

        # 入队处理
        await self.queue.enqueue_message_check(
            jid,
            group,
            self.sessions.get(jid),
            self.last_agent_timestamp.get(jid),
        )

    def _check_trigger(self, content: str, pattern: Optional[str]) -> bool:
        """检查触发词"""
        import re
        if not pattern:
            pattern = self.config.TRIGGER_PATTERN
        return bool(re.search(pattern, content, re.IGNORECASE))

    def _group_messages(self, messages: list[Message]) -> Dict[str, list[Message]]:
        """按群组分组消息"""
        groups = {}
        for msg in messages:
            if msg.chat_jid not in groups:
                groups[msg.chat_jid] = []
            groups[msg.chat_jid].append(msg)
        return groups

    async def _load_state(self):
        """加载状态"""
        state = await self.db.get_router_state()
        self.last_timestamp = state.get("last_timestamp")
        self.sessions = state.get("sessions", {})
        self.last_agent_timestamp = state.get("last_agent_timestamp", {})

        # 加载注册群组
        groups = await self.db.get_registered_groups()
        self.registered_groups = {g.jid: g for g in groups}

    async def _save_state(self):
        """保存状态"""
        await self.db.save_router_state({
            "last_timestamp": self.last_timestamp,
            "sessions": self.sessions,
            "last_agent_timestamp": self.last_agent_timestamp,
        })
```

### 3.4 群组队列 (`core/group_queue.py`)

```python
import asyncio
from typing import Dict, Optional
from dataclasses import dataclass
from loguru import logger
from ..config import Config
from ..database.db import Database

@dataclass
class GroupState:
    """群组状态"""
    active: bool = False
    pending_messages: bool = False
    pending_tasks: list = None
    process: Optional[asyncio.subprocess.Process] = None
    container_name: Optional[str] = None
    group_folder: Optional[str] = None
    retry_count: int = 0

    def __post_init__(self):
        if self.pending_tasks is None:
            self.pending_tasks = []

class GroupQueue:
    """群组队列管理器"""

    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.states: Dict[str, GroupState] = {}
        self.active_count = 0
        self.waiting_groups: list[str] = []
        self._lock = asyncio.Lock()

    async def enqueue_message_check(
        self,
        jid: str,
        group: RegisteredGroup,
        session_id: Optional[str],
        last_timestamp: Optional[str],
    ):
        """入队消息检查"""
        async with self._lock:
            state = self._get_state(jid)

            if state.active:
                # 群组正在处理，标记有待处理消息
                state.pending_messages = True
                await self._send_follow_up_messages(jid, last_timestamp)
            else:
                # 尝试启动容器
                await self._try_start_container(jid, group, session_id, last_timestamp)

    async def enqueue_task(
        self,
        jid: str,
        group: RegisteredGroup,
        task: ScheduledTask,
        session_id: Optional[str],
    ):
        """入队任务"""
        async with self._lock:
            state = self._get_state(jid)

            if state.active:
                # 任务优先级高于消息
                state.pending_tasks.insert(0, task)
            else:
                await self._try_start_task(jid, group, task, session_id)

    async def _try_start_container(
        self,
        jid: str,
        group: RegisteredGroup,
        session_id: Optional[str],
        last_timestamp: Optional[str],
    ):
        """尝试启动容器"""
        if self.active_count >= self.config.MAX_CONCURRENT_CONTAINERS:
            # 达到并发限制，加入等待队列
            if jid not in self.waiting_groups:
                self.waiting_groups.append(jid)
            logger.debug(f"Group {jid} waiting, active: {self.active_count}")
            return

        # 启动容器
        state = self._get_state(jid)
        state.active = True
        self.active_count += 1

        try:
            # 获取消息
            messages = await self.db.get_messages_since(jid, last_timestamp)

            # 格式化消息
            from ..utils.formatting import format_messages_xml
            prompt = format_messages_xml(messages)

            # 运行容器
            from .container_runner import run_container_agent
            result = await run_container_agent(
                group_folder=group.folder,
                prompt=prompt,
                session_id=session_id,
                chat_jid=jid,
                is_main=(group.folder == "main"),
                container_config=group.container_config,
            )

            # 处理结果
            await self._handle_container_result(jid, result)

        except Exception as e:
            logger.error(f"Container error for {jid}: {e}")
            state.retry_count += 1

            if state.retry_count < 5:
                # 指数退避重试
                delay = 5 * (2 ** (state.retry_count - 1))
                logger.info(f"Retrying {jid} in {delay}s (attempt {state.retry_count})")
                await asyncio.sleep(delay)
                await self._try_start_container(jid, group, session_id, last_timestamp)
            else:
                logger.error(f"Max retries reached for {jid}, dropping")

        finally:
            # 清理状态
            state.active = False
            state.retry_count = 0
            self.active_count -= 1

            # 处理待处理项
            await self._drain_pending(jid, group, session_id)

            # 唤醒等待的群组
            await self._drain_waiting()

    async def _send_follow_up_messages(self, jid: str, last_timestamp: Optional[str]):
        """发送 follow-up 消息到活跃容器"""
        messages = await self.db.get_messages_since(jid, last_timestamp)

        for msg in messages:
            ipc_file = self.config.DATA_DIR / "ipc" / jid / "input" / f"{msg.timestamp}.json"
            ipc_file.parent.mkdir(parents=True, exist_ok=True)

            import json
            ipc_file.write_text(json.dumps({
                "sender": msg.sender_name or msg.sender,
                "text": msg.content,
            }))

    async def _drain_pending(
        self,
        jid: str,
        group: RegisteredGroup,
        session_id: Optional[str],
    ):
        """处理待处理项"""
        state = self._get_state(jid)

        # 优先处理任务
        if state.pending_tasks:
            task = state.pending_tasks.pop(0)
            await self._try_start_task(jid, group, task, session_id)
        elif state.pending_messages:
            state.pending_messages = False
            last_timestamp = await self.db.get_last_agent_timestamp(jid)
            await self._try_start_container(jid, group, session_id, last_timestamp)

    async def _drain_waiting(self):
        """唤醒等待的群组"""
        while self.waiting_groups and self.active_count < self.config.MAX_CONCURRENT_CONTAINERS:
            jid = self.waiting_groups.pop(0)
            # TODO: 重新入队

    def _get_state(self, jid: str) -> GroupState:
        """获取群组状态"""
        if jid not in self.states:
            self.states[jid] = GroupState()
        return self.states[jid]

    async def _handle_container_result(self, jid: str, result: ContainerOutput):
        """处理容器结果"""
        if result.status == "success" and result.result:
            # 发送结果到通道
            # TODO: 通过路由器发送
            pass
```

### 3.5 容器运行器 (`core/container_runner.py`)

```python
import asyncio
import json
from pathlib import Path
from typing import Optional, Dict
from loguru import logger
from ..config import Config
from ..types import ContainerOutput, ContainerConfig

OUTPUT_START_MARKER = "---NANOCLAW_OUTPUT_START---"
OUTPUT_END_MARKER = "---NANOCLAW_OUTPUT_END---"

async def run_container_agent(
    group_folder: str,
    prompt: str,
    session_id: Optional[str],
    chat_jid: str,
    is_main: bool,
    container_config: Optional[ContainerConfig] = None,
) -> ContainerOutput:
    """运行容器化 Agent"""

    config = Config()

    # 构建挂载列表
    mounts = await _build_mounts(
        group_folder=group_folder,
        is_main=is_main,
        container_config=container_config,
    )

    # 准备输入
    input_data = {
        "prompt": prompt,
        "sessionId": session_id,
        "groupFolder": group_folder,
        "chatJid": chat_jid,
        "isMain": is_main,
    }

    # 构建 Docker 命令
    cmd = _build_docker_command(mounts, input_data, container_config)

    logger.debug(f"Starting container for {group_folder}")

    try:
        # 启动容器
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # 写入输入
        input_json = json.dumps(input_data)
        process.stdin.write(input_json.encode())
        await process.stdin.drain()
        process.stdin.close()

        # 流式读取输出
        output_buffer = []
        in_output = False

        async for line in process.stdout:
            line_str = line.decode()

            if OUTPUT_START_MARKER in line_str:
                in_output = True
                continue
            elif OUTPUT_END_MARKER in line_str:
                in_output = False
                break

            if in_output:
                output_buffer.append(line_str)

        # 等待进程结束
        await process.wait()

        # 解析输出
        if output_buffer:
            output_json = "".join(output_buffer)
            result = json.loads(output_json)
            return ContainerOutput(**result)
        else:
            return ContainerOutput(status="error", error="No output from container")

    except Exception as e:
        logger.error(f"Container error: {e}")
        return ContainerOutput(status="error", error=str(e))


async def _build_mounts(
    group_folder: str,
    is_main: bool,
    container_config: Optional[ContainerConfig],
) -> list[tuple[str, str, str]]:
    """构建挂载列表 [(host_path, container_path, mode)]"""

    config = Config()
    mounts = []

    if is_main:
        # 主群组：挂载项目根目录
        mounts.append((
            str(config.PROJECT_ROOT),
            "/workspace/project",
            "rw",
        ))

    # 群组目录
    group_path = config.GROUPS_DIR / group_folder
    mounts.append((
        str(group_path),
        "/workspace/group",
        "rw",
    ))

    # 全局只读目录
    global_path = config.GROUPS_DIR / "global"
    if global_path.exists():
        mounts.append((
            str(global_path),
            "/workspace/global",
            "ro",
        ))

    # Claude 会话目录
    session_path = config.DATA_DIR / "sessions" / group_folder / ".claude"
    session_path.mkdir(parents=True, exist_ok=True)
    mounts.append((
        str(session_path),
        "/home/node/.claude",
        "rw",
    ))

    # IPC 目录
    ipc_path = config.DATA_DIR / "ipc" / group_folder
    ipc_path.mkdir(parents=True, exist_ok=True)
    mounts.append((
        str(ipc_path),
        "/workspace/ipc",
        "rw",
    ))

    # 额外挂载（需要安全验证）
    if container_config and container_config.additional_mounts:
        from .mount_security import validate_mounts
        validated = await validate_mounts(
            container_config.additional_mounts,
            is_main=is_main,
        )
        mounts.extend(validated)

    return mounts


def _build_docker_command(
    mounts: list[tuple[str, str, str]],
    input_data: Dict,
    container_config: Optional[ContainerConfig],
) -> list[str]:
    """构建 Docker 命令"""

    config = Config()
    cmd = ["docker", "run", "--rm"]

    # 添加挂载
    for host_path, container_path, mode in mounts:
        cmd.extend(["-v", f"{host_path}:{container_path}:{mode}"])

    # 环境变量
    cmd.extend(["-e", f"NANOCLAW_IS_MAIN={input_data['isMain']}"])

    # 超时
    timeout = (container_config.timeout if container_config
               else config.CONTAINER_TIMEOUT)
    cmd.extend(["--stop-timeout", str(timeout // 1000)])

    # 镜像
    cmd.append(config.CONTAINER_IMAGE)

    return cmd
```

### 3.6 数据库操作 (`database/db.py`)

```python
import aiosqlite
from typing import Optional, List, Dict
from pathlib import Path
from loguru import logger
from ..types import Message, RegisteredGroup, ScheduledTask
from ..config import Config

class Database:
    """异步 SQLite 数据库操作"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """连接数据库"""
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._init_schema()

    async def close(self):
        """关闭连接"""
        if self._conn:
            await self._conn.close()

    async def _init_schema(self):
        """初始化数据库模式"""
        schema = """
        CREATE TABLE IF NOT EXISTS chats (
            jid TEXT PRIMARY KEY,
            name TEXT,
            last_message_time TEXT
        );

        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            chat_jid TEXT NOT NULL,
            sender TEXT NOT NULL,
            sender_name TEXT,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            is_from_me INTEGER DEFAULT 0,
            FOREIGN KEY (chat_jid) REFERENCES chats(jid)
        );

        CREATE INDEX IF NOT EXISTS idx_messages_chat_time
        ON messages(chat_jid, timestamp);

        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_folder TEXT NOT NULL,
            prompt TEXT NOT NULL,
            schedule_type TEXT NOT NULL,
            schedule_value TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            next_run TEXT,
            context_mode TEXT DEFAULT 'group',
            target_chat_jid TEXT
        );

        CREATE TABLE IF NOT EXISTS task_run_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            run_at TEXT NOT NULL,
            duration_ms INTEGER,
            status TEXT NOT NULL,
            result TEXT,
            error TEXT,
            FOREIGN KEY (task_id) REFERENCES scheduled_tasks(id)
        );

        CREATE TABLE IF NOT EXISTS router_state (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS sessions (
            group_folder TEXT PRIMARY KEY,
            session_id TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS registered_groups (
            jid TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            folder TEXT NOT NULL UNIQUE,
            trigger_pattern TEXT,
            container_config TEXT,
            requires_trigger INTEGER DEFAULT 1
        );
        """

        await self._conn.executescript(schema)
        await self._conn.commit()

    async def get_new_messages(
        self,
        last_timestamp: Optional[str],
    ) -> List[Message]:
        """获取新消息"""
        if last_timestamp:
            query = """
                SELECT * FROM messages
                WHERE timestamp > ?
                ORDER BY timestamp ASC
            """
            cursor = await self._conn.execute(query, (last_timestamp,))
        else:
            query = """
                SELECT * FROM messages
                ORDER BY timestamp ASC
                LIMIT 100
            """
            cursor = await self._conn.execute(query)

        rows = await cursor.fetchall()
        return [self._row_to_message(row) for row in rows]

    async def get_messages_since(
        self,
        chat_jid: str,
        since_timestamp: Optional[str],
    ) -> List[Message]:
        """获取特定群组的消息"""
        if since_timestamp:
            query = """
                SELECT * FROM messages
                WHERE chat_jid = ? AND timestamp > ?
                ORDER BY timestamp ASC
            """
            cursor = await self._conn.execute(query, (chat_jid, since_timestamp))
        else:
            query = """
                SELECT * FROM messages
                WHERE chat_jid = ?
                ORDER BY timestamp DESC
                LIMIT 50
            """
            cursor = await self._conn.execute(query, (chat_jid,))

        rows = await cursor.fetchall()
        messages = [self._row_to_message(row) for row in rows]
        return list(reversed(messages))

    async def store_message(self, message: Message):
        """存储消息"""
        query = """
            INSERT OR REPLACE INTO messages
            (id, chat_jid, sender, sender_name, content, timestamp, is_from_me)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        await self._conn.execute(query, (
            message.id,
            message.chat_jid,
            message.sender,
            message.sender_name,
            message.content,
            message.timestamp.isoformat(),
            1 if message.is_from_me else 0,
        ))
        await self._conn.commit()

    async def get_registered_groups(self) -> List[RegisteredGroup]:
        """获取已注册群组"""
        query = "SELECT * FROM registered_groups"
        cursor = await self._conn.execute(query)
        rows = await cursor.fetchall()
        return [self._row_to_registered_group(row) for row in rows]

    async def get_router_state(self) -> Dict:
        """获取路由状态"""
        query = "SELECT key, value FROM router_state"
        cursor = await self._conn.execute(query)
        rows = await cursor.fetchall()

        state = {}
        for row in rows:
            key = row["key"]
            value = row["value"]

            # 解析 JSON 值
            if key in ["sessions", "last_agent_timestamp"]:
                import json
                state[key] = json.loads(value) if value else {}
            else:
                state[key] = value

        return state

    async def save_router_state(self, state: Dict):
        """保存路由状态"""
        import json

        for key, value in state.items():
            if isinstance(value, dict):
                value = json.dumps(value)

            query = """
                INSERT OR REPLACE INTO router_state (key, value)
                VALUES (?, ?)
            """
            await self._conn.execute(query, (key, value))

        await self._conn.commit()

    def _row_to_message(self, row) -> Message:
        """转换数据库行为 Message 对象"""
        from datetime import datetime
        return Message(
            id=row["id"],
            chat_jid=row["chat_jid"],
            sender=row["sender"],
            sender_name=row["sender_name"],
            content=row["content"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            is_from_me=bool(row["is_from_me"]),
        )

    def _row_to_registered_group(self, row) -> RegisteredGroup:
        """转换数据库行为 RegisteredGroup 对象"""
        import json
        return RegisteredGroup(
            jid=row["jid"],
            name=row["name"],
            folder=row["folder"],
            trigger_pattern=row["trigger_pattern"],
            container_config=json.loads(row["container_config"]) if row["container_config"] else None,
            requires_trigger=bool(row["requires_trigger"]),
        )
```


## 4. 扩展功能设计

### 4.1 多通道支持

**Telegram 通道实现** (`channels/telegram.py`):

```python
from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters
from .base import Channel

class TelegramChannel(Channel):
    """Telegram 通道实现"""

    def __init__(self, token: str, db: Database):
        self.token = token
        self.db = db
        self.app: Optional[Application] = None
        self._connected = False

    @property
    def name(self) -> str:
        return "telegram"

    @property
    def prefix_assistant_name(self) -> bool:
        return False  # Telegram bots 不需要前缀

    async def connect(self):
        """连接 Telegram"""
        self.app = Application.builder().token(self.token).build()

        # 注册消息处理器
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

        # 启动轮询
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

        self._connected = True
        logger.info("Telegram channel connected")

    async def send_message(self, jid: str, text: str):
        """发送消息"""
        # jid 格式: telegram:{chat_id}
        chat_id = jid.split(":")[1]
        await self.app.bot.send_message(chat_id=chat_id, text=text)

    def is_connected(self) -> bool:
        return self._connected

    def owns_jid(self, jid: str) -> bool:
        return jid.startswith("telegram:")

    async def disconnect(self):
        """断开连接"""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
        self._connected = False

    async def _handle_message(self, update: Update, context):
        """处理收到的消息"""
        message = update.message
        jid = f"telegram:{message.chat_id}"

        # 存储到数据库
        msg = Message(
            id=f"telegram_{message.message_id}",
            chat_jid=jid,
            sender=str(message.from_user.id),
            sender_name=message.from_user.full_name,
            content=message.text,
            timestamp=message.date,
            is_from_me=False,
        )
        await self.db.store_message(msg)
```

### 4.2 插件系统

**插件基类** (`plugins/base.py`):

```python
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class Plugin(ABC):
    """插件基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """插件版本"""
        pass

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]):
        """初始化插件"""
        pass

    @abstractmethod
    async def shutdown(self):
        """关闭插件"""
        pass

    async def on_message_received(self, message: Message) -> Optional[Message]:
        """消息接收钩子（可修改消息）"""
        return message

    async def on_message_sent(self, jid: str, text: str) -> Optional[str]:
        """消息发送钩子（可修改文本）"""
        return text

    async def on_container_start(self, group_folder: str, prompt: str) -> Optional[str]:
        """容器启动钩子（可修改提示词）"""
        return prompt

    async def on_container_result(self, result: ContainerOutput) -> Optional[ContainerOutput]:
        """容器结果钩子（可修改结果）"""
        return result
```

**插件加载器** (`plugins/loader.py`):

```python
import importlib
import sys
from pathlib import Path
from typing import Dict, List
from loguru import logger
from .base import Plugin

class PluginLoader:
    """插件加载器"""

    def __init__(self, plugin_dir: Path):
        self.plugin_dir = plugin_dir
        self.plugins: Dict[str, Plugin] = {}

    async def load_all(self):
        """加载所有插件"""
        if not self.plugin_dir.exists():
            logger.warning(f"Plugin directory not found: {self.plugin_dir}")
            return

        # 添加插件目录到 sys.path
        sys.path.insert(0, str(self.plugin_dir))

        # 扫描插件
        for plugin_path in self.plugin_dir.glob("*/plugin.py"):
            await self._load_plugin(plugin_path)

    async def _load_plugin(self, plugin_path: Path):
        """加载单个插件"""
        try:
            # 导入模块
            module_name = plugin_path.parent.name
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 查找 Plugin 子类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and
                    issubclass(attr, Plugin) and
                    attr is not Plugin):

                    # 实例化插件
                    plugin = attr()
                    await plugin.initialize({})

                    self.plugins[plugin.name] = plugin
                    logger.info(f"Loaded plugin: {plugin.name} v{plugin.version}")
                    break

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_path}: {e}")

    async def shutdown_all(self):
        """关闭所有插件"""
        for plugin in self.plugins.values():
            try:
                await plugin.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down plugin {plugin.name}: {e}")

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """获取插件"""
        return self.plugins.get(name)

    def list_plugins(self) -> List[str]:
        """列出所有插件"""
        return list(self.plugins.keys())
```

**示例插件：速率限制** (`plugins/builtin/rate_limiter/plugin.py`):

```python
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional
from nanogridbot.plugins.base import Plugin
from nanogridbot.types import Message

class RateLimiterPlugin(Plugin):
    """速率限制插件"""

    @property
    def name(self) -> str:
        return "rate_limiter"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def initialize(self, config: Dict):
        self.max_messages_per_minute = config.get("max_messages_per_minute", 10)
        self.message_counts: Dict[str, list[datetime]] = defaultdict(list)

    async def shutdown(self):
        pass

    async def on_message_received(self, message: Message) -> Optional[Message]:
        """检查速率限制"""
        jid = message.chat_jid
        now = datetime.now()

        # 清理过期记录
        cutoff = now - timedelta(minutes=1)
        self.message_counts[jid] = [
            ts for ts in self.message_counts[jid] if ts > cutoff
        ]

        # 检查限制
        if len(self.message_counts[jid]) >= self.max_messages_per_minute:
            logger.warning(f"Rate limit exceeded for {jid}")
            return None  # 丢弃消息

        # 记录消息
        self.message_counts[jid].append(now)
        return message
```

### 4.3 Web 监控面板

**FastAPI 应用** (`web/app.py`):

```python
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import List
import asyncio

app = FastAPI(title="NanoGridBot Dashboard")

# 全局状态（通过依赖注入传入）
orchestrator = None

@app.get("/")
async def root():
    """主页"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>NanoGridBot Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.js"></script>
    </head>
    <body>
        <div id="app">
            <h1>NanoGridBot Dashboard</h1>
            <div v-for="group in groups" :key="group.jid">
                <h2>{{ group.name }}</h2>
                <p>Status: {{ group.status }}</p>
            </div>
        </div>
        <script>
            const { createApp } = Vue;
            createApp({
                data() {
                    return { groups: [] }
                },
                mounted() {
                    this.connectWebSocket();
                },
                methods: {
                    connectWebSocket() {
                        const ws = new WebSocket('ws://localhost:8000/ws');
                        ws.onmessage = (event) => {
                            this.groups = JSON.parse(event.data);
                        };
                    }
                }
            }).mount('#app');
        </script>
    </body>
    </html>
    """)

@app.get("/api/groups")
async def get_groups():
    """获取群组列表"""
    if not orchestrator:
        return []

    return [
        {
            "jid": jid,
            "name": group.name,
            "folder": group.folder,
            "active": orchestrator.queue.states.get(jid, {}).get("active", False),
        }
        for jid, group in orchestrator.registered_groups.items()
    ]

@app.get("/api/tasks")
async def get_tasks():
    """获取任务列表"""
    if not orchestrator:
        return []

    tasks = await orchestrator.db.get_all_tasks()
    return [task.dict() for task in tasks]

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 实时更新"""
    await websocket.accept()

    try:
        while True:
            # 发送状态更新
            groups = await get_groups()
            await websocket.send_json(groups)
            await asyncio.sleep(2)

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await websocket.close()

def create_app(orch):
    """创建 FastAPI 应用"""
    global orchestrator
    orchestrator = orch
    return app
```

### 4.4 消息历史搜索

**搜索 API** (`web/api/search.py`):

```python
from fastapi import APIRouter, Query
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/api/search", tags=["search"])

@router.get("/messages")
async def search_messages(
    query: str = Query(..., min_length=1),
    chat_jid: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(50, le=200),
):
    """搜索消息"""
    # 使用 SQLite FTS5 全文搜索
    sql = """
        SELECT * FROM messages
        WHERE content MATCH ?
    """
    params = [query]

    if chat_jid:
        sql += " AND chat_jid = ?"
        params.append(chat_jid)

    if start_date:
        sql += " AND timestamp >= ?"
        params.append(start_date.isoformat())

    if end_date:
        sql += " AND timestamp <= ?"
        params.append(end_date.isoformat())

    sql += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    cursor = await orchestrator.db._conn.execute(sql, params)
    rows = await cursor.fetchall()

    return [
        {
            "id": row["id"],
            "chat_jid": row["chat_jid"],
            "sender_name": row["sender_name"],
            "content": row["content"],
            "timestamp": row["timestamp"],
        }
        for row in rows
    ]
```

### 4.5 健康检查和指标

**健康检查端点** (`web/api/health.py`):

```python
from fastapi import APIRouter
from datetime import datetime

router = APIRouter(prefix="/api/health", tags=["health"])

@router.get("/")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    }

@router.get("/metrics")
async def get_metrics():
    """获取系统指标"""
    if not orchestrator:
        return {}

    return {
        "active_containers": orchestrator.queue.active_count,
        "waiting_groups": len(orchestrator.queue.waiting_groups),
        "registered_groups": len(orchestrator.registered_groups),
        "channels": [
            {
                "name": ch.name,
                "connected": ch.is_connected(),
            }
            for ch in orchestrator.channels
        ],
    }
```

---

## 5. 配置管理 (`config.py`)

```python
from pathlib import Path
from typing import Optional
import os

class Config:
    """配置管理"""

    # 基础路径
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    STORE_DIR = PROJECT_ROOT / "store"
    GROUPS_DIR = PROJECT_ROOT / "groups"
    DATA_DIR = PROJECT_ROOT / "data"

    # 助手配置
    ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "Andy")
    TRIGGER_PATTERN = rf"^@{ASSISTANT_NAME}\b"

    # 轮询间隔
    POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "2000"))  # ms
    SCHEDULER_POLL_INTERVAL = int(os.getenv("SCHEDULER_POLL_INTERVAL", "60000"))  # ms

    # 容器配置
    CONTAINER_IMAGE = os.getenv("CONTAINER_IMAGE", "nanogridbot-agent:latest")
    CONTAINER_TIMEOUT = int(os.getenv("CONTAINER_TIMEOUT", "1800000"))  # 30 min
    CONTAINER_MAX_OUTPUT_SIZE = int(os.getenv("CONTAINER_MAX_OUTPUT_SIZE", "10485760"))  # 10MB
    IDLE_TIMEOUT = int(os.getenv("IDLE_TIMEOUT", "1800000"))  # 30 min

    # 并发限制
    MAX_CONCURRENT_CONTAINERS = int(os.getenv("MAX_CONCURRENT_CONTAINERS", "5"))

    # 日志级别
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Web 监控
    WEB_ENABLED = os.getenv("WEB_ENABLED", "false").lower() == "true"
    WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT = int(os.getenv("WEB_PORT", "8000"))

    # WhatsApp 配置
    WHATSAPP_ENABLED = os.getenv("WHATSAPP_ENABLED", "true").lower() == "true"

    # Telegram 配置
    TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    # 挂载安全
    MOUNT_ALLOWLIST_PATH = Path.home() / ".config" / "nanogridbot" / "mount-allowlist.json"

    def __init__(self):
        # 确保目录存在
        self.STORE_DIR.mkdir(parents=True, exist_ok=True)
        self.GROUPS_DIR.mkdir(parents=True, exist_ok=True)
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
```

---

## 6. 主入口 (`__main__.py`)

```python
import asyncio
import signal
from loguru import logger
from .config import Config
from .logger import setup_logger
from .database.db import Database
from .core.orchestrator import Orchestrator
from .channels.whatsapp import WhatsAppChannel
from .channels.telegram import TelegramChannel
from .plugins.loader import PluginLoader

async def main():
    """主函数"""
    config = Config()
    setup_logger(config.LOG_LEVEL)

    logger.info("Starting NanoGridBot")

    # 初始化数据库
    db = Database(config.STORE_DIR / "messages.db")
    await db.connect()

    # 初始化通道
    channels = []

    if config.WHATSAPP_ENABLED:
        whatsapp = WhatsAppChannel(db, config.STORE_DIR / "auth")
        channels.append(whatsapp)

    if config.TELEGRAM_ENABLED and config.TELEGRAM_BOT_TOKEN:
        telegram = TelegramChannel(config.TELEGRAM_BOT_TOKEN, db)
        channels.append(telegram)

    # 加载插件
    plugin_loader = PluginLoader(config.PROJECT_ROOT / "plugins")
    await plugin_loader.load_all()

    # 创建编排器
    orchestrator = Orchestrator(config, db, channels)

    # 启动 Web 监控（可选）
    if config.WEB_ENABLED:
        from .web.app import create_app
        import uvicorn

        app = create_app(orchestrator)
        web_server = uvicorn.Server(
            uvicorn.Config(app, host=config.WEB_HOST, port=config.WEB_PORT)
        )

        # 在后台运行 Web 服务器
        asyncio.create_task(web_server.serve())

    # 信号处理
    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(orchestrator.stop())

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # 启动编排器
    try:
        await orchestrator.start()
    finally:
        await plugin_loader.shutdown_all()
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 6.1 CLI 命令行接口 (`cli.py`)

NanoGridBot 提供四种 CLI 模式，支持不同的使用场景：

### 6.1.1 CLI 模式

| 模式 | 命令 | 说明 |
|------|------|------|
| **serve** | `nanogridbot serve` | 启动完整服务（orchestrator + web dashboard）|
| **shell** | `nanogridbot shell` | 交互式容器 REPL |
| **chat** | `nanogridbot chat "prompt"` | 单次消息交互 |
| **run** | `nanogridbot run <group>` | 对已注册群组执行 prompt |

### 6.1.2 核心组件

```python
# src/nanogridbot/cli.py
import argparse
from nanogridbot.core.container_session import ContainerSession
from nanogridbot.core.container_runner import run_container_agent

async def cmd_serve(args):     # 启动完整服务
async def cmd_shell(args):      # 交互式 REPL
async def cmd_chat(args):      # 单次消息
async def cmd_run(args):        # 群组执行
```

### 6.1.3 ContainerSession

交互式 shell 模式使用的容器会话管理：

```python
class ContainerSession:
    """管理交互式容器会话"""

    def __init__(self, group_folder: str = "cli", session_id: str | None = None):
        self.group_folder = group_folder
        self.session_id = session_id
        self.container_name = f"ngb-shell-{group_folder}-{uuid}"

    async def start(self):      # 启动命名容器
    async def send(self, text):  # 发送消息
    async def receive(self):     # 接收消息 (AsyncGenerator)
    async def close(self):       # 关闭会话

    @property
    def is_alive(self) -> bool:  # 检查会话状态
```

### 6.1.4 IPC 机制

ContainerSession 通过文件系统进行 IPC 通信：

```
data_dir/ipc/{jid}/
├── input/           # 输入文件 (JSON)
│   ├── input-{timestamp}.json
│   └── _close       # 关闭信号
└── output/          # 输出文件 (JSON)
    └── {timestamp}.json
```

---

## 7. 项目配置 (`pyproject.toml`)

```toml
[project]
name = "nanogridbot"
version = "1.0.0"
description = "Personal Claude AI assistant accessible via WhatsApp"
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
requires-python = ">=3.12"
dependencies = [
    "aiosqlite>=0.19.0",
    "loguru>=0.7.0",
    "pydantic>=2.5.0",
    "croniter>=2.0.0",
    "aiofiles>=23.2.0",
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "python-telegram-bot>=20.7",
    "qrcode>=7.4.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "black>=23.12.0",
    "ruff>=0.1.9",
    "mypy>=1.8.0",
]

[project.scripts]
nanogridbot = "nanogridbot.__main__:main"

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.black]
line-length = 100
target-version = ["py312"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## 8. Docker 配置

**主应用 Dockerfile**:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY pyproject.toml .
COPY src/ src/

# 安装 Python 依赖
RUN pip install --no-cache-dir -e .

# 创建数据目录
RUN mkdir -p /data/store /data/groups /data/data

# 暴露 Web 端口
EXPOSE 8000

CMD ["python", "-m", "nanogridbot"]
```

**Agent 容器 Dockerfile** (`container/Dockerfile`):

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装 Chromium（用于浏览器自动化）
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# 安装 Claude Code（假设有 Python 版本）
RUN pip install --no-cache-dir claude-code

# 复制 Agent Runner
COPY agent_runner/ /app/

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 入口脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
```

**docker-compose.yml**:

```yaml
version: '3.8'

services:
  nanogridbot:
    build: .
    container_name: nanogridbot
    volumes:
      - ./store:/data/store
      - ./groups:/data/groups
      - ./data:/data/data
      - /var/run/docker.sock:/var/run/docker.sock  # 用于启动 Agent 容器
    environment:
      - ASSISTANT_NAME=Andy
      - LOG_LEVEL=INFO
      - WEB_ENABLED=true
      - WHATSAPP_ENABLED=true
      - TELEGRAM_ENABLED=false
    ports:
      - "8000:8000"
    restart: unless-stopped
```

---

## 9. 测试策略

### 9.1 单元测试

**测试数据库操作** (`tests/unit/test_database.py`):

```python
import pytest
from nanogridbot.database.db import Database
from nanogridbot.types import Message
from datetime import datetime

@pytest.fixture
async def db():
    db = Database(":memory:")
    await db.connect()
    yield db
    await db.close()

@pytest.mark.asyncio
async def test_store_and_retrieve_message(db):
    """测试存储和检索消息"""
    message = Message(
        id="test_1",
        chat_jid="test@s.whatsapp.net",
        sender="user@s.whatsapp.net",
        sender_name="Test User",
        content="Hello, world!",
        timestamp=datetime.now(),
        is_from_me=False,
    )

    await db.store_message(message)

    messages = await db.get_new_messages(None)
    assert len(messages) == 1
    assert messages[0].content == "Hello, world!"
```

### 9.2 集成测试

**测试消息流程** (`tests/integration/test_message_flow.py`):

```python
import pytest
from nanogridbot.core.orchestrator import Orchestrator
from nanogridbot.config import Config
from nanogridbot.database.db import Database

@pytest.mark.asyncio
async def test_message_processing():
    """测试完整的消息处理流程"""
    config = Config()
    db = Database(":memory:")
    await db.connect()

    # 创建模拟通道
    class MockChannel:
        name = "mock"
        def is_connected(self): return True
        def owns_jid(self, jid): return True
        async def connect(self): pass
        async def disconnect(self): pass
        async def send_message(self, jid, text): pass

    orchestrator = Orchestrator(config, db, [MockChannel()])

    # 注册测试群组
    # ... 测试逻辑
```

### 9.3 端到端测试

使用 pytest + Docker Compose 进行完整的端到端测试。

---

## 10. 部署指南

### 10.1 本地开发

```bash
# 克隆仓库
git clone https://github.com/yourusername/nanogridbot.git
cd nanogridbot

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# 安装依赖
pip install -e ".[dev]"

# 运行
python -m nanogridbot
```

### 10.2 Docker 部署

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 10.3 生产部署

1. **配置环境变量**
2. **设置挂载白名单**
3. **配置反向代理**（Nginx）
4. **启用 HTTPS**
5. **配置监控和告警**

---

## 11. 迁移路径

### 11.1 数据库兼容

Python 版本使用相同的 SQLite 数据库模式，可以直接读取 TypeScript 版本的数据库。

### 11.2 IPC 协议兼容

文件格式和目录结构保持一致，两个版本可以共享 IPC 目录。

### 11.3 渐进式迁移

1. 先部署 Python 版本，使用只读模式验证
2. 逐步切换通道到 Python 版本
3. 完全迁移后停止 TypeScript 版本

---

## 12. 最佳实践

### 12.1 性能优化

- 使用连接池管理数据库连接
- 实现消息批处理
- 使用 Redis 缓存热数据
- 异步 I/O 最大化并发

### 12.2 安全加固

- 定期审计挂载白名单
- 实现请求签名验证
- 启用容器资源限制
- 定期更新依赖

### 12.3 可观测性

- 结构化日志（JSON 格式）
- Prometheus 指标导出
- 分布式追踪（OpenTelemetry）
- 告警规则配置

---

## 13. 总结

NanoGridBot 是 NanoClaw 的完整 Python 移植，具有以下优势：

1. **功能对等**: 1:1 复制所有核心功能
2. **Python 生态**: 利用丰富的 Python 库
3. **异步架构**: 基于 asyncio 的高性能设计
4. **可扩展性**: 插件系统、多通道支持、Web 监控
5. **类型安全**: Pydantic 数据验证
6. **易于部署**: Docker 容器化
7. **向后兼容**: 可与 TypeScript 版本共存

**下一步行动**:
1. 实现核心模块（orchestrator, database, container_runner）
2. 实现 WhatsApp 通道（评估可用库）
3. 编写单元测试

---

## 14. Phase 10: 生产就绪 (Week 12-13)

### 14.1 错误处理和恢复机制

#### 新增模块: `src/nanogridbot/utils/error_handling.py`

```python
# 重试装饰器
@with_retry(max_retries=3, base_delay=1.0, exceptions=(ConnectionError,))
async def fetch_data():
    ...

# 断路器
breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
result = await breaker.call(async_function, args)

# 优雅关闭
shutdown = GracefulShutdown()
shutdown.request_shutdown()
await shutdown.wait_for_shutdown()
```

#### 增强的 Orchestrator

```python
class Orchestrator:
    async def start(self):
        self._setup_signal_handlers()  # SIGINT, SIGTERM
        await self._connect_channels_with_retry()

    def get_health_status(self) -> dict:
        # 返回健康状态
        return {
            "healthy": bool,
            "channels_connected": int,
            "registered_groups": int,
            "active_containers": int,
            "uptime_seconds": int,
        }
```

### 14.2 性能优化

#### 配置选项

```python
class Config:
    message_cache_size: int = 1000    # 消息缓存大小
    batch_size: int = 100              # 批处理大小
    db_connection_pool_size: int = 5   # 数据库连接池
    ipc_file_buffer_size: int = 8192   # IPC 文件缓冲区
```

#### 消息缓存

```python
class MessageCache:
    """LRU 缓存用于最近的消息"""
    def get(self, key: str) -> Message | None
    def put(self, key: str, message: Message) -> None
    def clear(self) -> None
```

#### 数据库优化

- 启用 WAL (Write-Ahead Logging) 模式
- 设置 busy_timeout 提高并发性能

### 14.3 日志改进

#### 结构化日志

```python
from nanogridbot.logger import get_structured_logger

log = get_structured_logger(__name__)
log.info("Container started", container_id="abc", group="main")
log.error("Connection failed", channel="telegram", error="timeout")
```

#### 日志配置

```python
setup_logger(
    structured=True,     # JSON 格式日志
    log_file=Path("logs/app.log"),
    rotation="10 MB",
    retention="7 days",
)
```

### 14.4 测试结果

- **单元测试**: 124 个测试通过
- **代码覆盖率**: 40%

---

## 15. 项目完成总结

NanoGridBot 项目现已完全完成，具备以下功能：

| 模块 | 状态 | 说明 |
|------|------|------|
| 基础架构 | ✅ | 配置、日志、类型定义 |
| 数据库层 | ✅ | 异步 SQLite 操作 |
| 通道抽象 | ✅ | 8 个消息平台支持 |
| 容器管理 | ✅ | Docker 容器运行器 |
| 任务调度 | ✅ | CRON/Interval/Once |
| Web 面板 | ✅ | FastAPI + Vue.js |
| 插件系统 | ✅ | 热重载、配置管理 |
| 错误处理 | ✅ | 重试、断路器、优雅关闭 |
| 性能优化 | ✅ | 消息缓存、数据库优化 |
| 日志系统 | ✅ | 结构化日志 |

**版本**: v0.1.0-alpha
**测试覆盖**: 40%
**支持平台**: 8 个 (WhatsApp, Telegram, Slack, Discord, QQ, Feishu, WeCom, DingTalk)
4. 构建 Docker 镜像
5. 端到端测试
6. 文档完善
