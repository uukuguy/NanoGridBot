# {🦑} NanoGridBot

> NanoGridBot - 基于 Claude Agent SDK 驱动的智能体开发控制台。使用最强大的智能体运行时，构建、测试和验证集成 Skills、MCP 和 CLI 的 AI 智能体。

[English](README.md)

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**NanoGridBot** 是一个基于 Claude Agent SDK 驱动的全面智能体开发平台。提供最强大的智能体运行时，具备深度 Skills、MCP 和 CLI 集成验证能力：

- 🔥 **Claude Agent SDK 驱动** - 最强大的智能体运行时，基于 Claude Code
- 🛠️ **Skills & MCP 集成** - 在隔离容器中验证 Skills、MCP 服务器和 CLI 工具
- 🔌 **多 LLM 支持**：Claude、OpenAI、Anthropic API、自定义 LLM
- 📡 **8 个消息平台**：在生产级环境中测试（WhatsApp、Telegram、Slack、Discord、QQ、飞书、企业微信、钉钉）
- ⚡ **交互式 Shell**：支持会话恢复的实时调试
- 🛠️ **5 种 CLI 模式**：serve、shell、run、logs、session

## 为何选择 NanoGridBot

| 特性 | 传统开发 | NanoGridBot |
|------|----------|--------------|
| **智能体运行时** | 手动搭建 | Claude Agent SDK - 最强大能力 |
| **Skills/MCP/CLI** | 难以测试 | 隔离容器内集成验证 |
| **调试** | 日志 + print | 交互式 Shell + Web 实时监控 |
| **多轮对话** | 无状态 | 会话恢复 + IPC 消息流 |
| **团队协作** | 单智能体 | Claude Agent SDK Teams 支持 |

## 应用场景

1. **Skills & MCP 验证** - 在隔离容器中验证 Skills、MCP 服务器和 CLI 工具
2. **交互式智能体开发** - 使用 `shell` 模式进行实时调试
3. **智能体行为测试** - 跨 8 个消息平台测试智能体行为
4. **功能原型** - 使用 `run` 模式快速验证提示词/功能
5. **个人 AI 助手** - 使用 `serve` 模式部署日常使用
6. **任务自动化** - 使用内置调度器实现周期性任务

## 目录

- [快速开始](#快速开始)
- [架构设计](#架构设计)
- [核心能力](#核心能力)
- [CLI 工具](#cli-工具)
- [开发指南](#开发指南)
- [部署方案](#部署方案)
- [文档索引](#文档索引)

---

## 快速开始

### 环境要求

- Python 3.12+
- Docker
- Git

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/nanogridbot.git
cd nanogridbot

# 使用 uv 安装（推荐）
uv sync

# 构建 Agent 容器镜像
docker build -t nanogridbot-agent:latest container/

# 启动服务
uv run nanogridbot serve
```

### 五种运行模式

```bash
# 1. Serve 模式：启动完整服务（Web 监控面板）
nanogridbot serve
nanogridbot serve --host 0.0.0.0 --port 8080

# 2. Shell 模式：交互式容器会话（多轮对话）
nanogridbot shell
nanogridbot shell -g myproject                 # 指定项目组
nanogridbot shell --resume session-id           # 恢复之前的会话

# 3. Run 模式：单次非交互式执行
nanogridbot run -p "请解释什么是递归"
echo "你的问题" | nanogridbot run -p -         # 管道输入
nanogridbot run -g myproject -p "分析代码"     # 指定项目组
nanogridbot run -g myproject -p "任务" --timeout 60 --env KEY=VALUE

# 4. Logs 模式：查看和跟踪日志
nanogridbot logs -n 100           # 显示最后100行
nanogridbot logs -f               # 跟踪日志输出

# 5. Session 模式：管理交互式会话
nanogridbot session ls            # 列出所有会话
nanogridbot session kill <id>     # 终止会话
nanogridbot session resume <id>   # 显示恢复信息
```

---

## 架构设计

### 设计理念

```
┌─────────────────────────────────────────────────────────────────┐
│                    NanoGridBot 智能体开发平台                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│   │   CLI 工具   │    │  Web 监控   │    │   消息通道   │   │
│   │  (调试/测试) │    │  (状态/日志) │    │ (多平台接入) │   │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘   │
│          │                    │                    │           │
│          └────────────────────┼────────────────────┘           │
│                               ▼                                │
│   ┌────────────────────────────────────────────────────────┐   │
│   │              核心编排层 (Orchestrator)                 │   │
│   │   • 消息路由    • 任务调度    • 容器管理    • 插件加载 │   │
│   └─────────────────────────┬──────────────────────────┘   │
│                               │                               │
│                               ▼                               │
│   ┌────────────────────────────────────────────────────────┐   │
│   │              容器隔离层 (Container Runtime)             │   │
│   │   • Docker 容器    • 文件系统隔离    • IPC 通信      │   │
│   │   • Claude Agent SDK    • 会话管理                  │   │
│   └────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 核心模块

| 模块 | 职责 | 文件 |
|------|------|------|
| **Orchestrator** | 全局状态管理、消息循环、通道协调 | `core/orchestrator.py` |
| **ContainerRunner** | 容器生命周期管理、挂载配置 | `core/container_runner.py` |
| **ContainerSession** | 交互式会话管理、IPC 通信 | `core/container_session.py` |
| **GroupQueue** | 并发控制、消息排队、重试机制 | `core/group_queue.py` |
| **TaskScheduler** | Cron/Interval/OneTime 任务调度 | `core/task_scheduler.py` |
| **Router** | 消息路由、触发词匹配、广播 | `core/router.py` |
| **Database** | SQLite 持久化、消息缓存 | `database/` |
| **Channels** | 8 种消息平台适配器 | `channels/` |

### 架构优势

- **Claude Agent SDK 原生能力**：基于 Claude Code 构建，具备智能体团队、会话恢复和对话归档功能
- **MCP 深度集成**：通过 `mcpServers` 配置自定义 MCP 服务器，智能体内可直接调用
- **Skills 零门槛验证**：使用 `shell` 模式直接测试 Skills 在智能体中的表现
- **文件系统隔离**：每个群组独立的 `/workspace/group` 目录，安全隔离
- **对话持久化**：PreCompact Hook 自动归档对话历史
- **IPC 消息流**：支持多轮对话，实时推送消息到运行中的智能体

### 容器隔离设计

NanoGridBot 从 NanoClaw 借鉴了容器隔离的核心思路，并进行了增强：

```
┌─────────────────────────────────────────────────────────────┐
│                    Host System (NanoGridBot)                │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              Agent Container (Docker)                  │ │
│  │  • Claude Agent SDK                                  │ │
│  │  • 非 root 用户 (node:1000)                         │ │
│  │  • 显式挂载 (仅允许目录)                           │ │
│  │  • 网络隔离 (--network=none)                        │ │
│  │  • IPC 文件监控 (follow-up messages)                │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ JSON via stdin/stdout
                              │ OR IPC files
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Host System (NanoGridBot)                │
│  • 消息轮询 (2s 间隔)                                      │
│  • SQLite 状态持久化                                       │
│  • 群组队列 (并发控制)                                     │
│  • 任务调度 (Cron)                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心能力

### 容器化智能体运行时

- ✅ **多 LLM 支持**：Claude、OpenAI、Anthropic API、自定义 LLM
- ✅ **容器隔离**：智能体在隔离的 Docker 容器中运行，安全可控
- ✅ **会话管理**：多轮对话支持，会话持久化
- ✅ **上下文管理**：为不同项目/群组维护独立上下文
- ✅ **实时监控**：Web 面板实时查看 Agent 状态和输出
- ✅ **交互式调试**：Shell 模式直接与 Agent 对话

### 多通道部署（用于测试/模拟）

> 8 个消息平台用于实现真实场景模拟，便于智能体行为测试，而非首要构建目的。

| 通道 | SDK | 状态 |
|------|-----|------|
| WhatsApp | pywa | ✅ |
| Telegram | python-telegram-bot | ✅ |
| Slack | python-slack-sdk | ✅ |
| Discord | discord.py | ✅ |
| QQ | NoneBot2/OneBot | ✅ |
| 飞书 | lark-oapi | ✅ |
| 企业微信 | httpx | ✅ |
| 钉钉 | dingtalk-stream | ✅ |

### 扩展功能

- 🔌 **插件系统**：热加载插件，自定义处理逻辑
- 📊 **Web 监控面板**：实时状态、任务管理、日志查看
- 🔄 **任务调度**：Cron 表达式、间隔任务、单次任务
- 🔒 **安全隔离**：挂载白名单、路径遍历防护

---

## CLI 工具

### 命令参考

```bash
# 查看帮助
nanogridbot --help

# 版本信息
nanogridbot --version

# Serve 模式：完整服务（Web 监控面板）
nanogridbot serve                    # 默认启动
nanogridbot serve --host 0.0.0.0    # 自定义地址
nanogridbot serve --port 9000        # 自定义端口
nanogridbot serve --debug            # 调试模式

# Shell 模式：交互式容器会话（多轮对话）
nanogridbot shell                           # 默认（项目组：cli）
nanogridbot shell -g myproject              # 指定项目文件夹
nanogridbot shell --resume session-id       # 恢复之前的会话
nanogridbot shell --attach                  # 附加到容器 shell

# Run 模式：单次非交互式执行
nanogridbot run -p "请解释什么是闭包"
echo "问题" | nanogridbot run -p -           # 管道输入
nanogridbot run -g mygroup -p "任务"         # 指定项目组
nanogridbot run -p "任务" --timeout 60       # 自定义超时时间
nanogridbot run -p "任务" -e KEY=VALUE       # 环境变量

# Logs 模式：查看和跟踪日志
nanogridbot logs -n 100           # 显示最后100行
nanogridbot logs -f               # 跟踪日志输出

# Session 模式：管理交互式会话
nanogridbot session ls            # 列出所有会话
nanogridbot session kill <id>     # 终止会话
nanogridbot session resume <id>   # 显示恢复信息
```

### LLM 参数

所有 CLI 模式支持共享的 LLM 参数：

```bash
--model MODEL              # 模型名称 (默认: claude-sonnet-4-20250514)
--max-tokens MAX_TOKENS   # 最大 tokens (默认: 4096)
--temperature TEMP        # 温度参数 (默认: 0.7)
--system SYSTEM           # 系统提示词
--stream                  # 流式输出
```

---

## 开发指南

### 项目结构

```
nanogridbot/
├── src/nanogridbot/       # 源代码
│   ├── core/              # 核心模块
│   │   ├── orchestrator.py
│   │   ├── container_runner.py
│   │   ├── container_session.py
│   │   ├── group_queue.py
│   │   ├── task_scheduler.py
│   │   ├── router.py
│   │   └── mount_security.py
│   ├── database/           # 数据库层
│   ├── channels/          # 消息通道
│   ├── plugins/           # 插件系统
│   ├── web/               # Web 监控
│   └── cli.py             # CLI 入口
├── container/             # Agent 容器
├── tests/                 # 测试
├── docs/                  # 文档
└── data/                  # 运行时数据
```

### 开发命令

```bash
# 运行测试
pytest -xvs

# 覆盖率报告
pytest --cov=src --cov-report=html

# 代码格式化
black . && isort .

# 类型检查
mypy src/

# 代码检查
ruff check .
```

### 创建插件

```python
# plugins/my_plugin/plugin.py
from nanogridbot.plugins.base import Plugin

class MyPlugin(Plugin):
    @property
    def name(self) -> str:
        return "my_plugin"

    async def on_message_received(self, message):
        # 处理消息
        return message
```

---

## 部署方案

### Docker 部署

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 生产环境配置

1. 配置环境变量
2. 设置挂载白名单
3. 配置反向代理（Nginx）
4. 启用 HTTPS
5. 配置监控告警

---

## 文档索引

### 设计文档

- [架构设计](docs/design/NANOGRIDBOT_DESIGN.md) - 详细模块设计和代码示例
- [实施方案](docs/design/IMPLEMENTATION_PLAN.md) - 开发阶段规划
- [项目对比分析](docs/design/PROJECT_COMPARISON_ANALYSIS.md) - 与同类项目对比

### 用户文档

- [快速开始](docs/main/QUICK_START.md) - 安装和使用指南
- [工作日志](docs/main/WORK_LOG.md) - 开发进度记录

### 测试文档

- [测试策略](docs/testing/TEST_STRATEGY.md)
- [测试用例](docs/testing/TEST_CASES.md)
- [环境配置](docs/testing/ENVIRONMENT_SETUP.md)

---

## 致谢

- [NanoClaw](https://github.com/nanoclaw/nanoclaw) - 容器隔离思路的启发来源
- 从"消息机器人"扩展为"智能体开发平台"
- [FastAPI](https://fastapi.tiangolo.com/) - Web 框架
- [Pydantic](https://docs.pydantic.dev/) - 数据验证

---

## 开源许可

MIT License - 详见 [LICENSE](LICENSE) 文件。

---

**版本**: v0.1.0-alpha

**最后更新**: 2026-02-16
