"""Unit tests for core modules."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.types import ContainerConfig, ContainerOutput, RegisteredGroup


class TestMountSecurity:
    """Tests for mount security validation."""

    def test_check_path_traversal_valid(self):
        """Test path traversal detection with valid paths."""
        from nanogridbot.core.mount_security import check_path_traversal

        assert check_path_traversal("/workspace/group/test") is True
        assert check_path_traversal("/workspace/global/CLAUDE.md") is True
        assert check_path_traversal("relative/path") is True

    def test_check_path_traversal_invalid(self):
        """Test path traversal detection with invalid paths."""
        from nanogridbot.core.mount_security import check_path_traversal

        # Path traversal attempts
        assert check_path_traversal("../etc/passwd") is False
        assert check_path_traversal("/workspace/../etc/passwd") is False
        assert check_path_traversal("/home/../etc/passwd") is False

        # Null bytes
        assert check_path_traversal("/workspace/test\x00") is False

        # Unusual characters
        assert check_path_traversal("/workspace/test;rm -rf") is False

    def test_validate_container_path_valid(self):
        """Test container path validation with valid paths."""
        from nanogridbot.utils.security import validate_container_path

        assert validate_container_path("/workspace/group") is True
        assert validate_container_path("/workspace/global") is True
        assert validate_container_path("/home/node/.claude") is True
        assert validate_container_path("/tmp/test") is True
        assert validate_container_path("/app") is True

    def test_validate_container_path_invalid(self):
        """Test container path validation with invalid paths."""
        from nanogridbot.utils.security import validate_container_path

        # Unsafe absolute paths
        assert validate_container_path("/etc/passwd") is False
        assert validate_container_path("/proc/cpuinfo") is False
        assert validate_container_path("/dev/null") is False

        # Parent directory references
        assert validate_container_path("/workspace/../etc") is False

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        from nanogridbot.utils.security import sanitize_filename

        # Normal filenames
        assert sanitize_filename("test.txt") == "test.txt"
        assert sanitize_filename("my-file.md") == "my-file.md"

        # Path components should be removed
        assert sanitize_filename("../etc/passwd") == "passwd"
        assert sanitize_filename("/path/to/file.txt") == "file.txt"

        # Semicolons removed
        assert sanitize_filename("test;rm -rf.txt") == "testrm -rf.txt"

        # Long filenames truncated
        long_name = "a" * 300
        assert len(sanitize_filename(long_name)) == 255


class TestContainerRunner:
    """Tests for container runner."""

    @pytest.mark.asyncio
    async def test_parse_output_json(self, temp_dir):
        """Test parsing JSON container output."""
        from nanogridbot.core.container_runner import _parse_output

        output = """some log lines
---NANOGRIDBOT_OUTPUT_START---
{"status": "success", "result": "test result", "newSessionId": "abc123"}
---NANOGRIDBOT_OUTPUT_END---
more log lines"""

        result = _parse_output(output)

        assert result is not None
        assert result.status == "success"
        assert result.result == "test result"
        assert result.new_session_id == "abc123"

    @pytest.mark.asyncio
    async def test_parse_output_error(self, temp_dir):
        """Test parsing error container output."""
        from nanogridbot.core.container_runner import _parse_output

        output = """---NANOGRIDBOT_OUTPUT_START---
{"status": "error", "error": "Something went wrong"}
---NANOGRIDBOT_OUTPUT_END---"""

        result = _parse_output(output)

        assert result is not None
        assert result.status == "error"
        assert result.error == "Something went wrong"

    @pytest.mark.asyncio
    async def test_parse_output_plain_text(self, temp_dir):
        """Test parsing plain text container output."""
        from nanogridbot.core.container_runner import _parse_output

        output = """---NANOGRIDBOT_OUTPUT_START---
This is plain text output
without JSON formatting
---NANOGRIDBOT_OUTPUT_END---"""

        result = _parse_output(output)

        assert result is not None
        assert result.status == "success"
        assert "plain text output" in result.result

    @pytest.mark.asyncio
    async def test_parse_output_no_output(self, temp_dir):
        """Test parsing empty container output."""
        from nanogridbot.core.container_runner import _parse_output

        result = _parse_output("no markers here")

        assert result is None

    def test_build_docker_command(self):
        """Test building docker command."""
        from nanogridbot.core.container_runner import _build_docker_command

        mounts = [
            ("/path/to/group", "/workspace/group", "rw"),
            ("/path/to/global", "/workspace/global", "ro"),
        ]

        input_data = {
            "prompt": "test prompt",
            "sessionId": "abc123",
            "groupFolder": "testgroup",
            "chatJid": "test@chat.com",
            "isMain": False,
        }

        with patch("nanogridbot.core.container_runner.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(
                container_image="nanogridbot-agent:latest",
                container_timeout=300,
            )

            cmd = _build_docker_command(mounts, input_data, 300)

            assert "docker" in cmd
            assert "run" in cmd
            assert "--rm" in cmd
            assert "--network=none" in cmd
            assert "-v" in cmd
            assert "/path/to/group:/workspace/group:rw" in cmd
            assert "/path/to/global:/workspace/global:ro" in cmd
            assert "--memory" in cmd
            assert "--cpus" in cmd
            assert "nanogridbot-agent:latest" in cmd


class TestTaskSchedulerCRON:
    """Tests for task scheduler."""

    def test_task_scheduler_init(self):
        """Test task scheduler initialization."""
        from nanogridbot.core.task_scheduler import TaskScheduler

        mock_config = MagicMock()
        mock_db = MagicMock()
        mock_queue = MagicMock()

        scheduler = TaskScheduler(mock_config, mock_db, mock_queue)

        assert scheduler.config == mock_config
        assert scheduler.db == mock_db
        assert scheduler.queue == mock_queue


class TestFormatting:
    """Tests for message formatting utilities."""

    def test_format_messages_xml_empty(self):
        """Test formatting empty message list."""
        from nanogridbot.utils.formatting import format_messages_xml

        result = format_messages_xml([])
        assert "<messages>" in result and "</messages>" in result

    def test_format_messages_xml_single(self):
        """Test formatting single message."""
        from datetime import datetime
        from nanogridbot.utils.formatting import format_messages_xml

        messages = [
            {
                "sender": "user1",
                "sender_name": "User One",
                "content": "Hello",
                "timestamp": datetime(2025, 1, 1, 10, 0, 0),
                "is_from_me": False,
            }
        ]

        result = format_messages_xml(messages)
        assert '<message role=' in result
        assert "Hello" in result
        assert "User One" in result

    def test_format_messages_xml_multiple(self):
        """Test formatting multiple messages."""
        from datetime import datetime
        from nanogridbot.utils.formatting import format_messages_xml

        messages = [
            {
                "sender": "user1",
                "sender_name": "User One",
                "content": "Hello",
                "timestamp": datetime(2025, 1, 1, 10, 0, 0),
                "is_from_me": False,
            },
            {
                "sender": "user2",
                "sender_name": "User Two",
                "content": "Hi there",
                "timestamp": datetime(2025, 1, 1, 10, 1, 0),
                "is_from_me": True,
            },
        ]

        result = format_messages_xml(messages)
        assert "<messages>" in result
        assert '<message role=' in result
        assert result.count('<message role=') == 2


class TestAsyncHelpers:
    """Tests for async helper utilities."""

    @pytest.mark.asyncio
    async def test_run_with_retry_success(self):
        """Test run with retry on successful execution."""
        from nanogridbot.utils.async_helpers import run_with_retry

        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await run_with_retry(success_func, max_retries=3)
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_run_with_retry_failure_then_success(self):
        """Test run with retry succeeds after failure."""
        from nanogridbot.utils.async_helpers import run_with_retry

        call_count = 0

        async def fail_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary error")
            return "success"

        result = await run_with_retry(fail_then_success, max_retries=3)
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_run_with_retry_all_fail(self):
        """Test run with retry fails after max retries."""
        from nanogridbot.utils.async_helpers import run_with_retry

        call_count = 0

        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise Exception("Permanent error")

        with pytest.raises(Exception):
            await run_with_retry(always_fail, max_retries=3)
        # Initial + max_retries attempts
        assert call_count == 4


class TestContainerOutput:
    """Tests for ContainerOutput type."""

    def test_container_output_success(self):
        """Test successful container output."""
        output = ContainerOutput(
            status="success",
            result="test result",
            new_session_id="abc123",
        )

        assert output.status == "success"
        assert output.result == "test result"
        assert output.new_session_id == "abc123"

    def test_container_output_error(self):
        """Test error container output."""
        output = ContainerOutput(
            status="error",
            error="Something went wrong",
        )

        assert output.status == "error"
        assert output.error == "Something went wrong"

    def test_container_output_to_dict(self):
        """Test container output serialization."""
        output = ContainerOutput(
            status="success",
            result="test",
            new_session_id="abc",
        )

        result = output.model_dump()
        assert result["status"] == "success"
        assert result["result"] == "test"
