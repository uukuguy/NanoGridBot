# NanoGridBot

> 🤖 Lightweight, Secure Personal Claude AI Assistant - Python Port of NanoClaw

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

NanoGridBot is a complete Python port of [NanoClaw](https://github.com/nanoclaw/nanoclaw), providing a personal Claude AI assistant accessible via multiple messaging platforms with container isolation, multi-group support, and extensible architecture.

## ✨ Key Features

- 🔒 **Container Isolation**: OS-level security isolation using Docker
- 👥 **Multi-Group Isolation**: Each messaging group has its own filesystem and session
- ⚡ **Async Architecture**: High-performance design based on asyncio
- 🎯 **Type Safety**: Runtime data validation using Pydantic
- 🔌 **Extensible**: Plugin system, multi-channel support, web monitoring
- 📊 **Web Monitoring**: Real-time system status and task management
- 🔄 **Task Scheduling**: Cron, interval, and one-time task support
- 🌐 **Multi-Channel**: WhatsApp, Telegram, Slack, Discord, QQ, Feishu, WeCom, DingTalk

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Features](#features)
- [Development](#development)
- [Deployment](#deployment)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Docker
- Node.js 20+ (for WhatsApp bridge)
- Git

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/nanogridbot.git
cd nanogridbot

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Build Docker image
docker build -t nanogridbot-agent:latest container/

# Start service
python -m nanogridbot
```

### Docker Compose Deployment

```bash
docker-compose up -d
```

See [Quick Start Guide](docs/main/QUICK_START.md) for detailed installation instructions.

## 🏗️ Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NanoGridBot Main Process                  │
│  • Message Polling (2s interval)                           │
│  • Multi-Channel Support (WhatsApp/Telegram/Slack/...)     │
│  • SQLite State Persistence                                │
│  • GroupQueue (Concurrency Control)                        │
│  • Task Scheduler (Cron)                                   │
│  • IPC Handler (File System)                               │
└────────────────────┬────────────────────────────────────────┘
                     │ Docker Container Start
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Agent Container (Docker)                        │
│  • Claude Agent SDK Execution                              │
│  • Isolated Filesystem (Explicit Mounts)                   │
│  • Non-root User (node:1000)                               │
│  • Chromium Browser Automation                             │
│  • IPC File Watching (follow-up messages)                 │
└─────────────────────────────────────────────────────────────┘
```

### Core Modules

| Module | Responsibility | File |
|--------|----------------|------|
| **Orchestrator** | Main coordinator, global state and message loop | `core/orchestrator.py` |
| **Container Runner** | Container lifecycle and mount configuration | `core/container_runner.py` |
| **Group Queue** | Group queue and concurrency control | `core/group_queue.py` |
| **Task Scheduler** | Scheduled task dispatch | `core/task_scheduler.py` |
| **IPC Handler** | Inter-process communication | `core/ipc_handler.py` |
| **Database** | SQLite data persistence | `database/db.py` |
| **Channels** | Channel abstraction layer | `channels/` |

See [Architecture Design Document](docs/design/NANOGRIDBOT_DESIGN.md) for details.

## 🎯 Features

### Core Features

- ✅ **Message Processing**: Auto-process messages with trigger word filtering
- ✅ **Container Isolation**: Each group runs in isolated containers
- ✅ **Session Management**: Multi-turn dialogue and session recovery
- ✅ **Task Scheduling**: Cron, interval, and one-time tasks
- ✅ **IPC Communication**: Container-host communication via filesystem
- ✅ **Mount Security**: External whitelist validation, path traversal prevention

### Extended Features

- 🔌 **Plugin System**: Custom plugins for extended functionality
- 📊 **Web Monitoring**: Real-time system status and task management
- 🌐 **Multi-Channel**: WhatsApp, Telegram, Slack, Discord, QQ, Feishu, WeCom, DingTalk
- 🔍 **Message Search**: Full-text search of message history
- 📈 **Metrics Export**: Prometheus-formatted system metrics
- 🚦 **Rate Limiting**: Abuse prevention and overload protection

### Supported Channels

| Channel | SDK | Difficulty |
|---------|-----|------------|
| WhatsApp | Baileys Bridge | ⭐⭐ |
| Telegram | python-telegram-bot | ⭐⭐ |
| Slack | python-slack-sdk | ⭐⭐ |
| Discord | discord.py | ⭐⭐ |
| QQ | NoneBot2/OneBot | ⭐⭐⭐ |
| 飞书 (Feishu) | lark-oapi | ⭐⭐⭐ |
| 企业微信 (WeCom) | httpx (native) | ⭐⭐ |
| 钉钉 (DingTalk) | dingtalk-stream-sdk | ⭐⭐ |

### Usage Examples

```
# Send message
@Andy help me analyze this code performance issue

# Create scheduled task
@Andy schedule task
Prompt: Send weather forecast every morning at 8am
Schedule type: cron
Cron expression: 0 8 * * *

# List tasks
@Andy list tasks

# Register new group
@Andy register group
```

## 🛠️ Development

### Project Structure

```
nanogridbot/
├── src/nanogridbot/       # Source code
│   ├── core/              # Core modules
│   ├── database/           # Database
│   ├── channels/          # Channel implementations
│   ├── plugins/           # Plugin system
│   └── web/               # Web monitoring
├── container/             # Agent container
├── bridge/                # Baileys bridge
├── groups/                # Group working directories
├── data/                  # Runtime data
├── store/                 # Persistent storage
├── tests/                 # Tests
└── docs/                  # Documentation
```

### Running Tests

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest tests/unit/test_database.py -v
```

### Code Quality

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Run Linter
ruff check src/ tests/

# Type check
mypy src/
```

### Plugin Development

Create custom plugins:

```python
# plugins/my_plugin/plugin.py
from nanogridbot.plugins.base import Plugin

class MyPlugin(Plugin):
    @property
    def name(self) -> str:
        return "my_plugin"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def initialize(self, config: dict):
        pass

    async def on_message_received(self, message):
        # Process message
        return message
```

See [Development Guide](docs/main/QUICK_START.md#development-guide) for details.

## 🚢 Deployment

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

### Production Deployment

1. Configure environment variables
2. Set mount whitelist
3. Configure reverse proxy (Nginx)
4. Enable HTTPS
5. Configure monitoring and alerts

See [Implementation Plan](docs/design/IMPLEMENTATION_PLAN.md) for deployment details.

## 📚 Documentation

### Design Documents

- [Architecture Design](docs/design/NANOGRIDBOT_DESIGN.md) - Detailed module design and code examples
- [Implementation Plan](docs/design/IMPLEMENTATION_PLAN.md) - Development phases and task breakdown
- [Channel Feasibility Assessment](docs/design/CHANNEL_FEASIBILITY_ASSESSMENT.md) - Multi-platform evaluation
- [Analysis Summary](docs/main/ANALYSIS_SUMMARY.md) - NanoClaw project analysis

### User Documents

- [Quick Start](docs/main/QUICK_START.md) - Installation and usage guide
- [Configuration](docs/main/QUICK_START.md#configuration) - Environment variables and config files
- [Troubleshooting](docs/main/QUICK_START.md#troubleshooting) - Common issues and solutions

### API Documentation

- Web API docs: `http://localhost:8000/docs` (after starting service)

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -am 'Add my feature'`
4. Push branch: `git push origin feature/my-feature`
5. Create Pull Request

### Contribution Guidelines

- Follow PEP 8 code style
- Format code with Black
- Add type annotations
- Write unit tests
- Update documentation

## 📊 Performance Targets

| Metric | Target | Actual |
|--------|--------|--------|
| Message Latency | < 2 sec | TBD |
| Container Startup | < 5 sec | TBD |
| Concurrent Containers | 5-10 | TBD |
| Memory Usage | < 500MB | TBD |
| Test Coverage | > 80% | TBD |

## 🔒 Security

### Security Features

- Container isolation (non-root user)
- Mount whitelist validation
- Path traversal protection
- Sensitive directory blacklist
- API authentication/authorization
- Rate limiting

### Reporting Security Issues

If you discover a security vulnerability, please email security@example.com instead of public disclosure.

## 📝 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file.

## 🙏 Acknowledgments

- [NanoClaw](https://github.com/nanoclaw/nanoclaw) - Original TypeScript implementation
- [Baileys](https://github.com/WhiskeySockets/Baileys) - WhatsApp Web API
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [Pydantic](https://docs.pydantic.dev/) - Data validation

## 📞 Contact

- GitHub: https://github.com/yourusername/nanogridbot
- Issues: https://github.com/yourusername/nanogridbot/issues
- Discussions: https://github.com/yourusername/nanogridbot/discussions

---

**Development Status**: 🚧 In Development

**Current Version**: v0.1.0-alpha

**Last Updated**: 2026-02-13
