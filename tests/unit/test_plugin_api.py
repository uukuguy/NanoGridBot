"""Unit tests for plugin API module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.plugins.api import PluginAPI, PluginContext


class TestPluginAPI:
    """Test PluginAPI class."""

    def test_init_without_orchestrator(self):
        api = PluginAPI()
        assert api._orchestrator is None

    def test_init_with_orchestrator(self):
        orch = MagicMock()
        api = PluginAPI(orchestrator=orch)
        assert api._orchestrator is orch

    @pytest.mark.asyncio
    async def test_send_message_no_orchestrator(self):
        api = PluginAPI()
        result = await api.send_message("jid1", "hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        orch = MagicMock()
        orch.send_message = AsyncMock()
        api = PluginAPI(orchestrator=orch)
        result = await api.send_message("jid1", "hello")
        assert result is True
        orch.send_message.assert_called_once_with("jid1", "hello")

    @pytest.mark.asyncio
    async def test_send_message_exception(self):
        orch = MagicMock()
        orch.send_message = AsyncMock(side_effect=Exception("fail"))
        api = PluginAPI(orchestrator=orch)
        result = await api.send_message("jid1", "hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_broadcast_no_orchestrator(self):
        api = PluginAPI()
        result = await api.broadcast_to_group("group1", "msg")
        assert result is False

    @pytest.mark.asyncio
    async def test_broadcast_success(self):
        orch = MagicMock()
        orch.router.broadcast = AsyncMock()
        api = PluginAPI(orchestrator=orch)
        result = await api.broadcast_to_group("group1", "msg")
        assert result is True

    @pytest.mark.asyncio
    async def test_broadcast_exception(self):
        orch = MagicMock()
        orch.router.broadcast = AsyncMock(side_effect=Exception("fail"))
        api = PluginAPI(orchestrator=orch)
        result = await api.broadcast_to_group("group1", "msg")
        assert result is False

    def test_get_registered_groups_no_orchestrator(self):
        api = PluginAPI()
        assert api.get_registered_groups() == []

    def test_get_registered_groups(self):
        orch = MagicMock()
        orch.router.groups = {"g1": MagicMock(), "g2": MagicMock()}
        api = PluginAPI(orchestrator=orch)
        result = api.get_registered_groups()
        assert sorted(result) == ["g1", "g2"]

    def test_get_group_info_no_orchestrator(self):
        api = PluginAPI()
        assert api.get_group_info("jid1") is None

    def test_get_group_info_not_found(self):
        orch = MagicMock()
        orch.router.groups = {}
        api = PluginAPI(orchestrator=orch)
        assert api.get_group_info("jid1") is None

    def test_get_group_info_found(self):
        group = MagicMock()
        group.jid = "jid1"
        group.name = "Test"
        group.folder = "test"
        group.trigger_pattern = "@bot"
        orch = MagicMock()
        orch.router.groups = {"jid1": group}
        api = PluginAPI(orchestrator=orch)
        result = api.get_group_info("jid1")
        assert result["jid"] == "jid1"
        assert result["name"] == "Test"
        assert result["folder"] == "test"
        assert result["trigger_pattern"] == "@bot"

    @pytest.mark.asyncio
    async def test_queue_container_run_no_orchestrator(self):
        api = PluginAPI()
        result = await api.queue_container_run("folder", "prompt")
        assert result is None

    @pytest.mark.asyncio
    async def test_queue_container_run_success(self):
        orch = MagicMock()
        orch.group_queue.enqueue = AsyncMock(return_value="task-123")
        api = PluginAPI(orchestrator=orch)
        result = await api.queue_container_run("folder", "prompt")
        assert result == "task-123"

    @pytest.mark.asyncio
    async def test_queue_container_run_exception(self):
        orch = MagicMock()
        orch.group_queue.enqueue = AsyncMock(side_effect=Exception("fail"))
        api = PluginAPI(orchestrator=orch)
        result = await api.queue_container_run("folder", "prompt")
        assert result is None

    def test_get_queue_status_no_orchestrator(self):
        api = PluginAPI()
        assert api.get_queue_status("jid1") is None

    def test_get_queue_status(self):
        orch = MagicMock()
        orch.group_queue.get_status.return_value = {"pending": 2}
        api = PluginAPI(orchestrator=orch)
        result = api.get_queue_status("jid1")
        assert result == {"pending": 2}

    def test_register_hook(self):
        api = PluginAPI()

        @api.register_hook("on_message")
        def my_hook():
            pass

        assert hasattr(api, "_registered_hooks")
        assert "on_message:my_hook" in api._registered_hooks

    def test_register_hook_preserves_function(self):
        api = PluginAPI()

        @api.register_hook("test")
        def handler():
            return "result"

        assert handler() == "result"

    @pytest.mark.asyncio
    async def test_execute_message_filter_no_orchestrator(self):
        api = PluginAPI()
        msg = MagicMock()
        result = await api.execute_message_filter(msg)
        assert result is msg

    @pytest.mark.asyncio
    async def test_execute_message_filter_with_plugin_loader(self):
        orch = MagicMock()
        orch.plugin_loader.execute_hook = AsyncMock()
        api = PluginAPI(orchestrator=orch)
        msg = MagicMock()
        result = await api.execute_message_filter(msg)
        assert result is msg
        orch.plugin_loader.execute_hook.assert_called_once_with("on_message_received", msg)

    @pytest.mark.asyncio
    async def test_execute_message_filter_no_plugin_loader(self):
        orch = MagicMock(spec=[])  # No attributes
        api = PluginAPI(orchestrator=orch)
        msg = MagicMock()
        result = await api.execute_message_filter(msg)
        assert result is msg


class TestPluginContext:
    """Test PluginContext class."""

    def test_init(self):
        api = PluginAPI()
        ctx = PluginContext(api=api, config={"key": "val"})
        assert ctx.api is api
        assert ctx.config == {"key": "val"}

    def test_logger_property(self):
        api = PluginAPI()
        ctx = PluginContext(api=api, config={})
        log = ctx.logger
        assert log is not None
