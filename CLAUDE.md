# NanoGridBot - Claude Code Instructions

This file contains project-specific instructions for Claude Code.

## Project Overview

NanoGridBot is a Python port of NanoClaw - a personal Claude AI assistant accessible via multiple messaging platforms (WhatsApp, Telegram, Slack, Discord, QQ, Feishu, WeCom, DingTalk).

## Development Status

**Current Phase**: Phase 15 - CLI Full Mode Implementation

- v0.1.0-alpha
- Python 3.12+
- asyncio-based async architecture
- 8 messaging platforms supported
- 4 CLI modes: serve, shell, chat, run
- Core orchestration, container runner, queue, scheduler, web dashboard implemented
- Container-based CLI with ContainerSession support

## Key Files

| File | Purpose |
|------|---------|
| `docs/design/NANOGRIDBOT_DESIGN.md` | Architecture design |
| `docs/design/IMPLEMENTATION_PLAN.md` | Implementation plan |
| `docs/design/CHANNEL_FEASIBILITY_ASSESSMENT.md` | Multi-platform evaluation |
| `docs/main/WORK_LOG.md` | Development progress |
| `docs/dev/NEXT_SESSION_GUIDE.md` | Next session guide |

## Code Style

- **Format**: Black (line length 100)
- **Import Sort**: isort (profile=black)
- **Type Check**: mypy strict mode
- **Linter**: ruff

## Important Conventions

### Python Version
- Must use Python 3.12+
- Use latest type annotation syntax (`list[str]`, not `List[str]`)

### Async Programming
- All I/O operations use async/await
- Use `aiosqlite` instead of `sqlite3`
- Use `aiofiles` for file operations

### Type Safety
- All functions must have type annotations
- Use Pydantic for data validation
- Run mypy for type checking

### Testing
- Use pytest and pytest-asyncio
- Target coverage > 80%

## Supported Channels

| Channel | SDK | Status |
|---------|-----|--------|
| WhatsApp | pywa | ✅ Implemented |
| Telegram | python-telegram-bot | ✅ Implemented |
| Slack | python-slack-sdk | ✅ Implemented |
| Discord | discord.py | ✅ Implemented |
| QQ | NoneBot2/OneBot | ✅ Implemented |
| Feishu | lark-oapi | ✅ Implemented |
| WeCom | httpx | ✅ Implemented |
| DingTalk | dingtalk-stream | ✅ Implemented |

## Implementation Phases

1. **Phase 1**: Basic Infrastructure (Week 1-2) ✅
   - Project structure
   - Config, Logger, Types

2. **Phase 2**: Database Layer (Week 2-3) ✅
   - SQLite async operations

3. **Phase 3**: Channel Abstraction (Week 3-4) ✅
   - Channel base class
   - JID format specification
   - Channel factory pattern

4. **Phase 4**: Simple Platforms (Week 4-6) ✅
   - WhatsApp, Telegram, Slack, Discord, WeCom

5. **Phase 5**: Medium Platforms (Week 6-7) ✅
   - DingTalk, Feishu, QQ

6. **Phase 6**: Container & Queue (Week 7-9) ✅
   - Docker container management
   - Message queue system
   - IPC handler
   - Task scheduler

7. **Phase 7**: Web Monitoring Panel (Week 9-10) ✅
   - FastAPI web dashboard
   - Vue.js frontend
   - WebSocket real-time updates
   - RESTful API endpoints

8. **Phase 8**: Integration Testing & Polish (Week 10-11) ✅
   - Web module integration tests
   - CLI entry point implementation
   - Bug fixes and polish

9. **Phase 9**: Plugin System Enhancement (Week 11-12) ✅
   - Plugin hot-reload (watchdog-based)
   - Plugin configuration management (JSON)
   - Third-party plugin API
   - Built-in plugins (rate_limiter, auto_reply, mention)

10. **Phase 10**: Production Readiness (Week 12-13) ✅
    - Error handling and recovery (retry, circuit breaker, graceful shutdown)
    - Performance optimization (message cache, DB WAL mode)
    - Logging improvements (structured logging)
    - Documentation finalization

11. **Phase 11**: Strategic Planning (Week 13-14) ✅
    - Project comparison analysis (NanoClaw, nanobot, picoclaw)
    - Multi-scenario architecture design

12. **Phase 12**: Testing Documentation (Week 14) ✅
    - Complete test documentation system (7 documents)
    - Test strategy, cases, data, automation, environment

13. **Phase 13**: Core Module Test Coverage (Week 15) ✅
    - Test coverage 51% → 62%
    - Router, Orchestrator, Container Runner, Error Handling, Plugin Loader tests

14. **Phase 14**: Test Coverage Target ✅
    - Test coverage 62% → 80%
    - 640 tests passing

15. **Phase 15**: CLI Full Mode Implementation ✅
    - CLI refactored to container-based shell/chat/run modes
    - ContainerSession for interactive shell mode
    - Added Pydantic response models for web API

## Testing Commands

```bash
# Run tests
pytest -xvs

# With coverage
pytest --cov=src --cov-report=term-missing

# Specific test
pytest tests/test_file.py::test_function -xvs

# Format
black . && isort .

# Lint
ruff check .

# Type check
mypy src/
```

## Context7 Usage

When implementing features using external libraries, always use Context7 MCP to verify latest API usage:

1. `mcp__context7__resolve-library-id` - Get library ID
2. `mcp__context7__query-docs` - Get documentation

## Memory

Project context is saved to claude-mem. Key decisions are recorded for cross-session continuity.

## Documentation Language

- `README.md`, `CLAUDE.md`: English
- `docs/` directory: Chinese (中文)
- Code comments: English

---

For more details, see [Architecture Design](docs/design/NANOGRIDBOT_DESIGN.md).
