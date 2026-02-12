"""Event system for channel abstraction."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    """Types of events emitted by channels."""

    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    TYPING = "typing"
    READ = "read"


@dataclass
class Event:
    """Base event class."""

    type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class MessageEvent(Event):
    """Event emitted when a message is received or sent."""

    message_id: str = ""
    chat_jid: str = ""
    sender: str = ""
    sender_name: str = ""
    content: str = ""
    is_from_me: bool = False
    type: EventType = EventType.MESSAGE_RECEIVED  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.type = EventType.MESSAGE_RECEIVED if not self.is_from_me else EventType.MESSAGE_SENT
        self.data = {
            "message_id": self.message_id,
            "chat_jid": self.chat_jid,
            "sender": self.sender,
            "sender_name": self.sender_name,
            "content": self.content,
            "is_from_me": self.is_from_me,
        }


@dataclass
class ConnectEvent(Event):
    """Event emitted when a channel connects or disconnects."""

    channel_type: str = ""
    connected: bool = True
    type: EventType = EventType.CONNECTED  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.type = EventType.CONNECTED if self.connected else EventType.DISCONNECTED
        self.data = {"channel_type": self.channel_type, "connected": self.connected}


@dataclass
class ErrorEvent(Event):
    """Event emitted when an error occurs."""

    error: str = ""
    channel_type: str = ""
    type: EventType = EventType.ERROR  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.type = EventType.ERROR
        self.data = {"error": self.error, "channel_type": self.channel_type}


# Event handler type
EventHandler = Callable[[Event], Awaitable[None]]


class EventEmitter:
    """Simple event emitter for channel events."""

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = {}

    def on(self, event_type: EventType, handler: EventHandler) -> None:
        """Register an event handler."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def off(self, event_type: EventType, handler: EventHandler) -> None:
        """Unregister an event handler."""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)

    async def emit(self, event: Event) -> None:
        """Emit an event to all registered handlers."""
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                # Log but don't raise to avoid breaking other handlers
                import logging

                logging.warning(f"Event handler error: {e}")

    def clear(self) -> None:
        """Clear all event handlers."""
        self._handlers.clear()
