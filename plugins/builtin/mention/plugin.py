"""Mention plugin for handling @mentions in messages."""

import re
from typing import Any

from nanogridbot.plugins.base import Plugin
from nanogridbot.types import Message


class MentionPlugin(Plugin):
    """Mention plugin to handle @mentions in messages."""

    @property
    def name(self) -> str:
        return "mention"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Mention plugin to handle @mentions in messages"

    @property
    def author(self) -> str:
        return "NanoGridBot Team"

    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the plugin.

        Args:
            config: Plugin configuration
        """
        self.enabled = config.get("enabled", True)
        self.bot_names = config.get("bot_names", ["andy", "bot", "assistant"])
        self.always_respond = config.get("always_respond", False)

        # Compile mention patterns
        mention_pattern = "|".join(re.escape(name) for name in self.bot_names)
        self.mention_regex = re.compile(rf"@({mention_pattern})\b", re.IGNORECASE)

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        pass

    async def on_message_received(self, message: Message) -> Message | None:
        """Check for @mentions in message.

        Args:
            message: Received message

        Returns:
            Message with mention metadata
        """
        if not self.enabled:
            return message

        text = message.text or ""

        # Find all mentions
        mentions = self.mention_regex.findall(text)

        if mentions:
            message.metadata = message.metadata or {}
            message.metadata["mentions"] = mentions
            message.metadata["has_mention"] = True

        # Check if message should always trigger a response
        if self.always_respond and not message.is_group:
            message.metadata = message.metadata or {}
            message.metadata["force_response"] = True

        return message
