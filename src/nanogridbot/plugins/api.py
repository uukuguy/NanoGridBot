"""Plugin API for third-party plugin integrations.

This module provides a safe API for external plugins to interact with NanoGridBot.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nanogridbot.types import Message


class PluginAPI:
    """API for third-party plugins to interact with NanoGridBot."""

    def __init__(self, orchestrator=None):
        """Initialize the plugin API.

        Args:
            orchestrator: Main orchestrator instance
        """
        self._orchestrator = orchestrator

    async def send_message(self, jid: str, text: str) -> bool:
        """Send a message to a specific JID.

        Args:
            jid: Target JID
            text: Message text

        Returns:
            True if sent successfully
        """
        if not self._orchestrator:
            return False

        try:
            await self._orchestrator.send_message(jid, text)
            return True
        except Exception:
            return False

    async def broadcast_to_group(self, group_jid: str, text: str) -> bool:
        """Broadcast a message to a registered group.

        Args:
            group_jid: Group JID
            text: Message text

        Returns:
            True if broadcast successfully
        """
        if not self._orchestrator:
            return False

        try:
            await self._orchestrator.router.broadcast(group_jid, text)
            return True
        except Exception:
            return False

    def get_registered_groups(self) -> list[str]:
        """Get list of registered group JIDs.

        Returns:
            List of group JIDs
        """
        if not self._orchestrator:
            return []

        return list(self._orchestrator.router.groups.keys())

    def get_group_info(self, jid: str) -> dict | None:
        """Get information about a registered group.

        Args:
            jid: Group JID

        Returns:
            Group info dict or None
        """
        if not self._orchestrator:
            return None

        group = self._orchestrator.router.groups.get(jid)
        if not group:
            return None

        return {
            "jid": group.jid,
            "name": group.name,
            "folder": group.folder,
            "trigger_pattern": group.trigger_pattern,
        }

    async def queue_container_run(
        self,
        group_folder: str,
        prompt: str,
    ) -> str | None:
        """Queue a container run for a group.

        Args:
            group_folder: Group folder name
            prompt: Prompt to send to the agent

        Returns:
            Task ID if queued successfully
        """
        if not self._orchestrator:
            return None

        try:
            task_id = await self._orchestrator.group_queue.enqueue(
                group_folder=group_folder,
                prompt=prompt,
            )
            return task_id
        except Exception:
            return None

    def get_queue_status(self, jid: str) -> dict | None:
        """Get queue status for a group.

        Args:
            jid: Group JID

        Returns:
            Queue status dict or None
        """
        if not self._orchestrator:
            return None

        return self._orchestrator.group_queue.get_status(jid)

    def register_hook(self, hook_name: str) -> callable:
        """Register a hook callback.

        Args:
            hook_name: Name of the hook

        Returns:
            Decorator function to register the hook
        """

        def decorator(func: callable):
            # Store the hook registration
            if not hasattr(self, "_registered_hooks"):
                self._registered_hooks = {}
            self._registered_hooks[f"{hook_name}:{func.__name__}"] = (hook_name, func)
            return func

        return decorator

    async def execute_message_filter(self, message: "Message") -> "Message":
        """Execute message through filters.

        Args:
            message: Message to filter

        Returns:
            Filtered message
        """
        if not self._orchestrator:
            return message

        # Apply plugin hooks
        if hasattr(self._orchestrator, "plugin_loader"):
            await self._orchestrator.plugin_loader.execute_hook("on_message_received", message)

        return message


class PluginContext:
    """Context object passed to plugins with access to the API."""

    def __init__(self, api: PluginAPI, config: dict):
        """Initialize plugin context.

        Args:
            api: Plugin API instance
            config: Plugin configuration
        """
        self.api = api
        self.config = config

    @property
    def logger(self):
        """Get a logger for the plugin."""
        from loguru import logger

        return logger.bind(plugin=True)
