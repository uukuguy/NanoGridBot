"""Slack channel implementation using python-slack-sdk."""

from datetime import datetime
from typing import Any

from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.web import WebClient

from nanogridbot.types import ChannelType, Message, MessageRole

from .base import Channel, ChannelRegistry


@ChannelRegistry.register(ChannelType.SLACK)
class SlackChannel(Channel):
    """Slack channel implementation using python-slack-sdk (Socket Mode)."""

    def __init__(
        self,
        channel_type: ChannelType = ChannelType.SLACK,
        bot_token: str | None = None,
        app_token: str | None = None,
    ) -> None:
        """Initialize Slack channel.

        Args:
            channel_type: The channel type (default: SLACK).
            bot_token: Slack Bot User OAuth Token (xoxb-...).
            app_token: Slack App Token (xapp-...) for Socket Mode.
        """
        super().__init__(channel_type)
        self._bot_token = bot_token
        self._app_token = app_token
        self._socket_client: SocketModeClient | None = None
        self._web_client: WebClient | None = None

    async def connect(self) -> None:
        """Establish connection to Slack via Socket Mode."""
        if not self._bot_token or not self._app_token:
            raise RuntimeError("Slack channel not configured. " "Provide bot_token and app_token.")

        self._web_client = WebClient(token=self._bot_token)

        # Create Socket Mode client
        self._socket_client = SocketModeClient(
            app_token=self._app_token,
            web_client=self._web_client,
            all_message_trace_enabled=True,
        )

        # Add message listener
        self._socket_client.socket_mode_request_listeners.append(self._handle_event)

        # Connect (this is blocking, run in thread)
        import threading

        thread = threading.Thread(target=self._socket_client.connect, daemon=True)
        thread.start()

        await self._on_connected()

    def _handle_event(self, client: SocketModeClient, req: Any) -> None:
        """Handle incoming Slack events."""
        if req.type == "events_api":
            # Acknowledge the event
            from slack_sdk.socket_mode.response import SocketModeResponse

            response = SocketModeResponse(envelope_id=req.envelope_id)
            client.send_socket_mode_response(response)

            # Process the event
            payload = req.payload
            event = payload.get("event", {})
            event_type = event.get("type")

            if event_type == "message":
                # Handle message event
                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._process_message(event))
                finally:
                    loop.close()

    async def _process_message(self, event: dict[str, Any]) -> None:
        """Process a Slack message event."""
        message = await self.receive_message({"event": event})
        if message:
            await self._on_message_received(
                message_id=message.id,
                chat_jid=message.chat_jid,
                sender=message.sender,
                sender_name=message.sender_name or "",
                content=message.content,
            )

    async def disconnect(self) -> None:
        """Close connection to Slack."""
        if self._socket_client:
            self._socket_client.close()
            self._socket_client = None
        self._web_client = None
        await self._on_disconnected()

    async def send_message(self, chat_jid: str, content: str) -> str:
        """Send a message to a Slack channel or user.

        Args:
            chat_jid: The JID of the chat (format: slack:C1234567890 or slack:U1234567890).
            content: The message content.

        Returns:
            The message ID of the sent message.
        """
        if not self._web_client:
            raise RuntimeError("Slack channel not connected")

        channel_id, _ = self.parse_jid(chat_jid)

        # Use sync client in thread pool
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        def _send():
            response = self._web_client.chat_postMessage(
                channel=channel_id,
                text=content,
            )
            return response["ts"]

        loop = asyncio.get_event_loop()
        ts = await loop.run_in_executor(ThreadPoolExecutor(), _send)
        await self._on_message_sent(ts, chat_jid, content)
        return ts

    async def receive_message(self, raw_data: dict[str, Any]) -> Message | None:
        """Parse and convert raw Slack message to Message model.

        Args:
            raw_data: Raw message data from Slack event.

        Returns:
            Parsed Message object, or None if parsing fails.
        """
        try:
            event = raw_data.get("event", {})
            if not event:
                return None

            # Get message details
            msg_type = event.get("type")
            if msg_type != "message":
                return None

            # Skip bot messages and edits
            if event.get("subtype") in ("bot_message", "message_changed", "message_deleted"):
                return None

            # Get sender info
            user = event.get("user", "")
            sender_name = event.get("username", "")

            # Get channel
            channel = event.get("channel", "")

            # Build JID
            chat_jid = self.build_jid(channel)

            # Get content
            content = event.get("text", "")

            # Get timestamp
            ts = event.get("ts", "")
            timestamp = datetime.now()
            if ts:
                timestamp = datetime.fromtimestamp(float(ts))

            return Message(
                id=ts,
                chat_jid=chat_jid,
                sender=user,
                sender_name=sender_name,
                content=content,
                timestamp=timestamp,
                is_from_me=False,
                role=MessageRole.USER,
            )
        except Exception:
            return None

    def parse_jid(self, jid: str) -> tuple[str, str]:
        """Parse a Slack JID into channel/user ID.

        Args:
            jid: The JID to parse (format: slack:C1234567890 or slack:U1234567890).

        Returns:
            Tuple of (channel_or_user_id, resource).

        Raises:
            ValueError: If JID format is invalid.
        """
        if not jid.startswith("slack:"):
            raise ValueError(f"Invalid Slack JID: {jid}")

        rest = jid[6:]  # Remove "slack:" prefix
        if not rest:
            raise ValueError(f"Invalid Slack JID: {jid}")

        # Check if it's a channel (C) or user (U)
        if len(rest) > 1:
            id_part = rest[1:]  # Remove prefix char
            return id_part, rest

        return rest, ""

    def build_jid(self, platform_id: str, resource: str | None = None) -> str:
        """Build a Slack JID from channel/user ID.

        Args:
            platform_id: The channel or user ID (C1234567890 or U1234567890).
            resource: Optional resource (not used for Slack).

        Returns:
            The formatted JID (format: slack:C1234567890 or slack:U1234567890).
        """
        # Determine prefix based on ID format
        if platform_id.startswith("C"):
            return f"slack:{platform_id}"
        elif platform_id.startswith("U"):
            return f"slack:{platform_id}"
        elif platform_id.startswith("G"):
            return f"slack:{platform_id}"
        else:
            # Default to user
            return f"slack:U{platform_id}"
