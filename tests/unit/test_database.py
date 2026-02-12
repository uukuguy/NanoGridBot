"""Unit tests for database modules."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path

from nanogridbot.database import Database, GroupRepository, MessageRepository, TaskRepository
from nanogridbot.types import (
    Message,
    MessageRole,
    RegisteredGroup,
    ScheduleType,
    ScheduledTask,
    TaskStatus,
)


@pytest.fixture
async def db(tmp_path: Path) -> Database:
    """Create a test database."""
    db = Database(tmp_path / "test.db")
    await db.initialize()
    yield db
    await db.close()


class TestDatabase:
    """Tests for Database class."""

    async def test_initialize_creates_tables(self, db: Database):
        """Test that initialize creates all required tables."""
        # Check messages table exists
        result = await db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
        )
        assert result is not None
        assert result["name"] == "messages"

        # Check groups table exists
        result = await db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='groups'"
        )
        assert result is not None
        assert result["name"] == "groups"

        # Check tasks table exists
        result = await db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
        )
        assert result is not None
        assert result["name"] == "tasks"

    async def test_execute_and_fetch(self, db: Database):
        """Test execute and fetch methods."""
        await db.execute(
            "INSERT INTO messages (id, chat_jid, sender, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            ("1", "test@chat", "user", "hello", "2024-01-01T00:00:00"),
        )
        await db.commit()

        result = await db.fetchone("SELECT * FROM messages WHERE id = ?", ("1",))
        assert result is not None
        assert result["content"] == "hello"


class TestMessageRepository:
    """Tests for MessageRepository class."""

    @pytest.fixture
    def repo(self, db: Database) -> MessageRepository:
        """Create a message repository."""
        return MessageRepository(db)

    async def test_store_message(self, repo: MessageRepository):
        """Test storing a message."""
        message = Message(
            id="msg_001",
            chat_jid="telegram:123456",
            sender="user123",
            sender_name="Test User",
            content="Hello, world!",
            timestamp=datetime.now(),
            is_from_me=False,
            role=MessageRole.USER,
        )

        await repo.store_message(message)

        # Verify message was stored
        result = await repo._db.fetchone("SELECT * FROM messages WHERE id = ?", ("msg_001",))
        assert result is not None
        assert result["content"] == "Hello, world!"
        assert result["sender"] == "user123"

    async def test_get_messages_since(self, repo: MessageRepository):
        """Test getting messages since a timestamp."""
        now = datetime.now()
        older = now - timedelta(hours=1)

        # Store messages
        msg1 = Message(
            id="msg_old",
            chat_jid="telegram:123",
            sender="user1",
            content="Old message",
            timestamp=older,
            role=MessageRole.USER,
        )
        msg2 = Message(
            id="msg_new",
            chat_jid="telegram:123",
            sender="user2",
            content="New message",
            timestamp=now,
            role=MessageRole.USER,
        )

        await repo.store_message(msg1)
        await repo.store_message(msg2)

        # Get messages since now - should only return msg_new
        messages = await repo.get_messages_since("telegram:123", now - timedelta(minutes=30))
        assert len(messages) == 1
        assert messages[0].id == "msg_new"

    async def test_get_recent_messages(self, repo: MessageRepository):
        """Test getting recent messages."""
        now = datetime.now()

        for i in range(5):
            msg = Message(
                id=f"msg_{i}",
                chat_jid="telegram:999",
                sender="user",
                content=f"Message {i}",
                timestamp=now - timedelta(minutes=5 - i),
                role=MessageRole.USER,
            )
            await repo.store_message(msg)

        messages = await repo.get_recent_messages("telegram:999", limit=3)
        assert len(messages) == 3

    async def test_delete_old_messages(self, repo: MessageRepository):
        """Test deleting old messages."""
        old_date = datetime.now() - timedelta(days=30)
        recent_date = datetime.now() - timedelta(days=1)

        msg_old = Message(
            id="msg_old",
            chat_jid="telegram:123",
            sender="user",
            content="Old",
            timestamp=old_date,
            role=MessageRole.USER,
        )
        msg_recent = Message(
            id="msg_recent",
            chat_jid="telegram:123",
            sender="user",
            content="Recent",
            timestamp=recent_date,
            role=MessageRole.USER,
        )

        await repo.store_message(msg_old)
        await repo.store_message(msg_recent)

        deleted = await repo.delete_old_messages(datetime.now() - timedelta(days=7))
        assert deleted == 1


class TestGroupRepository:
    """Tests for GroupRepository class."""

    @pytest.fixture
    def repo(self, db: Database) -> GroupRepository:
        """Create a group repository."""
        return GroupRepository(db)

    async def test_save_group(self, repo: GroupRepository):
        """Test saving a group."""
        group = RegisteredGroup(
            jid="telegram:-1001234567890",
            name="Test Group",
            folder="test_group",
            trigger_pattern=None,
            container_config={"timeout": 300},
            requires_trigger=True,
        )

        await repo.save_group(group)

        result = await repo._db.fetchone("SELECT * FROM groups WHERE jid = ?", (group.jid,))
        assert result is not None
        assert result["name"] == "Test Group"
        assert result["folder"] == "test_group"

    async def test_get_group(self, repo: GroupRepository):
        """Test getting a group by JID."""
        group = RegisteredGroup(
            jid="telegram:123",
            name="My Group",
            folder="my_folder",
            requires_trigger=True,
        )
        await repo.save_group(group)

        retrieved = await repo.get_group("telegram:123")
        assert retrieved is not None
        assert retrieved.name == "My Group"
        assert retrieved.folder == "my_folder"

    async def test_get_groups(self, repo: GroupRepository):
        """Test getting all groups."""
        group1 = RegisteredGroup(
            jid="telegram:1", name="Group A", folder="a", requires_trigger=True
        )
        group2 = RegisteredGroup(
            jid="telegram:2", name="Group B", folder="b", requires_trigger=True
        )

        await repo.save_group(group1)
        await repo.save_group(group2)

        groups = await repo.get_groups()
        assert len(groups) == 2

    async def test_delete_group(self, repo: GroupRepository):
        """Test deleting a group."""
        group = RegisteredGroup(
            jid="telegram:del", name="Delete Me", folder="del", requires_trigger=True
        )
        await repo.save_group(group)

        deleted = await repo.delete_group("telegram:del")
        assert deleted is True

        result = await repo.get_group("telegram:del")
        assert result is None


class TestTaskRepository:
    """Tests for TaskRepository class."""

    @pytest.fixture
    def repo(self, db: Database) -> TaskRepository:
        """Create a task repository."""
        return TaskRepository(db)

    async def test_save_task(self, repo: TaskRepository):
        """Test saving a task."""
        task = ScheduledTask(
            group_folder="my_group",
            prompt="Hello, assistant!",
            schedule_type=ScheduleType.CRON,
            schedule_value="0 9 * * *",
            status=TaskStatus.ACTIVE,
            next_run=datetime.now() + timedelta(hours=1),
            context_mode="group",
            target_chat_jid="telegram:123",
        )

        task_id = await repo.save_task(task)
        assert task_id is not None
        assert task_id > 0

    async def test_get_active_tasks(self, repo: TaskRepository):
        """Test getting active tasks."""
        task1 = ScheduledTask(
            group_folder="group1",
            prompt="Task 1",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="3600",
            status=TaskStatus.ACTIVE,
            next_run=datetime.now() + timedelta(hours=1),
        )
        task2 = ScheduledTask(
            group_folder="group2",
            prompt="Task 2",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="7200",
            status=TaskStatus.PAUSED,
            next_run=datetime.now() + timedelta(hours=2),
        )

        await repo.save_task(task1)
        await repo.save_task(task2)

        active = await repo.get_active_tasks()
        assert len(active) == 1
        assert active[0].group_folder == "group1"

    async def test_update_task_status(self, repo: TaskRepository):
        """Test updating task status."""
        task = ScheduledTask(
            group_folder="test",
            prompt="Test",
            schedule_type=ScheduleType.ONCE,
            schedule_value="2025-01-01T00:00:00",
            status=TaskStatus.ACTIVE,
        )

        task_id = await repo.save_task(task)
        await repo.update_task_status(task_id, TaskStatus.COMPLETED)

        updated = await repo.get_task(task_id)
        assert updated is not None
        assert updated.status == TaskStatus.COMPLETED

    async def test_get_due_tasks(self, repo: TaskRepository):
        """Test getting due tasks."""
        now = datetime.now()

        task1 = ScheduledTask(
            group_folder="due",
            prompt="Due now",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="3600",
            status=TaskStatus.ACTIVE,
            next_run=now - timedelta(minutes=1),  # Past due
        )
        task2 = ScheduledTask(
            group_folder="not_due",
            prompt="Not due",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="3600",
            status=TaskStatus.ACTIVE,
            next_run=now + timedelta(hours=1),  # Future
        )

        await repo.save_task(task1)
        await repo.save_task(task2)

        due = await repo.get_due_tasks()
        assert len(due) == 1
        assert due[0].group_folder == "due"
