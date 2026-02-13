# NanoGridBot - Claude Code Instructions

This file contains project-specific instructions for Claude Code.

## Project Overview

NanoGridBot is a Python port of NanoClaw - a personal Claude AI assistant accessible via multiple messaging platforms (WhatsApp, Telegram, Slack, Discord, QQ, Feishu, WeCom, DingTalk).

## Development Status

**Current Phase**: Phase 5 Complete - All 8 Messaging Channels Implemented

- v0.1.0-alpha
- Python 3.12+
- asyncio-based async architecture
- 8 messaging platforms supported

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

6. **Phase 6**: Container & Queue (Week 7-9)
   - Docker container management
   - Message queue system

7. **Phase 7-12**: Scheduler, Orchestrator, Plugins, Web

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
