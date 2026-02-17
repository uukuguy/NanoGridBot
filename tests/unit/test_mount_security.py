"""Unit tests for mount security module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.core.mount_security import (
    check_path_traversal,
    get_allowed_mount_paths,
    validate_group_mounts,
)
from nanogridbot.utils.security import MountSecurityError


class TestCheckPathTraversal:
    """Test check_path_traversal function."""

    def test_safe_path(self):
        assert check_path_traversal("/workspace/data/file.txt") is True

    def test_double_dot_blocked(self):
        assert check_path_traversal("/workspace/../etc") is False

    def test_workspace_escape(self):
        assert check_path_traversal("/workspace/../../../etc") is False

    def test_home_escape(self):
        assert check_path_traversal("/home/../../../etc") is False

    def test_null_byte_blocked(self):
        assert check_path_traversal("/workspace/file\x00.txt") is False

    def test_unusual_characters_blocked(self):
        assert check_path_traversal("/workspace/file;rm -rf") is False

    def test_normal_alphanumeric(self):
        assert check_path_traversal("/workspace/my-file_v2.txt") is True

    def test_colon_allowed(self):
        assert check_path_traversal("/workspace/file:tag") is True

    def test_space_blocked(self):
        assert check_path_traversal("/workspace/my file") is False

    def test_empty_path(self):
        assert check_path_traversal("") is True


class TestGetAllowedMountPaths:
    """Test get_allowed_mount_paths function."""

    def test_returns_list(self, mock_config):
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            result = get_allowed_mount_paths()
            assert isinstance(result, list)
            assert len(result) == 4

    def test_contains_project_dirs(self, mock_config, tmp_path):
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            result = get_allowed_mount_paths()
            assert mock_config.base_dir in result
            assert mock_config.groups_dir in result
            assert mock_config.data_dir in result
            assert mock_config.store_dir in result


class TestValidateGroupMounts:
    """Test validate_group_mounts function."""

    @pytest.mark.asyncio
    async def test_basic_group_mounts(self, mock_config, tmp_path):
        """Test basic group mount creation."""
        group_dir = tmp_path / "groups" / "testgroup"
        group_dir.mkdir(parents=True)

        with patch("nanogridbot.config.get_config", return_value=mock_config):
            with patch("nanogridbot.config.get_config", return_value=mock_config):
                result = await validate_group_mounts("testgroup", is_main=True)
                # Should have at least the group dir mount + session + ipc
                assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_global_dir_mounted_if_exists(self, mock_config, tmp_path):
        """Test global directory is mounted when it exists."""
        group_dir = tmp_path / "groups" / "testgroup"
        group_dir.mkdir(parents=True)
        global_dir = tmp_path / "groups" / "global"
        global_dir.mkdir(parents=True)

        with patch("nanogridbot.config.get_config", return_value=mock_config):
            with patch("nanogridbot.config.get_config", return_value=mock_config):
                result = await validate_group_mounts("testgroup", is_main=True)
                container_paths = [r[1] for r in result]
                assert "/workspace/global" in container_paths

    @pytest.mark.asyncio
    async def test_main_group_mounts_project_root(self, mock_config, tmp_path):
        """Test main group gets project root mount."""
        group_dir = tmp_path / "groups" / "testgroup"
        group_dir.mkdir(parents=True)

        with patch("nanogridbot.config.get_config", return_value=mock_config):
            with patch("nanogridbot.config.get_config", return_value=mock_config):
                result = await validate_group_mounts("testgroup", is_main=True)
                container_paths = [r[1] for r in result]
                assert "/workspace/project" in container_paths

    @pytest.mark.asyncio
    async def test_non_main_group_no_project_root(self, mock_config, tmp_path):
        """Test non-main group raises for non-groups mounts (session/ipc under data/)."""
        group_dir = tmp_path / "groups" / "testgroup"
        group_dir.mkdir(parents=True, exist_ok=True)

        with patch("nanogridbot.config.get_config", return_value=mock_config):
            with patch("nanogridbot.config.get_config", return_value=mock_config):
                # Non-main groups have session/ipc mounts under data/ which
                # violates the "only groups/" restriction in validate_mounts
                with pytest.raises(MountSecurityError, match="Non-main groups"):
                    await validate_group_mounts("testgroup", is_main=False)

    @pytest.mark.asyncio
    async def test_session_dir_created(self, mock_config, tmp_path):
        """Test session directory is created."""
        group_dir = tmp_path / "groups" / "testgroup"
        group_dir.mkdir(parents=True)

        with patch("nanogridbot.config.get_config", return_value=mock_config):
            with patch("nanogridbot.config.get_config", return_value=mock_config):
                await validate_group_mounts("testgroup", is_main=True)
                session_path = tmp_path / "data" / "sessions" / "testgroup" / ".claude"
                assert session_path.exists()

    @pytest.mark.asyncio
    async def test_ipc_dir_created(self, mock_config, tmp_path):
        """Test IPC directory is created."""
        group_dir = tmp_path / "groups" / "testgroup"
        group_dir.mkdir(parents=True)

        with patch("nanogridbot.config.get_config", return_value=mock_config):
            with patch("nanogridbot.config.get_config", return_value=mock_config):
                await validate_group_mounts("testgroup", is_main=True)
                ipc_path = tmp_path / "data" / "ipc" / "testgroup"
                assert ipc_path.exists()

    @pytest.mark.asyncio
    async def test_additional_mounts_from_config(self, mock_config, tmp_path):
        """Test additional mounts from container config."""
        group_dir = tmp_path / "groups" / "testgroup"
        group_dir.mkdir(parents=True)
        extra_dir = tmp_path / "groups" / "extra"
        extra_dir.mkdir(parents=True)

        container_config = {
            "additional_mounts": [
                {
                    "host_path": str(extra_dir),
                    "container_path": "/workspace/extra",
                    "mode": "ro",
                }
            ]
        }

        with patch("nanogridbot.config.get_config", return_value=mock_config):
            with patch("nanogridbot.config.get_config", return_value=mock_config):
                result = await validate_group_mounts(
                    "testgroup", container_config=container_config, is_main=True
                )
                container_paths = [r[1] for r in result]
                assert "/workspace/extra" in container_paths

    @pytest.mark.asyncio
    async def test_no_group_dir_still_works(self, mock_config, tmp_path):
        """Test works even if group directory doesn't exist."""
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            with patch("nanogridbot.config.get_config", return_value=mock_config):
                result = await validate_group_mounts("nonexistent", is_main=True)
                # Should still have session + ipc + project root mounts
                assert len(result) >= 1


class TestCreateGroupEnvFile:
    """Tests for create_group_env_file function."""

    def test_create_group_env_file_filters_correctly(self, tmp_path, monkeypatch):
        """Test that env file is created with only allowed vars."""
        from nanogridbot.config import Config
        config = Config(
            base_dir=tmp_path,
            data_dir=tmp_path / "data",
            groups_dir=tmp_path / "groups",
            store_dir=tmp_path / "store",
        )
        # Patch the config module's get_config function
        monkeypatch.setattr("nanogridbot.config.get_config", lambda: config)

        # Create .env with multiple vars
        env_path = tmp_path / ".env"
        env_path.write_text("""\
ANTHROPIC_API_KEY=sk-test-key
OTHER_VAR=secret
ANTHROPIC_MODEL=claude-sonnet
DEBUG=true
""")

        from nanogridbot.core.mount_security import create_group_env_file
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

    def test_create_group_env_file_no_env(self, tmp_path, monkeypatch):
        """Test None returned when no .env exists."""
        from nanogridbot.config import Config
        config = Config(
            base_dir=tmp_path / "nonexistent",
            data_dir=tmp_path / "data",
            groups_dir=tmp_path / "groups",
            store_dir=tmp_path / "store",
        )
        monkeypatch.setattr("nanogridbot.config.get_config", lambda: config)

        from nanogridbot.core.mount_security import create_group_env_file
        result = create_group_env_file("test-group")

        # No .env file exists, should return None
        assert result is None

    def test_create_group_env_file_custom_vars(self, tmp_path, monkeypatch):
        """Test custom allowed vars."""
        from nanogridbot.config import Config
        config = Config(
            base_dir=tmp_path,
            data_dir=tmp_path / "data",
            groups_dir=tmp_path / "groups",
            store_dir=tmp_path / "store",
        )
        monkeypatch.setattr("nanogridbot.config.get_config", lambda: config)

        # Create .env with multiple vars
        env_path = tmp_path / ".env"
        env_path.write_text("""\
ANTHROPIC_API_KEY=sk-test-key
CUSTOM_VAR=custom-value
DEBUG=true
""")

        from nanogridbot.core.mount_security import create_group_env_file
        # Only allow CUSTOM_VAR
        result = create_group_env_file("test-group", allowed_vars=["CUSTOM_VAR"])

        assert result is not None
        host_path, _, _ = result
        env_content = Path(host_path).read_text()
        assert "CUSTOM_VAR=custom-value" in env_content
        assert "ANTHROPIC_API_KEY" not in env_content


class TestSyncGroupSkills:
    """Tests for sync_group_skills function."""

    def test_sync_group_skills_no_source(self, tmp_path, monkeypatch):
        """Test None returned when no skills source exists."""
        from nanogridbot.config import Config
        config = Config(
            base_dir=tmp_path,
            data_dir=tmp_path / "data",
            groups_dir=tmp_path / "groups",
            store_dir=tmp_path / "store",
        )
        monkeypatch.setattr("nanogridbot.config.get_config", lambda: config)

        from nanogridbot.core.mount_security import sync_group_skills
        # No container/skills directory exists
        result = sync_group_skills("test-group")

        assert result is None

    def test_sync_group_skills_with_files(self, tmp_path, monkeypatch):
        """Test skills are synced when source exists."""
        from nanogridbot.config import Config
        config = Config(
            base_dir=tmp_path,
            data_dir=tmp_path / "data",
            groups_dir=tmp_path / "groups",
            store_dir=tmp_path / "store",
        )
        monkeypatch.setattr("nanogridbot.config.get_config", lambda: config)

        # Create source skills directory with files
        skills_src = tmp_path / "container" / "skills" / "test-skill"
        skills_src.mkdir(parents=True)
        (skills_src / "README.md").write_text("# Test Skill")
        (skills_src / "skill.md").write_text("## Test Skill Content")

        from nanogridbot.core.mount_security import sync_group_skills
        result = sync_group_skills("test-group")

        assert result is not None
        # Check files were copied
        assert (result / "test-skill" / "README.md").exists()
        assert (result / "test-skill" / "skill.md").exists()
