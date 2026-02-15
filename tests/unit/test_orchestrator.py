"""Unit tests for Orchestrator."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.core.orchestrator import Orchestrator
from nanogridbot.database import Database
from nanogridbot.types import Message, RegisteredGroup


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = MagicMock()
    config.poll_interval = 1000
    config.assistant_name = "TestBot"
    config.data_dir = MagicMock()
    return config


@pytest.fixture
def mock_db():
    """Mock database."""
    db = AsyncMock(spec=Database)
    db.get_router_state = AsyncMock(return_value={})
    db.get_groups = AsyncMock(return_value=[])
    db.save_router_state = AsyncMock()
    db.get_new_messages = AsyncMock(return_value=[])
    db.get_registered_groups = AsyncMock(return_value=[])
    db.save_group = AsyncMock()
    db.delete_group = AsyncMock()
    db.get_group_repository = MagicMock(return_value=None)
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
    return channel


@pytest.fixture
def orchestrator(mock_config, mock_db, mock_channel):
    """Create Orchestrator instance."""
    return Orchestrator(mock_config, mock_db, [mock_channel])


class TestOrchestratorInit:
    """Test Orchestrator initialization."""

    def test_init(self, orchestrator, mock_config, mock_db, mock_channel):
        """Test orchestrator initialization."""
        assert orchestrator.config == mock_config
        assert orchestrator.db == mock_db
        assert len(orchestrator.channels) == 1
        assert orchestrator.channels[0] == mock_channel
        assert orchestrator._running is False
        assert orchestrator._startup_complete is False
        assert orchestrator._health_status["healthy"] is False


class TestHealthStatus:
    """Test health status reporting."""

    def test_get_health_status_initial(self, orchestrator, mock_channel):
        """Test initial health status."""
        mock_channel._connected = False
        status = orchestrator.get_health_status()

        assert status["healthy"] is False
        assert status["channels_connected"] == 0
        assert status["channels_total"] == 1
        assert status["registered_groups"] == 0

    def test_get_health_status_after_startup(self, orchestrator, mock_channel):
        """Test health status after startup."""
        orchestrator._startup_complete = True
        mock_channel._connected = True

        status = orchestrator.get_health_status()

        assert status["healthy"] is True
        assert status["channels_connected"] == 1


class TestStateManagement:
    """Test state loading and saving."""

    @pytest.mark.asyncio
    async def test_load_state_empty(self, orchestrator, mock_db):
        """Test loading empty state."""
        await orchestrator._load_state()

        assert orchestrator.last_timestamp is None
        assert orchestrator.sessions == {}
        assert orchestrator.last_agent_timestamp == {}
        assert orchestrator.registered_groups == {}

    @pytest.mark.asyncio
    async def test_load_state_with_data(self, orchestrator, mock_db):
        """Test loading state with data."""
        mock_db.get_router_state = AsyncMock(
            return_value={
                "last_timestamp": "2024-01-01T00:00:00",
                "sessions": {"jid1": "session1"},
                "last_agent_timestamp": {"jid1": "2024-01-01T00:00:00"},
            }
        )

        group = RegisteredGroup(
            jid="jid1",
            name="Test Group",
            folder="test_folder",
            requires_trigger=False,
        )
        mock_db.get_groups = AsyncMock(return_value=[group])

        await orchestrator._load_state()

        assert orchestrator.last_timestamp == "2024-01-01T00:00:00"
        assert orchestrator.sessions == {"jid1": "session1"}
        assert orchestrator.last_agent_timestamp == {"jid1": "2024-01-01T00:00:00"}
        assert len(orchestrator.registered_groups) == 1
        assert orchestrator.registered_groups["jid1"] == group

    @pytest.mark.asyncio
    async def test_save_state(self, orchestrator, mock_db):
        """Test saving state."""
        orchestrator.last_timestamp = "2024-01-01T00:00:00"
        orchestrator.sessions = {"jid1": "session1"}
        orchestrator.last_agent_timestamp = {"jid1": "2024-01-01T00:00:00"}

        await orchestrator._save_state()

        mock_db.save_router_state.assert_called_once_with(
            {
                "last_timestamp": "2024-01-01T00:00:00",
                "sessions": {"jid1": "session1"},
                "last_agent_timestamp": {"jid1": "2024-01-01T00:00:00"},
            }
        )


class TestChannelManagement:
    """Test channel connection management."""

    @pytest.mark.asyncio
    async def test_connect_channels(self, orchestrator, mock_channel):
        """Test connecting channels."""
        await orchestrator._connect_channels()

        mock_channel.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_channels_with_error(self, orchestrator, mock_channel):
        """Test connecting channels with error."""
        mock_channel.connect = AsyncMock(side_effect=Exception("Connection failed"))

        await orchestrator._connect_channels()

        mock_channel.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_channels(self, orchestrator, mock_channel):
        """Test disconnecting channels."""
        await orchestrator._disconnect_channels()

        mock_channel.disconnect.assert_called_once()


class TestMessageGrouping:
    """Test message grouping logic."""

    def test_group_messages_empty(self, orchestrator):
        """Test grouping empty message list."""
        result = orchestrator._group_messages([])
        assert result == {}

    def test_group_messages_single_chat(self, orchestrator):
        """Test grouping messages from single chat."""
        from datetime import datetime

        messages = [
            Message(
                id="1",
                chat_jid="jid1",
                sender="user1",
                content="msg1",
                timestamp=datetime.now(),
            ),
            Message(
                id="2",
                chat_jid="jid1",
                sender="user2",
                content="msg2",
                timestamp=datetime.now(),
            ),
        ]

        result = orchestrator._group_messages(messages)

        assert len(result) == 1
        assert "jid1" in result
        assert len(result["jid1"]) == 2

    def test_group_messages_multiple_chats(self, orchestrator):
        """Test grouping messages from multiple chats."""
        from datetime import datetime

        messages = [
            Message(
                id="1",
                chat_jid="jid1",
                sender="user1",
                content="msg1",
                timestamp=datetime.now(),
            ),
            Message(
                id="2",
                chat_jid="jid2",
                sender="user2",
                content="msg2",
                timestamp=datetime.now(),
            ),
            Message(
                id="3",
                chat_jid="jid1",
                sender="user3",
                content="msg3",
                timestamp=datetime.now(),
            ),
        ]

        result = orchestrator._group_messages(messages)

        assert len(result) == 2
        assert len(result["jid1"]) == 2
        assert len(result["jid2"]) == 1


class TestTriggerChecking:
    """Test trigger pattern checking."""

    def test_check_trigger_default_pattern(self, orchestrator):
        """Test trigger with default pattern."""
        result = orchestrator._check_trigger("@TestBot hello", None)
        assert result is True

    def test_check_trigger_default_pattern_no_match(self, orchestrator):
        """Test trigger with default pattern no match."""
        result = orchestrator._check_trigger("hello world", None)
        assert result is False

    def test_check_trigger_custom_pattern(self, orchestrator):
        """Test trigger with custom pattern."""
        result = orchestrator._check_trigger("!help", r"^!")
        assert result is True

    def test_check_trigger_custom_pattern_no_match(self, orchestrator):
        """Test trigger with custom pattern no match."""
        result = orchestrator._check_trigger("hello", r"^!")
        assert result is False

    def test_check_trigger_case_insensitive(self, orchestrator):
        """Test trigger is case insensitive."""
        result = orchestrator._check_trigger("@testbot hello", None)
        assert result is True


class TestGroupRegistration:
    """Test group registration."""

    @pytest.mark.asyncio
    async def test_register_group(self, orchestrator, mock_db):
        """Test registering a group."""
        group = RegisteredGroup(
            jid="jid1",
            name="Test Group",
            folder="test_folder",
            requires_trigger=False,
        )

        await orchestrator.register_group(group)

        mock_db.save_group.assert_called_once_with(group)
        assert orchestrator.registered_groups["jid1"] == group

    @pytest.mark.asyncio
    async def test_unregister_group(self, orchestrator, mock_db):
        """Test unregistering a group."""
        group = RegisteredGroup(
            jid="jid1",
            name="Test Group",
            folder="test_folder",
            requires_trigger=False,
        )
        orchestrator.registered_groups["jid1"] = group

        await orchestrator.unregister_group("jid1")

        mock_db.delete_group.assert_called_once_with("jid1")
        assert "jid1" not in orchestrator.registered_groups


class TestMessageProcessing:
    """Test message processing."""

    @pytest.mark.asyncio
    async def test_process_group_messages_not_registered(self, orchestrator):
        """Test processing messages for unregistered group."""
        from datetime import datetime

        messages = [
            Message(
                id="1",
                chat_jid="jid1",
                sender="user1",
                content="test",
                timestamp=datetime.now(),
            )
        ]

        await orchestrator._process_group_messages("jid1", messages)

        # Should not enqueue anything

    @pytest.mark.asyncio
    async def test_process_group_messages_no_trigger_required(self, orchestrator):
        """Test processing messages when no trigger required."""
        from datetime import datetime

        group = RegisteredGroup(
            jid="jid1",
            name="Test Group",
            folder="test_folder",
            requires_trigger=False,
        )
        orchestrator.registered_groups["jid1"] = group

        messages = [
            Message(
                id="1",
                chat_jid="jid1",
                sender="user1",
                content="test",
                timestamp=datetime.now(),
            )
        ]

        with patch.object(orchestrator.queue, "enqueue_message_check", AsyncMock()):
            await orchestrator._process_group_messages("jid1", messages)

            orchestrator.queue.enqueue_message_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_group_messages_trigger_required_matched(self, orchestrator):
        """Test processing messages with trigger required and matched."""
        from datetime import datetime

        group = RegisteredGroup(
            jid="jid1",
            name="Test Group",
            folder="test_folder",
            requires_trigger=True,
            trigger_pattern=None,
        )
        orchestrator.registered_groups["jid1"] = group

        messages = [
            Message(
                id="1",
                chat_jid="jid1",
                sender="user1",
                content="@TestBot hello",
                timestamp=datetime.now(),
            )
        ]

        with patch.object(orchestrator.queue, "enqueue_message_check", AsyncMock()):
            await orchestrator._process_group_messages("jid1", messages)

            orchestrator.queue.enqueue_message_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_group_messages_trigger_required_not_matched(self, orchestrator):
        """Test processing messages with trigger required but not matched."""
        from datetime import datetime

        group = RegisteredGroup(
            jid="jid1",
            name="Test Group",
            folder="test_folder",
            requires_trigger=True,
            trigger_pattern=None,
        )
        orchestrator.registered_groups["jid1"] = group

        messages = [
            Message(
                id="1",
                chat_jid="jid1",
                sender="user1",
                content="hello world",
                timestamp=datetime.now(),
            )
        ]

        with patch.object(orchestrator.queue, "enqueue_message_check", AsyncMock()):
            await orchestrator._process_group_messages("jid1", messages)

            orchestrator.queue.enqueue_message_check.assert_not_called()


class TestSendToGroup:
    """Test sending messages to groups."""

    @pytest.mark.asyncio
    async def test_send_to_group(self, orchestrator):
        """Test sending message to group."""
        with patch.object(orchestrator.router, "send_response", AsyncMock()):
            await orchestrator.send_to_group("jid1", "test message")

            orchestrator.router.send_response.assert_called_once_with("jid1", "test message")
