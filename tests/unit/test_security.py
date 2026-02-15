"""Unit tests for security utilities."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.utils.security import (
    MountSecurityError,
    _is_path_allowed,
    _is_path_under_directory,
    sanitize_filename,
    validate_container_path,
    validate_mounts,
)


class TestValidateContainerPath:
    """Test validate_container_path function."""

    def test_safe_workspace_path(self):
        assert validate_container_path("/workspace/data") is True

    def test_safe_home_path(self):
        assert validate_container_path("/home/user") is True

    def test_safe_tmp_path(self):
        assert validate_container_path("/tmp/data") is True

    def test_safe_app_path(self):
        assert validate_container_path("/app/code") is True

    def test_unsafe_absolute_path(self):
        assert validate_container_path("/etc/passwd") is False

    def test_unsafe_root_path(self):
        assert validate_container_path("/root/.ssh") is False

    def test_parent_directory_traversal(self):
        assert validate_container_path("/workspace/../etc/passwd") is False

    def test_double_dot_in_path(self):
        assert validate_container_path("some/../../escape") is False

    def test_dev_path_blocked(self):
        assert validate_container_path("/dev/sda") is False

    def test_proc_path_blocked(self):
        assert validate_container_path("/proc/1/cmdline") is False

    def test_relative_path_safe(self):
        assert validate_container_path("workspace/data") is True

    def test_empty_path(self):
        assert validate_container_path("") is True


class TestSanitizeFilename:
    """Test sanitize_filename function."""

    def test_normal_filename(self):
        assert sanitize_filename("report.pdf") == "report.pdf"

    def test_removes_path_components(self):
        result = sanitize_filename("/etc/passwd")
        assert "/" not in result
        assert result == "passwd"

    def test_removes_dangerous_chars(self):
        result = sanitize_filename("file;rm -rf.txt")
        assert ";" not in result

    def test_preserves_dots_and_hyphens(self):
        result = sanitize_filename("my-file.v2.tar.gz")
        assert result == "my-file.v2.tar.gz"

    def test_truncates_long_filename(self):
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        assert len(result) <= 255

    def test_path_traversal_stripped(self):
        result = sanitize_filename("../../etc/passwd")
        assert result == "passwd"

    def test_windows_path_stripped(self):
        result = sanitize_filename("C:\\Users\\test\\file.txt")
        # Path().name handles this
        assert ".." not in result


class TestIsPathAllowed:
    """Test _is_path_allowed function."""

    def test_path_under_project_root(self, mock_config, tmp_path):
        """Test path under project root is allowed."""
        test_path = tmp_path / "subdir"
        test_path.mkdir()
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            assert _is_path_allowed(test_path, []) is True

    def test_path_outside_project_root(self, mock_config):
        """Test path outside project root is not allowed."""
        outside_path = Path("/usr/local/bin")
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            assert _is_path_allowed(outside_path, []) is False

    def test_path_in_allowlist(self, mock_config, tmp_path):
        """Test path in allowlist is allowed."""
        # Use real paths — _is_path_allowed calls resolve() internally
        extra_dir = tmp_path / "extra"
        extra_dir.mkdir(exist_ok=True)
        sub = extra_dir / "file"
        sub.mkdir(exist_ok=True)
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            assert _is_path_allowed(sub, [extra_dir]) is True

    def test_empty_allowlist_outside_root(self, mock_config):
        """Test empty allowlist with path outside root."""
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            assert _is_path_allowed(Path("/nowhere"), []) is False


class TestIsPathUnderDirectory:
    """Test _is_path_under_directory function."""

    def test_path_under_directory(self, mock_config, tmp_path):
        """Test path under named directory."""
        groups_dir = tmp_path / "groups"
        groups_dir.mkdir(exist_ok=True)
        sub = groups_dir / "mygroup"
        sub.mkdir(exist_ok=True)
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            assert _is_path_under_directory(sub, "groups") is True

    def test_path_not_under_directory(self, mock_config, tmp_path):
        """Test path not under named directory."""
        other = tmp_path / "other"
        other.mkdir()
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            assert _is_path_under_directory(other, "groups") is False


class TestValidateMounts:
    """Test validate_mounts function."""

    @pytest.mark.asyncio
    async def test_valid_mount(self, mock_config, tmp_path):
        """Test valid mount passes validation."""
        host_dir = tmp_path / "groups" / "test"
        host_dir.mkdir(parents=True)
        mounts = [
            {
                "host_path": str(host_dir),
                "container_path": "/workspace/group",
                "mode": "ro",
            }
        ]
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            result = await validate_mounts(mounts, is_main=True)
            assert len(result) == 1
            assert result[0][2] == "ro"

    @pytest.mark.asyncio
    async def test_nonexistent_path_skipped(self, mock_config):
        """Test nonexistent host path is skipped."""
        mounts = [
            {
                "host_path": "/nonexistent/path/xyz",
                "container_path": "/workspace",
                "mode": "ro",
            }
        ]
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            result = await validate_mounts(mounts, is_main=True)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_path_not_in_allowlist_raises(self, mock_config, tmp_path):
        """Test path outside allowlist raises error."""
        import tempfile

        with tempfile.TemporaryDirectory() as outside:
            mounts = [
                {
                    "host_path": outside,
                    "container_path": "/workspace",
                    "mode": "ro",
                }
            ]
            with patch("nanogridbot.config.get_config", return_value=mock_config):
                with pytest.raises(MountSecurityError, match="not in allowlist"):
                    await validate_mounts(mounts, is_main=True)

    @pytest.mark.asyncio
    async def test_non_main_group_restricted(self, mock_config, tmp_path):
        """Test non-main groups can only mount under groups/."""
        # Create a path under project root but not under groups/
        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        mounts = [
            {
                "host_path": str(data_dir),
                "container_path": "/workspace",
                "mode": "ro",
            }
        ]
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            with pytest.raises(MountSecurityError, match="Non-main groups"):
                await validate_mounts(mounts, is_main=False)

    @pytest.mark.asyncio
    async def test_default_mode_is_ro(self, mock_config, tmp_path):
        """Test default mount mode is read-only."""
        host_dir = tmp_path / "groups" / "test"
        host_dir.mkdir(parents=True)
        mounts = [
            {
                "host_path": str(host_dir),
                "container_path": "/workspace",
            }
        ]
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            result = await validate_mounts(mounts, is_main=True)
            assert result[0][2] == "ro"

    @pytest.mark.asyncio
    async def test_empty_mounts(self, mock_config):
        """Test empty mount list."""
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            result = await validate_mounts([], is_main=True)
            assert result == []


class TestMountSecurityError:
    """Test MountSecurityError exception."""

    def test_is_exception(self):
        assert issubclass(MountSecurityError, Exception)

    def test_message(self):
        err = MountSecurityError("test error")
        assert str(err) == "test error"
