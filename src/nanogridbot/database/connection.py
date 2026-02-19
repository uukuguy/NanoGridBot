"""Database connection management."""

import asyncio
from pathlib import Path
from typing import Any

import aiosqlite
from loguru import logger

from nanogridbot.database.groups import GroupRepository
from nanogridbot.database.messages import MessageRepository
from nanogridbot.database.tasks import TaskRepository
from nanogridbot.database.users import (
    AuditRepository,
    InviteCodeRepository,
    LoginAttemptRepository,
    SessionRepository,
    UserRepository,
)
from nanogridbot.utils.error_handling import with_retry


class Database:
    """Async SQLite database connection manager."""

    def __init__(self, db_path: Path) -> None:
        """Initialize database with path.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        self._connection: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    @with_retry(max_retries=3, base_delay=0.5, exceptions=(aiosqlite.Error,))
    async def get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection with retry.

        Returns:
            aiosqlite Connection instance.
        """
        async with self._lock:
            if self._connection is None:
                self._connection = await aiosqlite.connect(self.db_path)
                # Enable foreign keys
                await self._connection.execute("PRAGMA foreign_keys = ON")
                # Set row factory for dict-like access
                self._connection.row_factory = aiosqlite.Row
                # Enable WAL mode for better concurrency
                await self._connection.execute("PRAGMA journal_mode=WAL")
                await self._connection.execute("PRAGMA busy_timeout=5000")
            return self._connection

    async def close(self) -> None:
        """Close database connection."""
        async with self._lock:
            if self._connection is not None:
                await self._connection.close()
                self._connection = None
                logger.info("Database connection closed")

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

        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                is_verified INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        """)

        # User sessions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_activity TEXT,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Invite codes table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS invite_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                created_by INTEGER NOT NULL,
                used_by INTEGER,
                used_at TEXT,
                expires_at TEXT NOT NULL,
                max_uses INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (used_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # Login attempts table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                ip_address TEXT,
                attempt_time TEXT NOT NULL,
                success INTEGER DEFAULT 0
            )
        """)

        # Audit logs table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                user_id INTEGER,
                username TEXT,
                ip_address TEXT,
                user_agent TEXT,
                resource_type TEXT,
                resource_id TEXT,
                details TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # Audit logs indexes
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id)
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_logs(event_type)
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)
        """)

        # User directories table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_directories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                path TEXT NOT NULL,
                directory_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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

    def get_group_repository(self) -> GroupRepository:
        """Get group repository instance.

        Returns:
            GroupRepository instance.
        """
        return GroupRepository(self)

    def get_message_repository(self) -> MessageRepository:
        """Get message repository instance.

        Returns:
            MessageRepository instance.
        """
        return MessageRepository(self)

    def get_task_repository(self) -> TaskRepository:
        """Get task repository instance.

        Returns:
            TaskRepository instance.
        """
        return TaskRepository(self)

    def get_user_repository(self) -> UserRepository:
        """Get user repository instance.

        Returns:
            UserRepository instance.
        """
        return UserRepository(self)

    def get_session_repository(self) -> SessionRepository:
        """Get session repository instance.

        Returns:
            SessionRepository instance.
        """
        return SessionRepository(self)

    def get_invite_code_repository(self) -> InviteCodeRepository:
        """Get invite code repository instance.

        Returns:
            InviteCodeRepository instance.
        """
        return InviteCodeRepository(self)

    def get_login_attempt_repository(self) -> LoginAttemptRepository:
        """Get login attempt repository instance.

        Returns:
            LoginAttemptRepository instance.
        """
        return LoginAttemptRepository(self)

    def get_audit_repository(self) -> AuditRepository:
        """Get audit repository instance.

        Returns:
            AuditRepository instance.
        """
        return AuditRepository(self)
