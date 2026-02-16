# NanoGridBot

> 🤖 Agent Application Development Validator & Debugger Based on Claude Code

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Core Positioning

**NanoGridBot** is a validator and debugging framework specifically designed for Agent application development.

It originated from the container isolation concept in [NanoClaw](https://github.com/nanoclaw/nanoclaw), but underwent a fundamental architectural upgrade—from a single messaging proxy to a complete Agent application development platform. Through deep integration with Claude Code, NanoGridBot provides:

- 🧪 **Agent Validation**: Safely run and test Claude Agents in isolated containers
- 🔧 **Development & Debugging**: Real-time monitoring, log analysis, interactive debugging
- 📡 **Multi-Channel Deployment**: Support for 8 messaging platforms, deploy to any channel with one command
- ⏰ **Task Scheduling**: Scheduled tasks, periodic tasks, event triggers
- 🔌 **Plugin System**: Flexible functionality extension, easy third-party service integration

## Why NanoGridBot

| Feature | Traditional Development | NanoGridBot |
|---------|------------------------|-------------|
| **Agent Runtime** | Manual configuration needed | Automatic container isolation |
| **Multi-Channel Deployment** | Separate development per platform | Unified API, 8 platforms auto-adapted |
| **Debugging Experience** | Logs + print statements | Web real-time monitoring + CLI interaction |
| **Task Scheduling** | External cron | Built-in scheduler |
| **Extensibility** | Code modifications | Plugin hot-reloading |

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Core Features](#core-features)
- [CLI Tools](#cli-tools)
- [Development](#development)
- [Deployment](#deployment)
- [Documentation](#documentation)

---

## Quick Start

### Prerequisites

- Python 3.12+
- Docker
- Git

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/nanogridbot.git
cd nanogridbot

# Install with uv (recommended)
uv sync

# Build Agent container image
docker build -t nanogridbot-agent:latest container/

# Start service
uv run nanogridbot serve
```

### Four Running Modes

```bash
# 1. Serve mode: Start full service with Web dashboard
nanogridbot serve
nanogridbot serve --host 0.0.0.0 --port 8080

# 2. Shell mode: Interactive debugging REPL
nanogridbot shell
nanogridbot shell --model claude-sonnet-4-20250514

# 3. Chat mode: Single prompt testing
nanogridbot chat "Explain what recursion is"
echo "Your question" | nanogridbot chat

# 4. Run mode: Execute tasks on registered groups
nanogridbot run myproject --context "Analyze this code performance"
nanogridbot run myproject --send --context "Send report"
```

---

## Architecture

### Design Philosophy

```
┌─────────────────────────────────────────────────────────────────┐
│                 NanoGridBot Agent Development Platform             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│   │   CLI Tools  │    │ Web Dashboard│    │    Channels  │   │
│   │(Debug/Test)  │    │ (Status/Logs)│    │(Multi-platform│   │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘   │
│          │                    │                    │           │
│          └────────────────────┼────────────────────┘           │
│                               ▼                                │
│   ┌────────────────────────────────────────────────────────┐   │
│   │              Core Orchestration Layer                   │   │
│   │   • Message Routing  • Task Scheduling  • Container   │   │
│   │   • Plugin Loading  • Group Queue                     │   │
│   └─────────────────────────┬──────────────────────────┘   │
│                               │                               │
│                               ▼                               │
│   ┌────────────────────────────────────────────────────────┐   │
│   │              Container Isolation Layer                   │   │
│   │   • Docker Container  • Filesystem Isolation  • IPC  │   │
│   │   • Claude Agent SDK  • Session Management           │   │
│   └────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Core Modules

| Module | Responsibility | File |
|--------|----------------|------|
| **Orchestrator** | Global state management, message loop, channel coordination | `core/orchestrator.py` |
| **ContainerRunner** | Container lifecycle, mount configuration | `core/container_runner.py` |
| **ContainerSession** | Interactive session management, IPC communication | `core/container_session.py` |
| **GroupQueue** | Concurrency control, message queuing, retry mechanism | `core/group_queue.py` |
| **TaskScheduler** | Cron/Interval/OneTime task scheduling | `core/task_scheduler.py` |
| **Router** | Message routing, trigger matching, broadcasting | `core/router.py` |
| **Database** | SQLite persistence, message cache | `database/` |
| **Channels** | 8 messaging platform adapters | `channels/` |

### Container Isolation Design

NanoGridBot borrowed the core container isolation concept from NanoClaw and enhanced it:

```
┌─────────────────────────────────────────────────────────────┐
│                    Host System (NanoGridBot)                │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              Agent Container (Docker)                │ │
│  │  • Claude Agent SDK                                  │ │
│  │  • Non-root user (node:1000)                        │ │
│  │  • Explicit mounts (whitelist only)                 │ │
│  │  • Network isolation (--network=none)               │ │
│  │  • IPC file watching (follow-up messages)           │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ JSON via stdin/stdout
                              │ OR IPC files
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Host System (NanoGridBot)                │
│  • Message polling (2s interval)                           │
│  • SQLite state persistence                                │
│  • Group queue (concurrency control)                       │
│  • Task scheduling (Cron)                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Features

### Agent Development Support

- ✅ **Containerized Execution**: Claude Agent runs in isolated containers, safe and controllable
- ✅ **Session Management**: Multi-turn dialogue support, session recovery capability
- ✅ **Context Management**: Independent context for different projects/groups
- ✅ **Real-time Monitoring**: Web dashboard for Agent status and output
- ✅ **Interactive Debugging**: Shell mode for direct Agent conversation

### Multi-Channel Deployment

| Channel | SDK | Status |
|---------|-----|--------|
| WhatsApp | pywa | ✅ |
| Telegram | python-telegram-bot | ✅ |
| Slack | python-slack-sdk | ✅ |
| Discord | discord.py | ✅ |
| QQ | NoneBot2/OneBot | ✅ |
| Feishu | lark-oapi | ✅ |
| WeCom | httpx | ✅ |
| DingTalk | dingtalk-stream | ✅ |

### Extended Features

- 🔌 **Plugin System**: Hot-reload plugins, custom processing logic
- 📊 **Web Dashboard**: Real-time status, task management, log viewing
- 🔄 **Task Scheduling**: Cron expressions, interval tasks, one-time tasks
- 🔒 **Security Isolation**: Mount whitelist, path traversal protection

---

## CLI Tools

### Command Reference

```bash
# Help
nanogridbot --help

# Version
nanogridbot --version

# Serve mode: Full service
nanogridbot serve                    # Default
nanogridbot serve --host 0.0.0.0  # Custom address
nanogridbot serve --port 9000      # Custom port
nanogridbot serve --debug          # Debug mode

# Shell mode: Interactive REPL
nanogridbot shell                                    # Default
nanogridbot shell --model claude-sonnet-4-20250514 # Specify model
nanogridbot shell --system "You are a Python expert" # System prompt

# Chat mode: Single interaction
nanogridbot chat "Explain what closures are"
echo "Question" | nanogridbot chat                   # Pipe input
nanogridbot chat -m "You are a poet" "Write a poem" # With history

# Run mode: Group execution
nanogridbot run mygroup --context "Analyze this bug"
nanogridbot run mygroup --send --context "Send results"
```

### LLM Parameters

All CLI modes support shared LLM parameters:

```bash
--model MODEL              # Model name (default: claude-sonnet-4-20250514)
--max-tokens MAX_TOKENS   # Max tokens (default: 4096)
--temperature TEMP        # Temperature (default: 0.7)
--system SYSTEM           # System prompt
--stream                  # Stream output
```

---

## Development

### Project Structure

```
nanogridbot/
├── src/nanogridbot/       # Source code
│   ├── core/              # Core modules
│   │   ├── orchestrator.py
│   │   ├── container_runner.py
│   │   ├── container_session.py
│   │   ├── group_queue.py
│   │   ├── task_scheduler.py
│   │   ├── router.py
│   │   └── mount_security.py
│   ├── database/           # Database layer
│   ├── channels/          # Messaging channels
│   ├── plugins/           # Plugin system
│   ├── web/               # Web dashboard
│   └── cli.py             # CLI entry
├── container/             # Agent container
├── tests/                 # Tests
├── docs/                  # Documentation
└── data/                  # Runtime data
```

### Development Commands

```bash
# Run tests
pytest -xvs

# Coverage report
pytest --cov=src --cov-report=html

# Code formatting
black . && isort .

# Type checking
mypy src/

# Linting
ruff check .
```

### Create Plugin

```python
# plugins/my_plugin/plugin.py
from nanogridbot.plugins.base import Plugin

class MyPlugin(Plugin):
    @property
    def name(self) -> str:
        return "my_plugin"

    async def on_message_received(self, message):
        # Process message
        return message
```

---

## Deployment

### Docker Deployment

```bash
# Build image
docker-compose build

# Start service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop service
docker-compose down
```

### Production Configuration

1. Configure environment variables
2. Set mount whitelist
3. Configure reverse proxy (Nginx)
4. Enable HTTPS
5. Configure monitoring alerts

---

## Documentation

### Design Documents

- [Architecture Design](docs/design/NANOGRIDBOT_DESIGN.md) - Detailed module design and code examples
- [Implementation Plan](docs/design/IMPLEMENTATION_PLAN.md) - Development phase planning
- [Project Comparison Analysis](docs/design/PROJECT_COMPARISON_ANALYSIS.md) - Comparison with similar projects

### User Documents

- [Quick Start](docs/main/QUICK_START.md) - Installation and usage guide
- [Work Log](docs/main/WORK_LOG.md) - Development progress

### Testing Documents

- [Test Strategy](docs/testing/TEST_STRATEGY.md)
- [Test Cases](docs/testing/TEST_CASES.md)
- [Environment Setup](docs/testing/ENVIRONMENT_SETUP.md)

---

## Acknowledgments

- [NanoClaw](https://github.com/nanoclaw/nanoclaw) - Source of container isolation inspiration
- [Claude Agent SDK](https://docs.anthropic.com/en/docs/claude-code/overview) - Agent core
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [Pydantic](https://docs.pydantic.dev/) - Data validation

---

## License

MIT License - See [LICENSE](LICENSE) file.

---

**Version**: v0.1.0-alpha

**Last Updated**: 2026-02-16
