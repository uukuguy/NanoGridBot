"""Permission checking utilities."""

from functools import wraps
from typing import Any, Callable

from nanogridbot.types import Permission, User, UserRole, ROLE_PERMISSIONS


def has_permission(user: User, permission: Permission) -> bool:
    """Check if user has a specific permission.

    Args:
        user: User to check.
        permission: Permission to check for.

    Returns:
        True if user has the permission.
    """
    role_perms = ROLE_PERMISSIONS.get(user.role, set())
    return permission in role_perms


def has_role(user: User, min_role: UserRole) -> bool:
    """Check if user has at least the specified role.

    Args:
        user: User to check.
        min_role: Minimum required role.

    Returns:
        True if user has the role or higher.
    """
    role_hierarchy = {
        UserRole.GUEST: 0,
        UserRole.VIEWER: 1,
        UserRole.USER: 2,
        UserRole.ADMIN: 3,
        UserRole.OWNER: 4,
    }

    return role_hierarchy.get(user.role, 0) >= role_hierarchy.get(min_role, 0)


class PermissionChecker:
    """Permission checker with caching."""

    def __init__(self, user: User) -> None:
        """Initialize permission checker.

        Args:
            user: User to check permissions for.
        """
        self.user = user
        self._permissions: set[Permission] | None = None

    @property
    def permissions(self) -> set[Permission]:
        """Get user's permissions.

        Returns:
            Set of permissions for user's role.
        """
        if self._permissions is None:
            self._permissions = ROLE_PERMISSIONS.get(self.user.role, set())
        return self._permissions

    def can(self, permission: Permission) -> bool:
        """Check if user can perform action.

        Args:
            permission: Required permission.

        Returns:
            True if user has permission.
        """
        return permission in self.permissions

    def can_any(self, *permissions: Permission) -> bool:
        """Check if user has any of the permissions.

        Args:
            *permissions: Permissions to check.

        Returns:
            True if user has any permission.
        """
        return any(p in self.permissions for p in permissions)

    def can_all(self, *permissions: Permission) -> bool:
        """Check if user has all of the permissions.

        Args:
            *permissions: Permissions to check.

        Returns:
            True if user has all permissions.
        """
        return all(p in self.permissions for p in permissions)

    def is_at_least(self, role: UserRole) -> bool:
        """Check if user has at least the specified role.

        Args:
            role: Minimum required role.

        Returns:
            True if user has role or higher.
        """
        return has_role(self.user, role)


def require_permission(permission: Permission) -> Callable:
    """Decorator to require a permission for a function.

    Args:
        permission: Required permission.

    Returns:
        Decorator function.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get user from kwargs
            user = kwargs.get("user")
            if not user or not isinstance(user, User):
                raise PermissionError("User not found in function arguments")

            if not has_permission(user, permission):
                raise PermissionError(
                    f"Permission denied: requires {permission.value}"
                )

            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get user from kwargs
            user = kwargs.get("user")
            if not user or not isinstance(user, User):
                raise PermissionError("User not found in function arguments")

            if not has_permission(user, permission):
                raise PermissionError(
                    f"Permission denied: requires {permission.value}"
                )

            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
