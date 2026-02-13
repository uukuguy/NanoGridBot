"""WhatsApp channel implementation using PyWa."""

from datetime import datetime
from typing import Any

from pywa import WhatsApp
from pywa.types import Message as WaMessage
from pywa.types import MessageType

from nanogridbot.types import ChannelType, Message, MessageRole

from .base import Channel, ChannelRegistry


@ChannelRegistry.register(ChannelType.WHATSAPP)
class WhatsAppChannel(Channel):
    """WhatsApp channel implementation using PyWa (WhatsApp Cloud API)."""

    def __init__(
        self,
        channel_type: ChannelType = ChannelType.WHATSAPP,
        phone_id: str | None = None,
        token: str | None = None,
        verify_token: str | None = None,
    ) -> None:
        """Initialize WhatsApp channel.

        Args:
            channel_type: The channel type (default: WHATSAPP).
            phone_id: WhatsApp Business Phone ID.
            token: WhatsApp API token.
            verify_token: Webhook verification token.
        """
        super().__init__(channel_type)
        self._phone_id = phone_id
        self._token = token
        self._verify_token = verify_token
        self._client: WhatsApp | None = None
        self._server = None  # FastAPI app for webhook

    def _ensure_client(self) -> WhatsApp:
        """Ensure the WhatsApp client is initialized."""
        if self._client is None:
            if self._phone_id is None or self._token is None:
                raise RuntimeError(
                    "WhatsApp channel not configured. " "Provide phone_id and token."
                )
            from fastapi import FastAPI

            self._server = FastAPI()
            self._client = WhatsApp(
                phone_id=self._phone_id,
                token=self._token,
                server=self._server,
                verify_token=self._verify_token or "default_verify_token",
            )
        return self._client

    async def connect(self) -> None:
        """Establish connection to WhatsApp.

        Since WhatsApp Cloud API uses webhooks, this sets up
        the event handlers.
        """
        client = self._ensure_client()

        # Register message handler
        @client.on_message()
        async def handle_message(client: WhatsApp, msg: WaMessage) -> None:
            message = await self.receive_message({"message": msg.model_dump()})
            if message:
                await self._on_message_received(
                    message_id=message.id,
                    chat_jid=message.chat_jid,
                    sender=message.sender,
                    sender_name=message.sender_name or "",
                    content=message.content,
                )

        # Register connection handler
        await self._on_connected()

    async def disconnect(self) -> None:
        """Close connection to WhatsApp."""
        self._client = None
        self._server = None
        await self._on_disconnected()

    async def send_message(self, chat_jid: str, content: str) -> str:
        """Send a message to a WhatsApp chat.

        Args:
            chat_jid: The JID of the chat (format: whatsapp:+1234567890).
            content: The message content.

        Returns:
            The message ID of the sent message.
        """
        if not self._client:
            raise RuntimeError("WhatsApp channel not connected")

        _, phone = self.parse_jid(chat_jid)
        if not phone:
            raise ValueError(f"Invalid WhatsApp JID: {chat_jid}")

        # PyWa send_message is sync, run in thread pool
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        def _send():
            result = self._client.send_message(to=phone, text=content)
            return result.get("messages", [{}])[0].get("id", "")

        loop = asyncio.get_event_loop()
        msg_id = await loop.run_in_executor(ThreadPoolExecutor(), _send)
        await self._on_message_sent(msg_id, chat_jid, content)
        return msg_id

    async def receive_message(self, raw_data: dict[str, Any]) -> Message | None:
        """Parse and convert raw WhatsApp message to Message model.

        Args:
            raw_data: Raw message data from WhatsApp webhook.

        Returns:
            Parsed Message object, or None if parsing fails.
        """
        try:
            # Extract message from webhook payload
            msg_dict = raw_data.get("message", {})
            if not msg_dict:
                return None

            wa_msg = WaMessage(**msg_dict)

            # Get text content based on message type
            content = ""
            if wa_msg.type == MessageType.TEXT:
                content = wa_msg.text or ""
            elif wa_msg.type == MessageType.IMAGE:
                content = wa_msg.caption or "[Image]"
            elif wa_msg.type == MessageType.VIDEO:
                content = wa_msg.caption or "[Video]"
            elif wa_msg.type == MessageType.AUDIO:
                content = "[Audio]"
            elif wa_msg.type == MessageType.VOICE:
                content = "[Voice]"
            elif wa_msg.type == MessageType.DOCUMENT:
                content = wa_msg.caption or "[Document]"
            elif wa_msg.type == MessageType.STICKER:
                content = "[Sticker]"
            elif wa_msg.type == MessageType.LOCATION:
                content = "[Location]"
            else:
                content = f"[{wa_msg.type.value}]"

            # Build JID from phone number
            phone = wa_msg.from_user
            chat_jid = self.build_jid(phone)

            # Convert timestamp
            timestamp = datetime.fromtimestamp(int(wa_msg.timestamp))

            return Message(
                id=wa_msg.id,
                chat_jid=chat_jid,
                sender=phone,
                sender_name=phone,  # WhatsApp doesn't provide names in message
                content=content,
                timestamp=timestamp,
                is_from_me=False,
                role=MessageRole.USER,
            )
        except Exception:
            return None

    def parse_jid(self, jid: str) -> tuple[str, str]:
        """Parse a WhatsApp JID into phone number.

        Args:
            jid: The JID to parse (format: whatsapp:+1234567890).

        Returns:
            Tuple of (phone_number, empty_resource).

        Raises:
            ValueError: If JID format is invalid.
        """
        if not jid.startswith("whatsapp:"):
            raise ValueError(f"Invalid WhatsApp JID: {jid}")

        phone = jid[9:]  # Remove "whatsapp:" prefix
        if not phone:
            raise ValueError(f"Invalid WhatsApp JID: {jid}")

        return phone, ""

    def build_jid(self, platform_id: str, resource: str | None = None) -> str:
        """Build a WhatsApp JID from phone number.

        Args:
            platform_id: The phone number (with + prefix).
            resource: Optional resource (not used for WhatsApp).

        Returns:
            The formatted JID (format: whatsapp:+1234567890).
        """
        phone = platform_id
        if not phone.startswith("+"):
            phone = f"+{phone}"
        return f"whatsapp:{phone}"

    def get_server(self):
        """Get the FastAPI server for webhook handling.

        Returns:
            The FastAPI app instance.
        """
        self._ensure_client()
        return self._server
