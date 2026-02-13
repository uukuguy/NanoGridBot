"""Tests for the web module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from nanogridbot.web.app import (
    app,
    get_groups,
    get_tasks,
    get_messages,
    health_check,
    get_metrics,
    web_state,
    set_orchestrator,
)


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check_returns_healthy_status(self):
        """Test health check returns correct status."""
        # Use synchronous test client approach
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "0.1.0"

    @pytest.mark.asyncio
    async def test_health_check_async(self):
        """Test health check async endpoint."""
        result = await health_check()

        assert result["status"] == "healthy"
        assert result["version"] == "0.1.0"
        assert "timestamp" in result


class TestMetricsEndpoint:
    """Tests for metrics endpoint."""

    @pytest.mark.asyncio
    async def test_get_metrics_no_orchestrator(self):
        """Test metrics with no orchestrator."""
        web_state.orchestrator = None
        web_state.db = None

        result = await get_metrics()

        assert result["active_containers"] == 0
        assert result["registered_groups"] == 0
        assert result["active_tasks"] == 0
        assert result["connected_channels"] == 0
        assert result["total_channels"] == 0
        assert result["channels"] == []

    @pytest.mark.asyncio
    async def test_get_metrics_with_orchestrator(self):
        """Test metrics with mock orchestrator."""
        # Create mock orchestrator
        mock_channel = MagicMock()
        mock_channel.name = "test-channel"
        mock_channel.is_connected.return_value = True

        mock_orchestrator = MagicMock()
        mock_orchestrator.channels = [mock_channel]
        mock_orchestrator.registered_groups = {"group1": MagicMock(), "group2": MagicMock()}

        mock_queue = MagicMock()
        mock_queue.active_count = 2
        mock_orchestrator.queue = mock_queue

        web_state.orchestrator = mock_orchestrator
        web_state.db = None

        result = await get_metrics()

        assert result["active_containers"] == 2
        assert result["registered_groups"] == 2
        assert result["connected_channels"] == 1
        assert result["total_channels"] == 1
        assert len(result["channels"]) == 1
        assert result["channels"][0]["name"] == "test-channel"
        assert result["channels"][0]["connected"] is True


from nanogridbot.core.group_queue import GroupState


class TestGroupsEndpoint:
    """Tests for groups endpoint."""

    @pytest.mark.asyncio
    async def test_get_groups_no_orchestrator(self):
        """Test get groups with no orchestrator."""
        web_state.orchestrator = None

        result = await get_groups()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_groups_with_groups_no_queue(self):
        """Test get groups without queue attribute."""
        # Create mock group
        mock_group = MagicMock()
        mock_group.name = "Test Group"
        mock_group.folder = "test-folder"
        mock_group.trigger_pattern = "test.*"
        mock_group.requires_trigger = True

        mock_orchestrator = MagicMock()
        mock_orchestrator.registered_groups = {"test:123": mock_group}
        # No queue attribute

        web_state.orchestrator = mock_orchestrator

        result = await get_groups()

        assert len(result) == 1
        assert result[0]["jid"] == "test:123"
        assert result[0]["name"] == "Test Group"
        assert result[0]["active"] is False  # No queue, so inactive

    @pytest.mark.asyncio
    async def test_get_groups_with_groups_dict_state(self):
        """Test get groups with dict-based state."""
        # Create mock group
        mock_group = MagicMock()
        mock_group.name = "Test Group"
        mock_group.folder = "test-folder"
        mock_group.trigger_pattern = "test.*"
        mock_group.requires_trigger = True

        mock_orchestrator = MagicMock()
        mock_orchestrator.registered_groups = {"test:123": mock_group}

        # Use dict format for states (simulating dict from JSON)
        mock_queue = MagicMock()
        mock_queue.states = {"test:123": {"active": True}}
        mock_orchestrator.queue = mock_queue

        web_state.orchestrator = mock_orchestrator

        result = await get_groups()

        assert len(result) == 1
        assert result[0]["jid"] == "test:123"
        assert result[0]["name"] == "Test Group"
        assert result[0]["active"] is True  # Dict state with active=True


class TestTasksEndpoint:
    """Tests for tasks endpoint."""

    @pytest.mark.asyncio
    async def test_get_tasks_no_db(self):
        """Test get tasks with no database."""
        web_state.db = None
        web_state.orchestrator = None

        result = await get_tasks()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_tasks_with_db(self):
        """Test get tasks with database."""
        # Create mock task
        mock_task = MagicMock()
        mock_task.id = "task-1"
        mock_task.group_folder = "test-folder"
        mock_task.prompt = "Test prompt"
        mock_task.schedule_type = "CRON"
        mock_task.schedule_value = "0 * * * *"
        mock_task.status = "active"
        mock_task.next_run = datetime(2026, 1, 1, 12, 0, 0)
        mock_task.context_mode = "full"

        # Create mock repository
        mock_repo = MagicMock()
        mock_repo.get_active_tasks = AsyncMock(return_value=[mock_task])

        mock_db = MagicMock()
        mock_db.get_task_repository = MagicMock(return_value=mock_repo)

        web_state.db = mock_db

        result = await get_tasks()

        assert len(result) == 1
        assert result[0]["id"] == "task-1"
        assert result[0]["group_folder"] == "test-folder"
        assert result[0]["prompt"] == "Test prompt"
        assert result[0]["schedule_type"] == "CRON"
        assert result[0]["status"] == "active"


class TestMessagesEndpoint:
    """Tests for messages endpoint."""

    @pytest.mark.asyncio
    async def test_get_messages_no_db(self):
        """Test get messages with no database."""
        web_state.db = None

        result = await get_messages()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_messages_with_chat_jid(self):
        """Test get messages with specific chat."""
        # Create mock message
        mock_msg = MagicMock()
        mock_msg.id = "msg-1"
        mock_msg.chat_jid = "test:123"
        mock_msg.sender = "user:456"
        mock_msg.sender_name = "Test User"
        mock_msg.content = "Hello world"
        mock_msg.timestamp = datetime(2026, 1, 1, 12, 0, 0)
        mock_msg.is_from_me = False

        # Create mock repository
        mock_repo = MagicMock()
        mock_repo.get_recent_messages = AsyncMock(return_value=[mock_msg])

        mock_db = MagicMock()
        mock_db.get_message_repository = MagicMock(return_value=mock_repo)

        web_state.db = mock_db

        result = await get_messages(chat_jid="test:123")

        assert len(result) == 1
        assert result[0]["id"] == "msg-1"
        assert result[0]["chat_jid"] == "test:123"
        assert result[0]["sender"] == "user:456"
        assert result[0]["content"] == "Hello world"
        mock_repo.get_recent_messages.assert_called_once_with("test:123", 50)


class TestWebState:
    """Tests for web state management."""

    def test_set_orchestrator(self):
        """Test setting orchestrator."""
        mock_orchestrator = MagicMock()
        mock_db = MagicMock()
        mock_orchestrator.db = mock_db

        set_orchestrator(mock_orchestrator)

        assert web_state.orchestrator == mock_orchestrator
        assert web_state.db == mock_db

    def test_set_orchestrator_none(self):
        """Test setting orchestrator to None."""
        set_orchestrator(None)

        assert web_state.orchestrator is None
        assert web_state.db is None
