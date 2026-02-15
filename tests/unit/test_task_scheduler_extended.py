"""Extended unit tests for TaskScheduler to cover uncovered lines."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.core.task_scheduler import TaskScheduler
from nanogridbot.database import TaskRepository
from nanogridbot.types import RegisteredGroup, ScheduledTask, ScheduleType, TaskStatus


@pytest.fixture
def scheduler():
    """Create TaskScheduler instance with mocked dependencies."""
    config = MagicMock()
    db = MagicMock()
    queue = MagicMock()
    queue.enqueue_task = AsyncMock()
    return TaskScheduler(config=config, db=db, queue=queue)


class TestRunSchedulerErrorHandling:
    """Test _run_scheduler error handling (lines 58-61)."""

    @pytest.mark.asyncio
    async def test_run_scheduler_handles_exception(self, scheduler):
        """Test that _run_scheduler logs errors and continues running."""
        call_count = 0

        async def mock_check_and_run_tasks():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Test error in _check_and_run_tasks")
            # Stop after second call
            scheduler._running = False

        async def mock_sleep(seconds):
            # Don't actually sleep
            pass

        scheduler._running = True
        with patch.object(scheduler, "_check_and_run_tasks", mock_check_and_run_tasks):
            with patch("asyncio.sleep", mock_sleep):
                await scheduler._run_scheduler()

        # Should have been called twice (once with error, once without)
        assert call_count == 2


class TestCheckAndRunTasks:
    """Test _check_and_run_tasks method (lines 77-89)."""

    @pytest.mark.asyncio
    async def test_check_and_run_tasks_runs_due_once_task(self, scheduler):
        """Test running a due ONCE task and marking it COMPLETED."""
        past_time = datetime.now() - timedelta(minutes=5)
        task = ScheduledTask(
            id=1,
            group_folder="test_group",
            prompt="Test prompt",
            schedule_type=ScheduleType.ONCE,
            schedule_value="",
            status=TaskStatus.ACTIVE,
            next_run=past_time,
        )

        mock_task_repo = AsyncMock(spec=TaskRepository)
        mock_task_repo.get_active_tasks = AsyncMock(return_value=[task])
        mock_task_repo.update_task = AsyncMock()

        # Mock _calculate_next_run to return the past_time so task is considered due
        def mock_calculate_next_run(t):
            if t.schedule_type == ScheduleType.ONCE:
                return past_time
            return None

        with patch.object(TaskRepository, "__new__", return_value=mock_task_repo):
            with patch.object(scheduler, "_calculate_next_run", mock_calculate_next_run):
                with patch.object(scheduler, "_run_task", AsyncMock()) as mock_run:
                    await scheduler._check_and_run_tasks()

        # Verify task was run
        mock_run.assert_called_once_with(task)

        # Verify task status changed to COMPLETED
        assert task.status == TaskStatus.COMPLETED
        mock_task_repo.update_task.assert_called_once_with(task)

    @pytest.mark.asyncio
    async def test_check_and_run_tasks_runs_due_interval_task(self, scheduler):
        """Test running a due INTERVAL task and updating next_run."""
        past_time = datetime.now() - timedelta(minutes=5)
        future_time = datetime.now() + timedelta(hours=1)
        task = ScheduledTask(
            id=2,
            group_folder="test_group",
            prompt="Recurring task",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="1h",
            status=TaskStatus.ACTIVE,
            next_run=past_time,
        )

        mock_task_repo = AsyncMock(spec=TaskRepository)
        mock_task_repo.get_active_tasks = AsyncMock(return_value=[task])
        mock_task_repo.update_task = AsyncMock()

        call_count = 0

        def mock_calculate_next_run(t):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: return past_time so task is due
                return past_time
            else:
                # Second call: return future_time for next run
                return future_time

        with patch.object(TaskRepository, "__new__", return_value=mock_task_repo):
            with patch.object(scheduler, "_calculate_next_run", mock_calculate_next_run):
                with patch.object(scheduler, "_run_task", AsyncMock()) as mock_run:
                    await scheduler._check_and_run_tasks()

        # Verify task was run
        mock_run.assert_called_once_with(task)

        # Verify task status is still ACTIVE and next_run was updated
        assert task.status == TaskStatus.ACTIVE
        assert task.next_run == future_time
        mock_task_repo.update_task.assert_called_once_with(task)

    @pytest.mark.asyncio
    async def test_check_and_run_tasks_skips_future_tasks(self, scheduler):
        """Test that future tasks are not run."""
        future_time = datetime.now() + timedelta(hours=1)
        task = ScheduledTask(
            id=3,
            group_folder="test_group",
            prompt="Future task",
            schedule_type=ScheduleType.ONCE,
            schedule_value="",
            status=TaskStatus.ACTIVE,
            next_run=future_time,
        )

        mock_task_repo = AsyncMock(spec=TaskRepository)
        mock_task_repo.get_active_tasks = AsyncMock(return_value=[task])

        # Mock _calculate_next_run to return future_time
        def mock_calculate_next_run(t):
            return future_time

        with patch.object(TaskRepository, "__new__", return_value=mock_task_repo):
            with patch.object(scheduler, "_calculate_next_run", mock_calculate_next_run):
                with patch.object(scheduler, "_run_task", AsyncMock()) as mock_run:
                    await scheduler._check_and_run_tasks()

        # Verify task was NOT run
        mock_run.assert_not_called()


class TestCalculateNextRunCronWithoutNextRun:
    """Test _calculate_next_run with CRON and no next_run (line 108-110)."""

    def test_calculate_next_run_cron_without_next_run(self, scheduler):
        """Test CRON calculation when next_run is None (uses now as base)."""
        task = ScheduledTask(
            group_folder="test",
            prompt="test",
            schedule_type=ScheduleType.CRON,
            schedule_value="0 * * * *",  # Every hour
            status=TaskStatus.ACTIVE,
            next_run=None,  # No next_run set
        )

        now = datetime.now()
        result = scheduler._calculate_next_run(task)

        assert result is not None
        assert result > now
        # Should be within the next hour
        assert result <= now + timedelta(hours=1, minutes=1)

    def test_calculate_next_run_cron_with_next_run(self, scheduler):
        """Test CRON calculation when next_run is set (uses next_run as base)."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        task = ScheduledTask(
            group_folder="test",
            prompt="test",
            schedule_type=ScheduleType.CRON,
            schedule_value="0 * * * *",  # Every hour
            status=TaskStatus.ACTIVE,
            next_run=base_time,  # next_run is set
        )

        result = scheduler._calculate_next_run(task)

        assert result is not None
        # Should be one hour after base_time
        assert result == datetime(2024, 1, 1, 13, 0, 0)


class TestCalculateNextRunUnknownType:
    """Test _calculate_next_run returns None for unknown schedule type (line 133)."""

    def test_calculate_next_run_unknown_schedule_type(self, scheduler):
        """Test that unknown schedule type returns None."""
        # Create a task with an invalid schedule type by bypassing validation
        task = ScheduledTask(
            group_folder="test",
            prompt="test",
            schedule_type=ScheduleType.INTERVAL,  # Will be modified
            schedule_value="1h",
            status=TaskStatus.ACTIVE,
        )

        # Manually set an invalid schedule type
        task.schedule_type = "UNKNOWN_TYPE"  # type: ignore

        result = scheduler._calculate_next_run(task)
        assert result is None


class TestParseIntervalUnknownUnit:
    """Test _parse_interval returns None for unknown unit (line 162)."""

    def test_parse_interval_unknown_unit(self, scheduler):
        """Test that unknown unit returns None after all elif branches."""
        # This tests the fall-through case after all elif statements
        # We need to mock the regex match to return an unknown unit
        with patch("re.match") as mock_match:
            mock_match.return_value = MagicMock()
            mock_match.return_value.groups.return_value = ("10", "x")  # Unknown unit 'x'

            result = scheduler._parse_interval("10x")

        assert result is None


class TestRunTask:
    """Test _run_task method (lines 170-183)."""

    @pytest.mark.asyncio
    async def test_run_task_success(self, scheduler):
        """Test successfully running a task."""
        task = ScheduledTask(
            id=1,
            group_folder="test_group",
            prompt="Test prompt for execution",
            schedule_type=ScheduleType.ONCE,
            schedule_value="",
            status=TaskStatus.ACTIVE,
        )

        group = RegisteredGroup(
            jid="whatsapp:1234567890@s.whatsapp.net",
            name="Test Group",
            folder="test_group",
        )

        mock_group_repo = AsyncMock()
        mock_group_repo.get_group_by_folder = AsyncMock(return_value=group)

        scheduler.db.get_group_repository = MagicMock(return_value=mock_group_repo)
        scheduler.queue.enqueue_task = AsyncMock()

        await scheduler._run_task(task)

        # Verify group was fetched
        mock_group_repo.get_group_by_folder.assert_called_once_with("test_group")

        # Verify task was enqueued
        scheduler.queue.enqueue_task.assert_called_once_with(
            jid=group.jid,
            group=group,
            task=task,
            session_id=None,
        )

    @pytest.mark.asyncio
    async def test_run_task_group_not_found(self, scheduler):
        """Test running a task when group is not found."""
        task = ScheduledTask(
            id=2,
            group_folder="nonexistent_group",
            prompt="Test prompt",
            schedule_type=ScheduleType.ONCE,
            schedule_value="",
            status=TaskStatus.ACTIVE,
        )

        mock_group_repo = AsyncMock()
        mock_group_repo.get_group_by_folder = AsyncMock(return_value=None)

        scheduler.db.get_group_repository = MagicMock(return_value=mock_group_repo)
        scheduler.queue.enqueue_task = AsyncMock()

        await scheduler._run_task(task)

        # Verify group was fetched
        mock_group_repo.get_group_by_folder.assert_called_once_with("nonexistent_group")

        # Verify task was NOT enqueued
        scheduler.queue.enqueue_task.assert_not_called()


class TestPauseTaskNotFound:
    """Test pause_task when task not found (line 264)."""

    @pytest.mark.asyncio
    async def test_pause_task_not_found(self, scheduler):
        """Test pausing a non-existent task returns False."""
        mock_task_repo = AsyncMock(spec=TaskRepository)
        mock_task_repo.get_task = AsyncMock(return_value=None)

        with patch.object(TaskRepository, "__new__", return_value=mock_task_repo):
            result = await scheduler.pause_task(999)

        assert result is False
        mock_task_repo.get_task.assert_called_once_with(999)


class TestResumeTaskNotFound:
    """Test resume_task when task not found (line 284)."""

    @pytest.mark.asyncio
    async def test_resume_task_not_found(self, scheduler):
        """Test resuming a non-existent task returns False."""
        mock_task_repo = AsyncMock(spec=TaskRepository)
        mock_task_repo.get_task = AsyncMock(return_value=None)

        with patch.object(TaskRepository, "__new__", return_value=mock_task_repo):
            result = await scheduler.resume_task(999)

        assert result is False
        mock_task_repo.get_task.assert_called_once_with(999)

    @pytest.mark.asyncio
    async def test_resume_task_not_paused(self, scheduler):
        """Test resuming a task that is not PAUSED returns False."""
        task = ScheduledTask(
            id=1,
            group_folder="test",
            prompt="test",
            schedule_type=ScheduleType.INTERVAL,
            schedule_value="1h",
            status=TaskStatus.ACTIVE,  # Not PAUSED
        )

        mock_task_repo = AsyncMock(spec=TaskRepository)
        mock_task_repo.get_task = AsyncMock(return_value=task)

        with patch.object(TaskRepository, "__new__", return_value=mock_task_repo):
            result = await scheduler.resume_task(1)

        assert result is False
        mock_task_repo.get_task.assert_called_once_with(1)
