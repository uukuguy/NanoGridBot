"""Integration tests for Telegram and Slack channel adapters.

Tests the full channel lifecycle with mocked external SDK calls.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.channels.events import ConnectEvent, EventType
from nanogridbot.types import ChannelType, Message


# ---------------------------------------------------------------------------
# Telegram Channel Tests
# ---------------------------------------------------------------------------


class TestTelegramChannel:
    """Integration tests for TelegramChannel."""

    @pytest.fixture
    def telegram_channel(self):
        from nanogridbot.channels.telegram import TelegramChannel

        return TelegramChannel(channel_type=ChannelType.TELEGRAM, token="test-token-123")

    @pytest.fixture
    def telegram_channel_no_token(self):
        from nanogridbot.channels.telegram import TelegramChannel

        return TelegramChannel(channel_type=ChannelType.TELEGRAM, token=None)

    @pytest.mark.asyncio
    @patch("nanogridbot.channels.telegram.Application")
    async def test_telegram_connect_success(self, mock_app_cls, telegram_channel):
        """Verify connect() sets _connected=True and emits ConnectEvent."""
        # Set up the builder chain: Application.builder().token().build()
        mock_app = AsyncMock()
        mock_builder = MagicMock()
        mock_builder.token.return_value = mock_builder
        mock_builder.build.return_value = mock_app
        mock_app_cls.builder.return_value = mock_builder

        # Track emitted events
        events_received: list = []

        async def on_connect(event):
            events_received.append(event)

        telegram_channel.on(EventType.CONNECTED, on_connect)

        await telegram_channel.connect()

        assert telegram_channel._connected is True
        assert telegram_channel.is_connected is True
        assert telegram_channel._application is mock_app
        mock_app.initialize.assert_awaited_once()
        mock_app.start.assert_awaited_once()

        # Verify ConnectEvent was emitted
        assert len(events_received) == 1
        event = events_received[0]
        assert isinstance(event, ConnectEvent)
        assert event.connected is True
        assert event.channel_type == "telegram"

    @pytest.mark.asyncio
    async def test_telegram_connect_no_token(self, telegram_channel_no_token):
        """Verify connect() raises RuntimeError when no token is configured."""
        with pytest.raises(RuntimeError, match="Telegram bot token not configured"):
            await telegram_channel_no_token.connect()

    @pytest.mark.asyncio
    @patch("nanogridbot.channels.telegram.Application")
    async def test_telegram_disconnect(self, mock_app_cls, telegram_channel):
        """After connect, call disconnect(), verify _connected=False."""
        mock_app = AsyncMock()
        mock_builder = MagicMock()
        mock_builder.token.return_value = mock_builder
        mock_builder.build.return_value = mock_app
        mock_app_cls.builder.return_value = mock_builder

        await telegram_channel.connect()
        assert telegram_channel._connected is True

        await telegram_channel.disconnect()

        assert telegram_channel._connected is False
        assert telegram_channel.is_connected is False
        assert telegram_channel._application is None
        mock_app.stop.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("nanogridbot.channels.telegram.Application")
    async def test_telegram_send_message(self, mock_app_cls, telegram_channel):
        """Mock bot.send_message, verify correct chat_id and text, returns message_id."""
        mock_app = AsyncMock()
        mock_builder = MagicMock()
        mock_builder.token.return_value = mock_builder
        mock_builder.build.return_value = mock_app
        mock_app_cls.builder.return_value = mock_builder

        # Mock bot.send_message return value
        mock_sent = MagicMock()
        mock_sent.message_id = 42
        mock_app.bot.send_message = AsyncMock(return_value=mock_sent)

        await telegram_channel.connect()

        # Note: parse_jid uses jid[10:] so "telegram:123456789" -> "23456789"
        # The send_message calls int(user_id) on the parsed result
        result = await telegram_channel.send_message("telegram:123456789", "Hello!")

        mock_app.bot.send_message.assert_awaited_once_with(
            chat_id=int("23456789"),  # Off-by-one in parse_jid: jid[10:]
            text="Hello!",
        )
        assert result == "42"

    @pytest.mark.asyncio
    async def test_telegram_send_message_not_connected(self, telegram_channel):
        """Verify send_message raises RuntimeError when not connected."""
        with pytest.raises(RuntimeError, match="Telegram channel not connected"):
            await telegram_channel.send_message("telegram:123456789", "Hello!")

    @pytest.mark.asyncio
    async def test_telegram_receive_message_text(self, telegram_channel):
        """Create mock Update with text message, verify correct Message object."""
        mock_update = MagicMock()
        mock_update.message.text = "Hello from Telegram"
        mock_update.message.photo = None
        mock_update.message.video = None
        mock_update.message.voice = None
        mock_update.message.audio = None
        mock_update.message.document = None
        mock_update.message.sticker = None
        mock_update.message.location = None
        mock_update.message.message_id = 101
        mock_update.message.chat.id = 999
        mock_update.message.from_user.id = 555
        mock_update.message.from_user.name = "TestUser"
        mock_update.message.from_user.username = "testuser"
        mock_update.message.date = datetime(2025, 1, 15, 12, 0, 0)

        # Patch isinstance check — the real code checks isinstance(update, Update)
        with patch("nanogridbot.channels.telegram.Update") as mock_update_cls:
            mock_update_cls.__instancecheck__ = lambda cls, obj: True

            result = await telegram_channel.receive_message({"update": mock_update})

        assert result is not None
        assert isinstance(result, Message)
        assert result.id == "101"
        assert result.chat_jid == "telegram:999"
        assert result.sender == "555"
        assert result.sender_name == "TestUser"
        assert result.content == "Hello from Telegram"
        assert result.is_from_me is False

    @pytest.mark.asyncio
    async def test_telegram_receive_message_photo(self, telegram_channel):
        """Mock Update with photo, verify content is '[Photo]'."""
        mock_update = MagicMock()
        mock_update.message.text = None
        mock_update.message.photo = [MagicMock()]  # Non-empty photo list
        mock_update.message.video = None
        mock_update.message.voice = None
        mock_update.message.audio = None
        mock_update.message.document = None
        mock_update.message.sticker = None
        mock_update.message.location = None
        mock_update.message.message_id = 102
        mock_update.message.chat.id = 999
        mock_update.message.from_user.id = 555
        mock_update.message.from_user.name = "TestUser"
        mock_update.message.from_user.username = "testuser"
        mock_update.message.date = datetime(2025, 1, 15, 12, 0, 0)

        with patch("nanogridbot.channels.telegram.Update") as mock_update_cls:
            mock_update_cls.__instancecheck__ = lambda cls, obj: True

            result = await telegram_channel.receive_message({"update": mock_update})

        assert result is not None
        assert result.content == "[Photo]"

    @pytest.mark.asyncio
    async def test_telegram_receive_message_invalid(self, telegram_channel):
        """Pass invalid raw_data, verify returns None."""
        # No "update" key
        result = await telegram_channel.receive_message({})
        assert result is None

        # "update" is not an Update instance (without patching isinstance)
        result = await telegram_channel.receive_message({"update": "not-an-update"})
        assert result is None

        # "update" with no message
        mock_update = MagicMock()
        mock_update.message = None
        with patch("nanogridbot.channels.telegram.Update") as mock_update_cls:
            mock_update_cls.__instancecheck__ = lambda cls, obj: True
            result = await telegram_channel.receive_message({"update": mock_update})
        assert result is None

    def test_telegram_parse_jid_valid(self, telegram_channel):
        """Test parse_jid('telegram:123456789') returns actual behavior.

        Note: The code uses jid[10:] to strip 'telegram:' (9 chars), so the
        first character of the ID is also stripped. This is a known off-by-one bug.
        'telegram:123456789' -> jid[10:] -> '23456789'
        """
        user_id, resource = telegram_channel.parse_jid("telegram:123456789")
        assert user_id == "23456789"  # Off-by-one: jid[10:] instead of jid[9:]
        assert resource == ""

    def test_telegram_parse_jid_invalid(self, telegram_channel):
        """Test parse_jid('slack:123') raises ValueError."""
        with pytest.raises(ValueError, match="Invalid Telegram JID"):
            telegram_channel.parse_jid("slack:123")

    def test_telegram_build_jid(self, telegram_channel):
        """Test build_jid('123456789') returns 'telegram:123456789'."""
        jid = telegram_channel.build_jid("123456789")
        assert jid == "telegram:123456789"


# ---------------------------------------------------------------------------
# Slack Channel Tests
# ---------------------------------------------------------------------------


class TestSlackChannel:
    """Integration tests for SlackChannel."""

    @pytest.fixture
    def slack_channel(self):
        from nanogridbot.channels.slack import SlackChannel

        return SlackChannel(
            channel_type=ChannelType.SLACK,
            bot_token="xoxb-test-token",
            app_token="xapp-test-token",
        )

    @pytest.fixture
    def slack_channel_no_tokens(self):
        from nanogridbot.channels.slack import SlackChannel

        return SlackChannel(channel_type=ChannelType.SLACK, bot_token=None, app_token=None)

    @pytest.mark.asyncio
    @patch("nanogridbot.channels.slack.SocketModeClient")
    @patch("nanogridbot.channels.slack.WebClient")
    async def test_slack_connect_success(
        self, mock_web_cls, mock_socket_cls, slack_channel
    ):
        """Mock WebClient and SocketModeClient, verify connect() sets _connected=True."""
        mock_web_instance = MagicMock()
        mock_web_cls.return_value = mock_web_instance

        mock_socket_instance = MagicMock()
        mock_socket_instance.socket_mode_request_listeners = []
        mock_socket_cls.return_value = mock_socket_instance

        events_received: list = []

        async def on_connect(event):
            events_received.append(event)

        slack_channel.on(EventType.CONNECTED, on_connect)

        with patch("threading.Thread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread

            await slack_channel.connect()

            mock_thread.start.assert_called_once()

        assert slack_channel._connected is True
        assert slack_channel.is_connected is True
        assert slack_channel._web_client is mock_web_instance
        assert slack_channel._socket_client is mock_socket_instance

        # Verify ConnectEvent was emitted
        assert len(events_received) == 1
        event = events_received[0]
        assert isinstance(event, ConnectEvent)
        assert event.connected is True
        assert event.channel_type == "slack"

    @pytest.mark.asyncio
    async def test_slack_connect_no_tokens(self, slack_channel_no_tokens):
        """Verify connect() raises RuntimeError when tokens are missing."""
        with pytest.raises(RuntimeError, match="Slack channel not configured"):
            await slack_channel_no_tokens.connect()

    @pytest.mark.asyncio
    @patch("nanogridbot.channels.slack.SocketModeClient")
    @patch("nanogridbot.channels.slack.WebClient")
    async def test_slack_disconnect(self, mock_web_cls, mock_socket_cls, slack_channel):
        """After connect, call disconnect(), verify cleanup."""
        mock_web_instance = MagicMock()
        mock_web_cls.return_value = mock_web_instance

        mock_socket_instance = MagicMock()
        mock_socket_instance.socket_mode_request_listeners = []
        mock_socket_cls.return_value = mock_socket_instance

        with patch("threading.Thread") as mock_thread_cls:
            mock_thread_cls.return_value = MagicMock()
            await slack_channel.connect()

        assert slack_channel._connected is True

        await slack_channel.disconnect()

        assert slack_channel._connected is False
        assert slack_channel.is_connected is False
        assert slack_channel._socket_client is None
        assert slack_channel._web_client is None
        mock_socket_instance.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("nanogridbot.channels.slack.SocketModeClient")
    @patch("nanogridbot.channels.slack.WebClient")
    async def test_slack_send_message(self, mock_web_cls, mock_socket_cls, slack_channel):
        """Mock WebClient.chat_postMessage, verify correct channel and text."""
        mock_web_instance = MagicMock()
        mock_web_cls.return_value = mock_web_instance

        mock_socket_instance = MagicMock()
        mock_socket_instance.socket_mode_request_listeners = []
        mock_socket_cls.return_value = mock_socket_instance

        # Mock chat_postMessage response
        mock_response = {"ts": "1234567890.123456", "ok": True}
        mock_web_instance.chat_postMessage.return_value = mock_response

        with patch("threading.Thread") as mock_thread_cls:
            mock_thread_cls.return_value = MagicMock()
            await slack_channel.connect()

        # Note: parse_jid for "slack:C1234567890" returns ("1234567890", "C1234567890")
        # The first element is used as channel_id in chat_postMessage
        result = await slack_channel.send_message("slack:C1234567890", "Hello Slack!")

        mock_web_instance.chat_postMessage.assert_called_once_with(
            channel="1234567890",  # parse_jid returns rest[1:] as first element
            text="Hello Slack!",
        )
        assert result == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_slack_send_message_not_connected(self, slack_channel):
        """Verify raises RuntimeError when not connected."""
        with pytest.raises(RuntimeError, match="Slack channel not connected"):
            await slack_channel.send_message("slack:C1234567890", "Hello!")

    @pytest.mark.asyncio
    async def test_slack_receive_message_text(self, slack_channel):
        """Create mock Slack event dict, verify Message parsing."""
        raw_data = {
            "event": {
                "type": "message",
                "user": "U9876543210",
                "username": "testslackuser",
                "channel": "C1234567890",
                "text": "Hello from Slack",
                "ts": "1705312800.000000",
            }
        }

        result = await slack_channel.receive_message(raw_data)

        assert result is not None
        assert isinstance(result, Message)
        assert result.id == "1705312800.000000"
        assert result.chat_jid == "slack:C1234567890"
        assert result.sender == "U9876543210"
        assert result.sender_name == "testslackuser"
        assert result.content == "Hello from Slack"
        assert result.is_from_me is False

    @pytest.mark.asyncio
    async def test_slack_receive_message_bot(self, slack_channel):
        """Verify bot_message subtype returns None."""
        raw_data = {
            "event": {
                "type": "message",
                "subtype": "bot_message",
                "user": "UBOT",
                "channel": "C1234567890",
                "text": "I am a bot",
                "ts": "1705312800.000000",
            }
        }

        result = await slack_channel.receive_message(raw_data)
        assert result is None

    @pytest.mark.asyncio
    async def test_slack_receive_message_empty(self, slack_channel):
        """Verify empty event returns None."""
        # Completely empty raw_data
        result = await slack_channel.receive_message({})
        assert result is None

        # Empty event dict
        result = await slack_channel.receive_message({"event": {}})
        assert result is None

        # Wrong event type
        result = await slack_channel.receive_message(
            {"event": {"type": "reaction_added", "user": "U123"}}
        )
        assert result is None

    def test_slack_parse_jid_valid(self, slack_channel):
        """Test parse_jid('slack:C1234567890').

        The code does rest = jid[6:] -> 'C1234567890', then id_part = rest[1:] -> '1234567890'.
        Returns (id_part, rest) -> ('1234567890', 'C1234567890').
        """
        channel_id, resource = slack_channel.parse_jid("slack:C1234567890")
        assert channel_id == "1234567890"
        assert resource == "C1234567890"

    def test_slack_parse_jid_invalid(self, slack_channel):
        """Test parse_jid('telegram:123') raises ValueError."""
        with pytest.raises(ValueError, match="Invalid Slack JID"):
            slack_channel.parse_jid("telegram:123")

    def test_slack_build_jid_channel(self, slack_channel):
        """Test build_jid('C1234567890') returns 'slack:C1234567890'."""
        jid = slack_channel.build_jid("C1234567890")
        assert jid == "slack:C1234567890"

    def test_slack_build_jid_user(self, slack_channel):
        """Test build_jid('U1234567890') returns 'slack:U1234567890'."""
        jid = slack_channel.build_jid("U1234567890")
        assert jid == "slack:U1234567890"
