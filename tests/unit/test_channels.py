"""Unit tests for channel abstraction."""

from datetime import datetime

import pytest

from nanogridbot.channels import (
    Channel,
    ChannelFactory,
    ChannelRegistry,
    ConnectEvent,
    ErrorEvent,
    Event,
    EventEmitter,
    EventType,
    MessageEvent,
)
from nanogridbot.types import ChannelType, Message


class DummyChannel(Channel):
    """Dummy channel implementation for testing."""

    async def connect(self) -> None:
        await self._on_connected()

    async def disconnect(self) -> None:
        await self._on_disconnected()

    async def send_message(self, chat_jid: str, content: str) -> str:
        return f"msg_{chat_jid}_{content[:10]}"

    async def receive_message(self, raw_data: dict) -> Message:
        return Message(
            id=raw_data.get("id", "unknown"),
            chat_jid=raw_data.get("chat_jid", ""),
            sender=raw_data.get("sender", ""),
            sender_name=raw_data.get("sender_name", ""),
            content=raw_data.get("content", ""),
            timestamp=datetime.now(),
        )

    def parse_jid(self, jid: str) -> tuple[str, str]:
        parts = jid.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid JID format: {jid}")
        return parts[0], parts[1]

    def build_jid(self, platform_id: str, resource: str | None = None) -> str:
        if resource:
            return f"{self._channel_type.value}:{platform_id}:{resource}"
        return f"{self._channel_type.value}:{platform_id}"


class TestEventEmitter:
    """Tests for EventEmitter."""

    @pytest.mark.asyncio
    async def test_on_and_emit(self) -> None:
        emitter = EventEmitter()
        received_events: list[Event] = []

        async def handler(event: Event) -> None:
            received_events.append(event)

        emitter.on(EventType.MESSAGE_RECEIVED, handler)

        event = MessageEvent(
            message_id="123",
            chat_jid="test:channel",
            sender="user1",
            sender_name="Test User",
            content="Hello",
        )
        await emitter.emit(event)

        assert len(received_events) == 1
        assert received_events[0].message_id == "123"

    @pytest.mark.asyncio
    async def test_off(self) -> None:
        emitter = EventEmitter()
        received_events: list[Event] = []

        async def handler(event: Event) -> None:
            received_events.append(event)

        emitter.on(EventType.MESSAGE_RECEIVED, handler)
        emitter.off(EventType.MESSAGE_RECEIVED, handler)

        event = MessageEvent(
            message_id="123",
            chat_jid="test:channel",
            sender="user1",
            sender_name="Test User",
            content="Hello",
        )
        await emitter.emit(event)

        assert len(received_events) == 0

    @pytest.mark.asyncio
    async def test_multiple_handlers(self) -> None:
        emitter = EventEmitter()
        call_count = 0

        async def handler1(event: Event) -> None:
            nonlocal call_count
            call_count += 1

        async def handler2(event: Event) -> None:
            nonlocal call_count
            call_count += 1

        emitter.on(EventType.MESSAGE_RECEIVED, handler1)
        emitter.on(EventType.MESSAGE_RECEIVED, handler2)

        event = MessageEvent(
            message_id="123",
            chat_jid="test:channel",
            sender="user1",
            sender_name="Test User",
            content="Hello",
        )
        await emitter.emit(event)

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        emitter = EventEmitter()

        async def handler(event: Event) -> None:
            pass

        emitter.on(EventType.MESSAGE_RECEIVED, handler)
        emitter.clear()

        assert EventType.MESSAGE_RECEIVED not in emitter._handlers


class TestChannel:
    """Tests for Channel base class."""

    @pytest.mark.asyncio
    async def test_channel_creation(self) -> None:
        channel = DummyChannel(ChannelType.TELEGRAM)
        assert channel.channel_type == ChannelType.TELEGRAM
        assert not channel.is_connected

    @pytest.mark.asyncio
    async def test_connect(self) -> None:
        channel = DummyChannel(ChannelType.TELEGRAM)
        await channel.connect()
        assert channel.is_connected

    @pytest.mark.asyncio
    async def test_disconnect(self) -> None:
        channel = DummyChannel(ChannelType.TELEGRAM)
        await channel.connect()
        await channel.disconnect()
        assert not channel.is_connected

    @pytest.mark.asyncio
    async def test_send_message(self) -> None:
        channel = DummyChannel(ChannelType.TELEGRAM)
        message_id = await channel.send_message("chat123", "Hello world")
        assert message_id.startswith("msg_chat123")

    @pytest.mark.asyncio
    async def test_parse_jid(self) -> None:
        channel = DummyChannel(ChannelType.TELEGRAM)
        platform_id, resource = channel.parse_jid("telegram:123456")
        assert platform_id == "telegram"
        assert resource == "123456"

    @pytest.mark.asyncio
    async def test_parse_jid_with_resource(self) -> None:
        channel = DummyChannel(ChannelType.WHATSAPP)
        platform_id, resource = channel.parse_jid("whatsapp:123456:device1")
        assert platform_id == "whatsapp"
        assert resource == "123456:device1"

    @pytest.mark.asyncio
    async def test_parse_jid_invalid(self) -> None:
        channel = DummyChannel(ChannelType.TELEGRAM)
        with pytest.raises(ValueError, match="Invalid JID format"):
            channel.parse_jid("invalid")

    @pytest.mark.asyncio
    async def test_build_jid(self) -> None:
        channel = DummyChannel(ChannelType.TELEGRAM)
        jid = channel.build_jid("123456")
        assert jid == "telegram:123456"

    @pytest.mark.asyncio
    async def test_build_jid_with_resource(self) -> None:
        channel = DummyChannel(ChannelType.WHATSAPP)
        jid = channel.build_jid("123456", "device1")
        assert jid == "whatsapp:123456:device1"

    @pytest.mark.asyncio
    async def test_validate_jid(self) -> None:
        channel = DummyChannel(ChannelType.TELEGRAM)
        assert channel.validate_jid("telegram:123456") is True
        assert channel.validate_jid("invalid") is False


class TestChannelRegistry:
    """Tests for ChannelRegistry."""

    def test_register(self) -> None:
        ChannelRegistry.register(ChannelType.SLACK)(DummyChannel)
        assert ChannelRegistry.get(ChannelType.SLACK) == DummyChannel

    def test_create(self) -> None:
        ChannelRegistry.register(ChannelType.DISCORD)(DummyChannel)
        channel = ChannelRegistry.create(ChannelType.DISCORD)
        assert channel is not None
        assert isinstance(channel, DummyChannel)

    def test_create_not_registered(self) -> None:
        channel = ChannelRegistry.create(ChannelType.QQ)
        assert channel is None

    def test_available_channels(self) -> None:
        ChannelRegistry.register(ChannelType.FEISHU)(DummyChannel)
        available = ChannelRegistry.available_channels()
        assert ChannelType.FEISHU in available


class TestChannelFactory:
    """Tests for ChannelFactory."""

    def test_create(self) -> None:
        ChannelRegistry.register(ChannelType.DINGTALK)(DummyChannel)
        channel = ChannelFactory.create(ChannelType.DINGTALK)
        assert channel is not None

    def test_get_existing(self) -> None:
        ChannelRegistry.register(ChannelType.WECOM)(DummyChannel)
        channel1 = ChannelFactory.create(ChannelType.WECOM)
        channel2 = ChannelFactory.get(ChannelType.WECOM)
        assert channel1 is channel2

    def test_remove(self) -> None:
        ChannelRegistry.register(ChannelType.QQ)(DummyChannel)
        ChannelFactory.create(ChannelType.QQ)
        ChannelFactory.remove(ChannelType.QQ)
        assert ChannelFactory.get(ChannelType.QQ) is None

    def test_clear(self) -> None:
        ChannelRegistry.register(ChannelType.TELEGRAM)(DummyChannel)
        ChannelFactory.create(ChannelType.TELEGRAM)
        ChannelFactory.clear()
        assert ChannelFactory.get(ChannelType.TELEGRAM) is None


class TestEvents:
    """Tests for event classes."""

    def test_message_event(self) -> None:
        event = MessageEvent(
            message_id="123",
            chat_jid="test:channel",
            sender="user1",
            sender_name="Test User",
            content="Hello",
        )
        assert event.type == EventType.MESSAGE_RECEIVED
        assert event.message_id == "123"

    def test_message_event_from_me(self) -> None:
        event = MessageEvent(
            message_id="123",
            chat_jid="test:channel",
            sender="",
            sender_name="",
            content="Hello",
            is_from_me=True,
        )
        assert event.type == EventType.MESSAGE_SENT

    def test_connect_event(self) -> None:
        event = ConnectEvent(channel_type="telegram", connected=True)
        assert event.type == EventType.CONNECTED

    def test_disconnect_event(self) -> None:
        event = ConnectEvent(channel_type="telegram", connected=False)
        assert event.type == EventType.DISCONNECTED

    def test_error_event(self) -> None:
        event = ErrorEvent(error="Connection failed", channel_type="telegram")
        assert event.type == EventType.ERROR
        assert event.error == "Connection failed"
