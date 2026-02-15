"""Extended unit tests for Orchestrator - covering uncovered lines."""

import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.core.orchestrator import Orchestrator
from nanogridbot.types import Message, RegisteredGroup


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = MagicMock()
    config.poll_interval = 100  # 100ms for fast tests
    config.assistant_name = "TestBot"
    config.data_dir = MagicMock()
    return config


@pytest.fixture
def mock_db():
    """Mock database."""
    db = AsyncMock()
    db.get_router_state = AsyncMock(return_value={})
    db.get_groups = AsyncMock(return_value=[])
    db.save_router_state = AsyncMock()
    db.get_new_messages = AsyncMock(return_value=[])
    db.save_group = AsyncMock()
    db.delete_group = AsyncMock()
    return db


@pytest.fixture
def mock_channel():
    """Mock channel."""
    channel = AsyncMock()
    channel.name = "test_channel"
    channel.connect = AsyncMock()
    channel.disconnect = AsyncMock()
    channel.owns_jid = MagicMock(return_value=True)
    channel.send_message = AsyncMock()
    channel._connected = False
    return channel


@pytest.fixture
def orchestrator(mock_config, mock_db, mock_channel):
    """Create Orchestrator instance."""
    return Orchestrator(mock_config, mock_db, [mock_channel])


class TestOrchestratorStart:
    """Test orchestrator start sequence."""

    @pytest.mark.asyncio
    async def test_start_calls_subsystems(self, orchestrator, mock_db, mock_channel):
        """Test start initializes all subsystems."""
        # Make message loop exit immediately
        orchestrator._running = False

        with patch.object(orchestrator, "_setup_signal_handlers"), patch.object(
            orchestrator, "_message_loop", AsyncMock()
        ):
            await orchestrator.start()

            mock_db.get_router_state.assert_called_once()
            mock_db.get_groups.assert_called_once()
            mock_channel.connect.assert_called_once()
            assert orchestrator._startup_complete is True
            assert orchestrator._health_status["healthy"] is True


class TestOrchestratorStop:
    """Test orchestrator stop sequence."""

    @pytest.mark.asyncio
    async def test_stop_saves_state(self, orchestrator, mock_db):
        """Test stop saves state to database."""
        await orchestrator.stop()

        mock_db.save_router_state.assert_called_once()
        assert orchestrator._running is False
        assert orchestrator._health_status["healthy"] is False

    @pytest.mark.asyncio
    async def test_stop_disconnects_channels(self, orchestrator, mock_channel):
        """Test stop disconnects all channels."""
        await orchestrator.stop()

        mock_channel.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_disconnect_error(self, orchestrator, mock_channel):
        """Test stop handles channel disconnect errors."""
        mock_channel.disconnect = AsyncMock(side_effect=Exception("disconnect error"))

        # Should not raise
        await orchestrator.stop()


class TestConnectChannelsWithRetry:
    """Test channel connection with retry logic."""

    @pytest.mark.asyncio
    async def test_connect_success_first_try(self, orchestrator, mock_channel):
        """Test channel connects on first try."""
        await orchestrator._connect_channels_with_retry()
        mock_channel.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_retry_then_success(self, orchestrator, mock_channel):
        """Test channel retries then succeeds."""
        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("temporary failure")

        mock_channel.connect = AsyncMock(side_effect=fail_then_succeed)

        with patch("nanogridbot.core.orchestrator.asyncio.sleep", AsyncMock()):
            await orchestrator._connect_channels_with_retry()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_connect_all_retries_fail(self, orchestrator, mock_channel):
        """Test channel fails after all retries."""
        mock_channel.connect = AsyncMock(side_effect=Exception("permanent failure"))

        with patch("nanogridbot.core.orchestrator.asyncio.sleep", AsyncMock()):
            await orchestrator._connect_channels_with_retry()

        # 1 initial + 3 retries = 4 calls
        assert mock_channel.connect.call_count == 4


class TestSetupSignalHandlers:
    """Test signal handler setup."""

    def test_setup_signal_handlers(self, orchestrator):
        """Test signal handlers are registered."""
        with patch("nanogridbot.core.orchestrator.signal") as mock_signal:
            orchestrator._setup_signal_handlers()
            assert mock_signal.signal.call_count == 2

    def test_setup_signal_handlers_failure(self, orchestrator):
        """Test signal handler setup failure is handled."""
        with patch(
            "nanogridbot.core.orchestrator.signal.signal", side_effect=ValueError("not main thread")
        ):
            # Should not raise
            orchestrator._setup_signal_handlers()


class TestHealthStatus:
    """Test health status with uptime calculation."""

    def test_health_status_with_uptime(self, orchestrator, mock_channel):
        """Test health status includes uptime."""
        orchestrator._startup_complete = True
        mock_channel._connected = True
        orchestrator._health_status["startup_time"] = time.time() - 60

        status = orchestrator.get_health_status()

        assert status["healthy"] is True
        assert status["uptime_seconds"] >= 59

    def test_health_status_unhealthy_no_channels(self, orchestrator, mock_channel):
        """Test unhealthy when no channels connected."""
        orchestrator._startup_complete = True
        mock_channel._connected = False

        status = orchestrator.get_health_status()
        assert status["healthy"] is False

    def test_health_status_active_containers(self, orchestrator, mock_channel):
        """Test health status reports active containers."""
        orchestrator._startup_complete = True
        mock_channel._connected = True
        orchestrator.queue.active_count = 3

        status = orchestrator.get_health_status()
        assert status["active_containers"] == 3


class TestMessageLoop:
    """Test message polling loop."""

    @pytest.mark.asyncio
    async def test_message_loop_exits_on_not_running(self, orchestrator, mock_db):
        """Test message loop exits when _running is False."""
        orchestrator._running = False
        await orchestrator._message_loop()

    @pytest.mark.asyncio
    async def test_message_loop_exits_on_shutdown(self, orchestrator, mock_db):
        """Test message loop exits on shutdown signal."""
        orchestrator._running = True
        orchestrator._shutdown.request_shutdown()

        await orchestrator._message_loop()

    @pytest.mark.asyncio
    async def test_message_loop_processes_messages(self, orchestrator, mock_db):
        """Test message loop processes new messages."""
        msg = Message(
            id="1",
            chat_jid="jid1",
            sender="user1",
            content="hello",
            timestamp=datetime.now(),
        )

        call_count = 0

        async def get_messages_once(ts):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [msg]
            orchestrator._running = False
            return []

        mock_db.get_new_messages = AsyncMock(side_effect=get_messages_once)
        orchestrator._running = True

        with patch.object(orchestrator, "_process_group_messages", AsyncMock()):
            await orchestrator._message_loop()

            orchestrator._process_group_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_loop_updates_timestamp(self, orchestrator, mock_db):
        """Test message loop updates last_timestamp."""
        ts = datetime(2025, 1, 15, 10, 0, 0)
        msg = Message(
            id="1",
            chat_jid="jid1",
            sender="user1",
            content="hello",
            timestamp=ts,
        )

        call_count = 0

        async def get_messages_once(last_ts):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [msg]
            orchestrator._running = False
            return []

        mock_db.get_new_messages = AsyncMock(side_effect=get_messages_once)
        orchestrator._running = True

        with patch.object(orchestrator, "_process_group_messages", AsyncMock()):
            await orchestrator._message_loop()

        assert orchestrator.last_timestamp == ts.isoformat()

    @pytest.mark.asyncio
    async def test_message_loop_handles_error(self, orchestrator, mock_db):
        """Test message loop continues after error."""
        call_count = 0

        async def error_then_stop(ts):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("db error")
            orchestrator._running = False
            return []

        mock_db.get_new_messages = AsyncMock(side_effect=error_then_stop)
        orchestrator._running = True

        await orchestrator._message_loop()
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_message_loop_handles_cancelled(self, orchestrator, mock_db):
        """Test message loop handles CancelledError."""
        mock_db.get_new_messages = AsyncMock(side_effect=asyncio.CancelledError)
        orchestrator._running = True

        await orchestrator._message_loop()

    @pytest.mark.asyncio
    async def test_message_loop_shutdown_during_processing(self, orchestrator, mock_db):
        """Test message loop checks shutdown between groups."""
        msg1 = Message(
            id="1", chat_jid="jid1", sender="u1", content="a", timestamp=datetime.now()
        )
        msg2 = Message(
            id="2", chat_jid="jid2", sender="u2", content="b", timestamp=datetime.now()
        )

        call_count = 0

        async def get_messages(ts):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [msg1, msg2]
            orchestrator._running = False
            return []

        mock_db.get_new_messages = AsyncMock(side_effect=get_messages)
        orchestrator._running = True

        process_count = 0

        async def process_and_shutdown(jid, msgs):
            nonlocal process_count
            process_count += 1
            if process_count == 1:
                orchestrator._shutdown.request_shutdown()

        with patch.object(
            orchestrator, "_process_group_messages", AsyncMock(side_effect=process_and_shutdown)
        ):
            await orchestrator._message_loop()

        # Only first group should be processed before shutdown detected
        assert process_count == 1


class TestProcessGroupMessages:
    """Test _process_group_messages with various scenarios."""

    @pytest.mark.asyncio
    async def test_process_with_session_and_timestamp(self, orchestrator):
        """Test processing passes session and timestamp."""
        group = RegisteredGroup(
            jid="jid1", name="Test", folder="test", requires_trigger=False
        )
        orchestrator.registered_groups["jid1"] = group
        orchestrator.sessions["jid1"] = "session123"
        orchestrator.last_agent_timestamp["jid1"] = "2025-01-01T00:00:00"

        messages = [
            Message(
                id="1", chat_jid="jid1", sender="u1", content="test", timestamp=datetime.now()
            )
        ]

        with patch.object(orchestrator.queue, "enqueue_message_check", AsyncMock()) as mock_enqueue:
            await orchestrator._process_group_messages("jid1", messages)

            mock_enqueue.assert_called_once_with(
                jid="jid1",
                group=group,
                session_id="session123",
                last_timestamp="2025-01-01T00:00:00",
            )

    @pytest.mark.asyncio
    async def test_process_trigger_any_message_matches(self, orchestrator):
        """Test trigger check passes if any message matches."""
        group = RegisteredGroup(
            jid="jid1", name="Test", folder="test", requires_trigger=True, trigger_pattern=None
        )
        orchestrator.registered_groups["jid1"] = group

        messages = [
            Message(
                id="1", chat_jid="jid1", sender="u1", content="hello", timestamp=datetime.now()
            ),
            Message(
                id="2",
                chat_jid="jid1",
                sender="u2",
                content="@TestBot help",
                timestamp=datetime.now(),
            ),
        ]

        with patch.object(orchestrator.queue, "enqueue_message_check", AsyncMock()) as mock_enqueue:
            await orchestrator._process_group_messages("jid1", messages)
            mock_enqueue.assert_called_once()
