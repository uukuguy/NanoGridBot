"""Unit tests for task logging module."""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from nanogridbot.task_logging import (
    TaskLogService,
    TaskExecutionStatus,
    TaskStatistics,
    create_task_log_service,
)


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for testing."""
    return tmp_path


@pytest.fixture
def task_log_service(temp_dir):
    """Create a TaskLogService instance with temporary directory."""
    return TaskLogService(temp_dir)


class TestTaskLogService:
    """Test TaskLogService functionality."""

    def test_log_execution_start(self, task_log_service, temp_dir):
        """Test logging execution start."""
        exec_id = task_log_service.log_execution_start(
            task_id=1,
            group_folder="testgroup",
            session_id="session-123",
        )

        assert exec_id == 1

        summary_path = task_log_service.get_execution_summary_path("testgroup")
        assert summary_path.exists()

    def test_log_execution_end_success(self, task_log_service):
        """Test logging successful execution end."""
        exec_id = task_log_service.log_execution_start(
            task_id=1,
            group_folder="testgroup",
        )

        task_log_service.log_execution_end(
            execution_id=exec_id,
            group_folder="testgroup",
            status=TaskExecutionStatus.SUCCESS,
            result="Task completed successfully",
        )

        executions = task_log_service.get_executions(group_folder="testgroup")
        assert len(executions) == 1
        assert executions[0]["status"] == "success"
        assert executions[0]["result"] == "Task completed successfully"

    def test_log_execution_end_failure(self, task_log_service):
        """Test logging failed execution end."""
        exec_id = task_log_service.log_execution_start(
            task_id=1,
            group_folder="testgroup",
        )

        task_log_service.log_execution_end(
            execution_id=exec_id,
            group_folder="testgroup",
            status=TaskExecutionStatus.FAILED,
            error_message="Something went wrong",
        )

        executions = task_log_service.get_executions(group_folder="testgroup")
        assert executions[0]["status"] == "failed"
        assert executions[0]["error_message"] == "Something went wrong"

    def test_get_executions_with_status_filter(self, task_log_service):
        """Test getting executions filtered by status."""
        # Create successful execution
        exec_id1 = task_log_service.log_execution_start(task_id=1, group_folder="testgroup")
        task_log_service.log_execution_end(exec_id1, "testgroup", TaskExecutionStatus.SUCCESS)

        # Create failed execution
        exec_id2 = task_log_service.log_execution_start(task_id=2, group_folder="testgroup")
        task_log_service.log_execution_end(exec_id2, "testgroup", TaskExecutionStatus.FAILED)

        # Filter by success
        success_executions = task_log_service.get_executions(
            group_folder="testgroup",
            status=TaskExecutionStatus.SUCCESS,
        )
        assert len(success_executions) == 1

        # Filter by failed
        failed_executions = task_log_service.get_executions(
            group_folder="testgroup",
            status=TaskExecutionStatus.FAILED,
        )
        assert len(failed_executions) == 1

    def test_get_executions_with_limit(self, task_log_service):
        """Test getting executions with limit."""
        for i in range(10):
            exec_id = task_log_service.log_execution_start(task_id=i, group_folder="testgroup")
            task_log_service.log_execution_end(exec_id, "testgroup", TaskExecutionStatus.SUCCESS)

        executions = task_log_service.get_executions(group_folder="testgroup", limit=5)
        assert len(executions) == 5

    def test_get_statistics(self, task_log_service):
        """Test getting task statistics."""
        # Run multiple executions
        for i in range(3):
            exec_id = task_log_service.log_execution_start(task_id=1, group_folder="testgroup")
            task_log_service.log_execution_end(exec_id, "testgroup", TaskExecutionStatus.SUCCESS)

        # Run one failed execution
        exec_id = task_log_service.log_execution_start(task_id=2, group_folder="testgroup")
        task_log_service.log_execution_end(exec_id, "testgroup", TaskExecutionStatus.FAILED)

        stats = task_log_service.get_statistics("testgroup")

        assert stats.total_executions == 4
        assert stats.success_count == 3
        assert stats.failed_count == 1

    def test_get_execution_detail(self, task_log_service):
        """Test getting execution detail."""
        exec_id = task_log_service.log_execution_start(
            task_id=1,
            group_folder="testgroup",
            session_id="session-abc",
        )
        task_log_service.log_execution_end(
            exec_id,
            "testgroup",
            TaskExecutionStatus.SUCCESS,
            result="Done",
        )

        detail = task_log_service.get_execution_detail(exec_id)
        assert detail is not None
        assert detail["id"] == exec_id
        assert detail["session_id"] == "session-abc"

    def test_clear_old_executions(self, task_log_service):
        """Test clearing old executions."""
        # Create 50 executions
        for i in range(50):
            exec_id = task_log_service.log_execution_start(task_id=1, group_folder="testgroup")
            task_log_service.log_execution_end(exec_id, "testgroup", TaskExecutionStatus.SUCCESS)

        # Keep only last 30
        cleared = task_log_service.clear_old_executions("testgroup", keep_last=30)

        assert cleared == 20

        executions = task_log_service.get_executions(group_folder="testgroup")
        assert len(executions) == 30


class TestCreateTaskLogService:
    """Test create_task_log_service factory function."""

    def test_create_task_log_service(self, temp_dir):
        """Test creating task log service via factory."""
        from nanogridbot import config as config_module
        original_get_config = getattr(config_module, 'get_config', None)

        mock_config = MagicMock()
        mock_config.store_dir = temp_dir

        try:
            config_module.get_config = lambda: mock_config
            service = create_task_log_service()

            assert isinstance(service, TaskLogService)
            assert service.log_dir == temp_dir / "task_logs"
        finally:
            if original_get_config:
                config_module.get_config = original_get_config
