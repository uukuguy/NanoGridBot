# {🦑} NanoGridBot

> NanoGridBot - AI Agent Development Console powered by Claude Agent SDK. Build, test, and verify AI agents with Skills, MCP, and CLI integrations using the most capable agent runtime.

[中文文档](README_zh.md)

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**NanoGridBot** is a comprehensive agent development platform powered by Claude Agent SDK. It provides the most capable agent runtime with deep Skills, MCP, and CLI integration verification capabilities:

- 🔥 **Claude Agent SDK Powered** - Most capable agent runtime with Claude Code
- 🛠️ **Skills & MCP Integration** - Verify Skills, MCP servers, and CLI tools in isolated containers
- 🔌 **Multi-LLM Support** - Claude, OpenAI, Anthropic API, custom providers
- 📡 **8 IM Channels** - Test in production-like environments (WhatsApp, Telegram, Slack, Discord, QQ, Feishu, WeCom, DingTalk)
- ⚡ **Interactive Shell** - Real-time debugging with session resume capability
- 🛠️ **5 CLI Modes**: serve, shell, run, logs, session

## Why NanoGridBot

| Feature | Traditional Development | NanoGridBot |
|---------|------------------------|-------------|
| **Agent Runtime** | Manual setup | Claude Agent SDK - most powerful capability |
| **Skills/MCP/CLI** | Hard to test | Integrated verification in isolated containers |
| **Debugging** | Logs + print | Interactive shell + Web real-time monitoring |
| **Multi-turn** | Stateless | Session resume + IPC message streaming |
| **Team Collaboration** | Single agent | Claude Agent SDK Teams support |

## Use Cases

1. **Skills & MCP Verification** - Verify Skills, MCP servers, and CLI tools in isolated containers
2. **Interactive Agent Development** - Use `shell` mode for real-time debugging
3. **Agent Behavior Testing** - Test agent behavior across 8 IM channels
4. **Feature Prototyping** - Use `run` mode for quick prompt/feature validation
5. **Personal AI Assistant** - Deploy with `serve` mode for daily use
6. **Task Automation** - Schedule recurring tasks with built-in scheduler

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Core Capabilities](#core-capabilities)
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

### Five Running Modes

```bash
# 1. Serve mode: Start full service with Web dashboard
nanogridbot serve
nanogridbot serve --host 0.0.0.0 --port 8080

# 2. Shell mode: Interactive container session (multi-turn conversation)
nanogridbot shell
nanogridbot shell -g myproject                    # Specify group
nanogridbot shell --resume session-id             # Resume previous session

# 3. Run mode: Single-shot non-interactive execution
nanogridbot run -p "Explain what recursion is"
echo "Your question" | nanogridbot run -p -
nanogridbot run -g myproject -p "Analyze code"    # Specify group
nanogridbot run -g myproject -p "Task" --timeout 60 --env KEY=VALUE

# 4. Logs mode: View and follow logs
nanogridbot logs -n 100           # Show last 100 lines
nanogridbot logs -f               # Follow log output

# 5. Session mode: Manage interactive sessions
nanogridbot session ls            # List sessions
nanogridbot session kill <id>     # Terminate session
nanogridbot session resume <id>   # Show resume info
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

### Architecture Advantages

- **Claude Agent SDK Native Capabilities**: Built on Claude Code with Agent Teams, Session Resume, and Transcript Archiving
- **MCP Deep Integration**: Configure custom MCP servers via `mcpServers`, agents can invoke them directly
- **Skills Zero-Threshold Verification**: Use `shell` mode to directly test Skills performance in agents
- **Filesystem Isolation**: Each group has independent `/workspace/group` directory for secure isolation
- **Conversation Persistence**: PreCompact Hook automatically archives conversation history
- **IPC Message Streaming**: Multi-turn dialogue support with real-time message push to running agents

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

## Core Capabilities

### Containerized Agent Runtime

- ✅ **Multi-LLM Support**: Claude, OpenAI, Anthropic API, custom LLM providers
- ✅ **Container Isolation**: Agents run in isolated Docker containers for security
- ✅ **Session Management**: Multi-turn dialogue support with session persistence
- ✅ **Context Management**: Independent context for different projects/groups
- ✅ **Real-time Monitoring**: Web dashboard for Agent status and output
- ✅ **Interactive Debugging**: Shell mode for direct Agent conversation

### Multi-Channel Deployment (For Testing/Simulation)

> 8 IM channels enable realistic scenario simulation for agent behavior testing, not the primary development goal.

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

# Serve mode: Full service with web dashboard
nanogridbot serve                    # Default
nanogridbot serve --host 0.0.0.0  # Custom address
nanogridbot serve --port 9000      # Custom port
nanogridbot serve --debug          # Debug mode

# Shell mode: Interactive container session (multi-turn)
nanogridbot shell                           # Default (group: cli)
nanogridbot shell -g myproject              # Specify group folder
nanogridbot shell --resume session-id      # Resume previous session
nanogridbot shell --attach                  # Attach to container shell

# Run mode: Single-shot non-interactive execution
nanogridbot run -p "Explain what closures are"
echo "Question" | nanogridbot run -p -      # Pipe input
nanogridbot run -g mygroup -p "Task"        # Specify group
nanogridbot run -p "Task" --timeout 60      # Custom timeout
nanogridbot run -p "Task" -e KEY=VALUE      # Environment variables

# Logs mode: View and follow logs
nanogridbot logs -n 100           # Show last 100 lines
nanogridbot logs -f               # Follow log output

# Session mode: Manage interactive sessions
nanogridbot session ls            # List all sessions
nanogridbot session kill <id>     # Terminate a session
nanogridbot session resume <id>   # Show resume info
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
- Expanded from "messaging bot" to "agent development platform"
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [Pydantic](https://docs.pydantic.dev/) - Data validation

---

## License

MIT License - See [LICENSE](LICENSE) file.

---

**Version**: v0.1.0-alpha

**Last Updated**: 2026-02-16
