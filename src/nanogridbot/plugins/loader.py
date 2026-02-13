"""Plugin loader for loading and managing plugins."""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from nanogridbot.plugins.base import Plugin


class PluginConfig:
    """Plugin configuration manager."""

    def __init__(self, config_dir: Path):
        """Initialize plugin config.

        Args:
            config_dir: Directory to store plugin configs
        """
        self.config_dir = config_dir
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._configs: dict[str, dict[str, Any]] = {}

    def load_config(self, plugin_name: str) -> dict[str, Any]:
        """Load configuration for a plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin configuration dict
        """
        if plugin_name in self._configs:
            return self._configs[plugin_name]

        config_file = self.config_dir / f"{plugin_name}.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    config = json.load(f)
                    self._configs[plugin_name] = config
                    return config
            except Exception as e:
                logger.error(f"Failed to load config for {plugin_name}: {e}")

        return {}

    def save_config(self, plugin_name: str, config: dict[str, Any]) -> None:
        """Save configuration for a plugin.

        Args:
            plugin_name: Name of the plugin
            config: Configuration dict
        """
        config_file = self.config_dir / f"{plugin_name}.json"
        try:
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
            self._configs[plugin_name] = config
            logger.info(f"Saved config for plugin: {plugin_name}")
        except Exception as e:
            logger.error(f"Failed to save config for {plugin_name}: {e}")

    def get_all_configs(self) -> dict[str, dict[str, Any]]:
        """Get all plugin configurations.

        Returns:
            Dict of plugin name to config
        """
        return self._configs.copy()


class PluginLoader:
    """Manages plugin loading and lifecycle."""

    def __init__(
        self,
        plugin_dir: Path | None = None,
        config_dir: Path | None = None,
    ):
        """Initialize the plugin loader.

        Args:
            plugin_dir: Directory to load plugins from
            config_dir: Directory to store plugin configs
        """
        self.plugin_dir = plugin_dir
        self.config = PluginConfig(
            config_dir or (plugin_dir / "config" if plugin_dir else Path("plugins/config"))
        )
        self.plugins: dict[str, Plugin] = {}
        self._hot_reload_enabled = False
        self._hot_reload_task: asyncio.Task | None = None

    async def load_all(self) -> None:
        """Load all plugins from the plugin directory."""
        if not self.plugin_dir or not self.plugin_dir.exists():
            logger.warning(f"Plugin directory not found: {self.plugin_dir}")
            return

        # Create plugins directory if it doesn't exist
        self.plugin_dir.mkdir(parents=True, exist_ok=True)

        # Add plugin directory to sys.path
        plugin_path = str(self.plugin_dir)
        if plugin_path not in sys.path:
            sys.path.insert(0, plugin_path)

        # Scan for plugins
        for plugin_path in self.plugin_dir.glob("*/plugin.py"):
            await self._load_plugin(plugin_path)

        # Also check for single-file plugins
        for plugin_path in self.plugin_dir.glob("plugin_*.py"):
            await self._load_plugin(plugin_path)

    async def _load_plugin(self, plugin_path: Path) -> None:
        """Load a single plugin.

        Args:
            plugin_path: Path to plugin file
        """
        try:
            # Import module
            module_name = plugin_path.stem
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)
            if not spec or not spec.loader:
                return

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Find Plugin subclasses
            plugin_class = self._find_plugin_class(module)
            if not plugin_class:
                logger.debug(f"No Plugin class found in {plugin_path}")
                return

            # Load plugin config
            plugin_name = getattr(plugin_class, "name", module_name)
            plugin_config = self.config.load_config(plugin_name)

            # Instantiate plugin
            plugin = plugin_class()

            # Initialize plugin with config
            await plugin.initialize(plugin_config)

            # Register plugin
            self.plugins[plugin.name] = plugin
            logger.info(f"Loaded plugin: {plugin.name} v{plugin.version}")

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_path}: {e}")

    def _find_plugin_class(self, module: Any) -> type[Plugin] | None:
        """Find Plugin subclass in module.

        Args:
            module: Python module

        Returns:
            Plugin class or None
        """
        for attr_name in dir(module):
            attr = getattr(module, attr_name)

            if isinstance(attr, type) and issubclass(attr, Plugin) and attr is not Plugin:
                return attr

        return None

    async def shutdown_all(self) -> None:
        """Shutdown all loaded plugins."""
        # Stop hot reload first
        await self.disable_hot_reload()

        for name, plugin in self.plugins.items():
            try:
                await plugin.shutdown()
                logger.info(f"Shutdown plugin: {name}")
            except Exception as e:
                logger.error(f"Error shutting down plugin {name}: {e}")

        self.plugins.clear()

    def get_plugin(self, name: str) -> Plugin | None:
        """Get a plugin by name.

        Args:
            name: Plugin name

        Returns:
            Plugin instance or None
        """
        return self.plugins.get(name)

    def list_plugins(self) -> list[str]:
        """List all loaded plugin names.

        Returns:
            List of plugin names
        """
        return list(self.plugins.keys())

    async def execute_hook(
        self,
        hook_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> list[Any]:
        """Execute a hook on all plugins.

        Args:
            hook_name: Name of hook method
            *args: Positional arguments for hook
            **kwargs: Keyword arguments for hook

        Returns:
            List of results (non-None results)
        """
        results = []

        for plugin in self.plugins.values():
            try:
                hook = getattr(plugin, hook_name, None)
                if hook and callable(hook):
                    result = await hook(*args, **kwargs)
                    if result is not None:
                        results.append(result)
            except Exception as e:
                logger.error(f"Error executing hook {hook_name} on {plugin.name}: {e}")

        return results

    # Hot reload functionality
    async def enable_hot_reload(self, debounce_seconds: float = 1.0) -> None:
        """Enable hot reload for plugins.

        Args:
            debounce_seconds: Debounce time before reloading after changes
        """
        if self._hot_reload_enabled:
            logger.warning("Hot reload already enabled")
            return

        if not self.plugin_dir or not self.plugin_dir.exists():
            logger.warning(f"Cannot enable hot reload: plugin directory not found")
            return

        self._hot_reload_enabled = True
        self._hot_reload_task = asyncio.create_task(self._hot_reload_loop(debounce_seconds))
        logger.info(f"Hot reload enabled for {self.plugin_dir}")

    async def disable_hot_reload(self) -> None:
        """Disable hot reload."""
        if self._hot_reload_task:
            self._hot_reload_task.cancel()
            try:
                await self._hot_reload_task
            except asyncio.CancelledError:
                pass
            self._hot_reload_task = None

        self._hot_reload_enabled = False
        logger.info("Hot reload disabled")

    async def _hot_reload_loop(self, debounce_seconds: float) -> None:
        """Hot reload monitoring loop.

        Args:
            debounce_seconds: Debounce time before reloading
        """
        try:
            from watchdog.events import FileModifiedEvent, FileSystemEventHandler
            from watchdog.observers import Observer

            class PluginFileHandler(FileSystemEventHandler):
                def __init__(self, loader: PluginLoader, debounce: float):
                    self.loader = loader
                    self.debounce = debounce
                    self.pending_reload: dict[str, asyncio.Task] = {}
                    self.loop = asyncio.get_event_loop()

                def on_modified(self, event):
                    if event.is_directory:
                        return
                    if not event.src_path.endswith(".py"):
                        return
                    if "__pycache__" in event.src_path:
                        return

                    # Schedule reload with debounce
                    path = event.src_path
                    if path in self.pending_reload:
                        self.pending_reload[path].cancel()

                    async def do_reload():
                        await asyncio.sleep(self.debounce)
                        await self.loader._reload_plugin(path)

                    task = self.loop.create_task(do_reload())
                    self.pending_reload[path] = task

            handler = PluginFileHandler(self, debounce_seconds)
            observer = Observer()
            observer.schedule(handler, str(self.plugin_dir), recursive=True)
            observer.start()

            try:
                while self._hot_reload_enabled:
                    await asyncio.sleep(1)
            finally:
                observer.stop()
                observer.join()

        except ImportError:
            logger.error("watchdog not installed, hot reload unavailable")
            self._hot_reload_enabled = False
        except Exception as e:
            logger.error(f"Hot reload error: {e}")
            self._hot_reload_enabled = False

    async def _reload_plugin(self, plugin_path: str) -> None:
        """Reload a single plugin.

        Args:
            plugin_path: Path to the modified plugin file
        """
        path = Path(plugin_path)

        # Find the plugin name
        if path.stem in self.plugins:
            plugin_name = path.stem
        else:
            # Check if it's a directory-based plugin
            plugin_name = path.parent.name
            if not (self.plugin_dir / path.parent.name / "plugin.py").exists():
                logger.warning(f"Cannot determine plugin name for {plugin_path}")
                return

        logger.info(f"Reloading plugin: {plugin_name}")

        # Shutdown existing plugin
        if plugin_name in self.plugins:
            try:
                await self.plugins[plugin_name].shutdown()
            except Exception as e:
                logger.error(f"Error shutting down {plugin_name}: {e}")
            del self.plugins[plugin_name]

        # Clear module from cache
        module_name = path.stem
        if module_name in sys.modules:
            del sys.modules[module_name]

        # Reload the plugin
        await self._load_plugin(path)
