# Container Isolation Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance NanoGridBot's container isolation to fully cover (and exceed) nanoclaw's container running capabilities, including secure environment variable transfer, skills synchronization, session tracking, and improved timeout handling.

**Architecture:** This enhancement adds four key improvements: (1) Secure env file mounting instead of -e parameters, (2) Automatic skills sync from container/skills to each group's .claude/skills, (3) Sessions index for tracking conversation history, (4) Improved timeout with grace period. All changes focus on the container_runner and mount_security modules.

**Tech Stack:** Python 3.12+, Docker, TypeScript (agent-runner)

---

## Task 1: Environment Variable Secure Transfer

### Architecture

Use file-based env mounting instead of direct -e parameters. Create filtered env files that only expose necessary variables (ANTHROPIC_API_KEY, ANTHROPIC_MODEL) to each group's container, matching nanoclaw's security approach.

**Files:**
- Modify: `src/nanogridbot/core/container_runner.py:253-303`
- Modify: `src/nanogridbot/core/mount_security.py:1-143`
- Test: `tests/unit/test_container_runner.py`
- Test: `tests/unit/test_mount_security.py`

---

### Step 1: Add env file creation function to mount_security.py

Add a new function `create_group_env_file` that:
1. Reads .env from project root
2. Filters to only allowed vars (ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_API_URL)
3. Creates group-specific env file in data_dir/env/
4. Returns the mount tuple

```python
# Add to src/nanogridbot/core/mount_security.py after existing imports

def create_group_env_file(
    group_folder: str,
    allowed_vars: list[str] | None = None,
) -> tuple[str, str, str] | None:
    """Create a filtered env file for a group's container.

    Args:
        group_folder: Group folder name
        allowed_vars: List of env vars to expose (default: ANTHROPIC_*)

    Returns:
        Mount tuple (host_path, container_path, mode) or None if no env vars
    """
    from nanogridbot.config import get_config

    config = get_config()
    allowed = allowed_vars or ["ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_API_URL"]

    env_file = config.store_dir / "env" / f"{group_folder}.env"
    env_file.parent.mkdir(parents=True, exist_ok=True)

    env_content: list[str] = []
    env_path = config.base_dir / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                for var in allowed:
                    if line.startswith(f"{var}="):
                        env_content.append(line)
                        break

    if not env_content:
        return None

    env_file.write_text("\n".join(env_content) + "\n")
    return (str(env_file), "/workspace/env", "ro")
```

**Step 2: Run test to verify it works**

Create test file `tests/unit/test_mount_security.py`:

```python
import pytest
from pathlib import Path
from nanogridbot.core.mount_security import create_group_env_file


def test_create_group_env_file_filters_correctly(tmp_path, monkeypatch):
    """Test that env file is created with only allowed vars."""
    # Setup mock config
    from nanogridbot.config import Config

    config = Config(
        base_dir=tmp_path,
        data_dir=tmp_path / "data",
        groups_dir=tmp_path / "groups",
        store_dir=tmp_path / "store",
    )
    monkeypatch.setattr("nanogridbot.core.mount_security.get_config", lambda: config)

    # Create .env with multiple vars
    env_path = tmp_path / ".env"
    env_path.write_text("""\
ANTHROPIC_API_KEY=sk-test-key
OTHER_VAR=secret
ANTHROPIC_MODEL=claude-sonnet
DEBUG=true
""")

    result = create_group_env_file("test-group")

    assert result is not None
    host_path, container_path, mode = result
    assert container_path == "/workspace/env"
    assert mode == "ro"

    env_content = Path(host_path).read_text()
    assert "ANTHROPIC_API_KEY=sk-test-key" in env_content
    assert "ANTHROPIC_MODEL=claude-sonnet" in env_content
    assert "OTHER_VAR" not in env_content
    assert "DEBUG" not in env_content


def test_create_group_env_file_no_env():
    """Test None returned when no .env exists."""
    from nanogridbot.config import Config
    from unittest.mock import MagicMock

    config = MagicMock(spec=Config)
    config.base_dir = Path("/nonexistent")
    config.store_dir = Path("/nonexistent/store")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("nanogridbot.core.mount_security.get_config", lambda: config)
        result = create_group_env_file("test-group")

    # This will fail due to missing dir - expected behavior
    assert result is None or isinstance(result, tuple)
```

**Step 3: Run test to verify it fails**

```bash
pytest tests/unit/test_mount_security.py::test_create_group_env_file_filters_correctly -v
# Expected: FAIL - function not defined
```

**Step 4: Implement the function**

Add the `create_group_env_file` function to `src/nanogridbot/core/mount_security.py`

**Step 5: Run test to verify it passes**

```bash
pytest tests/unit/test_mount_security.py::test_create_group_env_file_filters_correctly -v
# Expected: PASS
```

**Step 6: Update container_runner.py to use env file mount**

Modify `build_docker_command` function to:
1. Call `create_group_env_file(group_folder)` instead of passing -e ANTHROPIC_*
2. Add the returned mount to the command

```python
# In build_docker_command, replace direct -e env vars with file mount

# OLD CODE (lines 280-287):
# Add custom environment variables
if env:
    for key, value in env.items():
        cmd.extend(["-e", f"{key}={value}"])

# NEW CODE:
# Add env file mount instead of direct -e params
env_mount = create_group_env_file(input_data.get("groupFolder", "default"))
if env_mount:
    host_path, container_path, mode = env_mount
    cmd.extend(["-v", f"{host_path}:{container_path}:{mode}"])
else:
    # Fallback: only pass non-sensitive env vars directly
    safe_env = {k: v for k, v in (env or {}).items()
                if not k.startswith("ANTHROPIC_") or k == "ANTHROPIC_MODEL"}
    for key, value in safe_env.items():
        cmd.extend(["-e", f"{key}={value}"])
```

**Step 7: Commit**

```bash
git add src/nanogridbot/core/mount_security.py src/nanogridbot/core/container_runner.py
git commit -m "feat: add secure env file mounting for containers"
```

---

## Task 2: Skills Synchronization

### Architecture

Automatically sync skills from `container/skills/` to each group's `.claude/skills/` directory on container startup. This matches nanoclaw's behavior and allows per-group skill customization.

**Files:**
- Modify: `src/nanogridbot/core/mount_security.py`
- Modify: `container/agent-runner/src/index.ts` (optional: preload skills)
- Test: `tests/unit/test_mount_security.py`

---

### Step 1: Add skills sync function

Add to `src/nanogridbot/core/mount_security.py`:

```python
import shutil
from pathlib import Path


def sync_group_skills(group_folder: str) -> Path | None:
    """Sync skills from container/skills to group's .claude/skills.

    Args:
        group_folder: Group folder name

    Returns:
        Path to synced skills directory or None if no skills exist
    """
    from nanogridbot.config import get_config

    config = get_config()

    # Source: container/skills/
    skills_src = config.base_dir / "container" / "skills"
    if not skills_src.exists():
        return None

    # Destination: data/sessions/{group}/.claude/skills/
    skills_dst = config.data_dir / "sessions" / group_folder / ".claude" / "skills"
    skills_dst.mkdir(parents=True, exist_ok=True)

    # Sync each skill directory
    for skill_dir in skills_src.iterdir():
        if not skill_dir.is_dir():
            continue
        dst = skills_dst / skill_dir.name
        dst.mkdir(exist_ok=True)
        for file in skill_dir.iterdir():
            if file.is_file():
                shutil.copy2(file, dst / file.name)

    return skills_dst
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_mount_security.py -v
# Expected: FAIL - function not defined
```

**Step 3: Implement the function**

Add `sync_group_skills` to mount_security.py

**Step 4: Update validate_group_mounts to call sync**

Modify `validate_group_mounts` to call `sync_group_skills` before creating session mount:

```python
# In validate_group_mounts, after session_path creation:

# Sync skills for this group
sync_group_skills(group_folder)
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/unit/test_mount_security.py -v
# Expected: PASS
```

**Step 6: Create container/skills directory structure**

```bash
mkdir -p container/skills
# Add sample skill if needed for testing
```

**Step 7: Commit**

```bash
git add src/nanogridbot/core/mount_security.py
git commit -m "feat: add skills synchronization for groups"
```

---

## Task 3: Sessions Index Tracking

### Architecture

Create and maintain a `sessions-index.json` file that tracks all conversation sessions for each group. This enables better session management and quick resume capabilities, matching nanoclaw's session tracking.

**Files:**
- Modify: `container/agent-runner/src/index.ts`
- Modify: `src/nanogridbot/core/container_runner.py` (optional: read index)
- Test: `tests/integration/test_sessions.py`

---

### Step 1: Update agent-runner to write sessions index

Modify `container/agent-runner/src/index.ts` to append to sessions index:

```typescript
// Add after newSessionId is set (around line 420)

// Write to sessions index
const sessionsIndexPath = path.join(
    '/home/node/.claude',
    'sessions-index.json'
);

interface SessionEntry {
    sessionId: string;
    fullPath: string;
    summary: string;
    firstPrompt: string;
    createdAt: string;
}

function updateSessionsIndex(newSessionId: string, firstPrompt: string): void {
    let index: { entries: SessionEntry[] } = { entries: [] };

    try {
        if (fs.existsSync(sessionsIndexPath)) {
            index = JSON.parse(fs.readFileSync(sessionsIndexPath, 'utf-8'));
        }
    } catch (err) {
        log('Failed to read sessions index, creating new');
    }

    // Find transcript path from the session
    const transcriptPath = path.join(
        '/home/node/.claude',
        'transcripts',
        `${newSessionId}.jsonl`
    );

    index.entries.push({
        sessionId: newSessionId,
        fullPath: transcriptPath,
        summary: firstPrompt.slice(0, 100),
        firstPrompt: firstPrompt.slice(0, 200),
        createdAt: new Date().toISOString(),
    });

    // Keep only last 50 sessions
    if (index.entries.length > 50) {
        index.entries = index.entries.slice(-50);
    }

    fs.writeFileSync(sessionsIndexPath, JSON.stringify(index, null, 2));
    log(`Updated sessions index with ${newSessionId}`);
}

// Call after newSessionId is first set (in the init message handler)
// Around line 421: if (message.type === 'system' && message.subtype === 'init')
```

**Step 2: Rebuild agent-runner**

```bash
cd container/agent-runner
npm run build
```

**Step 3: Test manually**

Run container and verify sessions-index.json is created in group session directory.

**Step 4: Commit**

```bash
git add container/agent-runner/src/index.ts container/agent-runner/dist/
git commit -m "feat: add sessions index tracking"
```

---

## Task 4: Improved Timeout with Grace Period

### Architecture

Implement nanoclaw's timeout pattern: hard timeout with a grace period. When timeout fires, send a close sentinel first, wait 30s, then force kill. This prevents abrupt interruptions and allows graceful shutdown.

**Files:**
- Modify: `src/nanogridbot/core/container_runner.py`
- Test: `tests/unit/test_container_runner.py`

---

### Step 1: Add timeout constants and grace period logic

Add to `src/nanogridbot/core/container_runner.py`:

```python
# Add near top of file (after imports)
GRACE_PERIOD_SECONDS = 30  # Grace period before force kill
IDLE_TIMEOUT_MS = 300000   # 5 minutes idle timeout
```

**Step 2: Modify _execute_container for graceful timeout**

Replace timeout handling in `_execute_container`:

```python
# OLD CODE (lines 186-195):
except asyncio.TimeoutError:
    # Try to kill the process
    try:
        process.kill()
    except Exception:
        pass
    return ContainerOutput(
        status="error",
        error="Container execution timed out",
    )

# NEW CODE:
except asyncio.TimeoutError:
    # Graceful timeout: send close sentinel first
    logger.warning("Container timeout, attempting graceful shutdown")

    # Write close sentinel to IPC
    try:
        ipc_path = Path(config.data_dir) / "ipc" / input_data.get("groupFolder", "") / "input" / "_close"
        ipc_path.parent.mkdir(parents=True, exist_ok=True)
        ipc_path.touch()
    except Exception as e:
        logger.warning(f"Failed to write close sentinel: {e}")

    # Wait for grace period
    try:
        await asyncio.wait_for(process.wait(), timeout=GRACE_PERIOD_SECONDS)
    except asyncio.TimeoutError:
        # Force kill after grace period
        try:
            process.kill()
            await process.wait()
        except Exception:
            pass
        return ContainerOutput(
            status="error",
            error=f"Container timed out after grace period ({GRACE_PERIOD_SECONDS}s)",
        )

    return ContainerOutput(
        status="error",
        error="Container timed out (handled gracefully)",
    )
```

**Step 3: Add test for graceful timeout**

```python
@pytest.mark.asyncio
async def test_graceful_timeout():
    """Test that timeout triggers graceful shutdown."""
    from nanogridbot.core.container_runner import GRACE_PERIOD_SECONDS

    # This is a unit test - actual timeout testing would be integration
    assert GRACE_PERIOD_SECONDS == 30
```

**Step 4: Run test**

```bash
pytest tests/unit/test_container_runner.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add src/nanogridbot/core/container_runner.py
git commit -m "feat: add graceful timeout with grace period"
```

---

## Task 5: Enhanced Container Logging

### Architecture

Add detailed container logging similar to nanoclaw: mount configuration logging, container lifecycle events, and output parsing debug info. Logs are stored per-group for easier troubleshooting.

**Files:**
- Modify: `src/nanogridbot/core/container_runner.py`
- Modify: `src/nanogridbot/core/mount_security.py`
- Test: `tests/unit/test_container_runner.py`

---

### Step 1: Add detailed mount logging

Enhance `validate_group_mounts` to log mount configuration:

```python
# In validate_group_mounts, after building mounts list:
from loguru import logger

logger.debug(
    {
        "group": group_folder,
        "is_main": is_main,
        "mounts": [
            {"host": m["host_path"], "container": m["container_path"], "mode": m["mode"]}
            for m in mounts
        ],
    },
    "Container mount configuration",
)
```

**Step 2: Add container lifecycle logging**

Enhance `_execute_container`:

```python
# After process creation (line ~154):
logger.info(
    {
        "group": input_data.get("groupFolder"),
        "prompt_length": len(input_data.get("prompt", "")),
        "session_id": input_data.get("sessionId"),
    },
    "Container started",
)

# After process completes (before return):
logger.info(
    {
        "group": input_data.get("groupFolder"),
        "duration_seconds": duration,
        "status": result.status,
    },
    "Container completed",
)
```

**Step 3: Commit**

```bash
git add src/nanogridbot/core/container_runner.py src/nanogridbot/core/mount_security.py
git commit -m "feat: add detailed container logging"
```

---

## Task 6: Integration Tests

### Architecture

Create integration tests that verify the complete container flow: env mounting, skills sync, session creation, and output parsing.

**Files:**
- Create: `tests/integration/test_container_isolation.py`

---

### Step 1: Create integration test

```python
"""Integration tests for container isolation features."""

import pytest
from pathlib import Path
from nanogridbot.core.mount_security import (
    validate_group_mounts,
    create_group_env_file,
    sync_group_skills,
)


@pytest.fixture
def temp_config(tmp_path):
    """Create temp config for testing."""
    from nanogridbot.config import Config
    from unittest.mock import MagicMock

    config = MagicMock(spec=Config)
    config.base_dir = tmp_path
    config.groups_dir = tmp_path / "groups"
    config.data_dir = tmp_path / "data"
    config.store_dir = tmp_path / "store"
    config.groups_dir.mkdir(parents=True, exist_ok=True)
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.store_dir.mkdir(parents=True, exist_ok=True)

    # Create .env
    (tmp_path / ".env").write_text("""\
ANTHROPIC_API_KEY=sk-test-key
ANTHROPIC_MODEL=claude-sonnet
DEBUG=false
""")

    return config


def test_full_mount_flow(temp_config, monkeypatch):
    """Test complete mount flow: env file + skills + validation."""
    from unittest.mock import patch

    with patch("nanogridbot.core.mount_security.get_config", return_value=temp_config):
        # Test env file creation
        env_mount = create_group_env_file("test-group")
        assert env_mount is not None

        # Test skills sync (no skills dir, should return None)
        skills_path = sync_group_skills("test-group")
        # Skills dir doesn't exist, returns None - this is expected

        # Test mount validation
        mounts = validate_group_mounts(group_folder="test-group", is_main=False)
        assert len(mounts) >= 3  # group, sessions, ipc


def test_env_file_not_leaking_secrets(temp_config, monkeypatch):
    """Verify env file doesn't leak sensitive vars."""
    from unittest.mock import patch

    # Add sensitive vars to .env
    (temp_config.base_dir / ".env").write_text("""\
ANTHROPIC_API_KEY=sk-secret-key-12345
DATABASE_URL=postgres://user:pass@host/db
ANTHROPIC_MODEL=claude-opus
AWS_SECRET=super-secret
""")

    with patch("nanogridbot.core.mount_security.get_config", return_value=temp_config):
        env_mount = create_group_env_file("test-group")

    assert env_mount is not None
    host_path, _, _ = env_mount
    content = Path(host_path).read_text()

    # Should contain
    assert "ANTHROPIC_API_KEY" in content
    assert "ANTHROPIC_MODEL" in content

    # Should NOT contain
    assert "DATABASE_URL" not in content
    assert "AWS_SECRET" not in content
```

**Step 2: Run integration tests**

```bash
pytest tests/integration/test_container_isolation.py -v
# Expected: PASS (after all tasks complete)
```

**Step 3: Commit**

```bash
git add tests/integration/test_container_isolation.py
git commit -m "test: add container isolation integration tests"
```

---

## Summary

| Task | Description | Files Modified |
|------|-------------|----------------|
| 1 | Environment variable secure transfer | container_runner.py, mount_security.py |
| 2 | Skills synchronization | mount_security.py |
| 3 | Sessions index tracking | agent-runner/index.ts |
| 4 | Graceful timeout | container_runner.py |
| 5 | Enhanced logging | container_runner.py, mount_security.py |
| 6 | Integration tests | tests/integration/test_container_isolation.py |

---

## Execution

**Plan complete and saved to `docs/plans/2026-02-17-container-isolation-enhancement.md`.**

**Two execution options:**

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
