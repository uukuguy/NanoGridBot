"""Session management."""

import secrets
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from nanogridbot.auth.exceptions import SessionExpiredError
from nanogridbot.database.connection import Database


class SessionManager:
    """Manages user sessions."""

    def __init__(self, db: Database, session_lifetime_days: int = 30) -> None:
        """Initialize session manager.

        Args:
            db: Database instance.
            session_lifetime_days: Session lifetime in days.
        """
        self.db = db
        self.session_lifetime = timedelta(days=session_lifetime_days)

    def generate_token(self) -> str:
        """Generate a secure session token.

        Returns:
            Session token.
        """
        return secrets.token_urlsafe(32)

    async def create_session(
        self,
        user_id: int,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> str:
        """Create a new session for a user.

        Args:
            user_id: User ID.
            ip_address: Client IP address.
            user_agent: Client user agent.

        Returns:
            Session token.
        """
        token = self.generate_token()
        expires_at = datetime.utcnow() + self.session_lifetime

        session_repo = self.db.get_session_repository()
        await session_repo.create_session(
            user_id=user_id,
            session_token=token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(f"Created session for user {user_id}")
        return token

    async def get_session(self, token: str) -> dict[str, Any] | None:
        """Get session by token.

        Args:
            token: Session token.

        Returns:
            Session data or None if not found/expired.
        """
        session_repo = self.db.get_session_repository()
        session = await session_repo.get_session_by_token(token)

        if not session:
            return None

        # Check if expired
        if datetime.fromisoformat(session.expires_at) < datetime.utcnow():
            await session_repo.delete_session_by_token(token)
            return None

        return {
            "id": session.id,
            "user_id": session.user_id,
            "token": session.session_token,
            "expires_at": session.expires_at,
            "created_at": session.created_at,
            "last_activity": session.last_activity,
            "ip_address": session.ip_address,
            "user_agent": session.user_agent,
        }

    async def delete_session(self, token: str) -> None:
        """Delete a session.

        Args:
            token: Session token.
        """
        session_repo = self.db.get_session_repository()
        await session_repo.delete_session_by_token(token)
        logger.info(f"Deleted session: {token[:8]}...")

    async def delete_user_sessions(self, user_id: int) -> None:
        """Delete all sessions for a user.

        Args:
            user_id: User ID.
        """
        session_repo = self.db.get_session_repository()
        await session_repo.delete_user_sessions(user_id)
        logger.info(f"Deleted all sessions for user {user_id}")

    async def cleanup_expired(self) -> int:
        """Clean up expired sessions.

        Returns:
            Number of deleted sessions.
        """
        session_repo = self.db.get_session_repository()
        return await session_repo.cleanup_expired_sessions()

    async def verify_session(self, token: str) -> int:
        """Verify session and return user ID.

        Args:
            token: Session token.

        Returns:
            User ID.

        Raises:
            SessionExpiredError: If session is invalid or expired.
        """
        session = await self.get_session(token)
        if not session:
            raise SessionExpiredError("Invalid or expired session")
        return session["user_id"]
