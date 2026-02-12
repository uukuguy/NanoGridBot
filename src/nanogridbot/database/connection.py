"""Database connection management."""

from pathlib import Path
from typing import Any

import aiosqlite


class Database:
    """Async SQLite database connection manager."""

    def __init__(self, db_path: Path) -> None:
        """Initialize database with path.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection.

        Returns:
            aiosqlite Connection instance.
        """
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
            # Enable foreign keys
            await self._connection.execute("PRAGMA foreign_keys = ON")
            # Set row factory for dict-like access
            self._connection.row_factory = aiosqlite.Row
        return self._connection

    async def close(self) -> None:
        """Close database connection."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def initialize(self) -> None:
        """Initialize database schema."""
        db = await self.get_connection()

        # Messages table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_jid TEXT NOT NULL,
                sender TEXT NOT NULL,
                sender_name TEXT,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                is_from_me INTEGER DEFAULT 0,
                role TEXT DEFAULT 'user'
            )
        """)

        # Messages index
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_chat_time
            ON messages(chat_jid, timestamp)
        """)

        # Groups table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                jid TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                folder TEXT NOT NULL,
                trigger_pattern TEXT,
                container_config TEXT,
                requires_trigger INTEGER DEFAULT 1
            )
        """)

        # Tasks table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_folder TEXT NOT NULL,
                prompt TEXT NOT NULL,
                schedule_type TEXT NOT NULL,
                schedule_value TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                next_run TEXT,
                context_mode TEXT DEFAULT 'group',
                target_chat_jid TEXT
            )
        """)

        await db.commit()

    async def execute(
        self,
        query: str,
        parameters: tuple[Any, ...] | dict[str, Any] = (),
    ) -> aiosqlite.Cursor:
        """Execute a query.

        Args:
            query: SQL query string.
            parameters: Query parameters.

        Returns:
            Cursor instance.
        """
        db = await self.get_connection()
        return await db.execute(query, parameters)

    async def fetchall(
        self,
        query: str,
        parameters: tuple[Any, ...] | dict[str, Any] = (),
    ) -> list[dict[str, Any]]:
        """Execute query and fetch all results.

        Args:
            query: SQL query string.
            parameters: Query parameters.

        Returns:
            List of row dictionaries.
        """
        db = await self.get_connection()
        async with db.execute(query, parameters) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def fetchone(
        self,
        query: str,
        parameters: tuple[Any, ...] | dict[str, Any] = (),
    ) -> dict[str, Any] | None:
        """Execute query and fetch one result.

        Args:
            query: SQL query string.
            parameters: Query parameters.

        Returns:
            Row dictionary or None.
        """
        db = await self.get_connection()
        async with db.execute(query, parameters) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def commit(self) -> None:
        """Commit current transaction."""
        db = await self.get_connection()
        await db.commit()
