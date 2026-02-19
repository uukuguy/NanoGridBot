"""Authentication module for NanoGridBot."""

from nanogridbot.auth.dependencies import get_current_user, require_permission, require_role
from nanogridbot.auth.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    InviteCodeError,
    LoginLockedError,
    PermissionDeniedError,
    SessionExpiredError,
    UserExistsError,
)
from nanogridbot.auth.invite import InviteCodeManager
from nanogridbot.auth.login_lock import LoginLockManager
from nanogridbot.auth.password import PasswordManager
from nanogridbot.auth.session import SessionManager

__all__ = [
    "AuthenticationError",
    "InvalidCredentialsError",
    "InviteCodeError",
    "LoginLockedError",
    "PermissionDeniedError",
    "SessionExpiredError",
    "UserExistsError",
    "InviteCodeManager",
    "LoginLockManager",
    "PasswordManager",
    "SessionManager",
    "get_current_user",
    "require_permission",
    "require_role",
]
