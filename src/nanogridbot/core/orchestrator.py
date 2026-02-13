"""Main orchestrator for NanoGridBot."""

import asyncio
import signal
from typing import Any

from loguru import logger

from nanogridbot.channels.base import Channel
from nanogridbot.config import get_config
from nanogridbot.core.group_queue import GroupQueue
from nanogridbot.core.ipc_handler import IpcHandler
from nanogridbot.core.router import MessageRouter
from nanogridbot.core.task_scheduler import TaskScheduler
from nanogridbot.database import Database
from nanogridbot.types import Message, RegisteredGroup
from nanogridbot.utils.error_handling import GracefulShutdown, with_retry


class Orchestrator:
    """Main orchestrator that coordinates all components."""

    def __init__(
        self,
        config: "get_config",
        db: Database,
        channels: list[Channel],
    ):
        """Initialize the orchestrator.

        Args:
            config: Application configuration
            db: Database instance
            channels: List of channel instances
        """
        self.config = config
        self.db = db
        self.channels = channels

        # Global state
        self.last_timestamp: str | None = None
        self.sessions: dict[str, str] = {}
        self.registered_groups: dict[str, RegisteredGroup] = {}
        self.last_agent_timestamp: dict[str, str] = {}

        # Subsystems
        self.queue = GroupQueue(config, db)
        self.scheduler = TaskScheduler(config, db, self.queue)
        self.ipc_handler = IpcHandler(config, db, channels)
        self.router = MessageRouter(config, db, channels)

        # Running flag and graceful shutdown
        self._running = False
        self._shutdown = GracefulShutdown()
        self._startup_complete = False

        # Health status
        self._health_status: dict[str, Any] = {
            "healthy": False,
            "channels_connected": 0,
            "channels_total": len(channels),
            "registered_groups": 0,
            "active_containers": 0,
            "pending_tasks": 0,
            "uptime_seconds": 0,
        }

    async def start(self) -> None:
        """Start the orchestrator."""
        import time

        logger.info("Starting NanoGridBot orchestrator")

        # Setup signal handlers
        self._setup_signal_handlers()

        # Load state
        await self._load_state()

        # Connect all channels with retry
        await self._connect_channels_with_retry()

        # Start subsystems
        self._running = True
        await self.scheduler.start()
        await self.ipc_handler.start()
        await self.router.start()

        # Mark startup complete
        self._startup_complete = True
        self._health_status["healthy"] = True
        self._health_status["registered_groups"] = len(self.registered_groups)
        self._health_status["startup_time"] = time.time()

        logger.info("NanoGridBot orchestrator started successfully")

        # Start message polling
        await self._message_loop()

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown signal handlers."""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self._shutdown.request_shutdown()

        # Register signal handlers
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except (ValueError, OSError):
            # May fail in some environments (e.g., Windows)
            logger.warning("Could not register signal handlers")

    async def stop(self) -> None:
        """Stop the orchestrator gracefully."""
        logger.info("Stopping orchestrator gracefully...")
        self._running = False

        # Save state
        await self._save_state()

        # Disconnect channels
        await self._disconnect_channels()

        # Stop subsystems
        await self.scheduler.stop()
        await self.ipc_handler.stop()
        await self.router.stop()

        # Mark as unhealthy
        self._health_status["healthy"] = False

        # Signal shutdown complete
        await self._shutdown.shutdown_complete()

        logger.info("Orchestrator stopped gracefully")

    def get_health_status(self) -> dict[str, Any]:
        """Get current health status of the orchestrator.

        Returns:
            Dictionary with health metrics
        """
        import time

        self._health_status["channels_connected"] = sum(
            1 for ch in self.channels if getattr(ch, "_connected", False)
        )
        self._health_status["registered_groups"] = len(self.registered_groups)
        self._health_status["active_containers"] = self.queue.active_count

        # Calculate uptime
        if "startup_time" in self._health_status:
            self._health_status["uptime_seconds"] = int(
                time.time() - self._health_status["startup_time"]
            )

        # Overall health
        self._health_status["healthy"] = (
            self._startup_complete and self._health_status["channels_connected"] > 0
        )

        return self._health_status.copy()

    async def _load_state(self) -> None:
        """Load state from database."""
        # Load router state
        state = await self.db.get_router_state()

        self.last_timestamp = state.get("last_timestamp")
        self.sessions = state.get("sessions", {})
        self.last_agent_timestamp = state.get("last_agent_timestamp", {})

        # Load registered groups
        groups = await self.db.get_groups()
        self.registered_groups = {g.jid: g for g in groups}

        logger.info(f"Loaded {len(self.registered_groups)} registered groups")

    async def _save_state(self) -> None:
        """Save state to database."""
        await self.db.save_router_state(
            {
                "last_timestamp": self.last_timestamp,
                "sessions": self.sessions,
                "last_agent_timestamp": self.last_agent_timestamp,
            }
        )

        logger.info("State saved")

    async def _connect_channels(self) -> None:
        """Connect all channels."""
        for channel in self.channels:
            try:
                await channel.connect()
                logger.info(f"Connected channel: {channel.name}")
            except Exception as e:
                logger.error(f"Failed to connect channel {channel.name}: {e}")

    async def _connect_channels_with_retry(self) -> None:
        """Connect all channels with retry on failure."""
        max_retries = 3
        retry_delay = 5

        for channel in self.channels:
            for attempt in range(max_retries + 1):
                try:
                    await channel.connect()
                    logger.info(f"Connected channel: {channel.name}")
                    break
                except Exception as e:
                    if attempt < max_retries:
                        logger.warning(
                            f"Failed to connect channel {channel.name} "
                            f"(attempt {attempt + 1}/{max_retries + 1}), "
                            f"retrying in {retry_delay}s: {e}"
                        )
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.error(
                            f"Failed to connect channel {channel.name} after {max_retries} retries: {e}"
                        )

    async def _disconnect_channels(self) -> None:
        """Disconnect all channels."""
        for channel in self.channels:
            try:
                await channel.disconnect()
                logger.info(f"Disconnected channel: {channel.name}")
            except Exception as e:
                logger.error(f"Error disconnecting channel {channel.name}: {e}")

    async def _message_loop(self) -> None:
        """Main message polling loop."""
        poll_interval = self.config.poll_interval / 1000  # Convert ms to seconds

        while self._running and not self._shutdown.is_shutting_down:
            try:
                # Check for shutdown
                if self._shutdown.is_shutting_down:
                    logger.info("Message loop detected shutdown signal, exiting...")
                    break

                # Get new messages from all channels
                messages = await self.db.get_new_messages(self.last_timestamp)

                if messages:
                    # Group messages by chat
                    grouped = self._group_messages(messages)

                    # Process each group
                    for jid, group_messages in grouped.items():
                        # Check for shutdown before each group
                        if self._shutdown.is_shutting_down:
                            break
                        await self._process_group_messages(jid, group_messages)

                    # Update timestamp
                    self.last_timestamp = messages[-1].timestamp.isoformat()

                # Wait for next poll
                await asyncio.sleep(poll_interval)

            except asyncio.CancelledError:
                logger.info("Message loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in message loop: {e}")
                # Use shorter sleep on error to recover faster
                await asyncio.sleep(min(poll_interval, 1))

    def _group_messages(self, messages: list[Message]) -> dict[str, list[Message]]:
        """Group messages by chat JID.

        Args:
            messages: List of messages

        Returns:
            Dict mapping chat JID to messages
        """
        groups: dict[str, list[Message]] = {}

        for msg in messages:
            if msg.chat_jid not in groups:
                groups[msg.chat_jid] = []
            groups[msg.chat_jid].append(msg)

        return groups

    async def _process_group_messages(self, jid: str, messages: list[Message]) -> None:
        """Process messages for a group.

        Args:
            jid: Group JID
            messages: Messages for the group
        """
        group = self.registered_groups.get(jid)

        if not group:
            logger.debug(f"Group {jid} not registered, skipping")
            return

        # Check trigger pattern
        if group.requires_trigger:
            triggered = any(
                self._check_trigger(msg.content, group.trigger_pattern) for msg in messages
            )
            if not triggered:
                return

        # Enqueue for processing
        await self.queue.enqueue_message_check(
            jid=jid,
            group=group,
            session_id=self.sessions.get(jid),
            last_timestamp=self.last_agent_timestamp.get(jid),
        )

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

    async def register_group(self, group: RegisteredGroup) -> None:
        """Register a new group.

        Args:
            group: Group to register
        """
        await self.db.save_group(group)
        self.registered_groups[group.jid] = group
        logger.info(f"Registered group: {group.jid}")

    async def unregister_group(self, jid: str) -> None:
        """Unregister a group.

        Args:
            jid: Group JID to unregister
        """
        await self.db.delete_group(jid)
        self.registered_groups.pop(jid, None)
        logger.info(f"Unregistered group: {jid}")

    async def send_to_group(self, jid: str, text: str) -> None:
        """Send a message to a group.

        Args:
            jid: Group JID
            text: Message text
        """
        await self.router.send_response(jid, text)
