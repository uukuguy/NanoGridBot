"""Feishu (Lark) channel implementation using lark-oapi SDK."""

from datetime import datetime
from typing import Any

import lark_oapi as lark

from nanogridbot.types import ChannelType, Message, MessageRole

from .base import Channel, ChannelRegistry


@ChannelRegistry.register(ChannelType.FEISHU)
class FeishuChannel(Channel):
    """Feishu (Lark) channel implementation using lark-oapi SDK."""

    def __init__(
        self,
        channel_type: ChannelType = ChannelType.FEISHU,
        app_id: str | None = None,
        app_secret: str | None = None,
        verification_token: str | None = None,
    ) -> None:
        """Initialize Feishu channel.

        Args:
            channel_type: The channel type (default: FEISHU).
            app_id: Feishu App ID.
            app_secret: Feishu App Secret.
            verification_token: Feishu Verification Token.
        """
        super().__init__(channel_type)
        self._app_id = app_id
        self._app_secret = app_secret
        self._verification_token = verification_token
        self._client: lark.Client | None = None

    async def connect(self) -> None:
        """Establish connection to Feishu."""
        if not self._app_id or not self._app_secret:
            raise RuntimeError("Feishu app_id and app_secret not configured")

        # Initialize Feishu client
        self._client = (
            lark.Client.builder()
            .app_id(self._app_id)
            .app_secret(self._app_secret)
            .log_level(lark.LogLevel.DEBUG)
            .build()
        )

        await self._on_connected()

    async def disconnect(self) -> None:
        """Close connection to Feishu."""
        self._client = None
        await self._on_disconnected()

    async def send_message(self, chat_jid: str, content: str) -> str:
        """Send a message to a Feishu chat.

        Args:
            chat_jid: The JID of the chat (format: feishu:open_id).
            content: The message content.

        Returns:
            The message ID of the sent message.
        """
        if not self._client:
            raise RuntimeError("Feishu channel not connected")

        _, open_id = self.parse_jid(chat_jid)

        # Build message
        message = (
            lark.Message.builder()
            .receive_id_type(lark.ReceiveIdType.OPEN_ID)
            .receive_id(open_id)
            .msg_type(lark.MsgType.TEXT)
            .content(lark.Content.builder().text(content).build())
            .build()
        )

        # Send message
        response = await self._client.im.message.create(message)

        if response.code != 0:
            raise RuntimeError(f"Failed to send message: {response.msg}")

        return response.data.message_id if response.data else ""

    async def receive_message(self, raw_data: dict[str, Any]) -> Message | None:
        """Parse and convert raw Feishu message to Message model.

        Args:
            raw_data: Raw message data from Feishu webhook.

        Returns:
            Parsed Message object, or None if parsing fails.
        """
        try:
            # Handle event callback
            # Format: {"type": "event_callback", "event": {...}}
            event_type = raw_data.get("type")
            if event_type != "event_callback":
                return None

            event = raw_data.get("event", {})
            if not event:
                return None

            # Check if it's a message event
            event_msg_type = event.get("msg_type")
            if not event_msg_type:
                return None

            # Get sender and chat info
            sender_id = ""
            sender_name = ""
            chat_id = ""

            sender = event.get("sender", {})
            if sender:
                sender_id_info = sender.get("sender_id", {})
                if sender_id_info:
                    sender_id = sender_id_info.get("open_id", "") or sender_id_info.get(
                        "user_id", ""
                    )
                sender_name = sender.get("sender_nick", "")

            chat_id_info = event.get("chat_id", {})
            if chat_id_info:
                chat_id = chat_id_info.get("open_id", "") or chat_id_info.get("chat_id", "")

            # Get content
            content = ""
            msg_body = event.get("body", {})
            if event_msg_type == "text":
                content = msg_body.get("content", "")
            elif event_msg_type == "image":
                content = "[Image]"
            elif event_msg_type == "file":
                content = "[File]"
            elif event_msg_type == "voice":
                content = "[Voice]"
            else:
                content = f"[{event_msg_type}]"

            # Get message ID
            message_id = event.get("message_id", "")

            # Get timestamp
            timestamp = datetime.now()
            if "create_time" in event:
                timestamp = datetime.fromtimestamp(event["create_time"] / 1000)

            return Message(
                id=message_id,
                chat_jid=self.build_jid(chat_id),
                sender=self.build_jid(sender_id),
                sender_name=sender_name,
                content=content,
                timestamp=timestamp,
                is_from_me=False,
                role=MessageRole.USER,
            )
        except Exception:
            return None

    def parse_jid(self, jid: str) -> tuple[str, str]:
        """Parse a Feishu JID into open ID.

        Args:
            jid: The JID to parse (format: feishu:open_id).

        Returns:
            Tuple of (open_id, empty_resource).

        Raises:
            ValueError: If JID format is invalid.
        """
        if not jid.startswith("feishu:"):
            raise ValueError(f"Invalid Feishu JID: {jid}")

        open_id = jid[8:]  # Remove "feishu:" prefix
        if not open_id:
            raise ValueError(f"Invalid Feishu JID: {jid}")

        return open_id, ""

    def build_jid(self, platform_id: str, resource: str | None = None) -> str:
        """Build a Feishu JID from open ID.

        Args:
            platform_id: The open ID.
            resource: Optional resource (not used for Feishu).

        Returns:
            The formatted JID (format: feishu:open_id).
        """
        return f"feishu:{platform_id}"
