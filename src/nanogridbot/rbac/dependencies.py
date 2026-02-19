"""FastAPI dependencies for RBAC."""

from typing import Any, Callable

from fastapi import Depends, HTTPException, status

from nanogridbot.auth.dependencies import get_current_user
from nanogridbot.rbac.permissions import has_permission, has_role
from nanogridbot.types import Permission, User, UserRole


async def check_permission(
    permission: Permission,
    user: User = Depends(get_current_user),
) -> User:
    """Dependency that checks if user has a specific permission.

    Args:
        permission: Permission to check.
        user: Current user.

    Returns:
        User if authorized.

    Raises:
        HTTPException: If user lacks permission.
    """
    if not has_permission(user, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission.value}",
        )
    return user


async def check_role(
    min_role: UserRole,
    user: User = Depends(get_current_user),
) -> User:
    """Dependency that checks if user has at least a minimum role.

    Args:
        min_role: Minimum required role.
        user: Current user.

    Returns:
        User if authorized.

    Raises:
        HTTPException: If user lacks required role.
    """
    if not has_role(user, min_role):
        role_hierarchy = {
            UserRole.GUEST: "guest",
            UserRole.VIEWER: "viewer",
            UserRole.USER: "user",
            UserRole.ADMIN: "admin",
            UserRole.OWNER: "owner",
        }
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role denied: requires {role_hierarchy.get(min_role, min_role.value)} or higher",
        )
    return user


def create_permission_dependency(permission: Permission) -> Callable:
    """Create a dependency for a specific permission.

    Args:
        permission: Permission to require.

    Returns:
        Dependency function.
    """

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value}",
            )
        return user

    return dependency


def create_role_dependency(min_role: UserRole) -> Callable:
    """Create a dependency for a minimum role.

    Args:
        min_role: Minimum required role.

    Returns:
        Dependency function.
    """
    role_hierarchy = {
        UserRole.GUEST: 0,
        UserRole.VIEWER: 1,
        UserRole.USER: 2,
        UserRole.ADMIN: 3,
        UserRole.OWNER: 4,
    }

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if role_hierarchy.get(user.role, 0) < role_hierarchy.get(min_role, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role denied: requires {min_role.value} or higher",
            )
        return user

    return dependency
