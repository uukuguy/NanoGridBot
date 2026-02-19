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


# ============================================
# User Management Types
# ============================================


class UserRole(str, Enum):
    """User roles for RBAC."""

    OWNER = "owner"
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
    GUEST = "guest"


class Permission(str, Enum):
    """System permissions."""

    # User management
    USERS_MANAGE = "users.manage"
    USERS_INVITE = "users.invite"
    USERS_VIEW = "users.view"

    # Group management
    GROUPS_CREATE = "groups.create"
    GROUPS_DELETE = "groups.delete"
    GROUPS_VIEW = "groups.view"

    # Container management
    CONTAINERS_CREATE = "containers.create"
    CONTAINERS_MANAGE = "containers.manage"
    CONTAINERS_VIEW = "containers.view"

    # Task management
    TASKS_CREATE = "tasks.create"
    TASKS_MANAGE = "tasks.manage"
    TASKS_VIEW = "tasks.view"

    # Configuration
    CONFIG_MANAGE = "config.manage"
    CONFIG_VIEW = "config.view"

    # Audit
    AUDIT_VIEW = "audit.view"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.OWNER: {
        Permission.USERS_MANAGE,
        Permission.USERS_INVITE,
        Permission.USERS_VIEW,
        Permission.GROUPS_CREATE,
        Permission.GROUPS_DELETE,
        Permission.GROUPS_VIEW,
        Permission.CONTAINERS_CREATE,
        Permission.CONTAINERS_MANAGE,
        Permission.CONTAINERS_VIEW,
        Permission.TASKS_CREATE,
        Permission.TASKS_MANAGE,
        Permission.TASKS_VIEW,
        Permission.CONFIG_MANAGE,
        Permission.CONFIG_VIEW,
        Permission.AUDIT_VIEW,
    },
    UserRole.ADMIN: {
        Permission.USERS_MANAGE,
        Permission.USERS_INVITE,
        Permission.USERS_VIEW,
        Permission.GROUPS_CREATE,
        Permission.GROUPS_DELETE,
        Permission.GROUPS_VIEW,
        Permission.CONTAINERS_CREATE,
        Permission.CONTAINERS_MANAGE,
        Permission.CONTAINERS_VIEW,
        Permission.TASKS_CREATE,
        Permission.TASKS_MANAGE,
        Permission.TASKS_VIEW,
        Permission.CONFIG_MANAGE,
        Permission.CONFIG_VIEW,
        Permission.AUDIT_VIEW,
    },
    UserRole.USER: {
        Permission.GROUPS_CREATE,
        Permission.GROUPS_VIEW,
        Permission.CONTAINERS_CREATE,
        Permission.CONTAINERS_MANAGE,
        Permission.CONTAINERS_VIEW,
        Permission.TASKS_CREATE,
        Permission.TASKS_MANAGE,
        Permission.TASKS_VIEW,
        Permission.CONFIG_VIEW,
    },
    UserRole.VIEWER: {
        Permission.GROUPS_VIEW,
        Permission.CONTAINERS_VIEW,
        Permission.TASKS_VIEW,
        Permission.CONFIG_VIEW,
    },
    UserRole.GUEST: {
        Permission.CONTAINERS_VIEW,
        Permission.TASKS_VIEW,
    },
}


class User(BaseModel):
    """User account model."""

    model_config = ConfigDict(use_enum_values=True)

    id: int | None = None
    username: str
    email: str | None = None
    password_hash: str
    role: UserRole = UserRole.USER
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime | None = None
    last_login: datetime | None = None


class UserCreate(BaseModel):
    """User creation request."""

    username: str = Field(..., min_length=3, max_length=50)
    email: str | None = None
    password: str = Field(..., min_length=8, max_length=100)
    invite_code: str


class UserLogin(BaseModel):
    """User login request."""

    username: str
    password: str


class UserResponse(BaseModel):
    """User response model (without password)."""

    model_config = ConfigDict(use_enum_values=True)

    id: int
    username: str
    email: str | None = None
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: datetime | None = None


class Session(BaseModel):
    """User session model."""

    model_config = ConfigDict(use_enum_values=True)

    id: int | None = None
    user_id: int
    session_token: str
    expires_at: datetime
    created_at: datetime | None = None
    last_activity: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None


class InviteCode(BaseModel):
    """Invite code model."""

    model_config = ConfigDict(use_enum_values=True)

    id: int | None = None
    code: str
    created_by: int
    used_by: int | None = None
    used_at: datetime | None = None
    expires_at: datetime
    max_uses: int = 1
    created_at: datetime | None = None


class InviteCodeCreate(BaseModel):
    """Invite code creation request."""

    expires_in_days: int = Field(default=7, ge=1, le=30)
    max_uses: int = Field(default=1, ge=1, le=10)


class AuditEventType(str, Enum):
    """Audit event types."""

    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    REGISTER = "register"
    SESSION_CREATED = "session_created"
    SESSION_REVOKED = "session_revoked"

    # User events
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_ROLE_CHANGED = "user.role_changed"

    # Resource events
    GROUP_CREATED = "group.created"
    GROUP_DELETED = "group.deleted"
    CONTAINER_STARTED = "container.started"
    CONTAINER_STOPPED = "container.stopped"
    TASK_CREATED = "task.created"

    # Security events
    SECURITY_LOGIN_LOCKED = "security.login_locked"
    SECURITY_PERMISSION_DENIED = "security.permission_denied"
    SECURITY_MOUNT_REJECTED = "security.mount_rejected"


class AuditEvent(BaseModel):
    """Audit event model."""

    model_config = ConfigDict(use_enum_values=True)

    id: int | None = None
    event_type: AuditEventType
    user_id: int | None = None
    username: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    details: dict[str, Any] | None = None
    timestamp: datetime | None = None
