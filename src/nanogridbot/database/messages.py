"""Message database operations."""

from collections import OrderedDict
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nanogridbot.database.connection import Database

from nanogridbot.types import Message, MessageRole


class MessageCache:
    """Simple LRU cache for recent messages."""

    def __init__(self, max_size: int = 1000):
        """Initialize message cache.

        Args:
            max_size: Maximum number of messages to cache
        """
        self._cache: OrderedDict[str, Message] = OrderedDict()
        self._max_size = max_size

    def get(self, key: str) -> Message | None:
        """Get message from cache.

        Args:
            key: Message ID

        Returns:
            Cached message or None
        """
        if key not in self._cache:
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return self._cache[key]

    def put(self, key: str, message: Message) -> None:
        """Put message in cache.

        Args:
            key: Message ID
            message: Message to cache
        """
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self._max_size:
                # Remove oldest (first) item
                self._cache.popitem(last=False)

        self._cache[key] = message

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()


class MessageRepository:
    """Repository for message storage and retrieval."""

    def __init__(self, database: "Database", cache_size: int = 1000) -> None:
        """Initialize message repository.

        Args:
            database: Database connection instance.
            cache_size: Size of message cache
        """
        self._db = database
        self._cache = MessageCache(max_size=cache_size)

    async def store_message(self, message: Message) -> None:
        """Store a message in the database.

        Args:
            message: Message to store.
        """
        await self._db.execute(
            """
            INSERT OR REPLACE INTO messages
            (id, chat_jid, sender, sender_name, content, timestamp, is_from_me, role)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message.id,
                message.chat_jid,
                message.sender,
                message.sender_name,
                message.content,
                message.timestamp.isoformat(),
                int(message.is_from_me),
                message.role.value if isinstance(message.role, MessageRole) else message.role,
            ),
        )
        await self._db.commit()

        # Update cache
        self._cache.put(message.id, message)

    async def get_messages_since(
        self,
        chat_jid: str,
        since: datetime,
    ) -> Sequence[Message]:
        """Get messages for a specific chat since a timestamp.

        Args:
            chat_jid: Chat JID to filter by.
            since: Filter messages after this timestamp.

        Returns:
            List of messages.
        """
        rows = await self._db.fetchall(
            """
            SELECT id, chat_jid, sender, sender_name, content, timestamp, is_from_me, role
            FROM messages
            WHERE chat_jid = ? AND timestamp > ?
            ORDER BY timestamp ASC
            """,
            (chat_jid, since.isoformat()),
        )
        return [self._row_to_message(row) for row in rows]

    async def get_new_messages(
        self,
        since: datetime | None = None,
    ) -> Sequence[Message]:
        """Get all new messages since a timestamp.

        Args:
            since: Filter messages after this timestamp. If None, returns all messages.

        Returns:
            List of messages.
        """
        if since is not None:
            rows = await self._db.fetchall(
                """
                SELECT id, chat_jid, sender, sender_name, content, timestamp, is_from_me, role
                FROM messages
                WHERE timestamp > ?
                ORDER BY timestamp ASC
                """,
                (since.isoformat(),),
            )
        else:
            rows = await self._db.fetchall(
                """
                SELECT id, chat_jid, sender, sender_name, content, timestamp, is_from_me, role
                FROM messages
                ORDER BY timestamp ASC
                """,
            )
        return [self._row_to_message(row) for row in rows]

    async def get_recent_messages(
        self,
        chat_jid: str,
        limit: int = 50,
    ) -> Sequence[Message]:
        """Get recent messages for a chat.

        Args:
            chat_jid: Chat JID to filter by.
            limit: Maximum number of messages to return.

        Returns:
            List of recent messages.
        """
        rows = await self._db.fetchall(
            """
            SELECT id, chat_jid, sender, sender_name, content, timestamp, is_from_me, role
            FROM messages
            WHERE chat_jid = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (chat_jid, limit),
        )
        # Return in chronological order
        return [self._row_to_message(row) for row in reversed(rows)]

    async def delete_old_messages(self, before: datetime) -> int:
        """Delete messages older than a timestamp.

        Args:
            before: Delete messages before this timestamp.

        Returns:
            Number of deleted messages.
        """
        cursor = await self._db.execute(
            """
            DELETE FROM messages
            WHERE timestamp < ?
            """,
            (before.isoformat(),),
        )
        await self._db.commit()
        return cursor.rowcount

    @staticmethod
    def _row_to_message(row: dict[str, object]) -> Message:
        """Convert database row to Message model.

        Args:
            row: Database row dictionary.

        Returns:
            Message instance.
        """
        sender_name_val = row.get("sender_name")
        sender_name: str | None = str(sender_name_val) if sender_name_val else None

        return Message(
            id=str(row["id"]),
            chat_jid=str(row["chat_jid"]),
            sender=str(row["sender"]),
            sender_name=sender_name,
            content=str(row["content"]),
            timestamp=datetime.fromisoformat(str(row["timestamp"])),
            is_from_me=bool(row["is_from_me"]),
            role=MessageRole(str(row["role"])),
        )
