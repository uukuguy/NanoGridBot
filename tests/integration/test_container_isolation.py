"""Integration tests for container isolation features."""

import pytest
from pathlib import Path
from unittest.mock import patch

from nanogridbot.config import Config
from nanogridbot.core.mount_security import (
    validate_group_mounts,
    create_group_env_file,
    sync_group_skills,
)


@pytest.fixture
def temp_config(tmp_path):
    """Create temp config for testing."""
    config = Config(
        base_dir=tmp_path,
        groups_dir=tmp_path / "groups",
        data_dir=tmp_path / "data",
        store_dir=tmp_path / "store",
    )
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


@pytest.mark.asyncio
async def test_full_mount_flow(temp_config, monkeypatch):
    """Test complete mount flow: env file + skills + validation."""
    monkeypatch.setattr("nanogridbot.config.get_config", lambda: temp_config)

    # Create group directory
    (temp_config.groups_dir / "test-group").mkdir(parents=True)

    # Test env file creation
    env_mount = create_group_env_file("test-group")
    assert env_mount is not None

    # Test skills sync (no skills dir, should return None)
    skills_path = sync_group_skills("test-group")
    # Skills dir doesn't exist, returns None - this is expected

    # Test mount validation (use is_main=True to allow data/ mounts)
    mounts = await validate_group_mounts(group_folder="test-group", is_main=True)
    assert len(mounts) >= 3  # group, sessions, ipc, project


def test_env_file_not_leaking_secrets(temp_config, monkeypatch):
    """Verify env file doesn't leak sensitive vars."""
    monkeypatch.setattr("nanogridbot.config.get_config", lambda: temp_config)

    # Add sensitive vars to .env
    (temp_config.base_dir / ".env").write_text("""\
ANTHROPIC_API_KEY=sk-secret-key-12345
DATABASE_URL=postgres://user:pass@host/db
ANTHROPIC_MODEL=claude-opus
AWS_SECRET=super-secret
""")

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


def test_skills_sync_integration(temp_config, monkeypatch):
    """Test skills sync with actual files."""
    monkeypatch.setattr("nanogridbot.config.get_config", lambda: temp_config)

    # Create source skills directory with files
    skills_src = temp_config.base_dir / "container" / "skills" / "my-skill"
    skills_src.mkdir(parents=True)
    (skills_src / "skill.md").write_text("# My Skill")
    (skills_src / "README.md").write_text("Skill documentation")

    # Sync skills
    result = sync_group_skills("test-group")

    assert result is not None
    # Check files were copied
    assert (result / "my-skill" / "skill.md").exists()
    assert (result / "my-skill" / "README.md").exists()

    # Check content is correct
    assert (result / "my-skill" / "skill.md").read_text() == "# My Skill"


@pytest.mark.asyncio
async def test_validate_group_mounts_with_skills(temp_config, monkeypatch):
    """Test that validate_group_mounts triggers skills sync."""
    monkeypatch.setattr("nanogridbot.config.get_config", lambda: temp_config)

    # Create group directory
    (temp_config.groups_dir / "test-group").mkdir(parents=True)

    # Create skills source
    skills_src = temp_config.base_dir / "container" / "skills" / "test-skill"
    skills_src.mkdir(parents=True)
    (skills_src / "skill.md").write_text("# Test")

    # Call validate_group_mounts - this should trigger sync (use is_main=True for data/ mounts)
    mounts = await validate_group_mounts(group_folder="test-group", is_main=True)

    # Verify skills were synced
    expected_skills_dir = temp_config.data_dir / "sessions" / "test-group" / ".claude" / "skills" / "test-skill"
    assert expected_skills_dir.exists()
    assert (expected_skills_dir / "skill.md").exists()
