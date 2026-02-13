"""DingTalk channel implementation using dingtalk-stream SDK."""

from datetime import datetime
from typing import Any

from dingtalk_stream import CallbackMessage, DingTalkStreamClient, EventHandler

from nanogridbot.types import ChannelType, Message, MessageRole

from .base import Channel, ChannelRegistry


class DingTalkEventHandlerImpl(EventHandler):
    """DingTalk event handler implementation."""

    def __init__(self, channel: "DingTalkChannel") -> None:
        """Initialize handler with channel reference."""
        super().__init__()
        self._channel = channel

    async def process(self, callback: CallbackMessage) -> None:
        """Process incoming DingTalk events."""
        # Handle text messages
        if callback.event_type == "im.message.recv":
            data = callback.data
            if data and "text" in data:
                msg_type = data.get("msgType", "text")
                conversation_id = data.get("conversationId", "")
                sender_id = data.get("senderId", "")
                sender_nick = data.get("senderNick", "")
                content = data.get("text", {}).get("content", "")
                message_id = data.get("messageId", "")

                # Convert to Message and emit event
                chat_jid = self._channel.build_jid(conversation_id)
                sender = self._channel.build_jid(sender_id)

                await self._channel._on_message_received(
                    message_id=message_id,
                    chat_jid=chat_jid,
                    sender=sender,
                    sender_name=sender_nick,
                    content=content,
                )


@ChannelRegistry.register(ChannelType.DINGTALK)
class DingTalkChannel(Channel):
    """DingTalk channel implementation using dingtalk-stream SDK."""

    def __init__(
        self,
        channel_type: ChannelType = ChannelType.DINGTALK,
        app_key: str | None = None,
        app_secret: str | None = None,
    ) -> None:
        """Initialize DingTalk channel.

        Args:
            channel_type: The channel type (default: DINGTALK).
            app_key: DingTalk App Key.
            app_secret: DingTalk App Secret.
        """
        super().__init__(channel_type)
        self._app_key = app_key
        self._app_secret = app_secret
        self._client: DingTalkStreamClient | None = None
        self._event_handler: DingTalkEventHandlerImpl | None = None

    async def connect(self) -> None:
        """Establish connection to DingTalk."""
        if not self._app_key or not self._app_secret:
            raise RuntimeError("DingTalk app_key and app_secret not configured")

        self._client = DingTalkStreamClient(
            app_key=self._app_key,
            app_secret=self._app_secret,
        )

        # Register event handler
        self._event_handler = DingTalkEventHandlerImpl(self)
        self._client.register_event_handler(
            "im.message.recv",
            self._event_handler,
        )

        # Start the client
        await self._client.start()
        await self._on_connected()

    async def disconnect(self) -> None:
        """Close connection to DingTalk."""
        if self._client:
            await self._client.stop()
            self._client = None
            self._event_handler = None
        await self._on_disconnected()

    async def send_message(self, chat_jid: str, content: str) -> str:
        """Send a message to a DingTalk chat.

        Args:
            chat_jid: The JID of the chat (format: dingtalk:conversation_id).
            content: The message content.

        Returns:
            The message ID of the sent message.
        """
        if not self._client:
            raise RuntimeError("DingTalk channel not connected")

        _, conversation_id = self.parse_jid(chat_jid)

        # Use robot SDK to send message
        # Note: In production, you'd use the chat_id to send to specific conversations
        # This is a simplified implementation
        try:
            from dingtalk_stream import ChatbotMessage

            robot = ChatbotMessage(
                app_key=self._app_key,
                app_secret=self._app_secret,
            )
            # Send text message to conversation
            result = await robot.send(
                conversation_id=conversation_id,
                msg_type="text",
                content={"text": content},
            )
            return result.get("message_id", "")
        except Exception:
            # Fallback: return empty message ID
            return ""

    async def receive_message(self, raw_data: dict[str, Any]) -> Message | None:
        """Parse and convert raw DingTalk message to Message model.

        Args:
            raw_data: Raw message data from DingTalk webhook/event.

        Returns:
            Parsed Message object, or None if parsing fails.
        """
        try:
            data = raw_data.get("data", {})
            if not data:
                return None

            # Handle different message types
            msg_type = data.get("msgType", "text")

            content = ""
            if msg_type == "text":
                content = data.get("text", {}).get("content", "")
            elif msg_type == "image":
                content = "[Image]"
            elif msg_type == "file":
                content = "[File]"
            elif msg_type == "voice":
                content = "[Voice]"
            else:
                content = f"[{msg_type}]"

            sender_id = data.get("senderId", "")
            sender_nick = data.get("senderNick", "")
            conversation_id = data.get("conversationId", "")
            message_id = data.get("messageId", "")
            timestamp_ms = data.get("createAt", 0)

            timestamp = (
                datetime.fromtimestamp(timestamp_ms / 1000) if timestamp_ms else datetime.now()
            )

            return Message(
                id=message_id,
                chat_jid=self.build_jid(conversation_id),
                sender=self.build_jid(sender_id),
                sender_name=sender_nick,
                content=content,
                timestamp=timestamp,
                is_from_me=False,
                role=MessageRole.USER,
            )
        except Exception:
            return None

    def parse_jid(self, jid: str) -> tuple[str, str]:
        """Parse a DingTalk JID into conversation ID.

        Args:
            jid: The JID to parse (format: dingtalk:conversation_id).

        Returns:
            Tuple of (conversation_id, empty_resource).

        Raises:
            ValueError: If JID format is invalid.
        """
        if not jid.startswith("dingtalk:"):
            raise ValueError(f"Invalid DingTalk JID: {jid}")

        conversation_id = jid[10:]  # Remove "dingtalk:" prefix
        if not conversation_id:
            raise ValueError(f"Invalid DingTalk JID: {jid}")

        return conversation_id, ""

    def build_jid(self, platform_id: str, resource: str | None = None) -> str:
        """Build a DingTalk JID from conversation ID.

        Args:
            platform_id: The conversation ID.
            resource: Optional resource (not used for DingTalk).

        Returns:
            The formatted JID (format: dingtalk:conversation_id).
        """
        return f"dingtalk:{platform_id}"
