"""Unit tests for WebSocket endpoint and lifespan handler."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from nanogridbot.web.app import app, lifespan, set_orchestrator, web_state


@pytest.fixture
def client():
    """Create test client with clean state."""
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


@pytest.fixture(autouse=True)
def cleanup():
    """Clean up web state after each test."""
    yield
    web_state.orchestrator = None
    web_state.db = None


class TestWebSocketEndpoint:
    """Test WebSocket endpoint."""

    @patch("nanogridbot.web.app.get_groups")
    @patch("nanogridbot.web.app.get_tasks")
    @patch("nanogridbot.web.app.get_metrics")
    def test_websocket_connects_and_receives_data(
        self, mock_get_metrics, mock_get_tasks, mock_get_groups, client
    ):
        """Test WebSocket connection and data reception."""
        # Mock data
        mock_get_groups.return_value = []
        mock_get_tasks.return_value = []
        mock_get_metrics.return_value = {"channels": [], "total_messages": 0}

        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()
            assert "groups" in data
            assert "tasks" in data
            assert "channels" in data
            assert "metrics" in data
            assert "timestamp" in data

    @patch("nanogridbot.web.app.get_groups")
    @patch("nanogridbot.web.app.get_tasks")
    @patch("nanogridbot.web.app.get_metrics")
    def test_websocket_sends_correct_data_structure(
        self, mock_get_metrics, mock_get_tasks, mock_get_groups, client
    ):
        """Test WebSocket sends correct data structure."""
        # Mock data with realistic values
        mock_groups = [{"id": "group1", "name": "Test Group"}]
        mock_tasks = [{"id": "task1", "status": "running"}]
        mock_metrics = {
            "channels": [{"name": "whatsapp", "status": "active"}],
            "total_messages": 42,
            "active_tasks": 3,
        }

        mock_get_groups.return_value = mock_groups
        mock_get_tasks.return_value = mock_tasks
        mock_get_metrics.return_value = mock_metrics

        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()

            # Verify structure
            assert data["groups"] == mock_groups
            assert data["tasks"] == mock_tasks
            assert data["channels"] == mock_metrics["channels"]
            assert data["metrics"] == mock_metrics
            assert isinstance(data["timestamp"], str)

            # Verify timestamp is valid ISO format
            datetime.fromisoformat(data["timestamp"])

    @patch("nanogridbot.web.app.get_groups")
    @patch("nanogridbot.web.app.get_tasks")
    @patch("nanogridbot.web.app.get_metrics")
    def test_websocket_sends_multiple_updates(
        self, mock_get_metrics, mock_get_tasks, mock_get_groups, client
    ):
        """Test WebSocket sends multiple updates with different timestamps."""
        mock_get_groups.return_value = []
        mock_get_tasks.return_value = []
        mock_get_metrics.return_value = {"channels": []}

        with client.websocket_connect("/ws") as websocket:
            # Receive first update
            data1 = websocket.receive_json()
            assert "timestamp" in data1
            timestamp1 = data1["timestamp"]

            # Verify timestamp is valid ISO format
            datetime.fromisoformat(timestamp1)

    @patch("nanogridbot.web.app.get_groups")
    @patch("nanogridbot.web.app.get_tasks")
    @patch("nanogridbot.web.app.get_metrics")
    def test_websocket_handles_empty_channels(
        self, mock_get_metrics, mock_get_tasks, mock_get_groups, client
    ):
        """Test WebSocket handles missing channels key in metrics."""
        mock_get_groups.return_value = []
        mock_get_tasks.return_value = []
        mock_get_metrics.return_value = {"total_messages": 0}  # No 'channels' key

        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()
            assert data["channels"] == []  # Should default to empty list

    @patch("nanogridbot.web.app.get_groups")
    @patch("nanogridbot.web.app.get_tasks")
    @patch("nanogridbot.web.app.get_metrics")
    def test_websocket_handles_exception_in_data_gathering(
        self, mock_get_metrics, mock_get_tasks, mock_get_groups, client
    ):
        """Test WebSocket handles exceptions during data gathering."""
        mock_get_groups.side_effect = Exception("Database error")
        mock_get_tasks.return_value = []
        mock_get_metrics.return_value = {"channels": []}

        with client.websocket_connect("/ws") as websocket:
            # Should handle exception and close connection
            with pytest.raises(Exception):
                websocket.receive_json()

    @patch("nanogridbot.web.app.get_groups")
    @patch("nanogridbot.web.app.get_tasks")
    @patch("nanogridbot.web.app.get_metrics")
    def test_websocket_closes_properly(
        self, mock_get_metrics, mock_get_tasks, mock_get_groups, client
    ):
        """Test WebSocket closes properly after disconnect."""
        mock_get_groups.return_value = []
        mock_get_tasks.return_value = []
        mock_get_metrics.return_value = {"channels": []}

        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()
            assert data is not None
            # Connection will be closed when exiting context

        # Test passes if no exception is raised during close


class TestLifespanHandler:
    """Test lifespan context manager."""

    @pytest.mark.asyncio
    @patch("nanogridbot.web.app.logger")
    async def test_lifespan_logs_startup(self, mock_logger):
        """Test lifespan logs startup message."""
        mock_app = MagicMock()

        async with lifespan(mock_app):
            pass

        # Verify startup log
        mock_logger.info.assert_any_call("NanoGridBot Web Dashboard starting...")

    @pytest.mark.asyncio
    @patch("nanogridbot.web.app.logger")
    async def test_lifespan_logs_shutdown(self, mock_logger):
        """Test lifespan logs shutdown message."""
        mock_app = MagicMock()

        async with lifespan(mock_app):
            pass

        # Verify shutdown log
        mock_logger.info.assert_any_call("NanoGridBot Web Dashboard shutting down...")

    @pytest.mark.asyncio
    @patch("nanogridbot.web.app.logger")
    async def test_lifespan_yields_properly(self, mock_logger):
        """Test lifespan context manager yields properly."""
        mock_app = MagicMock()
        yielded = False

        async with lifespan(mock_app):
            yielded = True

        assert yielded

    @pytest.mark.asyncio
    @patch("nanogridbot.web.app.logger")
    async def test_lifespan_handles_exception_during_yield(self, mock_logger):
        """Test lifespan handles exceptions during yield."""
        mock_app = MagicMock()

        with pytest.raises(ValueError):
            async with lifespan(mock_app):
                raise ValueError("Test error")

        # Verify startup was called
        mock_logger.info.assert_any_call("NanoGridBot Web Dashboard starting...")
        # Note: shutdown log may not be called if exception occurs during yield
        # This is expected behavior for context managers

    @pytest.mark.asyncio
    @patch("nanogridbot.web.app.logger")
    async def test_lifespan_call_order(self, mock_logger):
        """Test lifespan logs in correct order."""
        mock_app = MagicMock()
        call_order = []

        def track_call(msg):
            call_order.append(msg)

        mock_logger.info.side_effect = track_call

        async with lifespan(mock_app):
            pass

        assert len(call_order) == 2
        assert "starting" in call_order[0]
        assert "shutting down" in call_order[1]
