"""Unit tests for database repository classes with mocked database."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanogridbot.database.groups import GroupRepository
from nanogridbot.database.messages import MessageCache, MessageRepository
from nanogridbot.database.tasks import TaskRepository
from nanogridbot.types import (
    Message,
    MessageRole,
    RegisteredGroup,
    ScheduledTask,
    ScheduleType,
    TaskStatus,
)


@pytest.fixture
def mock_db():
    """Create a mock database."""
    db = MagicMock()
    db.execute = AsyncMock()
    db.fetchone = AsyncMock()
    db.fetchall = AsyncMock()
    db.commit = AsyncMock()
    return db


class TestTaskRepositoryUpdate:
    """Tests for TaskRepository update existing task path."""

    @pytest.mark.asyncio
    async def test_save_task_update_existing(self, mock_db):
        """Test updating an existing task (lines 62-86)."""
        repo = TaskRepository(mock_db)

        task = ScheduledTask(
            id=42,
            group_folder="test_folder",
            prompt="Updated prompt",
            schedule_type=ScheduleType.CRON,
            schedule_value="0 10 * * *",
            status=TaskStatus.ACTIVE,
            next_run=datetime(2025, 1, 15, 10, 0),
            context_mode="isolated",
            target_chat_jid="telegram:123",
        )

        mock_db.execute.return_value = MagicMock(lastrowid=42)

        result = await repo.save_task(task)

        assert result == 42
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        assert "UPDATE tasks" in call_args[0][0]
        assert call_args[0][1] == (
            "test_folder",
            "Updated prompt",
            "cron",
            "0 10 * * *",
            "active",
            "2025-01-15T10:00:00",
            "isolated",
            "telegram:123",
            42,
        )
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_tasks(self, mock_db):
        """Test getting all tasks (lines 129-136)."""
        repo = TaskRepository(mock_db)

        mock_db.fetchall.return_value = [
            {
                "id": 1,
                "group_folder": "folder1",
                "prompt": "Task 1",
                "schedule_type": "cron",
                "schedule_value": "0 9 * * *",
                "status": "active",
                "next_run": "2025-01-15T09:00:00",
                "context_mode": "group",
                "target_chat_jid": None,
            },
            {
                "id": 2,
                "group_folder": "folder2",
                "prompt": "Task 2",
                "schedule_type": "interval",
                "schedule_value": "3600",
                "status": "paused",
                "next_run": "2025-01-15T10:00:00",
                "context_mode": "isolated",
                "target_chat_jid": "telegram:456",
            },
        ]

        tasks = await repo.get_all_tasks()

        assert len(tasks) == 2
        assert tasks[0].id == 1
        assert tasks[0].group_folder == "folder1"
        assert tasks[1].id == 2
        assert tasks[1].status == TaskStatus.PAUSED
        mock_db.fetchall.assert_called_once()
        call_args = mock_db.fetchall.call_args
        assert "SELECT" in call_args[0][0]
        assert "ORDER BY next_run ASC" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_tasks_by_group(self, mock_db):
        """Test getting tasks by group folder (lines 147-156)."""
        repo = TaskRepository(mock_db)

        mock_db.fetchall.return_value = [
            {
                "id": 10,
                "group_folder": "target_folder",
                "prompt": "Group task",
                "schedule_type": "once",
                "schedule_value": "2025-02-01T12:00:00",
                "status": "active",
                "next_run": "2025-02-01T12:00:00",
                "context_mode": "group",
                "target_chat_jid": "slack:C123",
            }
        ]

        tasks = await repo.get_tasks_by_group("target_folder")

        assert len(tasks) == 1
        assert tasks[0].group_folder == "target_folder"
        assert tasks[0].schedule_type == ScheduleType.ONCE
        mock_db.fetchall.assert_called_once()
        call_args = mock_db.fetchall.call_args
        assert "WHERE group_folder = ?" in call_args[0][0]
        assert call_args[0][1] == ("target_folder",)

    @pytest.mark.asyncio
    async def test_update_next_run(self, mock_db):
        """Test updating task next run time (lines 185-190)."""
        repo = TaskRepository(mock_db)

        next_run = datetime(2025, 2, 20, 15, 30)
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_db.execute.return_value = mock_cursor

        result = await repo.update_next_run(5, next_run)

        assert result is True
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        assert "UPDATE tasks SET next_run = ? WHERE id = ?" in call_args[0][0]
        assert call_args[0][1] == ("2025-02-20T15:30:00", 5)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_task(self, mock_db):
        """Test deleting a task (lines 201-206)."""
        repo = TaskRepository(mock_db)

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_db.execute.return_value = mock_cursor

        result = await repo.delete_task(99)

        assert result is True
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        assert "DELETE FROM tasks WHERE id = ?" in call_args[0][0]
        assert call_args[0][1] == (99,)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, mock_db):
        """Test deleting a non-existent task."""
        repo = TaskRepository(mock_db)

        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        mock_db.execute.return_value = mock_cursor

        result = await repo.delete_task(999)

        assert result is False


class TestGroupRepositoryExtended:
    """Tests for GroupRepository uncovered paths."""

    @pytest.mark.asyncio
    async def test_get_groups_by_folder(self, mock_db):
        """Test getting groups by folder (lines 94-103)."""
        repo = GroupRepository(mock_db)

        mock_db.fetchall.return_value = [
            {
                "jid": "telegram:111",
                "name": "Group A",
                "folder": "work",
                "trigger_pattern": "@bot",
                "container_config": '{"timeout": 300}',
                "requires_trigger": 1,
            },
            {
                "jid": "telegram:222",
                "name": "Group B",
                "folder": "work",
                "trigger_pattern": None,
                "container_config": None,
                "requires_trigger": 0,
            },
        ]

        groups = await repo.get_groups_by_folder("work")

        assert len(groups) == 2
        assert groups[0].jid == "telegram:111"
        assert groups[0].folder == "work"
        assert groups[1].jid == "telegram:222"
        assert groups[1].requires_trigger is False
        mock_db.fetchall.assert_called_once()
        call_args = mock_db.fetchall.call_args
        assert "WHERE folder = ?" in call_args[0][0]
        assert call_args[0][1] == ("work",)

    @pytest.mark.asyncio
    async def test_group_exists_true(self, mock_db):
        """Test group_exists returns True (lines 130-134)."""
        repo = GroupRepository(mock_db)

        mock_db.fetchone.return_value = {"1": 1}

        result = await repo.group_exists("telegram:exists")

        assert result is True
        mock_db.fetchone.assert_called_once()
        call_args = mock_db.fetchone.call_args
        assert "SELECT 1 FROM groups WHERE jid = ?" in call_args[0][0]
        assert call_args[0][1] == ("telegram:exists",)

    @pytest.mark.asyncio
    async def test_group_exists_false(self, mock_db):
        """Test group_exists returns False."""
        repo = GroupRepository(mock_db)

        mock_db.fetchone.return_value = None

        result = await repo.group_exists("telegram:notfound")

        assert result is False


class TestMessageCache:
    """Tests for MessageCache class."""

    def test_cache_get_hit(self):
        """Test cache hit (lines 35-40)."""
        cache = MessageCache(max_size=10)

        msg = Message(
            id="msg1",
            chat_jid="telegram:123",
            sender="user1",
            content="Test",
            timestamp=datetime.now(),
            role=MessageRole.USER,
        )

        cache.put("msg1", msg)
        retrieved = cache.get("msg1")

        assert retrieved is not None
        assert retrieved.id == "msg1"
        assert retrieved.content == "Test"

    def test_cache_get_miss(self):
        """Test cache miss."""
        cache = MessageCache(max_size=10)

        result = cache.get("nonexistent")

        assert result is None

    def test_cache_put_update_existing(self):
        """Test updating existing cache entry (line 50)."""
        cache = MessageCache(max_size=10)

        msg1 = Message(
            id="msg1",
            chat_jid="telegram:123",
            sender="user1",
            content="Original",
            timestamp=datetime.now(),
            role=MessageRole.USER,
        )
        msg2 = Message(
            id="msg1",
            chat_jid="telegram:123",
            sender="user1",
            content="Updated",
            timestamp=datetime.now(),
            role=MessageRole.USER,
        )

        cache.put("msg1", msg1)
        cache.put("msg1", msg2)

        retrieved = cache.get("msg1")
        assert retrieved is not None
        assert retrieved.content == "Updated"

    def test_cache_eviction_when_full(self):
        """Test cache eviction when max_size reached (line 54)."""
        cache = MessageCache(max_size=3)

        for i in range(4):
            msg = Message(
                id=f"msg{i}",
                chat_jid="telegram:123",
                sender="user",
                content=f"Message {i}",
                timestamp=datetime.now(),
                role=MessageRole.USER,
            )
            cache.put(f"msg{i}", msg)

        assert cache.get("msg0") is None
        assert cache.get("msg1") is not None
        assert cache.get("msg2") is not None
        assert cache.get("msg3") is not None

    def test_cache_clear(self):
        """Test cache clear (line 60)."""
        cache = MessageCache(max_size=10)

        for i in range(5):
            msg = Message(
                id=f"msg{i}",
                chat_jid="telegram:123",
                sender="user",
                content=f"Message {i}",
                timestamp=datetime.now(),
                role=MessageRole.USER,
            )
            cache.put(f"msg{i}", msg)

        cache.clear()

        for i in range(5):
            assert cache.get(f"msg{i}") is None


class TestMessageRepositoryExtended:
    """Tests for MessageRepository uncovered paths."""

    @pytest.mark.asyncio
    async def test_get_new_messages_with_since(self, mock_db):
        """Test get_new_messages with since parameter (lines 141-150)."""
        repo = MessageRepository(mock_db, cache_size=100)

        since = datetime(2025, 1, 1, 12, 0)
        mock_db.fetchall.return_value = [
            {
                "id": "msg1",
                "chat_jid": "telegram:123",
                "sender": "user1",
                "sender_name": "User One",
                "content": "New message",
                "timestamp": "2025-01-01T13:00:00",
                "is_from_me": 0,
                "role": "user",
            }
        ]

        messages = await repo.get_new_messages(since=since)

        assert len(messages) == 1
        assert messages[0].id == "msg1"
        mock_db.fetchall.assert_called_once()
        call_args = mock_db.fetchall.call_args
        assert "WHERE timestamp > ?" in call_args[0][0]
        assert call_args[0][1] == ("2025-01-01T12:00:00",)

    @pytest.mark.asyncio
    async def test_get_new_messages_without_since(self, mock_db):
        """Test get_new_messages without since parameter (lines 151-158)."""
        repo = MessageRepository(mock_db, cache_size=100)

        mock_db.fetchall.return_value = [
            {
                "id": "msg1",
                "chat_jid": "telegram:111",
                "sender": "user1",
                "sender_name": None,
                "content": "Message 1",
                "timestamp": "2025-01-01T10:00:00",
                "is_from_me": 0,
                "role": "user",
            },
            {
                "id": "msg2",
                "chat_jid": "telegram:222",
                "sender": "user2",
                "sender_name": "User Two",
                "content": "Message 2",
                "timestamp": "2025-01-01T11:00:00",
                "is_from_me": 1,
                "role": "assistant",
            },
        ]

        messages = await repo.get_new_messages(since=None)

        assert len(messages) == 2
        assert messages[0].id == "msg1"
        assert messages[0].sender_name is None
        assert messages[1].id == "msg2"
        assert messages[1].is_from_me is True
        mock_db.fetchall.assert_called_once()
        call_args = mock_db.fetchall.call_args
        assert "WHERE timestamp > ?" not in call_args[0][0]
        assert "ORDER BY timestamp ASC" in call_args[0][0]
