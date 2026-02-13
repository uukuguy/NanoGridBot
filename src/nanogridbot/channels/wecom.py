"""WeCom (WeChat Work) channel implementation using webhook."""

from datetime import datetime
from typing import Any

import httpx

from nanogridbot.types import ChannelType, Message, MessageRole

from .base import Channel, ChannelRegistry


@ChannelRegistry.register(ChannelType.WECOM)
class WeComChannel(Channel):
    """WeCom channel implementation using webhook (Group Robot)."""

    def __init__(
        self,
        channel_type: ChannelType = ChannelType.WECOM,
        webhook_url: str | None = None,
        corp_id: str | None = None,
        corp_secret: str | None = None,
        agent_id: str | None = None,
    ) -> None:
        """Initialize WeCom channel.

        Args:
            channel_type: The channel type (default: WECOM).
            webhook_url: Webhook URL for group robot.
            corp_id: Corp ID for WeCom API (for user messaging).
            corp_secret: Corp Secret for WeCom API.
            agent_id: Agent ID for WeCom API.
        """
        super().__init__(channel_type)
        self._webhook_url = webhook_url
        self._corp_id = corp_id
        self._corp_secret = corp_secret
        self._agent_id = agent_id
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._http_client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        """Establish connection to WeCom."""
        self._http_client = httpx.AsyncClient(timeout=30.0)

        # If we have webhook URL, no need to get access token
        if self._webhook_url:
            await self._on_connected()
            return

        # Otherwise, get access token using corp credentials
        if not self._corp_id or not self._corp_secret:
            raise RuntimeError(
                "WeCom channel not configured. "
                "Provide webhook_url or (corp_id + corp_secret)."
            )

        await self._get_access_token()
        await self._on_connected()

    async def _get_access_token(self) -> str:
        """Get WeCom access token."""
        if not self._corp_id or not self._corp_secret:
            raise RuntimeError("WeCom corp credentials not configured")

        url = (
            f"https://qyapi.weixin.qq.com/cgi-bin/gettoken"
            f"?corpid={self._corp_id}&corpsecret={self._corp_secret}"
        )

        response = await self._http_client.get(url)
        data = response.json()

        if data.get("errcode") != 0:
            raise RuntimeError(f"Failed to get WeCom access token: {data}")

        self._access_token = data["access_token"]
        # Token expires in 7200 seconds
        self._token_expires_at = datetime.now().timestamp() + 7100
        return self._access_token

    async def _ensure_token(self) -> str:
        """Ensure access token is valid."""
        if not self._access_token or (
            self._token_expires_at and datetime.now().timestamp() > self._token_expires_at
        ):
            await self._get_access_token()
        return self._access_token

    async def disconnect(self) -> None:
        """Close connection to WeCom."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        await self._on_disconnected()

    async def send_message(self, chat_jid: str, content: str) -> str:
        """Send a message to a WeCom chat.

        Args:
            chat_jid: The JID of the chat (format: wecom:ww_xxx).
            content: The message content.

        Returns:
            The message ID of the sent message.
        """
        if not self._http_client:
            raise RuntimeError("WeCom channel not connected")

        # Use webhook if available
        if self._webhook_url:
            return await self._send_via_webhook(content)

        # Otherwise use API
        return await self._send_via_api(chat_jid, content)

    async def _send_via_webhook(self, content: str) -> str:
        """Send message via webhook."""
        payload = {"msgtype": "text", "text": {"content": content}}

        response = await self._http_client.post(
            self._webhook_url,
            json=payload,
        )

        data = response.json()
        if data.get("errcode") != 0:
            raise RuntimeError(f"Failed to send WeCom message: {data}")

        return f"webhook_{datetime.now().timestamp()}"

    async def _send_via_api(self, chat_jid: str, content: str) -> str:
        """Send message via WeCom API."""
        token = await self._ensure_token()

        # Parse JID to get user ID or chat ID
        _, user_id = self.parse_jid(chat_jid)

        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"

        payload = {
            "touser": user_id,
            "msgtype": "text",
            "agentid": self._agent_id,
            "text": {"content": content},
        }

        response = await self._http_client.post(url, json=payload)
        data = response.json()

        if data.get("errcode") != 0:
            raise RuntimeError(f"Failed to send WeCom message: {data}")

        return str(data.get("msgid", ""))

    async def receive_message(self, raw_data: dict[str, Any]) -> Message | None:
        """Parse and convert raw WeCom message to Message model.

        Args:
            raw_data: Raw message data from WeCom webhook.

        Returns:
            Parsed Message object, or None if parsing fails.
        """
        try:
            # Handle WeCom webhook payload
            msg_data = raw_data.get("message", raw_data)

            msg_type = msg_data.get("msgType", msg_data.get("msg_type"))
            if not msg_type:
                return None

            # Build JID
            from_user = msg_data.get("fromUserName", msg_data.get("from_user_name", ""))
            chat_jid = self.build_jid(from_user)

            # Get content based on type
            content = ""
            if msg_type == "text":
                content = msg_data.get("content", "")
            elif msg_type == "image":
                content = "[Image]"
            elif msg_type == "voice":
                content = "[Voice]"
            elif msg_type == "video":
                content = "[Video]"
            elif msg_type == "file":
                content = "[File]"
            elif msg_type == "location":
                content = "[Location]"
            else:
                content = f"[{msg_type}]"

            # Get timestamp
            create_time = msg_data.get("createTime", msg_data.get("create_time"))
            timestamp = datetime.now()
            if create_time:
                timestamp = datetime.fromtimestamp(int(create_time))

            return Message(
                id=str(msg_data.get("msgId", msg_data.get("msg_id", ""))),
                chat_jid=chat_jid,
                sender=from_user,
                sender_name=from_user,
                content=content,
                timestamp=timestamp,
                is_from_me=False,
                role=MessageRole.USER,
            )
        except Exception:
            return None

    def parse_jid(self, jid: str) -> tuple[str, str]:
        """Parse a WeCom JID into user ID.

        Args:
            jid: The JID to parse (format: wecom:ww_xxx).

        Returns:
            Tuple of (user_id, empty_resource).

        Raises:
            ValueError: If JID format is invalid.
        """
        if not jid.startswith("wecom:"):
            raise ValueError(f"Invalid WeCom JID: {jid}")

        user_id = jid[6:]  # Remove "wecom:" prefix
        if not user_id:
            raise ValueError(f"Invalid WeCom JID: {jid}")

        return user_id, ""

    def build_jid(self, platform_id: str, resource: str | None = None) -> str:
        """Build a WeCom JID from user ID.

        Args:
            platform_id: The user ID (ww_xxx format).
            resource: Optional resource (not used for WeCom).

        Returns:
            The formatted JID (format: wecom:ww_xxx).
        """
        return f"wecom:{platform_id}"
