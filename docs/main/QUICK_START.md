# NanoGridBot 快速开始指南

## 项目简介

NanoGridBot 是 NanoClaw 项目的 Python 1:1 移植版本，是一个轻量级、安全的个人 Claude AI 助手，通过 WhatsApp 提供交互界面。

### 核心特性

- ✅ **容器隔离**: 使用 Docker 实现 OS 级别的安全隔离
- ✅ **多组隔离**: 每个 WhatsApp 群组拥有独立的文件系统和会话
- ✅ **异步架构**: 基于 asyncio 的高性能设计
- ✅ **类型安全**: 使用 Pydantic 进行数据验证
- ✅ **可扩展**: 支持插件系统、多通道、Web 监控

---

## 快速开始

### 前置要求

- Python 3.12+
- Docker
- Node.js 20+ (用于 WhatsApp 桥接)
- Git

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/yourusername/nanogridbot.git
cd nanogridbot

# 2. 创建虚拟环境
python3.12 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -e ".[dev]"

# 4. 构建 Docker 镜像
docker build -t nanogridbot-agent:latest container/

# 5. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，设置必要的配置

# 6. 初始化数据库
python -m nanogridbot.database.init

# 7. 启动服务
python -m nanogridbot
```

### Docker Compose 部署

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

---

## 项目结构

```
nanogridbot/
├── src/nanogridbot/       # 源代码
│   ├── core/              # 核心模块
│   ├── database/          # 数据库
│   ├── channels/          # 通道抽象
│   ├── plugins/           # 插件系统
│   └── web/               # Web 监控
├── container/             # Agent 容器
├── bridge/                # Baileys 桥接
├── groups/                # 群组工作目录
├── data/                  # 运行时数据
├── store/                 # 持久化存储
├── tests/                 # 测试
└── docs/                  # 文档
```

---

## 配置说明

### 环境变量

在 `.env` 文件中配置以下变量：

```bash
# 助手配置
ASSISTANT_NAME=Andy
TRIGGER_PATTERN=^@Andy\b

# 轮询间隔
POLL_INTERVAL=2000                    # 消息轮询间隔（毫秒）
SCHEDULER_POLL_INTERVAL=60000         # 任务调度间隔（毫秒）

# 容器配置
CONTAINER_IMAGE=nanogridbot-agent:latest
CONTAINER_TIMEOUT=1800000             # 容器超时（30 分钟）
MAX_CONCURRENT_CONTAINERS=5           # 最大并发容器数

# 日志级别
LOG_LEVEL=INFO

# Web 监控
WEB_ENABLED=true
WEB_HOST=0.0.0.0
WEB_PORT=8000

# WhatsApp
WHATSAPP_ENABLED=true

# Telegram（可选）
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 挂载白名单

创建 `~/.config/nanogridbot/mount-allowlist.json`:

```json
{
  "allowedRoots": [
    {
      "path": "~/projects",
      "allowReadWrite": true,
      "description": "开发项目目录"
    }
  ],
  "blockedPatterns": [
    ".ssh",
    ".gnupg",
    ".aws",
    ".env",
    "credentials"
  ],
  "nonMainReadOnly": true
}
```

---

## 使用指南

### 注册群组

1. 将机器人添加到 WhatsApp 群组
2. 发送消息: `@Andy register group`
3. 机器人会自动创建群组目录和配置

### 发送消息

在群组中发送消息，以 `@Andy` 开头：

```
@Andy 帮我分析这段代码的性能问题
```

### 创建定时任务

```
@Andy schedule task
提示词: 每天早上 8 点发送天气预报
调度类型: cron
Cron 表达式: 0 8 * * *
```

### 查看任务列表

```
@Andy list tasks
```

---

## 开发指南

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/unit/test_database.py

# 运行测试并生成覆盖率报告
pytest --cov=src --cov-report=html
```

### 代码格式化

```bash
# 格式化代码
black src/ tests/

# 排序导入
isort src/ tests/

# 运行 Linter
ruff check src/ tests/

# 类型检查
mypy src/
```

### 构建 Docker 镜像

```bash
# 构建主应用镜像
docker build -t nanogridbot:latest .

# 构建 Agent 容器镜像
docker build -t nanogridbot-agent:latest container/
```

---

## 插件开发

### 创建插件

1. 在 `plugins/` 目录下创建插件目录
2. 创建 `plugin.py` 文件
3. 继承 `Plugin` 基类

示例插件：

```python
# plugins/my_plugin/plugin.py
from nanogridbot.plugins.base import Plugin
from nanogridbot.types import Message

class MyPlugin(Plugin):
    @property
    def name(self) -> str:
        return "my_plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def initialize(self, config: dict):
        """初始化插件"""
        self.config = config

    async def shutdown(self):
        """关闭插件"""
        pass

    async def on_message_received(self, message: Message):
        """消息接收钩子"""
        # 处理消息
        return message
```

### 加载插件

插件会在启动时自动加载。可以通过配置文件禁用特定插件。

---

## Web 监控面板

### 访问面板

启动服务后，访问: `http://localhost:8000`

### 功能

- 📊 实时群组状态
- 📝 任务管理
- 🔍 消息历史搜索
- 📈 系统指标
- 🔔 实时通知

### API 端点

- `GET /api/groups` - 获取群组列表
- `GET /api/tasks` - 获取任务列表
- `GET /api/health` - 健康检查
- `GET /api/metrics` - 系统指标
- `WS /ws` - WebSocket 实时更新

---

## 故障排除

### 常见问题

#### 1. 容器启动失败

**症状**: 容器无法启动或立即退出

**解决方案**:
```bash
# 检查 Docker 是否运行
docker ps

# 检查镜像是否存在
docker images | grep nanogridbot-agent

# 重新构建镜像
docker build -t nanogridbot-agent:latest container/
```

#### 2. WhatsApp 连接失败

**症状**: 无法连接到 WhatsApp

**解决方案**:
```bash
# 检查 Baileys 桥接进程
ps aux | grep whatsapp-bridge

# 重启桥接
pkill -f whatsapp-bridge
python -m nanogridbot
```

#### 3. 数据库锁定

**症状**: `database is locked` 错误

**解决方案**:
```bash
# 启用 WAL 模式
sqlite3 store/messages.db "PRAGMA journal_mode=WAL;"

# 检查是否有其他进程占用
lsof store/messages.db
```

#### 4. 消息处理延迟

**症状**: 消息响应缓慢

**解决方案**:
- 检查并发容器数配置
- 增加 `MAX_CONCURRENT_CONTAINERS`
- 优化数据库查询
- 检查系统资源使用

---

## 性能优化

### 数据库优化

```sql
-- 启用 WAL 模式
PRAGMA journal_mode=WAL;

-- 增加缓存大小
PRAGMA cache_size=-64000;  -- 64MB

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_messages_chat_time
ON messages(chat_jid, timestamp);
```

### 容器优化

```bash
# 预拉取镜像
docker pull nanogridbot-agent:latest

# 使用 BuildKit
export DOCKER_BUILDKIT=1
docker build -t nanogridbot-agent:latest container/
```

### 系统优化

```bash
# 增加文件描述符限制
ulimit -n 65536

# 优化 Python GC
export PYTHONOPTIMIZE=1
```

---

## 监控和日志

### 查看日志

```bash
# 实时日志
tail -f logs/nanogridbot.log

# 过滤错误日志
grep ERROR logs/nanogridbot.log

# 使用 jq 解析 JSON 日志
tail -f logs/nanogridbot.log | jq '.'
```

### 系统指标

访问 `http://localhost:8000/api/metrics` 查看：

- 活跃容器数
- 等待队列长度
- 消息处理速率
- 错误率
- 资源使用情况

---

## 安全最佳实践

### 1. 挂载安全

- 仅挂载必要的目录
- 使用只读挂载
- 定期审计白名单

### 2. 容器安全

- 使用非 root 用户
- 限制容器资源
- 定期更新镜像

### 3. 数据安全

- 加密敏感配置
- 定期备份数据库
- 实施访问控制

### 4. 网络安全

- 使用 HTTPS
- 实施 API 认证
- 启用速率限制

---

## 贡献指南

### 提交代码

1. Fork 仓库
2. 创建特性分支: `git checkout -b feature/my-feature`
3. 提交更改: `git commit -am 'Add my feature'`
4. 推送分支: `git push origin feature/my-feature`
5. 创建 Pull Request

### 代码规范

- 遵循 PEP 8
- 使用 Black 格式化
- 添加类型注解
- 编写单元测试
- 更新文档

---

## 许可证

MIT License

---

## 联系方式

- GitHub: https://github.com/yourusername/nanogridbot
- Issues: https://github.com/yourusername/nanogridbot/issues
- Discussions: https://github.com/yourusername/nanogridbot/discussions

---

## 致谢

本项目基于 [NanoClaw](https://github.com/nanoclaw/nanoclaw) 项目，感谢原作者的优秀工作。

---

**文档版本**: 1.0
**最后更新**: 2026-02-13
