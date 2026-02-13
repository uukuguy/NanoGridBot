"""Plugin loader for loading and managing plugins."""

import importlib.util
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from nanogridbot.plugins.base import Plugin


class PluginLoader:
    """Manages plugin loading and lifecycle."""

    def __init__(self, plugin_dir: Path | None = None):
        """Initialize the plugin loader.

        Args:
            plugin_dir: Directory to load plugins from
        """
        self.plugin_dir = plugin_dir
        self.plugins: dict[str, Plugin] = {}

    async def load_all(self) -> None:
        """Load all plugins from the plugin directory."""
        if not self.plugin_dir or not self.plugin_dir.exists():
            logger.warning(f"Plugin directory not found: {self.plugin_dir}")
            return

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

            # Instantiate plugin
            plugin = plugin_class()

            # Initialize plugin
            await plugin.initialize({})

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
