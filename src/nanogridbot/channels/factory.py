"""Channel factory for creating channel instances."""

from ..types import ChannelType
from .base import Channel, ChannelRegistry


class ChannelFactory:
    """Factory for creating and managing channel instances."""

    _instances: dict[ChannelType, Channel] = {}

    @classmethod
    def create(cls, channel_type: ChannelType) -> Channel | None:
        """Create a channel instance for the given type.

        Args:
            channel_type: The type of channel to create.

        Returns:
            A channel instance, or None if the channel type is not supported.
        """
        # Check if already instantiated
        if channel_type in cls._instances:
            return cls._instances[channel_type]

        # Create new instance
        channel = ChannelRegistry.create(channel_type)
        if channel is not None:
            cls._instances[channel_type] = channel

        return channel

    @classmethod
    def get(cls, channel_type: ChannelType) -> Channel | None:
        """Get an existing channel instance.

        Args:
            channel_type: The type of channel to get.

        Returns:
            The channel instance, or None if not found.
        """
        return cls._instances.get(channel_type)

    @classmethod
    def get_or_create(cls, channel_type: ChannelType) -> Channel | None:
        """Get existing instance or create new one.

        Args:
            channel_type: The type of channel.

        Returns:
            The channel instance.
        """
        return cls.get(channel_type) or cls.create(channel_type)

    @classmethod
    def remove(cls, channel_type: ChannelType) -> None:
        """Remove a channel instance.

        Args:
            channel_type: The type of channel to remove.
        """
        if channel_type in cls._instances:
            del cls._instances[channel_type]

    @classmethod
    def clear(cls) -> None:
        """Remove all channel instances."""
        cls._instances.clear()

    @classmethod
    async def connect_all(cls) -> dict[ChannelType, bool]:
        """Connect all registered channels.

        Returns:
            Dict mapping channel type to connection success status.
        """
        results: dict[ChannelType, bool] = {}
        for channel_type, channel in cls._instances.items():
            try:
                await channel.connect()
                results[channel_type] = True
            except Exception:
                results[channel_type] = False
        return results

    @classmethod
    async def disconnect_all(cls) -> None:
        """Disconnect all registered channels."""
        for channel in cls._instances.values():
            try:
                await channel.disconnect()
            except Exception:
                pass  # Best effort disconnect

    @classmethod
    def available_channels(cls) -> list[ChannelType]:
        """Get list of registered channel types."""
        return ChannelRegistry.available_channels()

    @classmethod
    def connected_channels(cls) -> list[ChannelType]:
        """Get list of currently connected channel types."""
        return [ct for ct, ch in cls._instances.items() if ch.is_connected]
