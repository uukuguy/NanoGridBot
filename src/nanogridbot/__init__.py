"""NanoGridBot - Personal Claude AI assistant via messaging platforms."""

__version__ = "0.1.0-alpha"
__author__ = "NanoGridBot Team"

from nanogridbot.config import Config
from nanogridbot.logger import setup_logger
from nanogridbot.types import (
    ChannelType,
    ContainerConfig,
    ContainerOutput,
    Message,
    MessageRole,
    RegisteredGroup,
    ScheduledTask,
    ScheduleType,
    TaskStatus,
)

__all__ = [
    "__version__",
    "Config",
    "setup_logger",
    # Types
    "ChannelType",
    "ContainerConfig",
    "ContainerOutput",
    "Message",
    "MessageRole",
    "RegisteredGroup",
    "ScheduleType",
    "ScheduledTask",
    "TaskStatus",
]
