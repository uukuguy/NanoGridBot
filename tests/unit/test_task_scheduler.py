"""Unit tests for TaskScheduler."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.core.group_queue import GroupQueue
from nanogridbot.core.task_scheduler import TaskScheduler
from nanogridbot.database import Database, TaskRepository
from nanogridbot.types import ScheduledTask, ScheduleType, TaskStatus


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = MagicMock()
    config.data_dir = MagicMock()
    return config


@pytest.fixture
def mock_db():
    """Mock database."""
    return MagicMock(spec=Database)


@pytest.fixture
def mock_queue():
    """Mock group queue."""
    return MagicMock(spec=GroupQueue)


@pytest.fixture
def scheduler(mock_config, mock_db, mock_queue):
    """Create TaskScheduler instance."""
    return TaskScheduler(mock_config, mock_db, mock_queue)


class TestTaskSchedulerInit:
    """Test TaskScheduler initialization."""

    def test_init(self, scheduler, mock_config, mock_db, mock_queue):
        """Test scheduler initialization."""
        assert scheduler.config == mock_config
        assert scheduler.db == mock_db
        assert scheduler.queue == mock_queue
        assert scheduler._running is False
        assert scheduler._task is None


class TestTaskSchedulerLifecycle:
    """Test TaskScheduler start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start(self, scheduler):
        """Test starting the scheduler."""
        await scheduler.start()

        assert scheduler._running is True
        assert scheduler._task is not None
        assert not scheduler._task.done()

        # Cleanup
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop(self, scheduler):
        """Test stopping the scheduler."""
        await scheduler.start()
        await scheduler.stop()

        assert scheduler._running is False
        assert scheduler._task.cancelled() or scheduler._task.done()

    @pytest.mark.asyncio
    async def test_stop_without_start(self, scheduler):
        """Test stopping scheduler that was never started."""
        await scheduler.stop()
        assert scheduler._running is False


class TestIntervalParsing:
    """Test interval string parsing."""

    def test_parse_interval_seconds(self, scheduler):
        """Test parsing seconds interval."""
        result = scheduler._parse_interval("30s")
        assert result == timedelta(seconds=30)

    def test_parse_interval_minutes(self, scheduler):
        """Test parsing minutes interval."""
        result = scheduler._parse_interval("15m")
        assert result == timedelta(minutes=15)

    def test_parse_interval_hours(self, scheduler):
        """Test parsing hours interval."""
        result = scheduler._parse_interval("2h")
        assert result == timedelta(hours=2)

    def test_parse_interval_days(self, scheduler):
        """Test parsing days interval."""
        result = scheduler._parse_interval("7d")
        assert result == timedelta(days=7)

    def test_parse_interval_invalid(self, scheduler):
        """Test parsing invalid interval."""
        assert scheduler._parse_interval("invalid") is None
        assert scheduler._parse_interval("10x") is None
        assert scheduler._parse_interval("") is None


class TestNextRunCalculation:
    """Test next run time calculation."""

    def test_calculate_next_run_inactive(self, scheduler):
        """Test calculation for inactive task."""
        task = ScheduledTask(
            group_folder="test",
            prompt="test",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="1h",
            status=TaskStatus.COMPLETED,
        )

        result = scheduler._calculate_next_run(task)
        assert result is None

    def test_calculate_next_run_interval_first_time(self, scheduler):
        """Test interval calculation for first run."""
        task = ScheduledTask(
            group_folder="test",
            prompt="test",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="1h",
            status=TaskStatus.ACTIVE,
        )

        now = datetime.now()
        result = scheduler._calculate_next_run(task)

        assert result is not None
        assert result > now
        assert result <= now + timedelta(hours=1, seconds=1)

    def test_calculate_next_run_interval_with_next_run(self, scheduler):
        """Test interval calculation with existing next_run."""
        base_time = datetime.now()
        task = ScheduledTask(
            group_folder="test",
            prompt="test",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="30m",
            status=TaskStatus.ACTIVE,
            next_run=base_time,
        )

        result = scheduler._calculate_next_run(task)

        assert result == base_time + timedelta(minutes=30)

    def test_calculate_next_run_cron(self, scheduler):
        """Test cron expression calculation."""
        task = ScheduledTask(
            group_folder="test",
            prompt="test",
            schedule_type=ScheduleType.CRON,
            schedule_value="0 * * * *",  # Every hour
            status=TaskStatus.ACTIVE,
        )

        now = datetime.now()
        result = scheduler._calculate_next_run(task)

        assert result is not None
        assert result > now

    def test_calculate_next_run_cron_invalid(self, scheduler):
        """Test invalid cron expression."""
        task = ScheduledTask(
            group_folder="test",
            prompt="test",
            schedule_type=ScheduleType.CRON,
            schedule_value="invalid cron",
            status=TaskStatus.ACTIVE,
        )

        result = scheduler._calculate_next_run(task)
        assert result is None

    def test_calculate_next_run_once_future(self, scheduler):
        """Test one-time task in the future."""
        future_time = datetime.now() + timedelta(hours=1)
        task = ScheduledTask(
            group_folder="test",
            prompt="test",
            schedule_type=ScheduleType.ONCE,
            schedule_value="",
            status=TaskStatus.ACTIVE,
            next_run=future_time,
        )

        result = scheduler._calculate_next_run(task)
        assert result == future_time

    def test_calculate_next_run_once_past(self, scheduler):
        """Test one-time task in the past."""
        past_time = datetime.now() - timedelta(hours=1)
        task = ScheduledTask(
            group_folder="test",
            prompt="test",
            schedule_type=ScheduleType.ONCE,
            schedule_value="",
            status=TaskStatus.ACTIVE,
            next_run=past_time,
        )

        result = scheduler._calculate_next_run(task)
        assert result is None


class TestScheduleTask:
    """Test task scheduling."""

    @pytest.mark.asyncio
    async def test_schedule_task(self, scheduler, mock_db):
        """Test scheduling a new task."""
        mock_task_repo = AsyncMock(spec=TaskRepository)
        mock_task_repo.save_task = AsyncMock(side_effect=lambda t: t)

        with patch.object(TaskRepository, '__new__', return_value=mock_task_repo):
            result = await scheduler.schedule_task(
                group_folder="test_group",
                prompt="Test prompt",
                schedule_type=ScheduleType.INTERVAL,
                schedule_value="1h",
            )

        assert result.group_folder == "test_group"
        assert result.prompt == "Test prompt"
        assert result.schedule_type == ScheduleType.INTERVAL
        assert result.schedule_value == "1h"
        assert result.status == TaskStatus.ACTIVE
        assert result.next_run is not None
        mock_task_repo.save_task.assert_called_once()


class TestTaskControl:
    """Test task control operations."""

    @pytest.mark.asyncio
    async def test_cancel_task(self, scheduler, mock_db):
        """Test cancelling a task."""
        task = ScheduledTask(
            id=1,
            group_folder="test",
            prompt="test",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="1h",
            status=TaskStatus.ACTIVE,
        )

        mock_task_repo = AsyncMock(spec=TaskRepository)
        mock_task_repo.get_task = AsyncMock(return_value=task)
        mock_task_repo.update_task = AsyncMock()

        with patch.object(TaskRepository, '__new__', return_value=mock_task_repo):
            result = await scheduler.cancel_task(1)

        assert result is True
        assert task.status == TaskStatus.COMPLETED
        mock_task_repo.update_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_task_not_found(self, scheduler, mock_db):
        """Test cancelling non-existent task."""
        mock_task_repo = AsyncMock(spec=TaskRepository)
        mock_task_repo.get_task = AsyncMock(return_value=None)

        with patch.object(TaskRepository, '__new__', return_value=mock_task_repo):
            result = await scheduler.cancel_task(999)

        assert result is False

    @pytest.mark.asyncio
    async def test_pause_task(self, scheduler, mock_db):
        """Test pausing a task."""
        task = ScheduledTask(
            id=1,
            group_folder="test",
            prompt="test",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="1h",
            status=TaskStatus.ACTIVE,
        )

        mock_task_repo = AsyncMock(spec=TaskRepository)
        mock_task_repo.get_task = AsyncMock(return_value=task)
        mock_task_repo.update_task = AsyncMock()

        with patch.object(TaskRepository, '__new__', return_value=mock_task_repo):
            result = await scheduler.pause_task(1)

        assert result is True
        assert task.status == TaskStatus.PAUSED

    @pytest.mark.asyncio
    async def test_resume_task(self, scheduler, mock_db):
        """Test resuming a paused task."""
        task = ScheduledTask(
            id=1,
            group_folder="test",
            prompt="test",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="1h",
            status=TaskStatus.PAUSED,
        )

        mock_task_repo = AsyncMock(spec=TaskRepository)
        mock_task_repo.get_task = AsyncMock(return_value=task)
        mock_task_repo.update_task = AsyncMock()

        with patch.object(TaskRepository, '__new__', return_value=mock_task_repo):
            result = await scheduler.resume_task(1)

        assert result is True
        assert task.status == TaskStatus.ACTIVE
        assert task.next_run is not None

    @pytest.mark.asyncio
    async def test_resume_task_not_paused(self, scheduler, mock_db):
        """Test resuming a task that is not paused."""
        task = ScheduledTask(
            id=1,
            group_folder="test",
            prompt="test",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="1h",
            status=TaskStatus.ACTIVE,
        )

        mock_task_repo = AsyncMock(spec=TaskRepository)
        mock_task_repo.get_task = AsyncMock(return_value=task)

        with patch.object(TaskRepository, '__new__', return_value=mock_task_repo):
            result = await scheduler.resume_task(1)

        assert result is False
