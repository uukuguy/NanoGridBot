"""Plugin base class and interfaces."""

from abc import ABC, abstractmethod
from typing import Any

from nanogridbot.types import ContainerOutput, Message


class Plugin(ABC):
    """Base class for all plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version."""
        pass

    @property
    def description(self) -> str:
        """Plugin description."""
        return ""

    @property
    def author(self) -> str:
        """Plugin author."""
        return "Unknown"

    async def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the plugin.

        Args:
            config: Plugin configuration
        """
        pass

    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        pass

    async def on_message_received(self, message: Message) -> Message | None:
        """Hook called when a message is received.

        Args:
            message: Received message

        Returns:
            Modified message, or None to drop the message
        """
        return message

    async def on_message_sent(self, jid: str, text: str) -> str | None:
        """Hook called when a message is about to be sent.

        Args:
            jid: Target JID
            text: Message text

        Returns:
            Modified text, or None to cancel sending
        """
        return text

    async def on_container_start(
        self,
        group_folder: str,
        prompt: str,
    ) -> str | None:
        """Hook called when a container is about to start.

        Args:
            group_folder: Group folder name
            prompt: Prompt to send

        Returns:
            Modified prompt, or None to cancel
        """
        return prompt

    async def on_container_result(
        self,
        result: ContainerOutput,
    ) -> ContainerOutput | None:
        """Hook called when a container completes.

        Args:
            result: Container output

        Returns:
            Modified result, or None to drop
        """
        return result

    async def on_group_registered(self, group: Any) -> None:
        """Hook called when a group is registered.

        Args:
            group: Registered group
        """
        pass

    async def on_group_unregistered(self, jid: str) -> None:
        """Hook called when a group is unregistered.

        Args:
            jid: Group JID
        """
        pass
