"""Unit tests for plugin loader."""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.plugins.base import Plugin
from nanogridbot.plugins.loader import PluginConfig, PluginLoader


# Helper plugin class for tests
class SamplePlugin(Plugin):
    @property
    def name(self) -> str:
        return "sample"

    @property
    def version(self) -> str:
        return "1.0.0"


class TestPluginConfig:
    """Test PluginConfig class."""

    def test_init_creates_directory(self, tmp_path):
        """Test config dir is created on init."""
        config_dir = tmp_path / "new_config"
        assert not config_dir.exists()

        PluginConfig(config_dir)
        assert config_dir.exists()

    def test_load_config_from_file(self, tmp_path):
        """Test loading config from JSON file."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "myplugin.json").write_text('{"enabled": true, "rate": 5}')

        pc = PluginConfig(config_dir)
        result = pc.load_config("myplugin")

        assert result == {"enabled": True, "rate": 5}

    def test_load_config_cached(self, tmp_path):
        """Test config is cached after first load."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "myplugin.json").write_text('{"key": "value"}')

        pc = PluginConfig(config_dir)
        result1 = pc.load_config("myplugin")
        result2 = pc.load_config("myplugin")

        assert result1 is result2

    def test_load_config_missing_file(self, tmp_path):
        """Test loading config when file doesn't exist."""
        pc = PluginConfig(tmp_path)
        result = pc.load_config("nonexistent")
        assert result == {}

    def test_load_config_invalid_json(self, tmp_path):
        """Test loading config with invalid JSON."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "bad.json").write_text("not json {{{")

        pc = PluginConfig(config_dir)
        result = pc.load_config("bad")
        assert result == {}

    def test_save_config(self, tmp_path):
        """Test saving config to file."""
        pc = PluginConfig(tmp_path)
        pc.save_config("myplugin", {"enabled": True, "limit": 10})

        config_file = tmp_path / "myplugin.json"
        assert config_file.exists()

        data = json.loads(config_file.read_text())
        assert data == {"enabled": True, "limit": 10}

    def test_save_config_updates_cache(self, tmp_path):
        """Test saving config updates internal cache."""
        pc = PluginConfig(tmp_path)
        pc.save_config("myplugin", {"a": 1})

        result = pc.load_config("myplugin")
        assert result == {"a": 1}

    def test_get_all_configs(self, tmp_path):
        """Test getting all configs."""
        pc = PluginConfig(tmp_path)
        pc.save_config("p1", {"a": 1})
        pc.save_config("p2", {"b": 2})

        all_configs = pc.get_all_configs()
        assert "p1" in all_configs
        assert "p2" in all_configs
        assert all_configs["p1"] == {"a": 1}

    def test_get_all_configs_returns_copy(self, tmp_path):
        """Test get_all_configs returns a shallow copy of the outer dict."""
        pc = PluginConfig(tmp_path)
        pc.save_config("p1", {"a": 1})

        configs = pc.get_all_configs()
        # Adding a new key to the copy should not affect the original
        configs["new_plugin"] = {"x": 1}

        assert "new_plugin" not in pc.get_all_configs()


    def test_save_config_error_handling(self, tmp_path):
        """Test save_config handles write errors gracefully."""
        pc = PluginConfig(tmp_path)

        # Make the config dir read-only to trigger write error
        import os

        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        pc_readonly = PluginConfig(readonly_dir)

        # Create a file where the config file should be (to cause error)
        bad_path = readonly_dir / "test.json"
        bad_path.mkdir()  # Directory instead of file

        # Should not raise, just log error
        pc_readonly.save_config("test", {"a": 1})


class TestPluginLoader:
    """Test PluginLoader class."""

    def test_init_with_dirs(self, tmp_path):
        """Test loader initialization with directories."""
        plugin_dir = tmp_path / "plugins"
        config_dir = tmp_path / "config"

        loader = PluginLoader(plugin_dir=plugin_dir, config_dir=config_dir)

        assert loader.plugin_dir == plugin_dir
        assert loader.plugins == {}
        assert loader._hot_reload_enabled is False

    def test_init_default_config_dir(self, tmp_path):
        """Test loader uses default config dir when not specified."""
        plugin_dir = tmp_path / "plugins"
        loader = PluginLoader(plugin_dir=plugin_dir)

        assert loader.config.config_dir == plugin_dir / "config"

    def test_init_no_plugin_dir(self):
        """Test loader with no plugin dir."""
        loader = PluginLoader()
        assert loader.plugin_dir is None

    @pytest.mark.asyncio
    async def test_load_all_no_plugin_dir(self):
        """Test load_all with no plugin directory."""
        loader = PluginLoader(plugin_dir=None)
        await loader.load_all()
        assert loader.plugins == {}

    @pytest.mark.asyncio
    async def test_load_all_nonexistent_dir(self, tmp_path):
        """Test load_all with nonexistent directory."""
        loader = PluginLoader(plugin_dir=tmp_path / "nonexistent")
        await loader.load_all()
        assert loader.plugins == {}

    @pytest.mark.asyncio
    async def test_load_all_empty_dir(self, tmp_path):
        """Test load_all with empty plugin directory."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        loader = PluginLoader(plugin_dir=plugin_dir, config_dir=tmp_path / "config")
        await loader.load_all()
        assert loader.plugins == {}

    @pytest.mark.asyncio
    async def test_load_single_file_plugin(self, tmp_path):
        """Test loading a single-file plugin."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        plugin_code = '''
from nanogridbot.plugins.base import Plugin

class MyPlugin(Plugin):
    @property
    def name(self) -> str:
        return "my_plugin"

    @property
    def version(self) -> str:
        return "1.0.0"
'''
        (plugin_dir / "plugin_my.py").write_text(plugin_code)

        loader = PluginLoader(plugin_dir=plugin_dir, config_dir=tmp_path / "config")
        await loader.load_all()

        assert "my_plugin" in loader.plugins
        assert loader.plugins["my_plugin"].version == "1.0.0"

    @pytest.mark.asyncio
    async def test_load_directory_plugin(self, tmp_path):
        """Test loading a directory-based plugin."""
        plugin_dir = tmp_path / "plugins"
        sub_dir = plugin_dir / "myplugin"
        sub_dir.mkdir(parents=True)

        plugin_code = '''
from nanogridbot.plugins.base import Plugin

class DirPlugin(Plugin):
    @property
    def name(self) -> str:
        return "dir_plugin"

    @property
    def version(self) -> str:
        return "2.0.0"
'''
        (sub_dir / "plugin.py").write_text(plugin_code)

        loader = PluginLoader(plugin_dir=plugin_dir, config_dir=tmp_path / "config")
        await loader.load_all()

        assert "dir_plugin" in loader.plugins

    @pytest.mark.asyncio
    async def test_load_plugin_with_error(self, tmp_path):
        """Test loading a plugin that raises an error."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        (plugin_dir / "plugin_bad.py").write_text("raise ImportError('broken')")

        loader = PluginLoader(plugin_dir=plugin_dir, config_dir=tmp_path / "config")
        await loader.load_all()

        assert loader.plugins == {}

    @pytest.mark.asyncio
    async def test_load_plugin_no_plugin_class(self, tmp_path):
        """Test loading a module without Plugin subclass."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        (plugin_dir / "plugin_empty.py").write_text("x = 42\n")

        loader = PluginLoader(plugin_dir=plugin_dir, config_dir=tmp_path / "config")
        await loader.load_all()

        assert loader.plugins == {}

    def test_find_plugin_class(self, tmp_path):
        """Test _find_plugin_class finds correct class."""
        loader = PluginLoader(plugin_dir=tmp_path, config_dir=tmp_path / "config")

        module = MagicMock()
        module.__dir__ = lambda self: ["SamplePlugin", "other"]
        module.SamplePlugin = SamplePlugin
        module.other = "not a class"

        result = loader._find_plugin_class(module)
        assert result is SamplePlugin

    def test_find_plugin_class_none(self, tmp_path):
        """Test _find_plugin_class returns None when no plugin found."""
        loader = PluginLoader(plugin_dir=tmp_path, config_dir=tmp_path / "config")

        module = MagicMock()
        module.__dir__ = lambda self: ["x"]
        module.x = 42

        result = loader._find_plugin_class(module)
        assert result is None

    def test_get_plugin(self, tmp_path):
        """Test getting a plugin by name."""
        loader = PluginLoader(plugin_dir=tmp_path, config_dir=tmp_path / "config")
        plugin = SamplePlugin()
        loader.plugins["sample"] = plugin

        assert loader.get_plugin("sample") is plugin
        assert loader.get_plugin("nonexistent") is None

    def test_list_plugins(self, tmp_path):
        """Test listing plugin names."""
        loader = PluginLoader(plugin_dir=tmp_path, config_dir=tmp_path / "config")
        loader.plugins["a"] = SamplePlugin()
        loader.plugins["b"] = SamplePlugin()

        names = loader.list_plugins()
        assert sorted(names) == ["a", "b"]

    @pytest.mark.asyncio
    async def test_shutdown_all(self, tmp_path):
        """Test shutting down all plugins."""
        loader = PluginLoader(plugin_dir=tmp_path, config_dir=tmp_path / "config")

        p1 = AsyncMock(spec=Plugin)
        p1.name = "p1"
        p2 = AsyncMock(spec=Plugin)
        p2.name = "p2"

        loader.plugins = {"p1": p1, "p2": p2}

        await loader.shutdown_all()

        p1.shutdown.assert_called_once()
        p2.shutdown.assert_called_once()
        assert loader.plugins == {}

    @pytest.mark.asyncio
    async def test_shutdown_all_with_error(self, tmp_path):
        """Test shutdown continues even if one plugin fails."""
        loader = PluginLoader(plugin_dir=tmp_path, config_dir=tmp_path / "config")

        p1 = AsyncMock(spec=Plugin)
        p1.name = "p1"
        p1.shutdown = AsyncMock(side_effect=Exception("shutdown error"))
        p2 = AsyncMock(spec=Plugin)
        p2.name = "p2"

        loader.plugins = {"p1": p1, "p2": p2}

        await loader.shutdown_all()

        p1.shutdown.assert_called_once()
        p2.shutdown.assert_called_once()
        assert loader.plugins == {}


class TestPluginLoaderHooks:
    """Test execute_hook method."""

    @pytest.mark.asyncio
    async def test_execute_hook_calls_all_plugins(self, tmp_path):
        """Test hook is called on all plugins."""
        loader = PluginLoader(plugin_dir=tmp_path, config_dir=tmp_path / "config")

        p1 = MagicMock()
        p1.name = "p1"
        p1.on_message_received = AsyncMock(return_value="result1")

        p2 = MagicMock()
        p2.name = "p2"
        p2.on_message_received = AsyncMock(return_value="result2")

        loader.plugins = {"p1": p1, "p2": p2}

        results = await loader.execute_hook("on_message_received", "msg")

        assert results == ["result1", "result2"]

    @pytest.mark.asyncio
    async def test_execute_hook_skips_none_results(self, tmp_path):
        """Test hook skips None results."""
        loader = PluginLoader(plugin_dir=tmp_path, config_dir=tmp_path / "config")

        p1 = MagicMock()
        p1.name = "p1"
        p1.on_message_received = AsyncMock(return_value=None)

        p2 = MagicMock()
        p2.name = "p2"
        p2.on_message_received = AsyncMock(return_value="result2")

        loader.plugins = {"p1": p1, "p2": p2}

        results = await loader.execute_hook("on_message_received", "msg")
        assert results == ["result2"]

    @pytest.mark.asyncio
    async def test_execute_hook_missing_method(self, tmp_path):
        """Test hook handles plugins without the hook method."""
        loader = PluginLoader(plugin_dir=tmp_path, config_dir=tmp_path / "config")

        p1 = MagicMock(spec=[])  # No attributes
        p1.name = "p1"

        loader.plugins = {"p1": p1}

        results = await loader.execute_hook("nonexistent_hook")
        assert results == []

    @pytest.mark.asyncio
    async def test_execute_hook_error_handling(self, tmp_path):
        """Test hook continues after plugin error."""
        loader = PluginLoader(plugin_dir=tmp_path, config_dir=tmp_path / "config")

        p1 = MagicMock()
        p1.name = "p1"
        p1.on_message_received = AsyncMock(side_effect=Exception("plugin error"))

        p2 = MagicMock()
        p2.name = "p2"
        p2.on_message_received = AsyncMock(return_value="ok")

        loader.plugins = {"p1": p1, "p2": p2}

        results = await loader.execute_hook("on_message_received", "msg")
        assert results == ["ok"]


class TestPluginLoaderHotReload:
    """Test hot reload functionality."""

    @pytest.mark.asyncio
    async def test_enable_hot_reload_no_plugin_dir(self):
        """Test enabling hot reload without plugin dir."""
        loader = PluginLoader(plugin_dir=None)
        await loader.enable_hot_reload()
        assert loader._hot_reload_enabled is False

    @pytest.mark.asyncio
    async def test_enable_hot_reload_nonexistent_dir(self, tmp_path):
        """Test enabling hot reload with nonexistent dir."""
        nonexistent = tmp_path / "nonexistent"
        # Pass separate config_dir so PluginConfig doesn't create plugin_dir as side effect
        loader = PluginLoader(plugin_dir=nonexistent, config_dir=tmp_path / "config")
        await loader.enable_hot_reload()
        assert loader._hot_reload_enabled is False

    @pytest.mark.asyncio
    async def test_enable_hot_reload_already_enabled(self, tmp_path):
        """Test enabling hot reload when already enabled."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        loader = PluginLoader(plugin_dir=plugin_dir, config_dir=tmp_path / "config")
        loader._hot_reload_enabled = True

        await loader.enable_hot_reload()
        # Should just warn, not create another task

    @pytest.mark.asyncio
    async def test_disable_hot_reload(self, tmp_path):
        """Test disabling hot reload."""
        loader = PluginLoader(plugin_dir=tmp_path, config_dir=tmp_path / "config")
        loader._hot_reload_enabled = True

        # Create a real cancelled future to simulate a running task
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        future.cancel()

        loader._hot_reload_task = future

        await loader.disable_hot_reload()

        assert loader._hot_reload_enabled is False
        assert loader._hot_reload_task is None

    @pytest.mark.asyncio
    async def test_disable_hot_reload_no_task(self, tmp_path):
        """Test disabling hot reload when no task exists."""
        loader = PluginLoader(plugin_dir=tmp_path, config_dir=tmp_path / "config")
        await loader.disable_hot_reload()
        assert loader._hot_reload_enabled is False

    @pytest.mark.asyncio
    async def test_reload_plugin(self, tmp_path):
        """Test reloading a plugin by path."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        plugin_code = '''
from nanogridbot.plugins.base import Plugin

class ReloadPlugin(Plugin):
    @property
    def name(self) -> str:
        return "reload_test"

    @property
    def version(self) -> str:
        return "1.0.0"
'''
        plugin_file = plugin_dir / "plugin_reload.py"
        plugin_file.write_text(plugin_code)

        loader = PluginLoader(plugin_dir=plugin_dir, config_dir=tmp_path / "config")
        await loader.load_all()

        assert "reload_test" in loader.plugins

        # Reload
        await loader._reload_plugin(str(plugin_file))

        assert "reload_test" in loader.plugins

    @pytest.mark.asyncio
    async def test_reload_plugin_unknown_path(self, tmp_path):
        """Test reloading with unknown plugin path."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        loader = PluginLoader(plugin_dir=plugin_dir, config_dir=tmp_path / "config")

        # Should not raise
        await loader._reload_plugin(str(tmp_path / "unknown" / "file.py"))

    @pytest.mark.asyncio
    async def test_reload_plugin_directory_based(self, tmp_path):
        """Test reloading a directory-based plugin."""
        plugin_dir = tmp_path / "plugins"
        sub_dir = plugin_dir / "myplugin"
        sub_dir.mkdir(parents=True)

        plugin_code = '''
from nanogridbot.plugins.base import Plugin

class DirPlugin(Plugin):
    @property
    def name(self) -> str:
        return "myplugin"

    @property
    def version(self) -> str:
        return "1.0.0"
'''
        plugin_file = sub_dir / "plugin.py"
        plugin_file.write_text(plugin_code)

        loader = PluginLoader(plugin_dir=plugin_dir, config_dir=tmp_path / "config")
        await loader.load_all()

        assert "myplugin" in loader.plugins

        # Reload via a file inside the plugin directory
        await loader._reload_plugin(str(sub_dir / "helper.py"))

    @pytest.mark.asyncio
    async def test_reload_plugin_shutdown_error(self, tmp_path):
        """Test reload handles shutdown error of existing plugin."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        plugin_code = '''
from nanogridbot.plugins.base import Plugin

class ReloadPlugin(Plugin):
    @property
    def name(self) -> str:
        return "plugin_err"

    @property
    def version(self) -> str:
        return "1.0.0"
'''
        plugin_file = plugin_dir / "plugin_err.py"
        plugin_file.write_text(plugin_code)

        loader = PluginLoader(plugin_dir=plugin_dir, config_dir=tmp_path / "config")
        await loader.load_all()

        # Make shutdown raise
        loader.plugins["plugin_err"].shutdown = AsyncMock(side_effect=Exception("shutdown err"))

        # Reload should still work
        await loader._reload_plugin(str(plugin_file))
        assert "plugin_err" in loader.plugins

    @pytest.mark.asyncio
    async def test_load_plugin_invalid_spec(self, tmp_path):
        """Test loading a plugin file that can't produce a valid spec."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        loader = PluginLoader(plugin_dir=plugin_dir, config_dir=tmp_path / "config")

        # Create a file with a name that importlib can't handle
        bad_file = plugin_dir / "plugin_test.py"
        bad_file.write_text("x = 1")

        with patch("importlib.util.spec_from_file_location", return_value=None):
            await loader._load_plugin(bad_file)

        assert loader.plugins == {}

    @pytest.mark.asyncio
    async def test_enable_hot_reload_creates_task(self, tmp_path):
        """Test enable_hot_reload creates monitoring task."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        loader = PluginLoader(plugin_dir=plugin_dir, config_dir=tmp_path / "config")

        # Patch _hot_reload_loop to avoid actually running watchdog
        async def fake_loop(debounce):
            await asyncio.sleep(100)

        with patch.object(loader, "_hot_reload_loop", side_effect=fake_loop):
            await loader.enable_hot_reload(debounce_seconds=0.5)

        assert loader._hot_reload_enabled is True
        assert loader._hot_reload_task is not None

        # Cleanup
        await loader.disable_hot_reload()

    @pytest.mark.asyncio
    async def test_hot_reload_loop_no_watchdog(self, tmp_path):
        """Test _hot_reload_loop handles missing watchdog."""
        plugin_dir = tmp_path / "plugins"
        plugin_dir.mkdir()

        loader = PluginLoader(plugin_dir=plugin_dir, config_dir=tmp_path / "config")
        loader._hot_reload_enabled = True

        with patch.dict("sys.modules", {"watchdog": None, "watchdog.events": None, "watchdog.observers": None}):
            with patch("builtins.__import__", side_effect=ImportError("no watchdog")):
                await loader._hot_reload_loop(1.0)

        assert loader._hot_reload_enabled is False
