"""Unit tests for MessageRouter."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.core.router import MessageRouter
from nanogridbot.types import Message, RegisteredGroup


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = MagicMock()
    config.assistant_name = "TestBot"
    return config


@pytest.fixture
def mock_db():
    """Mock database."""
    db = AsyncMock()
    db.store_message = AsyncMock()
    db.get_group_repository = MagicMock()
    return db


@pytest.fixture
def mock_channel():
    """Mock channel."""
    channel = AsyncMock()
    channel.name = "test_channel"
    channel.owns_jid = MagicMock(return_value=True)
    channel.send_message = AsyncMock()
    return channel


@pytest.fixture
def router(mock_config, mock_db, mock_channel):
    """Create MessageRouter instance."""
    return MessageRouter(mock_config, mock_db, [mock_channel])


class TestRouterLifecycle:
    """Test router start/stop."""

    @pytest.mark.asyncio
    async def test_start(self, router):
        """Test router starts and sets running flag."""
        await router.start()
        assert router._running is True

    @pytest.mark.asyncio
    async def test_stop(self, router):
        """Test router stops and clears running flag."""
        await router.start()
        await router.stop()
        assert router._running is False

    def test_init(self, router, mock_config, mock_db, mock_channel):
        """Test router initialization."""
        assert router.config == mock_config
        assert router.db == mock_db
        assert router.channels == [mock_channel]
        assert router._running is False


class TestTriggerChecking:
    """Test _check_trigger method."""

    def test_default_pattern_match(self, router):
        """Test default trigger pattern matches @BotName."""
        assert router._check_trigger("@TestBot hello", None) is True

    def test_default_pattern_no_match(self, router):
        """Test default trigger pattern doesn't match random text."""
        assert router._check_trigger("hello world", None) is False

    def test_default_pattern_case_insensitive(self, router):
        """Test default trigger is case insensitive."""
        assert router._check_trigger("@testbot hello", None) is True
        assert router._check_trigger("@TESTBOT hello", None) is True

    def test_custom_pattern_match(self, router):
        """Test custom trigger pattern."""
        assert router._check_trigger("!help me", r"^!") is True

    def test_custom_pattern_no_match(self, router):
        """Test custom trigger pattern no match."""
        assert router._check_trigger("hello", r"^!") is False

    def test_default_pattern_requires_word_boundary(self, router):
        """Test default pattern uses word boundary."""
        assert router._check_trigger("@TestBotExtra hello", None) is False

    def test_default_pattern_at_start(self, router):
        """Test default pattern requires @ at start."""
        assert router._check_trigger("hey @TestBot", None) is False


class TestRouteMessage:
    """Test route_message method."""

    @pytest.mark.asyncio
    async def test_route_stores_message(self, router, mock_db):
        """Test that route_message stores the message in DB."""
        group_repo = AsyncMock()
        group_repo.get_group_by_jid = AsyncMock(return_value=None)
        mock_db.get_group_repository.return_value = group_repo

        msg = Message(
            id="1",
            chat_jid="jid1",
            sender="user1",
            content="hello",
            timestamp=datetime.now(),
        )

        await router.route_message(msg)
        mock_db.store_message.assert_called_once_with(msg)

    @pytest.mark.asyncio
    async def test_route_unregistered_group_skips(self, router, mock_db):
        """Test that unregistered group messages are skipped."""
        group_repo = AsyncMock()
        group_repo.get_group_by_jid = AsyncMock(return_value=None)
        mock_db.get_group_repository.return_value = group_repo

        msg = Message(
            id="1",
            chat_jid="unknown_jid",
            sender="user1",
            content="hello",
            timestamp=datetime.now(),
        )

        await router.route_message(msg)
        # Should not raise, just skip

    @pytest.mark.asyncio
    async def test_route_registered_group_no_trigger(self, router, mock_db):
        """Test routing to registered group without trigger requirement."""
        group = MagicMock()
        group.requires_trigger = False

        group_repo = AsyncMock()
        group_repo.get_group_by_jid = AsyncMock(return_value=group)
        mock_db.get_group_repository.return_value = group_repo

        msg = Message(
            id="1",
            chat_jid="jid1",
            sender="user1",
            content="hello",
            timestamp=datetime.now(),
        )

        await router.route_message(msg)
        mock_db.store_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_registered_group_trigger_matched(self, router, mock_db):
        """Test routing when trigger pattern matches."""
        group = MagicMock()
        group.requires_trigger = True
        group.trigger_pattern = None  # Uses default @TestBot

        group_repo = AsyncMock()
        group_repo.get_group_by_jid = AsyncMock(return_value=group)
        mock_db.get_group_repository.return_value = group_repo

        msg = Message(
            id="1",
            chat_jid="jid1",
            sender="user1",
            content="@TestBot help",
            timestamp=datetime.now(),
        )

        await router.route_message(msg)
        mock_db.store_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_route_registered_group_trigger_not_matched(self, router, mock_db):
        """Test routing when trigger pattern doesn't match."""
        group = MagicMock()
        group.requires_trigger = True
        group.trigger_pattern = None

        group_repo = AsyncMock()
        group_repo.get_group_by_jid = AsyncMock(return_value=group)
        mock_db.get_group_repository.return_value = group_repo

        msg = Message(
            id="1",
            chat_jid="jid1",
            sender="user1",
            content="just chatting",
            timestamp=datetime.now(),
        )

        await router.route_message(msg)
        mock_db.store_message.assert_called_once()


class TestSendResponse:
    """Test send_response method."""

    @pytest.mark.asyncio
    async def test_send_to_matching_channel(self, router, mock_channel):
        """Test sending response via matching channel."""
        await router.send_response("jid1", "hello")

        mock_channel.owns_jid.assert_called_once_with("jid1")
        mock_channel.send_message.assert_called_once_with("jid1", "hello")

    @pytest.mark.asyncio
    async def test_send_no_matching_channel(self, router):
        """Test sending when no channel owns the JID."""
        router.channels = []

        # Should not raise
        await router.send_response("unknown_jid", "hello")

    @pytest.mark.asyncio
    async def test_send_channel_not_owning_jid(self, router, mock_channel):
        """Test sending when channel doesn't own the JID."""
        mock_channel.owns_jid.return_value = False

        await router.send_response("other_jid", "hello")
        mock_channel.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_channel_error(self, router, mock_channel):
        """Test sending when channel raises an error."""
        mock_channel.send_message = AsyncMock(side_effect=Exception("Send failed"))

        # Should not raise, just log error
        await router.send_response("jid1", "hello")
        mock_channel.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_multiple_channels_first_match(self, router, mock_channel):
        """Test that only the first matching channel sends."""
        channel2 = AsyncMock()
        channel2.name = "channel2"
        channel2.owns_jid = MagicMock(return_value=True)
        channel2.send_message = AsyncMock()

        router.channels = [mock_channel, channel2]

        await router.send_response("jid1", "hello")

        mock_channel.send_message.assert_called_once()
        channel2.send_message.assert_not_called()


class TestBroadcastToGroups:
    """Test broadcast_to_groups method."""

    @pytest.mark.asyncio
    async def test_broadcast_all_groups(self, router, mock_db, mock_channel):
        """Test broadcasting to all groups."""
        group1 = MagicMock()
        group1.jid = "jid1"
        group2 = MagicMock()
        group2.jid = "jid2"

        group_repo = AsyncMock()
        group_repo.get_groups = AsyncMock(return_value=[group1, group2])
        mock_db.get_group_repository.return_value = group_repo

        await router.broadcast_to_groups("announcement")

        assert mock_channel.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_broadcast_specific_folders(self, router, mock_db, mock_channel):
        """Test broadcasting to specific group folders."""
        group1 = MagicMock()
        group1.jid = "jid1"

        group_repo = AsyncMock()
        group_repo.get_group_by_folder = AsyncMock(return_value=group1)
        mock_db.get_group_repository.return_value = group_repo

        await router.broadcast_to_groups("announcement", group_folders=["folder1"])

        mock_channel.send_message.assert_called_once_with("jid1", "announcement")

    @pytest.mark.asyncio
    async def test_broadcast_folder_not_found(self, router, mock_db, mock_channel):
        """Test broadcasting when folder not found."""
        group_repo = AsyncMock()
        group_repo.get_group_by_folder = AsyncMock(return_value=None)
        mock_db.get_group_repository.return_value = group_repo

        await router.broadcast_to_groups("announcement", group_folders=["nonexistent"])

        mock_channel.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_empty_groups(self, router, mock_db, mock_channel):
        """Test broadcasting when no groups exist."""
        group_repo = AsyncMock()
        group_repo.get_groups = AsyncMock(return_value=[])
        mock_db.get_group_repository.return_value = group_repo

        await router.broadcast_to_groups("announcement")

        mock_channel.send_message.assert_not_called()


class TestGetRegisteredGroup:
    """Test _get_registered_group method."""

    @pytest.mark.asyncio
    async def test_get_existing_group(self, router, mock_db):
        """Test getting an existing registered group."""
        group = MagicMock()
        group_repo = AsyncMock()
        group_repo.get_group_by_jid = AsyncMock(return_value=group)
        mock_db.get_group_repository.return_value = group_repo

        result = await router._get_registered_group("jid1")
        assert result == group

    @pytest.mark.asyncio
    async def test_get_nonexistent_group(self, router, mock_db):
        """Test getting a non-existent group."""
        group_repo = AsyncMock()
        group_repo.get_group_by_jid = AsyncMock(return_value=None)
        mock_db.get_group_repository.return_value = group_repo

        result = await router._get_registered_group("unknown")
        assert result is None
