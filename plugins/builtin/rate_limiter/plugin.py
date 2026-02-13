"""Rate limiter plugin for message rate control."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from nanogridbot.plugins.base import Plugin
from nanogridbot.types import Message


class RateLimiterPlugin(Plugin):
    """Rate limiting plugin to prevent message flooding."""

    @property
    def name(self) -> str:
        return "rate_limiter"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Rate limiting plugin to prevent message flooding"

    @property
    def author(self) -> str:
        return "NanoGridBot Team"

    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the plugin.

        Args:
            config: Plugin configuration
        """
        self.max_messages_per_minute = config.get("max_messages_per_minute", 10)
        self.max_messages_per_hour = config.get("max_messages_per_hour", 100)
        self.enabled = config.get("enabled", True)
        self.message_counts_per_minute: dict[str, list[datetime]] = defaultdict(list)
        self.message_counts_per_hour: dict[str, list[datetime]] = defaultdict(list)

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        self.message_counts_per_minute.clear()
        self.message_counts_per_hour.clear()

    async def on_message_received(self, message: Message) -> Message | None:
        """Check rate limit for incoming message.

        Args:
            message: Received message

        Returns:
            Message if allowed, None if rate limited
        """
        if not self.enabled:
            return message

        jid = message.chat_jid
        now = datetime.now()

        # Check per-minute limit
        cutoff_minute = now - timedelta(minutes=1)
        self.message_counts_per_minute[jid] = [
            ts for ts in self.message_counts_per_minute[jid] if ts > cutoff_minute
        ]

        if len(self.message_counts_per_minute[jid]) >= self.max_messages_per_minute:
            return None

        # Check per-hour limit
        cutoff_hour = now - timedelta(hours=1)
        self.message_counts_per_hour[jid] = [
            ts for ts in self.message_counts_per_hour[jid] if ts > cutoff_hour
        ]

        if len(self.message_counts_per_hour[jid]) >= self.max_messages_per_hour:
            return None

        # Record the message
        self.message_counts_per_minute[jid].append(now)
        self.message_counts_per_hour[jid].append(now)

        return message
