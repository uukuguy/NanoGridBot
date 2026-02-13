"""Group queue manager for managing concurrent group processing."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from nanogridbot.config import get_config
from nanogridbot.database import Database
from nanogridbot.types import ContainerConfig, ContainerOutput, RegisteredGroup, ScheduledTask
from nanogridbot.utils.formatting import format_messages_xml


@dataclass
class GroupState:
    """State for a group in the queue."""

    jid: str
    active: bool = False
    pending_messages: bool = False
    pending_tasks: list[ScheduledTask] = field(default_factory=list)
    container_name: str | None = None
    group_folder: str | None = None
    retry_count: int = 0


class GroupQueue:
    """Manages concurrent processing of group messages and tasks."""

    def __init__(self, config: "get_config", db: Database):
        """Initialize the group queue.

        Args:
            config: Application configuration
            db: Database instance
        """
        self.config = config
        self.db = db
        self.states: dict[str, GroupState] = {}
        self.active_count = 0
        self.waiting_groups: list[str] = []
        self._lock = asyncio.Lock()

    async def enqueue_message_check(
        self,
        jid: str,
        group: RegisteredGroup,
        session_id: str | None,
        last_timestamp: str | None,
    ) -> None:
        """Enqueue a message check for a group.

        Args:
            jid: Group JID
            group: Registered group configuration
            session_id: Current session ID
            last_timestamp: Last processed message timestamp
        """
        async with self._lock:
            state = self._get_state(jid, group.folder)

            if state.active:
                # Group is processing, mark as pending
                state.pending_messages = True
                await self._send_follow_up_messages(jid, last_timestamp)
            else:
                # Try to start container
                await self._try_start_container(jid, group, session_id, last_timestamp)

    async def enqueue_task(
        self,
        jid: str,
        group: RegisteredGroup,
        task: ScheduledTask,
        session_id: str | None,
    ) -> None:
        """Enqueue a scheduled task for a group.

        Args:
            jid: Group JID
            group: Registered group configuration
            task: Scheduled task
            session_id: Current session ID
        """
        async with self._lock:
            state = self._get_state(jid, group.folder)

            if state.active:
                # Tasks have higher priority than messages
                state.pending_tasks.insert(0, task)
            else:
                await self._try_start_task(jid, group, task, session_id)

    async def _try_start_container(
        self,
        jid: str,
        group: RegisteredGroup,
        session_id: str | None,
        last_timestamp: str | None,
    ) -> None:
        """Try to start a container for the group.

        Args:
            jid: Group JID
            group: Registered group configuration
            session_id: Current session ID
            last_timestamp: Last processed message timestamp
        """
        from loguru import logger

        # Check concurrency limit
        if self.active_count >= self.config.container_max_concurrent_containers:
            if jid not in self.waiting_groups:
                self.waiting_groups.append(jid)
            logger.debug(f"Group {jid} waiting, active: {self.active_count}")
            return

        # Start container
        state = self._get_state(jid, group.folder)
        state.active = True
        self.active_count += 1

        try:
            # Get messages since last timestamp
            messages = await self.db.get_messages_since(jid, last_timestamp)

            # Format messages as XML
            prompt = format_messages_xml(
                [
                    {
                        "sender": msg.sender,
                        "sender_name": msg.sender_name,
                        "content": msg.content,
                        "timestamp": msg.timestamp,
                        "is_from_me": msg.is_from_me,
                    }
                    for msg in messages
                ]
            )

            # Create container config if specified
            container_config: ContainerConfig | None = None
            if group.container_config:
                container_config = ContainerConfig(**group.container_config)

            # Import here to avoid circular dependency
            from nanogridbot.core.container_runner import run_container_agent

            # Run container
            result = await run_container_agent(
                group_folder=group.folder,
                prompt=prompt,
                session_id=session_id,
                chat_jid=jid,
                is_main=(group.folder == "main"),
                container_config=container_config,
            )

            # Handle result
            await self._handle_container_result(jid, result, group, session_id)

        except Exception as e:
            logger.error(f"Container error for {jid}: {e}")
            state.retry_count += 1

            if state.retry_count < 5:
                # Exponential backoff retry
                delay = 5 * (2 ** (state.retry_count - 1))
                logger.info(f"Retrying {jid} in {delay}s (attempt {state.retry_count})")
                await asyncio.sleep(delay)
                await self._try_start_container(jid, group, session_id, last_timestamp)
            else:
                logger.error(f"Max retries reached for {jid}, dropping")

        finally:
            # Clean up state
            state.active = False
            state.retry_count = 0
            self.active_count -= 1

            # Process pending items
            await self._drain_pending(jid, group, session_id)

            # Wake up waiting groups
            await self._drain_waiting()

    async def _try_start_task(
        self,
        jid: str,
        group: RegisteredGroup,
        task: ScheduledTask,
        session_id: str | None,
    ) -> None:
        """Try to start a task for the group.

        Args:
            jid: Group JID
            group: Registered group configuration
            task: Scheduled task
            session_id: Current session ID
        """
        from loguru import logger

        # Check concurrency limit
        if self.active_count >= self.config.container_max_concurrent_containers:
            if jid not in self.waiting_groups:
                self.waiting_groups.append(jid)
            return

        # Start task
        state = self._get_state(jid, group.folder)
        state.active = True
        self.active_count += 1

        try:
            # Create container config if specified
            container_config: ContainerConfig | None = None
            if group.container_config:
                container_config = ContainerConfig(**group.container_config)

            # Import here to avoid circular dependency
            from nanogridbot.core.container_runner import run_container_agent

            # Run container with task prompt
            result = await run_container_agent(
                group_folder=group.folder,
                prompt=task.prompt,
                session_id=session_id,
                chat_jid=jid,
                is_main=(group.folder == "main"),
                container_config=container_config,
            )

            # Handle result
            await self._handle_container_result(jid, result, group, session_id)

        except Exception as e:
            logger.error(f"Task error for {jid}: {e}")

        finally:
            # Clean up state
            state.active = False
            self.active_count -= 1

            # Process pending items
            await self._drain_pending(jid, group, session_id)

            # Wake up waiting groups
            await self._drain_waiting()

    async def _send_follow_up_messages(
        self,
        jid: str,
        last_timestamp: str | None,
    ) -> None:
        """Send follow-up messages to an active container.

        Args:
            jid: Group JID
            last_timestamp: Last processed timestamp
        """
        import json
        from pathlib import Path

        messages = await self.db.get_messages_since(jid, last_timestamp)

        # Write IPC files for each new message
        ipc_dir = self.config.data_dir / "ipc" / jid
        ipc_dir.mkdir(parents=True, exist_ok=True)

        for msg in messages:
            ipc_file = ipc_dir / "input" / f"{msg.timestamp}.json"
            ipc_file.parent.mkdir(parents=True, exist_ok=True)

            ipc_file.write_text(
                json.dumps(
                    {
                        "sender": msg.sender_name or msg.sender,
                        "text": msg.content,
                    }
                )
            )

    async def _drain_pending(
        self,
        jid: str,
        group: RegisteredGroup,
        session_id: str | None,
    ) -> None:
        """Process pending items for a group.

        Args:
            jid: Group JID
            group: Registered group configuration
            session_id: Current session ID
        """
        state = self._get_state(jid, group.folder)

        # Priority: tasks first, then messages
        if state.pending_tasks:
            task = state.pending_tasks.pop(0)
            await self._try_start_task(jid, group, task, session_id)
        elif state.pending_messages:
            state.pending_messages = False
            last_timestamp = await self.db.get_last_agent_timestamp(jid)
            await self._try_start_container(jid, group, session_id, last_timestamp)

    async def _drain_waiting(self) -> None:
        """Wake up waiting groups if capacity is available."""
        while (
            self.waiting_groups
            and self.active_count < self.config.container_max_concurrent_containers
        ):
            jid = self.waiting_groups.pop(0)
            # TODO: Re-enqueue the group

    def _get_state(self, jid: str, group_folder: str) -> GroupState:
        """Get or create state for a group.

        Args:
            jid: Group JID
            group_folder: Group folder name

        Returns:
            GroupState for the group
        """
        if jid not in self.states:
            self.states[jid] = GroupState(jid=jid, group_folder=group_folder)
        return self.states[jid]

    async def _handle_container_result(
        self,
        jid: str,
        result: ContainerOutput,
        group: RegisteredGroup,
        session_id: str | None,
    ) -> None:
        """Handle container execution result.

        Args:
            jid: Group JID
            result: Container output
            group: Registered group
            session_id: Current session ID
        """
        from loguru import logger

        if result.status == "success" and result.result:
            # Send result to channel
            logger.info(f"Container completed for {jid}")
            # TODO: Send via router
        else:
            logger.error(f"Container failed for {jid}: {result.error}")
