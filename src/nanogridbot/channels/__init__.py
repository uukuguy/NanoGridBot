"""Channel abstraction for multi-platform messaging support."""

from .base import Channel, ChannelRegistry
from .dingtalk import DingTalkChannel
from .discord import DiscordChannel
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
from .feishu import FeishuChannel
from .qq import QQChannel
from .slack import SlackChannel
from .telegram import TelegramChannel
from .wecom import WeComChannel
from .whatsapp import WhatsAppChannel

# Import all channel implementations to register them
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
    # Channel implementations
    "WhatsAppChannel",
    "TelegramChannel",
    "SlackChannel",
    "DiscordChannel",
    "WeComChannel",
    "DingTalkChannel",
    "FeishuChannel",
    "QQChannel",
]
