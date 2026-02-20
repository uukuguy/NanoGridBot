"""Unit tests for security utilities."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.utils.security import (
    MountSecurityError,
    _is_path_allowed,
    _is_path_under_directory,
    check_readonly_directory,
    check_rw_required_directory,
    check_symlink,
    sanitize_filename,
    validate_container_path,
    validate_mounts,
    validate_no_symlink_escape,
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


class TestCheckSymlink:
    """Test check_symlink function."""

    def test_regular_directory(self, tmp_path):
        """Test regular directory is not a symlink."""
        regular_dir = tmp_path / "regular"
        regular_dir.mkdir()
        assert check_symlink(regular_dir) is False

    def test_symlink_directory(self, tmp_path):
        """Test symlink directory is detected."""
        target = tmp_path / "target"
        target.mkdir()
        link = tmp_path / "link"
        link.symlink_to(target)
        assert check_symlink(link) is True

    def test_nested_symlink(self, tmp_path):
        """Test nested symlink is detected."""
        level1 = tmp_path / "level1"
        level1.mkdir()
        level2 = level1 / "level2"
        level2.mkdir()
        link = tmp_path / "link"
        link.symlink_to(level1)
        # Path itself is not symlink, but contains one
        assert check_symlink(level2) is False


class TestValidateNoSymlinkEscape:
    """Test validate_no_symlink_escape function."""

    def test_regular_path_allowed(self, mock_config, tmp_path):
        """Test regular path is allowed."""
        regular_dir = tmp_path / "regular"
        regular_dir.mkdir()
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            assert validate_no_symlink_escape(regular_dir) is True

    def test_symlink_to_allowed_path(self, mock_config, tmp_path):
        """Test symlink to allowed path is allowed."""
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        link = tmp_path / "link"
        link.symlink_to(allowed)
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            assert validate_no_symlink_escape(link) is True


class TestCheckReadonlyDirectory:
    """Test check_readonly_directory function."""

    def test_ssh_directory(self, tmp_path):
        """Test .ssh directory is detected as sensitive."""
        ssh_dir = tmp_path / ".ssh"
        ssh_dir.mkdir()
        assert check_readonly_directory(ssh_dir) is True

    def test_gnupg_directory(self, tmp_path):
        """Test .gnupg directory is detected as sensitive."""
        gnupg_dir = tmp_path / ".gnupg"
        gnupg_dir.mkdir()
        assert check_readonly_directory(gnupg_dir) is True

    def test_nested_ssh(self, tmp_path):
        """Test nested .ssh directory is detected."""
        nested = tmp_path / "home" / "user" / ".ssh"
        nested.mkdir(parents=True)
        assert check_readonly_directory(nested) is True

    def test_regular_directory(self, tmp_path):
        """Test regular directory is not sensitive."""
        regular = tmp_path / "documents"
        regular.mkdir()
        assert check_readonly_directory(regular) is False


class TestCheckRwRequiredDirectory:
    """Test check_rw_required_directory function."""

    def test_ipc_directory(self, tmp_path):
        """Test ipc directory requires read-write."""
        ipc_dir = tmp_path / "ipc"
        ipc_dir.mkdir()
        assert check_rw_required_directory(ipc_dir) is True

    def test_sessions_directory(self, tmp_path):
        """Test sessions directory requires read-write."""
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        assert check_rw_required_directory(sessions_dir) is True

    def test_claude_directory(self, tmp_path):
        """Test .claude directory requires read-write."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        assert check_rw_required_directory(claude_dir) is True

    def test_regular_directory(self, tmp_path):
        """Test regular directory doesn't require read-write."""
        regular = tmp_path / "data"
        regular.mkdir()
        assert check_rw_required_directory(regular) is False


class TestNonMainGroupReadonly:
    """Test non-main group read-only enforcement."""

    @pytest.mark.asyncio
    async def test_non_main_forced_readonly(self, mock_config, tmp_path):
        """Test non-main group mounts are forced to read-only."""
        groups_dir = tmp_path / "groups" / "testgroup"
        groups_dir.mkdir(parents=True)
        mounts = [
            {
                "host_path": str(groups_dir),
                "container_path": "/workspace/group",
                "mode": "rw",  # Requested rw but should be forced to ro
            }
        ]
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            result = await validate_mounts(mounts, is_main=False, enforce_readonly=True)
            assert len(result) == 1
            assert result[0][2] == "ro"  # Forced to read-only

    @pytest.mark.asyncio
    async def test_rw_required_allows_rw(self, mock_config, tmp_path):
        """Test ipc directory allows read-write for non-main groups."""
        groups_dir = tmp_path / "groups" / "testgroup"
        groups_dir.mkdir(parents=True)
        ipc_dir = groups_dir / "ipc"
        ipc_dir.mkdir()
        mounts = [
            {
                "host_path": str(ipc_dir),
                "container_path": "/workspace/ipc",
                "mode": "rw",
            }
        ]
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            result = await validate_mounts(mounts, is_main=False, enforce_readonly=True)
            assert len(result) == 1
            assert result[0][2] == "rw"  # IPC allows rw

    @pytest.mark.asyncio
    async def test_sensitive_directory_forced_ro(self, mock_config, tmp_path):
        """Test sensitive directories are forced to read-only."""
        groups_dir = tmp_path / "groups" / "testgroup"
        groups_dir.mkdir(parents=True)
        ssh_dir = groups_dir / ".ssh"
        ssh_dir.mkdir()
        mounts = [
            {
                "host_path": str(ssh_dir),
                "container_path": "/workspace/.ssh",
                "mode": "rw",
            }
        ]
        with patch("nanogridbot.config.get_config", return_value=mock_config):
            result = await validate_mounts(mounts, is_main=True, enforce_readonly=True)
            assert len(result) == 1
            assert result[0][2] == "ro"  # Sensitive dirs forced to ro
