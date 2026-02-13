"""Built-in plugins for NanoGridBot."""

from pathlib import Path

from nanogridbot.plugins.loader import PluginLoader


async def load_builtin_plugins(plugins_dir: Path | None = None) -> PluginLoader:
    """Load built-in plugins.

    Args:
        plugins_dir: Base plugins directory

    Returns:
        PluginLoader instance with loaded plugins
    """
    builtin_dir = plugins_dir / "builtin" if plugins_dir else Path("plugins/builtin")
    loader = PluginLoader(plugin_dir=builtin_dir)
    await loader.load_all()
    return loader
