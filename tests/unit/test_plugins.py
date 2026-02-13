"""Unit tests for plugins module."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.plugins.base import Plugin
from nanogridbot.types import Message


class TestPluginBase:
    """Tests for Plugin base class."""

    def test_plugin_abstract_methods(self):
        """Test that Plugin is abstract and requires name/version."""

        class MinimalPlugin(Plugin):
            @property
            def name(self) -> str:
                return "test_plugin"

            @property
            def version(self) -> str:
                return "1.0.0"

        plugin = MinimalPlugin()
        assert plugin.name == "test_plugin"
        assert plugin.version == "1.0.0"

    def test_plugin_default_description(self):
        """Test plugin default description."""

        class TestPlugin(Plugin):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0"

        plugin = TestPlugin()
        assert plugin.description == ""

    def test_plugin_default_author(self):
        """Test plugin default author."""

        class TestPlugin(Plugin):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0"

        plugin = TestPlugin()
        assert plugin.author == "Unknown"

    def test_plugin_custom_description_author(self):
        """Test plugin custom description and author."""

        class TestPlugin(Plugin):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0"

            @property
            def description(self) -> str:
                return "A test plugin"

            @property
            def author(self) -> str:
                return "Test Author"

        plugin = TestPlugin()
        assert plugin.description == "A test plugin"
        assert plugin.author == "Test Author"

    @pytest.mark.asyncio
    async def test_plugin_initialize_default(self):
        """Test plugin initialize default implementation."""

        class TestPlugin(Plugin):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0"

        plugin = TestPlugin()
        await plugin.initialize({"key": "value"})

    @pytest.mark.asyncio
    async def test_plugin_shutdown_default(self):
        """Test plugin shutdown default implementation."""

        class TestPlugin(Plugin):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0"

        plugin = TestPlugin()
        await plugin.shutdown()

    @pytest.mark.asyncio
    async def test_plugin_on_message_received_default(self):
        """Test on_message_received default implementation."""

        class TestPlugin(Plugin):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0"

        plugin = TestPlugin()
        message = Message(
            id="1",
            chat_jid="test@chat.com",
            sender="user1",
            content="Hello",
            timestamp="2025-01-01T10:00:00",
            is_from_me=False,
        )
        result = await plugin.on_message_received(message)
        assert result == message

    @pytest.mark.asyncio
    async def test_plugin_on_message_received_modify(self):
        """Test on_message_received can modify message."""

        class ModifyingPlugin(Plugin):
            @property
            def name(self) -> str:
                return "modifying"

            @property
            def version(self) -> str:
                return "1.0"

            async def on_message_received(self, message: Message) -> Message | None:
                message.content = "Modified"
                return message

        plugin = ModifyingPlugin()
        message = Message(
            id="1",
            chat_jid="test@chat.com",
            sender="user1",
            content="Hello",
            timestamp="2025-01-01T10:00:00",
            is_from_me=False,
        )
        result = await plugin.on_message_received(message)
        assert result.content == "Modified"

    @pytest.mark.asyncio
    async def test_plugin_on_message_received_drop(self):
        """Test on_message_received can drop message."""

        class DroppingPlugin(Plugin):
            @property
            def name(self) -> str:
                return "dropping"

            @property
            def version(self) -> str:
                return "1.0"

            async def on_message_received(self, message: Message) -> Message | None:
                return None

        plugin = DroppingPlugin()
        message = Message(
            id="1",
            chat_jid="test@chat.com",
            sender="user1",
            content="Hello",
            timestamp="2025-01-01T10:00:00",
            is_from_me=False,
        )
        result = await plugin.on_message_received(message)
        assert result is None

    @pytest.mark.asyncio
    async def test_plugin_on_message_sent_default(self):
        """Test on_message_sent default implementation."""

        class TestPlugin(Plugin):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0"

        plugin = TestPlugin()
        result = await plugin.on_message_sent("test@chat.com", "Hello")
        assert result == "Hello"

    @pytest.mark.asyncio
    async def test_plugin_on_container_start_default(self):
        """Test on_container_start default implementation."""

        class TestPlugin(Plugin):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0"

        plugin = TestPlugin()
        result = await plugin.on_container_start("group1", "prompt")
        assert result == "prompt"

    @pytest.mark.asyncio
    async def test_plugin_on_container_result_default(self):
        """Test on_container_result default implementation."""

        class TestPlugin(Plugin):
            @property
            def name(self) -> str:
                return "test"

            @property
            def version(self) -> str:
                return "1.0"

        from nanogridbot.types import ContainerOutput

        plugin = TestPlugin()
        output = ContainerOutput(status="success", result="test")
        result = await plugin.on_container_result(output)
        assert result == output


class TestPluginLoader:
    """Tests for plugin loader."""

    @pytest.mark.asyncio
    async def test_plugin_loader_init(self):
        """Test plugin loader initialization."""
        from nanogridbot.plugins.loader import PluginLoader

        loader = PluginLoader(plugin_dir=Path("/tmp/plugins"), config_dir=Path("/tmp/config"))
        assert loader.plugin_dir == Path("/tmp/plugins")
        assert loader.config is not None

    def test_load_plugin_config(self, tmp_path):
        """Test loading plugin configuration."""
        from nanogridbot.plugins.loader import PluginConfig

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        config_file = config_dir / "test_plugin.json"
        config_file.write_text('{"enabled": true, "limit": 10}')

        plugin_config = PluginConfig(config_dir)
        result = plugin_config.load_config("test_plugin")

        assert result == {"enabled": True, "limit": 10}

    def test_save_plugin_config(self, tmp_path):
        """Test saving plugin configuration."""
        from nanogridbot.plugins.loader import PluginConfig

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        plugin_config = PluginConfig(config_dir)
        plugin_config.save_config("test_plugin", {"key": "value"})

        config_file = config_dir / "test_plugin.json"
        assert config_file.exists()

        import json

        data = json.loads(config_file.read_text())
        assert data["key"] == "value"

    def test_get_all_configs(self, tmp_path):
        """Test getting all configs."""
        from nanogridbot.plugins.loader import PluginConfig

        config_dir = tmp_path / "config"
        config_dir.mkdir()

        plugin_config = PluginConfig(config_dir)
        plugin_config.save_config("plugin1", {"a": 1})
        plugin_config.save_config("plugin2", {"b": 2})

        all_configs = plugin_config.get_all_configs()
        assert "plugin1" in all_configs
        assert "plugin2" in all_configs
        assert all_configs["plugin1"] == {"a": 1}


class TestPluginAPI:
    """Tests for plugin API."""

    @pytest.mark.asyncio
    async def test_plugin_api_init(self):
        """Test plugin API initialization."""
        from nanogridbot.plugins.api import PluginAPI

        api = PluginAPI(orchestrator=None)
        assert api._orchestrator is None

    @pytest.mark.asyncio
    async def test_plugin_api_send_message_no_orchestrator(self):
        """Test plugin API send_message with no orchestrator."""
        from nanogridbot.plugins.api import PluginAPI

        api = PluginAPI(orchestrator=None)
        result = await api.send_message("test@chat.com", "Hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_plugin_api_send_message_with_orchestrator(self):
        """Test plugin API send_message with orchestrator."""
        from nanogridbot.plugins.api import PluginAPI

        mock_orchestrator = MagicMock()
        mock_orchestrator.send_message = AsyncMock()

        api = PluginAPI(orchestrator=mock_orchestrator)
        result = await api.send_message("test@chat.com", "Hello")

        assert result is True
        mock_orchestrator.send_message.assert_called_once_with("test@chat.com", "Hello")

    @pytest.mark.asyncio
    async def test_plugin_api_broadcast_to_group(self):
        """Test plugin API broadcast_to_group."""
        from nanogridbot.plugins.api import PluginAPI

        mock_router = MagicMock()
        mock_router.broadcast = AsyncMock()

        mock_orchestrator = MagicMock()
        mock_orchestrator.router = mock_router

        api = PluginAPI(orchestrator=mock_orchestrator)
        result = await api.broadcast_to_group("group1@chat.com", "Hello")

        assert result is True
        mock_router.broadcast.assert_called_once_with("group1@chat.com", "Hello")

    def test_plugin_api_get_registered_groups(self):
        """Test plugin API get_registered_groups."""
        from nanogridbot.plugins.api import PluginAPI

        mock_router = MagicMock()
        mock_router.groups = {"group1@chat.com": MagicMock()}

        mock_orchestrator = MagicMock()
        mock_orchestrator.router = mock_router

        api = PluginAPI(orchestrator=mock_orchestrator)
        groups = api.get_registered_groups()

        assert len(groups) == 1
        assert "group1@chat.com" in groups

    def test_plugin_api_get_group_info(self):
        """Test plugin API get_group_info."""
        from nanogridbot.plugins.api import PluginAPI

        mock_group = MagicMock()
        mock_group.jid = "group1@chat.com"
        mock_group.folder = "group1"
        mock_group.requires_trigger = False
        mock_group.trigger_pattern = None
        mock_group.container_config = None

        mock_router = MagicMock()
        mock_router.groups = {"group1@chat.com": mock_group}

        mock_orchestrator = MagicMock()
        mock_orchestrator.router = mock_router

        api = PluginAPI(orchestrator=mock_orchestrator)
        info = api.get_group_info("group1@chat.com")

        assert info is not None
        assert info["jid"] == "group1@chat.com"

    def test_plugin_api_get_group_info_not_found(self):
        """Test plugin API get_group_info not found."""
        from nanogridbot.plugins.api import PluginAPI

        mock_router = MagicMock()
        mock_router.groups = {}

        mock_orchestrator = MagicMock()
        mock_orchestrator.router = mock_router

        api = PluginAPI(orchestrator=mock_orchestrator)
        info = api.get_group_info("nonexistent@chat.com")
        assert info is None


class TestPluginContext:
    """Tests for plugin context."""

    def test_plugin_context_init(self):
        """Test plugin context initialization."""
        from nanogridbot.plugins.api import PluginAPI, PluginContext

        api = PluginAPI(orchestrator=None)
        context = PluginContext(api=api, config={"key": "value"})

        assert context.api == api
        assert context.config == {"key": "value"}

    def test_plugin_context_logger(self):
        """Test plugin context logger."""
        from nanogridbot.plugins.api import PluginAPI, PluginContext

        api = PluginAPI(orchestrator=None)
        context = PluginContext(api=api, config={})

        logger = context.logger
        assert logger is not None
