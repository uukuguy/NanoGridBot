"""Authentication exceptions."""


class AuthenticationError(Exception):
    """Base authentication exception."""

    pass


class InvalidCredentialsError(AuthenticationError):
    """Raised when credentials are invalid."""

    pass


class UserExistsError(AuthenticationError):
    """Raised when trying to create a user that already exists."""

    pass


class SessionExpiredError(AuthenticationError):
    """Raised when session is expired or invalid."""

    pass


class LoginLockedError(AuthenticationError):
    """Raised when account is locked due to too many failed attempts."""

    pass


class InviteCodeError(AuthenticationError):
    """Raised when invite code is invalid or expired."""

    pass


class PermissionDeniedError(AuthenticationError):
    """Raised when user lacks required permission."""

    pass
