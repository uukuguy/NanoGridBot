"""Task database operations."""

from collections.abc import Sequence
from datetime import datetime
from typing import Literal, cast

from nanogridbot.database.connection import Database
from nanogridbot.types import ScheduledTask, ScheduleType, TaskStatus


class TaskRepository:
    """Repository for scheduled task storage and retrieval."""

    def __init__(self, database: Database) -> None:
        """Initialize task repository.

        Args:
            database: Database connection instance.
        """
        self._db = database

    async def save_task(self, task: ScheduledTask) -> int:
        """Save or update a task.

        Args:
            task: Task to save.

        Returns:
            Task ID (new or updated).
        """
        next_run = task.next_run.isoformat() if task.next_run else None

        if task.id is None:
            # Insert new task
            cursor = await self._db.execute(
                """
                INSERT INTO tasks
                (group_folder, prompt, schedule_type, schedule_value, status, next_run, context_mode, target_chat_jid)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.group_folder,
                    task.prompt,
                    (
                        task.schedule_type.value
                        if isinstance(task.schedule_type, ScheduleType)
                        else task.schedule_type
                    ),
                    task.schedule_value,
                    task.status.value if isinstance(task.status, TaskStatus) else task.status,
                    next_run,
                    task.context_mode,
                    task.target_chat_jid,
                ),
            )
            await self._db.commit()
            return cursor.lastrowid if cursor.lastrowid is not None else 0
        else:
            # Update existing task
            await self._db.execute(
                """
                UPDATE tasks
                SET group_folder = ?, prompt = ?, schedule_type = ?, schedule_value = ?,
                    status = ?, next_run = ?, context_mode = ?, target_chat_jid = ?
                WHERE id = ?
                """,
                (
                    task.group_folder,
                    task.prompt,
                    (
                        task.schedule_type.value
                        if isinstance(task.schedule_type, ScheduleType)
                        else task.schedule_type
                    ),
                    task.schedule_value,
                    task.status.value if isinstance(task.status, TaskStatus) else task.status,
                    next_run,
                    task.context_mode,
                    task.target_chat_jid,
                    task.id,
                ),
            )
            await self._db.commit()
            return task.id

    async def get_task(self, task_id: int) -> ScheduledTask | None:
        """Get a task by ID.

        Args:
            task_id: Task ID.

        Returns:
            Task if found, None otherwise.
        """
        row = await self._db.fetchone(
            """
            SELECT id, group_folder, prompt, schedule_type, schedule_value, status, next_run, context_mode, target_chat_jid
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        )
        return self._row_to_task(row) if row else None

    async def get_active_tasks(self) -> Sequence[ScheduledTask]:
        """Get all active tasks.

        Returns:
            List of active tasks.
        """
        rows = await self._db.fetchall(
            """
            SELECT id, group_folder, prompt, schedule_type, schedule_value, status, next_run, context_mode, target_chat_jid
            FROM tasks
            WHERE status = 'active'
            ORDER BY next_run ASC
            """,
        )
        return [self._row_to_task(row) for row in rows]

    async def get_all_tasks(self) -> Sequence[ScheduledTask]:
        """Get all tasks.

        Returns:
            List of all tasks.
        """
        rows = await self._db.fetchall(
            """
            SELECT id, group_folder, prompt, schedule_type, schedule_value, status, next_run, context_mode, target_chat_jid
            FROM tasks
            ORDER BY next_run ASC
            """,
        )
        return [self._row_to_task(row) for row in rows]

    async def get_tasks_by_group(self, group_folder: str) -> Sequence[ScheduledTask]:
        """Get tasks for a specific group folder.

        Args:
            group_folder: Group folder name.

        Returns:
            List of tasks for the group.
        """
        rows = await self._db.fetchall(
            """
            SELECT id, group_folder, prompt, schedule_type, schedule_value, status, next_run, context_mode, target_chat_jid
            FROM tasks
            WHERE group_folder = ?
            ORDER BY next_run ASC
            """,
            (group_folder,),
        )
        return [self._row_to_task(row) for row in rows]

    async def update_task_status(self, task_id: int, status: TaskStatus) -> bool:
        """Update task status.

        Args:
            task_id: Task ID.
            status: New status.

        Returns:
            True if updated, False if not found.
        """
        cursor = await self._db.execute(
            "UPDATE tasks SET status = ? WHERE id = ?",
            (status.value if isinstance(status, TaskStatus) else status, task_id),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def update_next_run(self, task_id: int, next_run: datetime) -> bool:
        """Update task next run time.

        Args:
            task_id: Task ID.
            next_run: Next run timestamp.

        Returns:
            True if updated, False if not found.
        """
        cursor = await self._db.execute(
            "UPDATE tasks SET next_run = ? WHERE id = ?",
            (next_run.isoformat(), task_id),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def delete_task(self, task_id: int) -> bool:
        """Delete a task by ID.

        Args:
            task_id: Task ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        cursor = await self._db.execute(
            "DELETE FROM tasks WHERE id = ?",
            (task_id,),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def get_due_tasks(self) -> Sequence[ScheduledTask]:
        """Get tasks that are due to run.

        Returns:
            List of due tasks.
        """
        now = datetime.now().isoformat()
        rows = await self._db.fetchall(
            """
            SELECT id, group_folder, prompt, schedule_type, schedule_value, status, next_run, context_mode, target_chat_jid
            FROM tasks
            WHERE status = 'active' AND next_run <= ?
            ORDER BY next_run ASC
            """,
            (now,),
        )
        return [self._row_to_task(row) for row in rows]

    @staticmethod
    def _row_to_task(row: dict[str, object]) -> ScheduledTask:
        """Convert database row to ScheduledTask model.

        Args:
            row: Database row dictionary.

        Returns:
            ScheduledTask instance.
        """
        next_run_raw = row.get("next_run")
        next_run: datetime | None = None
        if next_run_raw:
            next_run = datetime.fromisoformat(str(next_run_raw))

        ctx = str(row["context_mode"])
        context_mode_val = cast(
            Literal["group", "isolated"], ctx if ctx in ("group", "isolated") else "group"
        )

        target_jid = row.get("target_chat_jid")
        target_chat_jid: str | None = str(target_jid) if target_jid else None

        return ScheduledTask(
            id=int(str(row["id"])),
            group_folder=str(row["group_folder"]),
            prompt=str(row["prompt"]),
            schedule_type=ScheduleType(str(row["schedule_type"])),
            schedule_value=str(row["schedule_value"]),
            status=TaskStatus(str(row["status"])),
            next_run=next_run,
            context_mode=context_mode_val,
            target_chat_jid=target_chat_jid,
        )
