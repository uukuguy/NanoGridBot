"""Unit tests for web application."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from nanogridbot.web.app import (
    WebState,
    app,
    create_app,
    get_app,
    set_orchestrator,
    web_state,
)


@pytest.fixture
def client():
    """Create test client."""
    # Reset state
    web_state.orchestrator = None
    web_state.db = None
    return TestClient(app)


@pytest.fixture
def mock_orchestrator():
    """Create mock orchestrator."""
    orch = MagicMock()
    orch.registered_groups = {}
    orch.channels = []
    orch.db = MagicMock()
    orch.queue = MagicMock()
    orch.queue.active_count = 0
    orch.queue.states = {}
    return orch


class TestWebState:
    """Test WebState class."""

    def test_initial_state(self):
        state = WebState()
        assert state.orchestrator is None
        assert state.db is None


class TestSetOrchestrator:
    """Test set_orchestrator function."""

    def test_sets_orchestrator(self):
        orch = MagicMock()
        orch.db = MagicMock()
        set_orchestrator(orch)
        assert web_state.orchestrator is orch
        assert web_state.db is orch.db
        # Cleanup
        web_state.orchestrator = None
        web_state.db = None

    def test_sets_none(self):
        set_orchestrator(None)
        assert web_state.orchestrator is None
        assert web_state.db is None


class TestCreateApp:
    """Test create_app function."""

    def test_returns_app(self):
        result = create_app()
        assert result is app

    def test_with_orchestrator(self):
        orch = MagicMock()
        orch.db = MagicMock()
        result = create_app(orch)
        assert result is app
        assert web_state.orchestrator is orch
        # Cleanup
        web_state.orchestrator = None
        web_state.db = None


class TestGetApp:
    """Test get_app function."""

    def test_returns_app(self):
        assert get_app() is app


class TestRootEndpoint:
    """Test root dashboard endpoint."""

    def test_returns_html(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "NanoGridBot Dashboard" in response.text


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "0.1.0"


class TestGroupsEndpoint:
    """Test groups API endpoint."""

    def test_no_orchestrator(self, client):
        response = client.get("/api/groups")
        assert response.status_code == 200
        assert response.json() == []

    def test_with_groups(self, client, mock_orchestrator):
        group = MagicMock()
        group.name = "Test Group"
        group.folder = "test"
        group.trigger_pattern = "@bot"
        group.requires_trigger = True
        mock_orchestrator.registered_groups = {"jid1": group}

        set_orchestrator(mock_orchestrator)
        response = client.get("/api/groups")
        data = response.json()
        assert len(data) == 1
        assert data[0]["jid"] == "jid1"
        assert data[0]["name"] == "Test Group"
        # Cleanup
        web_state.orchestrator = None
        web_state.db = None


class TestTasksEndpoint:
    """Test tasks API endpoint."""

    def test_no_db(self, client):
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_with_tasks(self, client, mock_orchestrator):
        task = MagicMock()
        task.id = 1
        task.group_folder = "test"
        task.prompt = "do something"
        task.schedule_type = "cron"
        task.schedule_value = "* * * * *"
        task.status = "active"
        task.next_run = datetime(2024, 1, 1, 12, 0, 0)
        task.context_mode = "full"

        task_repo = MagicMock()
        task_repo.get_active_tasks = AsyncMock(return_value=[task])
        mock_orchestrator.db.get_task_repository.return_value = task_repo

        set_orchestrator(mock_orchestrator)
        response = client.get("/api/tasks")
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == 1
        assert data[0]["schedule_type"] == "cron"
        # Cleanup
        web_state.orchestrator = None
        web_state.db = None

    def test_db_error_returns_empty(self, client, mock_orchestrator):
        task_repo = MagicMock()
        task_repo.get_active_tasks = AsyncMock(side_effect=Exception("db error"))
        mock_orchestrator.db.get_task_repository.return_value = task_repo

        set_orchestrator(mock_orchestrator)
        response = client.get("/api/tasks")
        assert response.json() == []
        # Cleanup
        web_state.orchestrator = None
        web_state.db = None


class TestMessagesEndpoint:
    """Test messages API endpoint."""

    def test_no_db(self, client):
        response = client.get("/api/messages")
        assert response.status_code == 200
        assert response.json() == []

    def test_with_messages(self, client, mock_orchestrator):
        msg = MagicMock()
        msg.id = 1
        msg.chat_jid = "chat1"
        msg.sender = "user1"
        msg.sender_name = "Alice"
        msg.content = "Hello"
        msg.timestamp = datetime(2024, 1, 1, 12, 0, 0)
        msg.is_from_me = False

        msg_repo = MagicMock()
        msg_repo.get_new_messages = AsyncMock(return_value=[msg])
        mock_orchestrator.db.get_message_repository.return_value = msg_repo

        set_orchestrator(mock_orchestrator)
        response = client.get("/api/messages")
        data = response.json()
        assert len(data) == 1
        assert data[0]["sender"] == "user1"
        # Cleanup
        web_state.orchestrator = None
        web_state.db = None

    def test_with_chat_jid_filter(self, client, mock_orchestrator):
        msg = MagicMock()
        msg.id = 1
        msg.chat_jid = "chat1"
        msg.sender = "user1"
        msg.sender_name = "Alice"
        msg.content = "Hello"
        msg.timestamp = datetime(2024, 1, 1)
        msg.is_from_me = False

        msg_repo = MagicMock()
        msg_repo.get_recent_messages = AsyncMock(return_value=[msg])
        mock_orchestrator.db.get_message_repository.return_value = msg_repo

        set_orchestrator(mock_orchestrator)
        response = client.get("/api/messages?chat_jid=chat1&limit=10")
        data = response.json()
        assert len(data) == 1
        msg_repo.get_recent_messages.assert_called_once_with("chat1", 10)
        # Cleanup
        web_state.orchestrator = None
        web_state.db = None

    def test_db_error_returns_empty(self, client, mock_orchestrator):
        msg_repo = MagicMock()
        msg_repo.get_new_messages = AsyncMock(side_effect=Exception("db error"))
        mock_orchestrator.db.get_message_repository.return_value = msg_repo

        set_orchestrator(mock_orchestrator)
        response = client.get("/api/messages")
        assert response.json() == []
        # Cleanup
        web_state.orchestrator = None
        web_state.db = None


class TestMetricsEndpoint:
    """Test metrics API endpoint."""

    def test_no_orchestrator(self, client):
        response = client.get("/api/health/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["active_containers"] == 0
        assert data["registered_groups"] == 0

    def test_with_orchestrator(self, client, mock_orchestrator):
        channel = MagicMock()
        channel.name = "telegram"
        channel.is_connected.return_value = True
        mock_orchestrator.channels = [channel]
        mock_orchestrator.queue.active_count = 2

        group = MagicMock()
        mock_orchestrator.registered_groups = {"g1": group, "g2": group}

        task_repo = MagicMock()
        task_repo.get_active_tasks = AsyncMock(return_value=[MagicMock(), MagicMock()])
        mock_orchestrator.db.get_task_repository.return_value = task_repo

        set_orchestrator(mock_orchestrator)
        response = client.get("/api/health/metrics")
        data = response.json()
        assert data["active_containers"] == 2
        assert data["registered_groups"] == 2
        assert data["active_tasks"] == 2
        assert data["connected_channels"] == 1
        assert data["total_channels"] == 1
        # Cleanup
        web_state.orchestrator = None
        web_state.db = None

    def test_metrics_db_error(self, client, mock_orchestrator):
        """Test metrics when db throws error."""
        task_repo = MagicMock()
        task_repo.get_active_tasks = AsyncMock(side_effect=Exception("db error"))
        mock_orchestrator.db.get_task_repository.return_value = task_repo

        set_orchestrator(mock_orchestrator)
        response = client.get("/api/health/metrics")
        data = response.json()
        assert data["active_tasks"] == 0
        # Cleanup
        web_state.orchestrator = None
        web_state.db = None
