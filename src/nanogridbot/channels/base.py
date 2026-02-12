"""Base channel abstraction for multi-platform messaging."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from ..types import ChannelType, Message
from .events import EventEmitter

if TYPE_CHECKING:
    pass


class Channel(ABC, EventEmitter):
    """Abstract base class for messaging channel implementations."""

    def __init__(self, channel_type: ChannelType) -> None:
        """Initialize the channel.

        Args:
            channel_type: The type of messaging platform this channel connects to.
        """
        super().__init__()
        self._channel_type = channel_type
        self._connected = False

    @property
    def channel_type(self) -> ChannelType:
        """Get the channel type."""
        return self._channel_type

    @property
    def is_connected(self) -> bool:
        """Check if the channel is currently connected."""
        return self._connected

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the messaging platform.

        Raises:
            ConnectionError: If connection fails.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the messaging platform."""
        ...

    @abstractmethod
    async def send_message(self, chat_jid: str, content: str) -> str:
        """Send a message to a chat.

        Args:
            chat_jid: The JID of the chat to send to.
            content: The message content.

        Returns:
            The message ID of the sent message.

        Raises:
            RuntimeError: If not connected.
        """
        ...

    @abstractmethod
    async def receive_message(self, raw_data: dict[str, Any]) -> Message | None:
        """Parse and convert raw platform message to Message model.

        Args:
            raw_data: Raw message data from the platform SDK.

        Returns:
            Parsed Message object, or None if parsing fails.
        """
        ...

    @abstractmethod
    def parse_jid(self, jid: str) -> tuple[str, str]:
        """Parse a JID into channel type and platform-specific ID.

        Args:
            jid: The JID to parse.

        Returns:
            Tuple of (platform_id, resource).

        Raises:
            ValueError: If JID format is invalid.
        """
        ...

    @abstractmethod
    def build_jid(self, platform_id: str, resource: str | None = None) -> str:
        """Build a JID from platform-specific ID and optional resource.

        Args:
            platform_id: The platform-specific ID (e.g., phone number, user ID).
            resource: Optional resource (e.g., device ID for WhatsApp).

        Returns:
            The formatted JID.
        """
        ...

    def validate_jid(self, jid: str) -> bool:
        """Validate a JID format for this channel.

        Args:
            jid: The JID to validate.

        Returns:
            True if the JID format is valid.
        """
        try:
            self.parse_jid(jid)
            return True
        except ValueError:
            return False

    async def _on_message_received(
        self, message_id: str, chat_jid: str, sender: str, sender_name: str, content: str
    ) -> None:
        """Handle incoming message event.

        Args:
            message_id: The message ID.
            chat_jid: The chat JID.
            sender: The sender's JID.
            sender_name: The sender's display name.
            content: The message content.
        """
        from .events import MessageEvent

        event = MessageEvent(
            message_id=message_id,
            chat_jid=chat_jid,
            sender=sender,
            sender_name=sender_name,
            content=content,
            is_from_me=False,
        )
        await self.emit(event)

    async def _on_message_sent(self, message_id: str, chat_jid: str, content: str) -> None:
        """Handle outgoing message event.

        Args:
            message_id: The message ID.
            chat_jid: The chat JID.
            content: The message content.
        """
        from .events import MessageEvent

        event = MessageEvent(
            message_id=message_id,
            chat_jid=chat_jid,
            sender="",
            sender_name="",
            content=content,
            is_from_me=True,
        )
        await self.emit(event)

    async def _on_connected(self) -> None:
        """Handle connection event."""
        from .events import ConnectEvent

        self._connected = True
        event = ConnectEvent(channel_type=self._channel_type.value, connected=True)
        await self.emit(event)

    async def _on_disconnected(self) -> None:
        """Handle disconnection event."""
        from .events import ConnectEvent

        self._connected = False
        event = ConnectEvent(channel_type=self._channel_type.value, connected=False)
        await self.emit(event)

    async def _on_error(self, error: str) -> None:
        """Handle error event.

        Args:
            error: The error message.
        """
        from .events import ErrorEvent

        event = ErrorEvent(error=error, channel_type=self._channel_type.value)
        await self.emit(event)


class ChannelRegistry:
    """Registry for channel implementations."""

    _channels: dict[ChannelType, type[Channel]] = {}

    @classmethod
    def register(cls, channel_type: ChannelType) -> callable:
        """Decorator to register a channel implementation.

        Usage:
            @ChannelRegistry.register(ChannelType.TEGRAM)
            class TelegramChannel(Channel):
                ...
        """

        def decorator(channel_class: type[Channel]) -> type[Channel]:
            cls._channels[channel_type] = channel_class
            return channel_class

        return decorator

    @classmethod
    def get(cls, channel_type: ChannelType) -> type[Channel] | None:
        """Get a channel class by type."""
        return cls._channels.get(channel_type)

    @classmethod
    def create(cls, channel_type: ChannelType) -> Channel | None:
        """Create a channel instance by type."""
        channel_class = cls.get(channel_type)
        if channel_class is None:
            return None
        return channel_class(channel_type)

    @classmethod
    def available_channels(cls) -> list[ChannelType]:
        """Get list of available channel types."""
        return list(cls._channels.keys())
