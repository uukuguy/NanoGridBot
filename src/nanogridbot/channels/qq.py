"""QQ channel implementation using NoneBot2 with OneBot protocol."""

from datetime import datetime
from typing import Any

from nanogridbot.types import ChannelType, Message, MessageRole

from .base import Channel, ChannelRegistry


@ChannelRegistry.register(ChannelType.QQ)
class QQChannel(Channel):
    """QQ channel implementation using NoneBot2 with OneBot protocol."""

    def __init__(
        self,
        channel_type: ChannelType = ChannelType.QQ,
        host: str = "127.0.0.1",
        port: int = 20000,
    ) -> None:
        """Initialize QQ channel.

        Args:
            channel_type: The channel type (default: QQ).
            host: OneBot server host (default: 127.0.0.1).
            port: OneBot server port (default: 20000).
        """
        super().__init__(channel_type)
        self._host = host
        self._port = port
        self._connected = False

    async def connect(self) -> None:
        """Establish connection to QQ via OneBot.

        Note: This establishes a connection TO the OneBot server (like NapCat).
        The actual QQ connection is managed by the OneBot server.
        """
        # In a typical deployment:
        # 1. NapCat or similar OneBot server runs and manages QQ connection
        # 2. This client connects to the OneBot HTTP/WebSocket server
        # 3. Events are received via WebSocket, messages sent via HTTP

        # For now, we mark as connected - actual implementation would
        # establish WebSocket connection to OneBot server
        self._connected = True
        await self._on_connected()

    async def disconnect(self) -> None:
        """Close connection to QQ."""
        self._connected = False
        await self._on_disconnected()

    async def send_message(self, chat_jid: str, content: str) -> str:
        """Send a message to a QQ chat.

        Args:
            chat_jid: The JID of the chat (format: qq:group_id or qq:user_id).
            content: The message content.

        Returns:
            The message ID of the sent message.
        """
        if not self._connected:
            raise RuntimeError("QQ channel not connected")

        _, target_id = self.parse_jid(chat_jid)

        # In a real implementation, this would call the OneBot API
        # Example: POST /send_private_msg or /send_group_msg
        # For now, return a placeholder message ID
        import uuid

        return f"msg_{uuid.uuid4().hex[:8]}"

    async def receive_message(self, raw_data: dict[str, Any]) -> Message | None:
        """Parse and convert raw QQ message to Message model.

        Args:
            raw_data: Raw message data from OneBot webhook/event.

        Returns:
            Parsed Message object, or None if parsing fails.
        """
        try:
            # OneBot v11/v12 event format
            # {
            #     "post_type": "message",
            #     "message_type": "group" | "private",
            #     "sub_type": "friend" | "group" | "anonymous",
            #     "message_id": "xxx",
            #     "user_id": 123456,
            #     "message": "[CQ:xxx,...]",
            #     "raw_message": "...",
            #     "font": 0,
            #     "sender": {...},
            #     "group_id": 123456789,  # for group messages
            # }

            post_type = raw_data.get("post_type")
            if post_type != "message":
                return None

            message_type = raw_data.get("message_type", "private")
            message_id = str(raw_data.get("message_id", ""))
            user_id = str(raw_data.get("user_id", ""))
            raw_message = raw_data.get("raw_message", "")
            message = raw_data.get("message", "")

            # Get sender info
            sender = raw_data.get("sender", {})
            sender_nick = sender.get("nickname", "") or sender.get("card", "")

            # Determine chat JID
            if message_type == "group":
                group_id = str(raw_data.get("group_id", ""))
                chat_jid = self.build_jid(f"group_{group_id}")
            else:
                chat_jid = self.build_jid(user_id)

            # Parse message content (simplified - real implementation would parse CQ codes)
            content = self._parse_message_content(message or raw_message)

            # Get timestamp
            timestamp = datetime.now()
            if "time" in raw_data:
                timestamp = datetime.fromtimestamp(raw_data["time"])

            return Message(
                id=message_id,
                chat_jid=chat_jid,
                sender=self.build_jid(user_id),
                sender_name=sender_nick,
                content=content,
                timestamp=timestamp,
                is_from_me=False,
                role=MessageRole.USER,
            )
        except Exception:
            return None

    def _parse_message_content(self, message: str) -> str:
        """Parse QQ message content, handling CQ codes.

        Args:
            message: Raw message with CQ codes.

        Returns:
            Parsed message content.
        """
        import re

        # Replace common CQ codes with readable text
        replacements = [
            (r"\[CQ:at,qq=all\]", "@所有人"),
            (r"\[CQ:at,qq=(\d+)\]", "@\\1"),
            (r"\[CQ:image,file=([^,]+),.*\]", "[图片]"),
            (r"\[CQ:voice,file=([^,]+),.*\]", "[语音]"),
            (r"\[CQ:video,file=([^,]+),.*\]", "[视频]"),
            (r"\[CQ:file,file=([^,]+),.*\]", "[文件]"),
            (r"\[CQ:face,id=(\d+)\]", "[表情]"),
            (r"\[CQ:share,url=([^,]+),title=([^\]]+)\]", "[分享: \\2]"),
            (r"\[CQ:location,lat=([^,]+),lon=([^\]]+)\]", "[位置]"),
            (r"\[CQ:json,.*\]", "[JSON]"),
            (r"\[CQ:xml,.*\]", "[XML]"),
        ]

        content = message
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)

        return content

    def parse_jid(self, jid: str) -> tuple[str, str]:
        """Parse a QQ JID into user/group ID.

        Args:
            jid: The JID to parse (format: qq:123456789 or qq:group_123456789).

        Returns:
            Tuple of (user_id_or_group_id, empty_resource).

        Raises:
            ValueError: If JID format is invalid.
        """
        if not jid.startswith("qq:"):
            raise ValueError(f"Invalid QQ JID: {jid}")

        platform_id = jid[3:]  # Remove "qq:" prefix
        if not platform_id:
            raise ValueError(f"Invalid QQ JID: {jid}")

        return platform_id, ""

    def build_jid(self, platform_id: str, resource: str | None = None) -> str:
        """Build a QQ JID from user/group ID.

        Args:
            platform_id: The user ID or group ID (use "group_" prefix for groups).
            resource: Optional resource (not used for QQ).

        Returns:
            The formatted JID (format: qq:123456789 or qq:group_123456789).
        """
        return f"qq:{platform_id}"
