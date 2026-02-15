"""Tests to boost coverage for plugins/base, channels/base, __main__, and cli modules."""

import asyncio
import signal
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.plugins.base import Plugin
from nanogridbot.types import ContainerOutput, Message, MessageRole


# ============================================================================
# Plugin Base Class Tests (covers lines 16, 22, 105, 113)
# ============================================================================


class ConcretePlugin(Plugin):
    """Concrete plugin for testing abstract base class."""

    @property
    def name(self) -> str:
        return "test-plugin"

    @property
    def version(self) -> str:
        return "1.0.0"


class TestPluginBase:
    """Test Plugin base class default implementations."""

    @pytest.mark.asyncio
    async def test_on_group_registered_default(self):
        """Cover line 105: on_group_registered default is no-op."""
        plugin = ConcretePlugin()
        await plugin.on_group_registered(MagicMock())

    @pytest.mark.asyncio
    async def test_on_group_unregistered_default(self):
        """Cover line 113: on_group_unregistered default is no-op."""
        plugin = ConcretePlugin()
        await plugin.on_group_unregistered("test:jid")

    def test_name_property(self):
        """Cover line 16: name abstract property."""
        plugin = ConcretePlugin()
        assert plugin.name == "test-plugin"

    def test_version_property(self):
        """Cover line 22: version abstract property."""
        plugin = ConcretePlugin()
        assert plugin.version == "1.0.0"


# ============================================================================
# Channel Base Class Tests (covers lines 133-143, 153-163, 187-190)
# ============================================================================


class TestChannelBaseEvents:
    """Test Channel base class event handler methods."""

    @pytest.mark.asyncio
    async def test_on_message_received(self):
        """Cover lines 133-143: _on_message_received creates MessageEvent."""
        from nanogridbot.channels.base import Channel
        from nanogridbot.types import ChannelType

        channel = MagicMock(spec=Channel)
        channel._channel_type = ChannelType.TELEGRAM
        channel.emit = AsyncMock()

        # Call the unbound method with the mock as self
        await Channel._on_message_received(
            channel,
            message_id="msg1",
            chat_jid="telegram:123",
            sender="user1",
            sender_name="Alice",
            content="Hello",
        )
        channel.emit.assert_called_once()
        event = channel.emit.call_args[0][0]
        assert event.message_id == "msg1"
        assert event.is_from_me is False

    @pytest.mark.asyncio
    async def test_on_message_sent(self):
        """Cover lines 153-163: _on_message_sent creates MessageEvent with is_from_me=True."""
        from nanogridbot.channels.base import Channel
        from nanogridbot.types import ChannelType

        channel = MagicMock(spec=Channel)
        channel._channel_type = ChannelType.TELEGRAM
        channel.emit = AsyncMock()

        await Channel._on_message_sent(
            channel,
            message_id="msg2",
            chat_jid="telegram:123",
            content="Reply",
        )
        channel.emit.assert_called_once()
        event = channel.emit.call_args[0][0]
        assert event.is_from_me is True

    @pytest.mark.asyncio
    async def test_on_disconnected(self):
        """Cover lines 187-190: _on_disconnected emits DisconnectEvent."""
        from nanogridbot.channels.base import Channel
        from nanogridbot.types import ChannelType

        channel = MagicMock(spec=Channel)
        channel._channel_type = ChannelType.TELEGRAM
        channel._connected = True
        channel.emit = AsyncMock()

        await Channel._on_disconnected(channel)
        assert channel._connected is False
        channel.emit.assert_called_once()


# ============================================================================
# Container Runner Tests (covers lines 57-79, 126-128, 139-140, 150-151)
# ============================================================================


class TestContainerRunnerExtended:
    """Test container runner uncovered paths."""

    @pytest.mark.asyncio
    async def test_run_container_agent_input_data_and_docker_cmd(self):
        """Cover lines 57-79: input_data preparation and docker command building."""
        from nanogridbot.core.container_runner import run_container_agent

        mock_config = MagicMock()
        mock_config.container_timeout = 30
        mock_config.container_image = "test-image"
        mock_config.container_max_memory = "512m"
        mock_config.container_max_cpus = "1.0"

        mock_result = ContainerOutput(status="success", result="done")

        with patch("nanogridbot.core.container_runner.get_config", return_value=mock_config):
            with patch(
                "nanogridbot.core.container_runner.validate_group_mounts",
                new_callable=AsyncMock,
                return_value=[],
            ):
                with patch(
                    "nanogridbot.core.container_runner._build_docker_command",
                    return_value=["docker", "run"],
                ):
                    with patch(
                        "nanogridbot.core.container_runner._execute_container",
                        new_callable=AsyncMock,
                        return_value=mock_result,
                    ):
                        result = await run_container_agent(
                            group_folder="test",
                            prompt="hello",
                            session_id="sess1",
                            chat_jid="telegram:123",
                            is_main=False,
                        )
                        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_run_container_agent_exception(self):
        """Cover lines 77-79: exception in container execution."""
        from nanogridbot.core.container_runner import run_container_agent

        mock_config = MagicMock()
        mock_config.container_timeout = 30

        with patch("nanogridbot.core.container_runner.get_config", return_value=mock_config):
            with patch(
                "nanogridbot.core.container_runner.validate_group_mounts",
                new_callable=AsyncMock,
                return_value=[],
            ):
                with patch(
                    "nanogridbot.core.container_runner._build_docker_command",
                    return_value=["docker", "run"],
                ):
                    with patch(
                        "nanogridbot.core.container_runner._execute_container",
                        new_callable=AsyncMock,
                        side_effect=RuntimeError("docker crashed"),
                    ):
                        result = await run_container_agent(
                            group_folder="test",
                            prompt="hello",
                            session_id="sess1",
                            chat_jid="telegram:123",
                            is_main=False,
                        )
                        assert result.status == "error"
                        assert "docker crashed" in result.error

    def _make_mock_process(self, stdout=b"", stderr=b"", communicate_side_effect=None):
        """Helper to create a properly mocked subprocess."""
        mock_process = MagicMock()
        mock_stdin = MagicMock()
        mock_stdin.write = MagicMock()
        mock_stdin.drain = AsyncMock()
        mock_stdin.close = MagicMock()
        mock_process.stdin = mock_stdin
        if communicate_side_effect:
            mock_process.communicate = AsyncMock(side_effect=communicate_side_effect)
        else:
            mock_process.communicate = AsyncMock(return_value=(stdout, stderr))
        mock_process.returncode = 0 if not stderr else 1
        return mock_process

    @pytest.mark.asyncio
    async def test_execute_container_stderr(self):
        """Cover lines 126-128: stderr output from container."""
        from nanogridbot.core.container_runner import _execute_container

        mock_process = self._make_mock_process(stdout=b"", stderr=b"some error output")
        mock_config = MagicMock()
        mock_config.container_timeout = 30

        with patch("nanogridbot.core.container_runner.get_config", return_value=mock_config):
            with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_process):
                result = await _execute_container(["docker", "run"], {"prompt": "test"})
                assert result.status == "error"

    @pytest.mark.asyncio
    async def test_execute_container_timeout_kill_fails(self):
        """Cover lines 139-140: process.kill() fails silently on timeout."""
        from nanogridbot.core.container_runner import _execute_container

        mock_process = self._make_mock_process()
        mock_process.kill = MagicMock(side_effect=ProcessLookupError)
        mock_config = MagicMock()
        mock_config.container_timeout = 30

        with patch("nanogridbot.core.container_runner.get_config", return_value=mock_config):
            with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_process):
                with patch("asyncio.wait_for", new_callable=AsyncMock, side_effect=asyncio.TimeoutError):
                    result = await _execute_container(["docker", "run"], {"prompt": "test"})
                    assert result.status == "error"
                    assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_execute_container_docker_not_found(self):
        """Cover lines 150-151: FileNotFoundError when docker not installed."""
        from nanogridbot.core.container_runner import _execute_container

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            side_effect=FileNotFoundError,
        ):
            result = await _execute_container(["docker", "run"], {"prompt": "test"})
            assert result.status == "error"
            assert "Docker not found" in result.error


