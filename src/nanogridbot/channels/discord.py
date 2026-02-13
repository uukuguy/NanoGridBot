"""Discord channel implementation using discord.py."""

from typing import Any

import discord

from nanogridbot.types import ChannelType, Message, MessageRole

from .base import Channel, ChannelRegistry


@ChannelRegistry.register(ChannelType.DISCORD)
class DiscordChannel(Channel):
    """Discord channel implementation using discord.py."""

    def __init__(
        self,
        channel_type: ChannelType = ChannelType.DISCORD,
        token: str | None = None,
        intents: discord.Intents | None = None,
    ) -> None:
        """Initialize Discord channel.

        Args:
            channel_type: The channel type (default: DISCORD).
            token: Discord Bot Token.
            intents: Discord Intents for event subscription.
        """
        super().__init__(channel_type)
        self._token = token
        self._intents = intents or self._default_intents()
        self._client: discord.Client | None = None

    def _default_intents(self) -> discord.Intents:
        """Create default intents for the bot."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        return intents

    async def connect(self) -> None:
        """Establish connection to Discord."""
        if not self._token:
            raise RuntimeError("Discord bot token not configured")

        self._client = discord.Client(intents=self._intents)

        @self._client.event
        async def on_ready() -> None:
            print(f"Logged in as {self._client.user}")

        @self._client.event
        async def on_message(message: discord.Message) -> None:
            # Ignore bot messages
            if message.author.bot:
                return

            parsed = await self.receive_message({"message": message})
            if parsed:
                await self._on_message_received(
                    message_id=parsed.id,
                    chat_jid=parsed.chat_jid,
                    sender=parsed.sender,
                    sender_name=parsed.sender_name or "",
                    content=parsed.content,
                )

        await self._client.login(self._token)
        await self._client.connect(reconnect=True)
        await self._on_connected()

    async def disconnect(self) -> None:
        """Close connection to Discord."""
        if self._client:
            await self._client.close()
            self._client = None
        await self._on_disconnected()

    async def send_message(self, chat_jid: str, content: str) -> str:
        """Send a message to a Discord channel.

        Args:
            chat_jid: The JID of the chat (format: discord:channel:123456789).
            content: The message content.

        Returns:
            The message ID of the sent message.
        """
        if not self._client:
            raise RuntimeError("Discord channel not connected")

        _, resource = self.parse_jid(chat_jid)
        if not resource:
            raise ValueError(f"Invalid Discord JID: {chat_jid}")

        # Get channel
        channel = self._client.get_channel(int(resource))
        if not channel or not isinstance(channel, discord.abc.Messageable):
            raise ValueError(f"Cannot find channel: {resource}")

        sent = await channel.send(content)
        await self._on_message_sent(str(sent.id), chat_jid, content)
        return str(sent.id)

    async def receive_message(self, raw_data: dict[str, Any]) -> Message | None:
        """Parse and convert raw Discord message to Message model.

        Args:
            raw_data: Raw message data from Discord.

        Returns:
            Parsed Message object, or None if parsing fails.
        """
        try:
            msg = raw_data.get("message")
            if not msg or not isinstance(msg, discord.Message):
                return None

            # Build JID: discord:channel:{channel_id}
            chat_jid = self.build_jid(str(msg.channel.id), "channel")

            # Get sender info
            sender = str(msg.author.id)
            sender_name = msg.author.name

            # Get content
            content = msg.content

            # Get timestamp
            timestamp = msg.created_at

            return Message(
                id=str(msg.id),
                chat_jid=chat_jid,
                sender=sender,
                sender_name=sender_name,
                content=content,
                timestamp=timestamp,
                is_from_me=False,
                role=MessageRole.USER,
            )
        except Exception:
            return None

    def parse_jid(self, jid: str) -> tuple[str, str]:
        """Parse a Discord JID into channel/user ID.

        Args:
            jid: The JID to parse (format: discord:channel:123456789).

        Returns:
            Tuple of (channel_id, resource_type).

        Raises:
            ValueError: If JID format is invalid.
        """
        if not jid.startswith("discord:"):
            raise ValueError(f"Invalid Discord JID: {jid}")

        rest = jid[8:]  # Remove "discord:" prefix
        parts = rest.split(":", 1)

        if len(parts) != 2:
            raise ValueError(f"Invalid Discord JID: {jid}")

        return parts[1], parts[0]  # (id, type)

    def build_jid(self, platform_id: str, resource: str | None = None) -> str:
        """Build a Discord JID from channel/user ID.

        Args:
            platform_id: The channel or user ID.
            resource: Resource type ("channel" or "user").

        Returns:
            The formatted JID (format: discord:channel:123456789).
        """
        res_type = resource if resource else "channel"
        return f"discord:{res_type}:{platform_id}"
