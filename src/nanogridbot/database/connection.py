"""Database connection management."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import aiosqlite
from loguru import logger

from nanogridbot.database.groups import GroupRepository, RegisteredGroup
from nanogridbot.database.messages import Message, MessageRepository
from nanogridbot.database.tasks import TaskRepository
from nanogridbot.database.user_channel_configs import UserChannelConfigRepository
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
                user_id INTEGER,
                trigger_pattern TEXT,
                container_config TEXT,
                requires_trigger INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # Groups index
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_groups_user ON groups(user_id)
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

        # User channel configs table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_channel_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel TEXT NOT NULL,
                telegram_bot_token TEXT,
                slack_bot_token TEXT,
                slack_signing_secret TEXT,
                discord_bot_token TEXT,
                whatsapp_session_path TEXT,
                qq_host TEXT,
                qq_port INTEGER,
                feishu_app_id TEXT,
                feishu_app_secret TEXT,
                wecom_corp_id TEXT,
                wecom_agent_id TEXT,
                wecom_secret TEXT,
                dingtalk_app_key TEXT,
                dingtalk_app_secret TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, channel)
            )
        """)

        # User channel configs indexes
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_channel_user ON user_channel_configs(user_id)
        """)

        # App state table for router state
        await db.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    # Delegation methods for orchestrator compatibility
    async def get_groups(self) -> Sequence[RegisteredGroup]:
        """Get all groups. Delegates to GroupRepository."""
        return await self.get_group_repository().get_groups()

    async def get_registered_groups(self) -> Sequence[RegisteredGroup]:
        """Get all registered groups. Alias for get_groups()."""
        return await self.get_groups()

    async def save_group(self, group: RegisteredGroup) -> None:
        """Save a group. Delegates to GroupRepository."""
        return await self.get_group_repository().save_group(group)

    async def delete_group(self, jid: str) -> bool:
        """Delete a group. Delegates to GroupRepository."""
        return await self.get_group_repository().delete_group(jid)

    async def get_new_messages(self, since: datetime | None) -> Sequence[Message]:
        """Get new messages since timestamp. Delegates to MessageRepository."""
        return await self.get_message_repository().get_new_messages(since)

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

    def get_user_channel_config_repository(self) -> UserChannelConfigRepository:
        """Get user channel config repository instance.

        Returns:
            UserChannelConfigRepository instance.
        """
        return UserChannelConfigRepository(self)

    async def get_router_state(self) -> dict[str, Any]:
        """Get router state from database.

        Returns:
            Dictionary containing router state.
        """
        db = await self.get_connection()
        cursor = await db.execute(
            "SELECT key, value FROM app_state WHERE key IN ('last_timestamp', 'sessions', 'last_agent_timestamp')"
        )
        rows = await cursor.fetchall()
        state = {}
        for row in rows:
            import json

            try:
                state[row[0]] = json.loads(row[1])
            except (json.JSONDecodeError, TypeError):
                state[row[0]] = row[1]
        return state

    async def save_router_state(self, state: dict[str, Any]) -> None:
        """Save router state to database.

        Args:
            state: Dictionary containing router state.
        """
        db = await self.get_connection()
        import json

        for key, value in state.items():
            value_json = json.dumps(value)
            await db.execute(
                """
                INSERT INTO app_state (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value_json),
            )
        await db.commit()


# Global metrics database instance for metrics.py
_metrics_db: Database | None = None


class MetricsConnection:
    """Async context manager for metrics database connection."""

    def __init__(self) -> None:
        self._conn: aiosqlite.Connection | None = None

    async def __aenter__(self) -> aiosqlite.Connection:
        global _metrics_db

        if _metrics_db is None:
            from nanogridbot.config import Config

            config = Config()
            # Use a separate metrics database
            metrics_db_path = config.store_dir / "metrics.db"
            _metrics_db = Database(metrics_db_path)

        self._conn = await _metrics_db.get_connection()
        return self._conn

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        # Don't close the connection, just let it be reused
        pass


async def get_db_connection() -> MetricsConnection:
    """Get a database connection for metrics.

    This is a compatibility function for metrics.py that needs
    a standalone database connection.

    Returns:
        MetricsConnection context manager.
    """
    return MetricsConnection()
