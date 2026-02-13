"""Task scheduler for scheduled and recurring tasks."""

import asyncio
from datetime import datetime, timedelta
from typing import Any

from croniter import croniter

from nanogridbot.config import get_config
from nanogridbot.core.group_queue import GroupQueue
from nanogridbot.database import Database, TaskRepository
from nanogridbot.types import ScheduledTask, ScheduleType, TaskStatus


class TaskScheduler:
    """Manages scheduled task execution."""

    def __init__(self, config: "get_config", db: Database, queue: GroupQueue):
        """Initialize the task scheduler.

        Args:
            config: Application configuration
            db: Database instance
            queue: Group queue for task execution
        """
        self.config = config
        self.db = db
        self.queue = queue
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the task scheduler."""
        from loguru import logger

        self._running = True
        self._task = asyncio.create_task(self._run_scheduler())
        logger.info("Task scheduler started")

    async def stop(self) -> None:
        """Stop the task scheduler."""
        from loguru import logger

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Task scheduler stopped")

    async def _run_scheduler(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._check_and_run_tasks()
            except Exception as e:
                from loguru import logger

                logger.error(f"Scheduler error: {e}")

            # Poll every minute
            await asyncio.sleep(60)

    async def _check_and_run_tasks(self) -> None:
        """Check for due tasks and run them."""
        task_repo = TaskRepository(self.db)

        # Get all active tasks
        tasks = await task_repo.get_active_tasks()

        now = datetime.now()

        for task in tasks:
            # Calculate next run time
            next_run = self._calculate_next_run(task)

            if next_run and next_run <= now:
                # Task is due
                await self._run_task(task)

                # Update task
                if task.schedule_type == ScheduleType.ONCE:
                    task.status = TaskStatus.COMPLETED
                else:
                    task.next_run = self._calculate_next_run(task)

                await task_repo.update_task(task)

    def _calculate_next_run(self, task: ScheduledTask) -> datetime | None:
        """Calculate the next run time for a task.

        Args:
            task: Scheduled task

        Returns:
            Next run datetime or None if task is completed
        """
        if task.status != TaskStatus.ACTIVE:
            return None

        now = datetime.now()

        if task.schedule_type == ScheduleType.CRON:
            # Use croniter for cron expressions
            if task.next_run:
                base = task.next_run
            else:
                base = now

            try:
                cron = croniter(task.schedule_value, base)
                return cron.get_next(datetime)
            except Exception:
                return None

        elif task.schedule_type == ScheduleType.INTERVAL:
            # Parse interval (e.g., "1h", "30m", "7d")
            interval = self._parse_interval(task.schedule_value)
            if interval:
                if task.next_run:
                    return task.next_run + interval
                else:
                    return now + interval

        elif task.schedule_type == ScheduleType.ONCE:
            # One-time task
            if task.next_run and task.next_run > now:
                return task.next_run
            return None

        return None

    def _parse_interval(self, value: str) -> timedelta | None:
        """Parse interval string to timedelta.

        Args:
            value: Interval string (e.g., "1h", "30m", "7d")

        Returns:
            timedelta or None if invalid
        """
        import re

        match = re.match(r"^(\d+)([smhd])$", value)
        if not match:
            return None

        amount, unit = match.groups()
        amount = int(amount)

        if unit == "s":
            return timedelta(seconds=amount)
        elif unit == "m":
            return timedelta(minutes=amount)
        elif unit == "h":
            return timedelta(hours=amount)
        elif unit == "d":
            return timedelta(days=amount)

        return None

    async def _run_task(self, task: ScheduledTask) -> None:
        """Run a scheduled task.

        Args:
            task: Task to run
        """
        from loguru import logger

        logger.info(f"Running scheduled task: {task.group_folder} - {task.prompt[:50]}...")

        # Get group info
        group_repo = self.db.get_group_repository()
        group = await group_repo.get_group_by_folder(task.group_folder)

        if not group:
            logger.warning(f"Group not found for task: {task.group_folder}")
            return

        # Enqueue task
        await self.queue.enqueue_task(
            jid=group.jid,
            group=group,
            task=task,
            session_id=None,  # Will be retrieved from state
        )

    async def schedule_task(
        self,
        group_folder: str,
        prompt: str,
        schedule_type: ScheduleType,
        schedule_value: str,
        context_mode: str = "group",
        target_chat_jid: str | None = None,
    ) -> ScheduledTask:
        """Schedule a new task.

        Args:
            group_folder: Group folder name
            prompt: Task prompt
            schedule_type: Type of schedule
            schedule_value: Schedule value (cron expression or interval)
            context_mode: "group" or "isolated"
            target_chat_jid: Optional target chat JID

        Returns:
            Created scheduled task
        """
        task = ScheduledTask(
            group_folder=group_folder,
            prompt=prompt,
            schedule_type=schedule_type,
            schedule_value=schedule_value,
            context_mode=context_mode,
            target_chat_jid=target_chat_jid,
            status=TaskStatus.ACTIVE,
        )

        # Calculate next run
        task.next_run = self._calculate_next_run(task)

        # Save to database
        task_repo = TaskRepository(self.db)
        task = await task_repo.save_task(task)

        return task

    async def cancel_task(self, task_id: int) -> bool:
        """Cancel a scheduled task.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled, False if not found
        """
        task_repo = TaskRepository(self.db)

        task = await task_repo.get_task(task_id)
        if not task:
            return False

        task.status = TaskStatus.COMPLETED
        await task_repo.update_task(task)

        return True

    async def pause_task(self, task_id: int) -> bool:
        """Pause a scheduled task.

        Args:
            task_id: Task ID

        Returns:
            True if paused, False if not found
        """
        task_repo = TaskRepository(self.db)

        task = await task_repo.get_task(task_id)
        if not task:
            return False

        task.status = TaskStatus.PAUSED
        await task_repo.update_task(task)

        return True

    async def resume_task(self, task_id: int) -> bool:
        """Resume a paused task.

        Args:
            task_id: Task ID

        Returns:
            True if resumed, False if not found
        """
        task_repo = TaskRepository(self.db)

        task = await task_repo.get_task(task_id)
        if not task:
            return False

        if task.status != TaskStatus.PAUSED:
            return False

        task.status = TaskStatus.ACTIVE
        task.next_run = self._calculate_next_run(task)
        await task_repo.update_task(task)

        return True
