"""Auto reply plugin for automatic message responses."""

import re
from typing import Any

from loguru import logger

from nanogridbot.plugins.base import Plugin
from nanogridbot.types import Message


class AutoReplyPlugin(Plugin):
    """Auto-reply plugin for keyword-based automatic responses."""

    @property
    def name(self) -> str:
        return "auto_reply"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Auto-reply plugin for keyword-based automatic responses"

    @property
    def author(self) -> str:
        return "NanoGridBot Team"

    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the plugin.

        Args:
            config: Plugin configuration
        """
        self.enabled = config.get("enabled", True)
        self.auto_replies = config.get("auto_replies", [])

        # Compile regex patterns
        for reply in self.auto_replies:
            if "pattern" in reply:
                reply["regex"] = re.compile(reply["pattern"], re.IGNORECASE)

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        pass

    async def on_message_received(self, message: Message) -> Message | None:
        """Check for auto-reply triggers.

        Args:
            message: Received message

        Returns:
            Message unchanged (auto-replies are handled separately)
        """
        if not self.enabled or not self.auto_replies:
            return message

        text = message.text or ""
        sender_jid = message.sender_jid

        for reply in self.auto_replies:
            pattern = reply.get("regex") or reply.get("pattern", "")
            response = reply.get("response", "")
            reply_to_sender = reply.get("reply_to_sender", False)
            ignore_pattern = reply.get("ignore_pattern")

            # Check if we should ignore this message
            if ignore_pattern:
                ignore_regex = re.compile(ignore_pattern, re.IGNORECASE)
                if ignore_regex.search(text):
                    continue

            # Check for match
            if isinstance(pattern, re.Pattern):
                match = pattern.search(text)
            else:
                match = text.lower() == pattern.lower()

            if match:
                logger.info(f"Auto-reply triggered for {sender_jid}: {response}")
                # Store the auto-reply in message metadata for the router to handle
                message.metadata = message.metadata or {}
                message.metadata["auto_reply"] = response
                message.metadata["reply_to_sender"] = reply_to_sender
                break

        return message
