"""Container session management for interactive shell mode."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import AsyncGenerator

from nanogridbot.config import get_config
from nanogridbot.core.container_runner import (
    build_docker_command,
    cleanup_container,
    validate_group_mounts,
)


class ContainerSession:
    """Manages an interactive container session for shell mode."""

    def __init__(self, group_folder: str = "cli", session_id: str | None = None):
        """Initialize container session.

        Args:
            group_folder: The group folder name for this session.
            session_id: Optional session ID to resume an existing session.
        """
        self.group_folder = group_folder
        self.session_id = session_id or None
        self.container_name = f"ngb-shell-{group_folder}-{uuid.uuid4().hex[:8]}"
        self._process: asyncio.subprocess.Process | None = None
        self._ipc_dir: Path | None = None

    @property
    def is_alive(self) -> bool:
        """Check if the session is still running."""
        if self._process is None:
            return False
        # Use == instead of is to handle both real process and mock objects
        return self._process.returncode == None

    async def start(self) -> None:
        """Start the container and initialize the session."""
        config = get_config()
        group_jid = f"cli:{self.group_folder}"

        # Validate mounts
        mounts = await validate_group_mounts(self.group_folder, config.data_dir)

        # Build docker command (not --rm, so container persists)
        input_data = {
            "groupFolder": self.group_folder,
            "chatJid": group_jid,
            "sessionId": self.session_id,
        }
        cmd = build_docker_command(
            mounts=mounts,
            input_data=input_data,
            timeout=config.container_timeout,
        )

        # Create IPC directory
        ipc_base = config.data_dir / "ipc" / group_jid
        input_dir = ipc_base / "input"
        output_dir = ipc_base / "output"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        self._ipc_dir = ipc_base

        # Start the process
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Send initial configuration via stdin
        init_data = {
            "groupFolder": self.group_folder,
            "chatJid": group_jid,
            "sessionId": self.session_id,
        }
        if self._process.stdin:
            await self._process.stdin.write(json.dumps(init_data).encode())
            await self._process.stdin.drain()

    async def send(self, text: str) -> None:
        """Send a message to the container.

        Args:
            text: The text to send.

        Raises:
            RuntimeError: If the session has not been started.
        """
        if not self._ipc_dir:
            raise RuntimeError("Session not started")

        input_dir = self._ipc_dir / "input"

        # Write to IPC file
        timestamp = asyncio.get_event_loop().time()
        filename = f"input-{timestamp}.json"
        filepath = input_dir / filename

        data = {
            "text": text,
            "sender": "cli-user",
            "timestamp": timestamp,
        }

        filepath.write_text(json.dumps(data))

    async def close(self) -> None:
        """Close the container session."""
        if self._ipc_dir:
            # Write close sentinel
            sentinel = self._ipc_dir / "input" / "_close"
            sentinel.write_text(json.dumps({"action": "close"}))

        if self._process:
            # Close stdin and kill process
            if self._process.stdin:
                await self._process.stdin.close()
            if self.is_alive:
                self._process.kill()
            await self._process.wait()

        # Cleanup container
        await cleanup_container(self.container_name)

    async def receive(self) -> AsyncGenerator[str, None]:
        """Receive messages from the container.

        Yields:
            Text content from the container output.
        """
        if not self._ipc_dir:
            return

        output_dir = self._ipc_dir / "output"

        while self.is_alive:
            # Read output files
            try:
                for output_file in sorted(output_dir.glob("*.json")):
                    try:
                        data = json.loads(output_file.read_text())
                        # Update session ID before yielding (so it's updated even if caller breaks)
                        if "newSessionId" in data:
                            self.session_id = data["newSessionId"]
                        # Yield result if present
                        if "result" in data:
                            yield data["result"]
                        # Remove processed file
                        output_file.unlink()
                    except (json.JSONDecodeError, KeyError):
                        continue

                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
