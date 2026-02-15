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
