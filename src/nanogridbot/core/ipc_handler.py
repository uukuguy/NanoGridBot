"""IPC (Inter-Process Communication) handler for container messaging."""

import asyncio
import json
from pathlib import Path
from typing import Any

from nanogridbot.channels.base import Channel
from nanogridbot.config import get_config
from nanogridbot.database import Database


class IpcHandler:
    """Handles IPC communication with container processes."""

    def __init__(self, config: "get_config", db: Database, channels: list[Channel]):
        """Initialize IPC handler.

        Args:
            config: Application configuration
            db: Database instance
            channels: List of channel instances
        """
        self.config = config
        self.db = db
        self.channels = channels
        self._running = False
        self._watchers: dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        """Start the IPC handler."""
        from loguru import logger

        self._running = True
        logger.info("IPC handler started")

        # Start watching IPC directories for all groups
        await self._watch_all_groups()

    async def stop(self) -> None:
        """Stop the IPC handler."""
        from loguru import logger

        self._running = False

        # Cancel all watchers
        for watcher in self._watchers.values():
            watcher.cancel()
            try:
                await watcher
            except asyncio.CancelledError:
                pass

        self._watchers.clear()
        logger.info("IPC handler stopped")

    async def _watch_all_groups(self) -> None:
        """Start watching IPC directories for all groups."""
        from loguru import logger

        # Get all registered groups
        groups = await self.db.get_registered_groups()

        for group in groups:
            await self._watch_group(group.jid)

        logger.info(f"Watching IPC for {len(groups)} groups")

    async def _watch_group(self, jid: str) -> None:
        """Start watching IPC directory for a group.

        Args:
            jid: Group JID
        """
        if jid in self._watchers:
            return

        task = asyncio.create_task(self._watch_group_loop(jid))
        self._watchers[jid] = task

    async def _watch_group_loop(self, jid: str) -> None:
        """Watch loop for a group's IPC directory.

        Args:
            jid: Group JID
        """
        from loguru import logger

        ipc_dir = self.config.data_dir / "ipc" / jid
        input_dir = ipc_dir / "input"
        output_dir = ipc_dir / "output"

        # Create directories
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Track processed files
        processed: set[str] = set()

        while self._running:
            try:
                # Check for new input files
                for file_path in input_dir.glob("*.json"):
                    if file_path.name not in processed:
                        await self._process_input_file(jid, file_path)
                        processed.add(file_path.name)

                # Check for new output files
                for file_path in output_dir.glob("*.json"):
                    if file_path.name not in processed:
                        await self._process_output_file(jid, file_path)
                        processed.add(file_path.name)

                await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"IPC watch error for {jid}: {e}")
                await asyncio.sleep(1)

    async def _process_input_file(self, jid: str, file_path: Path) -> None:
        """Process an input IPC file.

        Args:
            jid: Group JID
            file_path: Path to input file
        """
        from loguru import logger

        try:
            content = file_path.read_text()
            data = json.loads(content)

            logger.debug(f"IPC input for {jid}: {data}")

            # TODO: Send to container via stdin or forward to active container

        except Exception as e:
            logger.error(f"Error processing IPC input {file_path}: {e}")

    async def _process_output_file(self, jid: str, file_path: Path) -> None:
        """Process an output IPC file.

        Args:
            jid: Group JID
            file_path: Path to output file
        """
        from loguru import logger

        try:
            content = file_path.read_text()
            data = json.loads(content)

            logger.debug(f"IPC output for {jid}: {data}")

            # Send result to channel
            result = data.get("result") or data.get("text")
            if result:
                await self._send_to_channel(jid, result)

        except Exception as e:
            logger.error(f"Error processing IPC output {file_path}: {e}")

    async def _send_to_channel(self, jid: str, text: str) -> None:
        """Send text to the appropriate channel.

        Args:
            jid: Target JID
            text: Text to send
        """
        # Find channel that owns this JID
        for channel in self.channels:
            if channel.owns_jid(jid):
                try:
                    await channel.send_message(jid, text)
                except Exception as e:
                    from loguru import logger

                    logger.error(f"Error sending to channel {channel.name}: {e}")
                break

    async def write_input(self, jid: str, sender: str, text: str) -> str:
        """Write input to IPC directory.

        Args:
            jid: Group JID
            sender: Sender name
            text: Message text

        Returns:
            Filename
        """
        from datetime import datetime

        ipc_dir = self.config.data_dir / "ipc" / jid / "input"
        ipc_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().isoformat()
        filename = f"{timestamp}.json"
        file_path = ipc_dir / filename

        file_path.write_text(
            json.dumps(
                {
                    "sender": sender,
                    "text": text,
                    "timestamp": timestamp,
                }
            )
        )

        return filename

    async def write_output(self, jid: str, result: str, session_id: str | None = None) -> str:
        """Write output to IPC directory.

        Args:
            jid: Group JID
            result: Result text
            session_id: Optional session ID

        Returns:
            Filename
        """
        from datetime import datetime

        ipc_dir = self.config.data_dir / "ipc" / jid / "output"
        ipc_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().isoformat()
        filename = f"{timestamp}.json"
        file_path = ipc_dir / filename

        data = {
            "result": result,
            "timestamp": timestamp,
        }

        if session_id:
            data["sessionId"] = session_id

        file_path.write_text(json.dumps(data))

        return filename
