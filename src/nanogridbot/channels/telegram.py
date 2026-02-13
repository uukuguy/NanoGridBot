"""Telegram channel implementation using python-telegram-bot."""

from datetime import datetime
from typing import Any

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler

from nanogridbot.types import ChannelType, Message, MessageRole

from .base import Channel, ChannelRegistry


@ChannelRegistry.register(ChannelType.TELEGRAM)
class TelegramChannel(Channel):
    """Telegram channel implementation using python-telegram-bot."""

    def __init__(
        self,
        channel_type: ChannelType = ChannelType.TELEGRAM,
        token: str | None = None,
    ) -> None:
        """Initialize Telegram channel.

        Args:
            channel_type: The channel type (default: TELEGRAM).
            token: Telegram Bot API token.
        """
        super().__init__(channel_type)
        self._token = token
        self._application: Application | None = None

    async def connect(self) -> None:
        """Establish connection to Telegram."""
        if not self._token:
            raise RuntimeError("Telegram bot token not configured")

        self._application = Application.builder().token(self._token).build()

        # Add handlers
        self._application.add_handler(CommandHandler("start", self._handle_start))
        self._application.add_handler(MessageHandler(None, self._handle_message))

        # Start polling
        await self._application.initialize()
        await self._application.start()
        await self._on_connected()

    async def disconnect(self) -> None:
        """Close connection to Telegram."""
        if self._application:
            await self._application.stop()
            self._application = None
        await self._on_disconnected()

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if update.message:
            await update.message.reply_text("Hello! I'm your AI assistant.")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages."""
        if not update.message:
            return

        message = await self.receive_message({"update": update})
        if message:
            await self._on_message_received(
                message_id=message.id,
                chat_jid=message.chat_jid,
                sender=message.sender,
                sender_name=message.sender_name or "",
                content=message.content,
            )

    async def send_message(self, chat_jid: str, content: str) -> str:
        """Send a message to a Telegram chat.

        Args:
            chat_jid: The JID of the chat (format: telegram:123456789).
            content: The message content.

        Returns:
            The message ID of the sent message.
        """
        if not self._application:
            raise RuntimeError("Telegram channel not connected")

        _, user_id = self.parse_jid(chat_jid)
        bot = self._application.bot

        sent = await bot.send_message(chat_id=int(user_id), text=content)
        await self._on_message_sent(str(sent.message_id), chat_jid, content)
        return str(sent.message_id)

    async def receive_message(self, raw_data: dict[str, Any]) -> Message | None:
        """Parse and convert raw Telegram message to Message model.

        Args:
            raw_data: Raw message data from Telegram webhook/polling.

        Returns:
            Parsed Message object, or None if parsing fails.
        """
        try:
            update = raw_data.get("update")
            if not update or not isinstance(update, Update):
                return None

            msg = update.message
            if not msg:
                return None

            # Get sender info
            sender = ""
            sender_name = ""
            if msg.from_user:
                sender = str(msg.from_user.id)
                sender_name = msg.from_user.name or msg.from_user.username or ""

            # Get chat info
            chat_id = str(msg.chat.id) if msg.chat else sender

            # Build JID
            chat_jid = self.build_jid(chat_id)

            # Get content
            content = ""
            if msg.text:
                content = msg.text
            elif msg.photo:
                content = "[Photo]"
            elif msg.video:
                content = "[Video]"
            elif msg.voice:
                content = "[Voice]"
            elif msg.audio:
                content = "[Audio]"
            elif msg.document:
                content = f"[Document: {msg.document.file_name}]"
            elif msg.sticker:
                content = "[Sticker]"
            elif msg.location:
                content = "[Location]"
            else:
                content = "[Unknown]"

            # Get timestamp
            timestamp = msg.date if msg.date else datetime.now()

            return Message(
                id=str(msg.message_id),
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
        """Parse a Telegram JID into user ID.

        Args:
            jid: The JID to parse (format: telegram:123456789).

        Returns:
            Tuple of (user_id, empty_resource).

        Raises:
            ValueError: If JID format is invalid.
        """
        if not jid.startswith("telegram:"):
            raise ValueError(f"Invalid Telegram JID: {jid}")

        user_id = jid[10:]  # Remove "telegram:" prefix
        if not user_id:
            raise ValueError(f"Invalid Telegram JID: {jid}")

        return user_id, ""

    def build_jid(self, platform_id: str, resource: str | None = None) -> str:
        """Build a Telegram JID from user ID.

        Args:
            platform_id: The user ID.
            resource: Optional resource (not used for Telegram).

        Returns:
            The formatted JID (format: telegram:123456789).
        """
        return f"telegram:{platform_id}"
