"""Channel abstraction for multi-platform messaging support."""

from .base import Channel, ChannelRegistry
from .events import (
    ConnectEvent,
    ErrorEvent,
    Event,
    EventEmitter,
    EventHandler,
    EventType,
    MessageEvent,
)
from .factory import ChannelFactory

__all__ = [
    # Base classes
    "Channel",
    "ChannelRegistry",
    # Factory
    "ChannelFactory",
    # Events
    "Event",
    "EventType",
    "EventEmitter",
    "EventHandler",
    "MessageEvent",
    "ConnectEvent",
    "ErrorEvent",
]
