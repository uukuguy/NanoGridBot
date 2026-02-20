"""Group database operations."""

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nanogridbot.database.connection import Database

from nanogridbot.types import RegisteredGroup


class GroupRepository:
    """Repository for group storage and retrieval."""

    def __init__(self, database: "Database") -> None:
        """Initialize group repository.

        Args:
            database: Database connection instance.
        """
        self._db = database

    async def save_group(self, group: RegisteredGroup) -> None:
        """Save or update a group.

        Args:
            group: Group to save.
        """
        container_config = (
            json.dumps(group.container_config) if group.container_config is not None else None
        )

        await self._db.execute(
            """
            INSERT OR REPLACE INTO groups
            (jid, name, folder, user_id, trigger_pattern, container_config, requires_trigger)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                group.jid,
                group.name,
                group.folder,
                group.user_id,
                group.trigger_pattern,
                container_config,
                int(group.requires_trigger),
            ),
        )
        await self._db.commit()

    async def get_group(self, jid: str) -> RegisteredGroup | None:
        """Get a group by JID.

        Args:
            jid: Group JID.

        Returns:
            Group if found, None otherwise.
        """
        row = await self._db.fetchone(
            """
            SELECT jid, name, folder, user_id, trigger_pattern, container_config, requires_trigger
            FROM groups
            WHERE jid = ?
            """,
            (jid,),
        )
        return self._row_to_group(row) if row else None

    async def get_groups(self) -> Sequence[RegisteredGroup]:
        """Get all registered groups.

        Returns:
            List of registered groups.
        """
        rows = await self._db.fetchall(
            """
            SELECT jid, name, folder, user_id, trigger_pattern, container_config, requires_trigger
            FROM groups
            ORDER BY name ASC
            """,
        )
        return [self._row_to_group(row) for row in rows]

    async def get_groups_by_folder(self, folder: str) -> Sequence[RegisteredGroup]:
        """Get groups by folder name.

        Args:
            folder: Folder name to filter by.

        Returns:
            List of groups in the folder.
        """
        rows = await self._db.fetchall(
            """
            SELECT jid, name, folder, user_id, trigger_pattern, container_config, requires_trigger
            FROM groups
            WHERE folder = ?
            ORDER BY name ASC
            """,
            (folder,),
        )
        return [self._row_to_group(row) for row in rows]

    async def get_groups_by_user(self, user_id: int) -> Sequence[RegisteredGroup]:
        """Get groups by user ID.

        Args:
            user_id: User ID to filter by.

        Returns:
            List of groups owned by the user.
        """
        rows = await self._db.fetchall(
            """
            SELECT jid, name, folder, user_id, trigger_pattern, container_config, requires_trigger
            FROM groups
            WHERE user_id = ?
            ORDER BY name ASC
            """,
            (user_id,),
        )
        return [self._row_to_group(row) for row in rows]

    async def delete_group(self, jid: str) -> bool:
        """Delete a group by JID.

        Args:
            jid: Group JID to delete.

        Returns:
            True if deleted, False if not found.
        """
        cursor = await self._db.execute(
            "DELETE FROM groups WHERE jid = ?",
            (jid,),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def group_exists(self, jid: str) -> bool:
        """Check if a group exists.

        Args:
            jid: Group JID to check.

        Returns:
            True if exists, False otherwise.
        """
        row = await self._db.fetchone(
            "SELECT 1 FROM groups WHERE jid = ?",
            (jid,),
        )
        return row is not None

    @staticmethod
    def _row_to_group(row: dict[str, Any]) -> RegisteredGroup:
        """Convert database row to RegisteredGroup model.

        Args:
            row: Database row dictionary.

        Returns:
            RegisteredGroup instance.
        """
        container_config_raw = row.get("container_config")
        container_config: dict[str, Any] | None = None
        if container_config_raw:
            try:
                container_config = json.loads(container_config_raw)
            except json.JSONDecodeError:
                pass

        return RegisteredGroup(
            jid=str(row["jid"]),
            name=str(row["name"]),
            folder=str(row["folder"]),
            user_id=row["user_id"] if row.get("user_id") else None,
            trigger_pattern=row["trigger_pattern"] if row["trigger_pattern"] else None,
            container_config=container_config,
            requires_trigger=bool(row["requires_trigger"]),
        )
