"""Core type definitions for NanoGridBot."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChannelType(str, Enum):
    """Supported messaging platforms."""

    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    SLACK = "slack"
    DISCORD = "discord"
    QQ = "qq"
    FEISHU = "feishu"
    WECOM = "wecom"
    DINGTALK = "dingtalk"


class MessageRole(str, Enum):
    """Message sender role."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """Chat message model."""

    model_config = ConfigDict(use_enum_values=True)

    id: str
    chat_jid: str
    sender: str
    sender_name: str | None = None
    content: str
    timestamp: datetime
    is_from_me: bool = False

    role: MessageRole = MessageRole.USER


class RegisteredGroup(BaseModel):
    """Registered group/chat configuration."""

    jid: str
    name: str
    folder: str
    trigger_pattern: str | None = None
    container_config: dict[str, Any] | None = None
    requires_trigger: bool = True


class ContainerConfig(BaseModel):
    """Container execution configuration."""

    additional_mounts: list[dict[str, Any]] = Field(default_factory=list)
    timeout: int | None = None
    max_output_size: int | None = None
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables for container")


class ScheduleType(str, Enum):
    """Task schedule type."""

    CRON = "cron"
    INTERVAL = "interval"
    ONCE = "once"


class TaskStatus(str, Enum):
    """Scheduled task status."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class ScheduledTask(BaseModel):
    """Scheduled task configuration."""

    model_config = ConfigDict(use_enum_values=True)

    id: int | None = None
    group_folder: str
    prompt: str
    schedule_type: ScheduleType
    schedule_value: str
    status: TaskStatus = TaskStatus.ACTIVE
    next_run: datetime | None = None
    context_mode: Literal["group", "isolated"] = "group"
    target_chat_jid: str | None = None


class ContainerOutput(BaseModel):
    """Container execution result."""

    status: Literal["success", "error"]
    result: str | None = None
    error: str | None = None
    new_session_id: str | None = None


# JID (Jabber ID) Format Specification
# Format: {channel}:{platform_specific_id}
# Examples:
#   - telegram:123456789
#   - discord:channel:987654321
#   - whatsapp:+1234567890
#   - slack:U1234567890
#   - feishu:oc_xxx
#   - wecom:ww_xxx
#   - dingtalk:xxx
#   - qq:123456
