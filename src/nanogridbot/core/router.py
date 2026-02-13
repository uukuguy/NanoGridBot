"""Message router for routing messages between channels and groups."""

import asyncio
from typing import Any

from nanogridbot.channels.base import Channel
from nanogridbot.config import get_config
from nanogridbot.database import Database
from nanogridbot.types import Message


class MessageRouter:
    """Routes messages between channels and internal components."""

    def __init__(self, config: "get_config", db: Database, channels: list[Channel]):
        """Initialize the message router.

        Args:
            config: Application configuration
            db: Database instance
            channels: List of channel instances
        """
        self.config = config
        self.db = db
        self.channels = channels
        self._running = False

    async def start(self) -> None:
        """Start the message router."""
        from loguru import logger

        self._running = True
        logger.info("Message router started")

    async def stop(self) -> None:
        """Stop the message router."""
        from loguru import logger

        self._running = False
        logger.info("Message router stopped")

    async def route_message(self, message: Message) -> None:
        """Route a received message to the appropriate handler.

        Args:
            message: Message to route
        """
        from loguru import logger

        # Store message in database
        await self.db.store_message(message)

        # Check if group is registered
        group = await self._get_registered_group(message.chat_jid)

        if not group:
            logger.debug(f"Group {message.chat_jid} not registered, skipping")
            return

        # Check trigger pattern
        if group.requires_trigger:
            triggered = self._check_trigger(message.content, group.trigger_pattern)
            if not triggered:
                logger.debug(f"Message in {message.chat_jid} did not trigger")
                return

        # TODO: Enqueue for processing via group queue

    def _check_trigger(self, content: str, pattern: str | None) -> bool:
        """Check if content matches trigger pattern.

        Args:
            content: Message content
            pattern: Trigger pattern (regex)

        Returns:
            True if triggered
        """
        import re

        if not pattern:
            pattern = rf"^@{self.config.assistant_name}\b"

        return bool(re.search(pattern, content, re.IGNORECASE))

    async def _get_registered_group(self, jid: str) -> Any:
        """Get registered group for JID.

        Args:
            jid: Group JID

        Returns:
            RegisteredGroup or None
        """
        group_repo = self.db.get_group_repository()
        return await group_repo.get_group_by_jid(jid)

    async def send_response(self, jid: str, text: str) -> None:
        """Send a response to a JID.

        Args:
            jid: Target JID
            text: Response text
        """
        from loguru import logger

        # Find channel that owns this JID
        for channel in self.channels:
            if channel.owns_jid(jid):
                try:
                    await channel.send_message(jid, text)
                    logger.info(f"Sent response to {jid} via {channel.name}")
                except Exception as e:
                    logger.error(f"Error sending to {channel.name}: {e}")
                break
        else:
            logger.warning(f"No channel found for JID: {jid}")

    async def broadcast_to_groups(self, text: str, group_folders: list[str] | None = None) -> None:
        """Broadcast message to all or selected groups.

        Args:
            text: Message text
            group_folders: Optional list of group folders to broadcast to
        """
        group_repo = self.db.get_group_repository()

        if group_folders:
            groups = []
            for folder in group_folders:
                group = await group_repo.get_group_by_folder(folder)
                if group:
                    groups.append(group)
        else:
            groups = await group_repo.get_groups()

        for group in groups:
            await self.send_response(group.jid, text)
