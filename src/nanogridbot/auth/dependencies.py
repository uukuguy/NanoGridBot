"""FastAPI dependencies for authentication and authorization."""

from typing import Callable

from fastapi import Depends, Header, HTTPException, Request, status
from loguru import logger

from nanogridbot.auth.exceptions import (
    PermissionDeniedError,
    SessionExpiredError,
)
from nanogridbot.database.connection import Database
from nanogridbot.types import Permission, User, UserRole, ROLE_PERMISSIONS


# Global database instance - will be set by web app
_db_instance: Database | None = None


def set_database(db: Database) -> None:
    """Set the global database instance.

    Args:
        db: Database instance.
    """
    global _db_instance
    _db_instance = db


def get_database() -> Database:
    """Get the global database instance.

    Returns:
        Database instance.
    """
    if _db_instance is None:
        raise RuntimeError("Database not initialized")
    return _db_instance


async def get_current_user(
    request: Request,
    authorization: str | None = Header(None),
) -> User:
    """Get current authenticated user from session token.

    Args:
        request: FastAPI request.
        authorization: Authorization header (Bearer token).

    Returns:
        Current user.

    Raises:
        HTTPException: If not authenticated.
    """
    db = get_database()

    # Extract token from Authorization header
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    # Verify session
    session_repo = db.get_session_repository()
    session = await session_repo.get_session_by_token(token)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user
    user_repo = db.get_user_repository()
    user = await user_repo.get_user_by_id(session.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Update session activity
    await session_repo.update_session_activity(session.id)

    return user


def require_role(min_role: UserRole) -> Callable:
    """Create a dependency that requires a minimum role.

    Args:
        min_role: Minimum required role.

    Returns:
        Dependency function.
    """

    async def role_checker(
        user: User = Depends(get_current_user),
    ) -> User:
        role_hierarchy = {
            UserRole.GUEST: 0,
            UserRole.VIEWER: 1,
            UserRole.USER: 2,
            UserRole.ADMIN: 3,
            UserRole.OWNER: 4,
        }

        if role_hierarchy.get(user.role, 0) < role_hierarchy.get(min_role, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {min_role.value} role or higher",
            )

        return user

    return role_checker


def require_permission(permission: Permission) -> Callable:
    """Create a dependency that requires a specific permission.

    Args:
        permission: Required permission.

    Returns:
        Dependency function.
    """

    async def permission_checker(
        user: User = Depends(get_current_user),
    ) -> User:
        # Get permissions for user's role
        role_perms = ROLE_PERMISSIONS.get(user.role, set())

        if permission not in role_perms:
            logger.warning(
                f"Permission denied: user {user.username} with role {user.role} "
                f"lacks permission {permission.value}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission.value}",
            )

        return user

    return permission_checker


async def get_optional_user(
    authorization: str | None = Header(None),
) -> User | None:
    """Get current user if authenticated, otherwise None.

    Args:
        authorization: Authorization header.

    Returns:
        User if authenticated, None otherwise.
    """
    try:
        return await get_current_user(
            Request(scope={"type": "http"}),
            authorization,
        )
    except HTTPException:
        return None
