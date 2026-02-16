"""Unit tests for container runner."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.core.container_runner import (
    OUTPUT_END_MARKER,
    OUTPUT_START_MARKER,
    build_docker_command,
    _parse_output,
    check_docker_available,
    cleanup_container,
    get_container_status,
)
from nanogridbot.types import ContainerOutput


class TestParseOutput:
    """Test _parse_output function."""

    def test_valid_json_output(self):
        """Test parsing valid JSON between markers."""
        output = f"""log line 1
{OUTPUT_START_MARKER}
{{"status": "success", "result": "hello", "newSessionId": "s1"}}
{OUTPUT_END_MARKER}
log line 2"""

        result = _parse_output(output)
        assert result is not None
        assert result.status == "success"
        assert result.result == "hello"
        assert result.new_session_id == "s1"

    def test_error_json_output(self):
        """Test parsing error JSON output."""
        output = f"""{OUTPUT_START_MARKER}
{{"status": "error", "error": "something broke"}}
{OUTPUT_END_MARKER}"""

        result = _parse_output(output)
        assert result is not None
        assert result.status == "error"
        assert result.error == "something broke"

    def test_plain_text_output(self):
        """Test parsing non-JSON text between markers."""
        output = f"""{OUTPUT_START_MARKER}
This is plain text
across multiple lines
{OUTPUT_END_MARKER}"""

        result = _parse_output(output)
        assert result is not None
        assert result.status == "success"
        assert "plain text" in result.result
        assert "multiple lines" in result.result

    def test_no_markers(self):
        """Test parsing output without markers."""
        result = _parse_output("just some random output")
        assert result is None

    def test_empty_between_markers(self):
        """Test parsing empty content between markers."""
        output = f"""{OUTPUT_START_MARKER}
{OUTPUT_END_MARKER}"""

        result = _parse_output(output)
        assert result is None

    def test_only_start_marker(self):
        """Test output with only start marker (no end)."""
        output = f"""{OUTPUT_START_MARKER}
some content here"""

        result = _parse_output(output)
        # Without end marker, content is collected but still parsed
        assert result is not None
        assert "some content here" in result.result

    def test_json_with_missing_fields(self):
        """Test JSON output with missing optional fields."""
        output = f"""{OUTPUT_START_MARKER}
{{"status": "success"}}
{OUTPUT_END_MARKER}"""

        result = _parse_output(output)
        assert result is not None
        assert result.status == "success"
        assert result.result is None
        assert result.new_session_id is None

    def test_multiline_json(self):
        """Test multiline JSON output."""
        data = json.dumps(
            {"status": "success", "result": "line1\nline2\nline3"},
        )
        output = f"""{OUTPUT_START_MARKER}
{data}
{OUTPUT_END_MARKER}"""

        result = _parse_output(output)
        assert result is not None
        assert result.status == "success"


class TestBuildDockerCommand:
    """Test build_docker_command function."""

    def test_basic_command(self):
        """Test basic docker command construction."""
        mounts = [("/host/path", "/container/path", "rw")]
        input_data = {"isMain": False, "groupFolder": "test"}

        with patch("nanogridbot.core.container_runner.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(container_image="test-image:latest")
            cmd = build_docker_command(mounts, input_data, 300)

        assert cmd[0] == "docker"
        assert cmd[1] == "run"
        assert "--rm" in cmd
        assert "--network=none" in cmd

    def test_mounts_included(self):
        """Test that mounts are properly included."""
        mounts = [
            ("/host/a", "/container/a", "rw"),
            ("/host/b", "/container/b", "ro"),
        ]
        input_data = {"isMain": False, "groupFolder": "test"}

        with patch("nanogridbot.core.container_runner.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(container_image="img:latest")
            cmd = build_docker_command(mounts, input_data, 300)

        assert "/host/a:/container/a:rw" in cmd
        assert "/host/b:/container/b:ro" in cmd

    def test_environment_variables(self):
        """Test environment variables are set."""
        mounts = []
        input_data = {"isMain": True, "groupFolder": "mygroup"}

        with patch("nanogridbot.core.container_runner.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(container_image="img:latest")
            cmd = build_docker_command(mounts, input_data, 300)

        assert "NANOGRIDBOT_IS_MAIN=true" in cmd
        assert "NANOGRIDBOT_GROUP=mygroup" in cmd

    def test_custom_environment_variables(self):
        """Test custom environment variables are passed to container."""
        mounts = []
        input_data = {"isMain": False, "groupFolder": "test"}

        with patch("nanogridbot.core.container_runner.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(container_image="img:latest")
            cmd = build_docker_command(
                mounts, input_data, 300, env={"ANTHROPIC_MODEL": "claude-sonnet-4-20250514", "CUSTOM_VAR": "test"}
            )

        assert "-e" in cmd
        assert "ANTHROPIC_MODEL=claude-sonnet-4-20250514" in cmd
        assert "CUSTOM_VAR=test" in cmd

    def test_no_custom_env_when_none_provided(self):
        """Test no custom env flags when env is None."""
        mounts = []
        input_data = {"isMain": False, "groupFolder": "test"}

        with patch("nanogridbot.core.container_runner.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(container_image="img:latest")
            cmd = build_docker_command(mounts, input_data, 300, env=None)

        # Should only have default env vars, no custom ones
        assert "NANOGRIDBOT_IS_MAIN=false" in cmd
        assert "ANTHROPIC_MODEL" not in " ".join(cmd)

    def test_resource_limits(self):
        """Test memory and CPU limits are set."""
        mounts = []
        input_data = {"isMain": False, "groupFolder": "test"}

        with patch("nanogridbot.core.container_runner.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(container_image="img:latest")
            cmd = build_docker_command(mounts, input_data, 300)

        assert "--memory" in cmd
        assert "2g" in cmd
        assert "--cpus" in cmd
        assert "1.0" in cmd

    def test_timeout_setting(self):
        """Test stop-timeout is set."""
        mounts = []
        input_data = {"isMain": False, "groupFolder": "test"}

        with patch("nanogridbot.core.container_runner.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(container_image="img:latest")
            cmd = build_docker_command(mounts, input_data, 600)

        idx = cmd.index("--stop-timeout")
        assert cmd[idx + 1] == "600"

    def test_image_from_config(self):
        """Test image name comes from config."""
        mounts = []
        input_data = {"isMain": False, "groupFolder": "test"}

        mock_config = MagicMock(container_image="custom-image:v2")
        with patch("nanogridbot.config.get_config", return_value=mock_config), patch(
            "nanogridbot.config._config", mock_config
        ):
            cmd = build_docker_command(mounts, input_data, 300)

        assert cmd[-1] == "custom-image:v2"


class TestCheckDockerAvailable:
    """Test check_docker_available function."""

    @pytest.mark.asyncio
    async def test_docker_available(self):
        """Test when docker is available."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_docker_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_docker_not_available(self):
        """Test when docker command fails."""
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"error"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await check_docker_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_docker_not_installed(self):
        """Test when docker is not installed."""
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await check_docker_available()
            assert result is False


class TestGetContainerStatus:
    """Test get_container_status function."""

    @pytest.mark.asyncio
    async def test_running_container(self):
        """Test getting status of running container."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"running\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await get_container_status("test-container")
            assert result == "running"

    @pytest.mark.asyncio
    async def test_exited_container(self):
        """Test getting status of exited container."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"exited\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await get_container_status("test-container")
            assert result == "exited"

    @pytest.mark.asyncio
    async def test_container_not_found(self):
        """Test getting status of non-existent container."""
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"not found"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await get_container_status("nonexistent")
            assert result == "not_found"

    @pytest.mark.asyncio
    async def test_docker_not_installed(self):
        """Test when docker is not installed."""
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await get_container_status("test")
            assert result == "not_found"


class TestCleanupContainer:
    """Test cleanup_container function."""

    @pytest.mark.asyncio
    async def test_cleanup_success(self):
        """Test successful container cleanup."""
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            await cleanup_container("test-container")
            # Should not raise

    @pytest.mark.asyncio
    async def test_cleanup_failure(self):
        """Test container cleanup failure."""
        with patch("asyncio.create_subprocess_exec", side_effect=Exception("docker error")):
            # Should not raise, just log warning
            await cleanup_container("test-container")


class TestRunContainerAgent:
    """Test run_container_agent function."""

    @pytest.mark.asyncio
    async def test_mount_validation_failure(self):
        """Test run_container_agent when mount validation fails."""
        from nanogridbot.core.container_runner import run_container_agent

        with patch(
            "nanogridbot.core.container_runner.validate_group_mounts",
            side_effect=Exception("Invalid mount"),
        ), patch("nanogridbot.core.container_runner.get_config") as mock_cfg:
            mock_cfg.return_value = MagicMock(container_timeout=300)

            result = await run_container_agent(
                group_folder="test",
                prompt="hello",
                session_id=None,
                chat_jid="jid1",
            )

            assert result.status == "error"
            assert "Invalid mount" in result.error

    @pytest.mark.asyncio
    async def test_execute_container_docker_not_found(self):
        """Test _execute_container when docker is not found."""
        from nanogridbot.core.container_runner import _execute_container

        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            result = await _execute_container(["docker", "run"], {"prompt": "test"})

            assert result.status == "error"
            assert "Docker not found" in result.error

    @pytest.mark.asyncio
    async def test_execute_container_timeout(self):
        """Test _execute_container when container times out."""
        from nanogridbot.core.container_runner import _execute_container

        mock_process = AsyncMock()
        mock_stdin = AsyncMock()
        mock_stdin.write = MagicMock()
        mock_stdin.drain = AsyncMock()
        mock_stdin.close = MagicMock()
        mock_process.stdin = mock_stdin
        mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_process.kill = MagicMock()

        with patch("asyncio.create_subprocess_exec", return_value=mock_process), patch(
            "nanogridbot.core.container_runner.get_config"
        ) as mock_cfg:
            mock_cfg.return_value = MagicMock(container_timeout=1)
            result = await _execute_container(["docker", "run"], {"prompt": "test"})

            assert result.status == "error"
            assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_execute_container_success(self):
        """Test _execute_container with successful output."""
        from nanogridbot.core.container_runner import _execute_container

        output_json = json.dumps({"status": "success", "result": "done"})
        stdout = f"{OUTPUT_START_MARKER}\n{output_json}\n{OUTPUT_END_MARKER}\n".encode()

        mock_stdin = AsyncMock()
        mock_stdin.write = MagicMock()
        mock_stdin.drain = AsyncMock()
        mock_stdin.close = MagicMock()

        mock_process = AsyncMock()
        mock_process.stdin = mock_stdin
        mock_process.communicate = AsyncMock(return_value=(stdout, b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process), patch(
            "nanogridbot.core.container_runner.get_config"
        ) as mock_cfg:
            mock_cfg.return_value = MagicMock(container_timeout=300)
            result = await _execute_container(["docker", "run"], {"prompt": "test"})

            assert result.status == "success"
            assert result.result == "done"

    @pytest.mark.asyncio
    async def test_execute_container_no_output(self):
        """Test _execute_container with no stdout."""
        from nanogridbot.core.container_runner import _execute_container

        mock_stdin = AsyncMock()
        mock_stdin.write = MagicMock()
        mock_stdin.drain = AsyncMock()
        mock_stdin.close = MagicMock()

        mock_process = AsyncMock()
        mock_process.stdin = mock_stdin
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process), patch(
            "nanogridbot.core.container_runner.get_config"
        ) as mock_cfg:
            mock_cfg.return_value = MagicMock(container_timeout=300)
            result = await _execute_container(["docker", "run"], {"prompt": "test"})

            assert result.status == "error"
            assert "No output" in result.error
