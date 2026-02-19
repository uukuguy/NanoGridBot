"""User database repository."""

from datetime import datetime
from typing import Any

from loguru import logger

from nanogridbot.types import (
    AuditEvent,
    AuditEventType,
    InviteCode,
    Session,
    User,
    UserRole,
)


class UserRepository:
    """Repository for user-related database operations."""

    def __init__(self, db) -> None:
        """Initialize repository with database connection.

        Args:
            db: Database instance.
        """
        self.db = db

    async def create_user(self, username: str, email: str | None, password_hash: str) -> int:
        """Create a new user.

        Args:
            username: User's username.
            email: User's email.
            password_hash: Hashed password.

        Returns:
            User ID.
        """
        now = datetime.utcnow().isoformat()
        result = await self.db.execute(
            """
            INSERT INTO users (username, email, password_hash, role, is_active, is_verified, created_at, last_login)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (username, email, password_hash, UserRole.USER.value, 1, 0, now, now),
        )
        await self.db.commit()
        logger.info(f"Created user: {username}")
        return result.lastrowid

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Get user by ID.

        Args:
            user_id: User ID.

        Returns:
            User instance or None.
        """
        row = await self.db.fetchone(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        )
        return User(**row) if row else None

    async def get_user_by_username(self, username: str) -> User | None:
        """Get user by username.

        Args:
            username: Username.

        Returns:
            User instance or None.
        """
        row = await self.db.fetchone(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        )
        return User(**row) if row else None

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email.

        Args:
            email: Email address.

        Returns:
            User instance or None.
        """
        row = await self.db.fetchone(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        )
        return User(**row) if row else None

    async def update_user(self, user_id: int, **kwargs: Any) -> None:
        """Update user fields.

        Args:
            user_id: User ID.
            **kwargs: Fields to update.
        """
        if not kwargs:
            return

        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [user_id]
        await self.db.execute(
            f"UPDATE users SET {set_clause} WHERE id = ?",
            values,
        )
        await self.db.commit()
        logger.info(f"Updated user {user_id}: {list(kwargs.keys())}")

    async def delete_user(self, user_id: int) -> None:
        """Delete a user.

        Args:
            user_id: User ID.
        """
        await self.db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await self.db.commit()
        logger.info(f"Deleted user: {user_id}")

    async def list_users(self, limit: int = 100, offset: int = 0) -> list[User]:
        """List all users.

        Args:
            limit: Maximum number of users.
            offset: Number of users to skip.

        Returns:
            List of users.
        """
        rows = await self.db.fetchall(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [User(**row) for row in rows]

    async def update_last_login(self, user_id: int) -> None:
        """Update user's last login time.

        Args:
            user_id: User ID.
        """
        now = datetime.utcnow().isoformat()
        await self.db.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (now, user_id),
        )
        await self.db.commit()


class SessionRepository:
    """Repository for session management."""

    def __init__(self, db) -> None:
        """Initialize repository with database connection.

        Args:
            db: Database instance.
        """
        self.db = db

    async def create_session(
        self,
        user_id: int,
        session_token: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> int:
        """Create a new session.

        Args:
            user_id: User ID.
            session_token: Session token.
            expires_at: Expiration time.
            ip_address: Client IP address.
            user_agent: Client user agent.

        Returns:
            Session ID.
        """
        now = datetime.utcnow().isoformat()
        result = await self.db.execute(
            """
            INSERT INTO user_sessions (user_id, session_token, expires_at, created_at, last_activity, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, session_token, expires_at.isoformat(), now, now, ip_address, user_agent),
        )
        await self.db.commit()
        logger.info(f"Created session for user {user_id}")
        return result.lastrowid

    async def get_session_by_token(self, token: str) -> Session | None:
        """Get session by token.

        Args:
            token: Session token.

        Returns:
            Session instance or None.
        """
        row = await self.db.fetchone(
            "SELECT * FROM user_sessions WHERE session_token = ?",
            (token,),
        )
        return Session(**row) if row else None

    async def delete_session(self, session_id: int) -> None:
        """Delete a session.

        Args:
            session_id: Session ID.
        """
        await self.db.execute("DELETE FROM user_sessions WHERE id = ?", (session_id,))
        await self.db.commit()

    async def delete_session_by_token(self, token: str) -> None:
        """Delete session by token.

        Args:
            token: Session token.
        """
        await self.db.execute("DELETE FROM user_sessions WHERE session_token = ?", (token,))
        await self.db.commit()
        logger.info(f"Deleted session: {token[:8]}...")

    async def delete_user_sessions(self, user_id: int) -> None:
        """Delete all sessions for a user.

        Args:
            user_id: User ID.
        """
        await self.db.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        await self.db.commit()
        logger.info(f"Deleted all sessions for user {user_id}")

    async def cleanup_expired_sessions(self) -> int:
        """Delete expired sessions.

        Returns:
            Number of deleted sessions.
        """
        now = datetime.utcnow().isoformat()
        cursor = await self.db.execute(
            "DELETE FROM user_sessions WHERE expires_at < ?",
            (now,),
        )
        await self.db.commit()
        count = cursor.rowcount
        if count > 0:
            logger.info(f"Cleaned up {count} expired sessions")
        return count

    async def update_session_activity(self, session_id: int) -> None:
        """Update session last activity time.

        Args:
            session_id: Session ID.
        """
        now = datetime.utcnow().isoformat()
        await self.db.execute(
            "UPDATE user_sessions SET last_activity = ? WHERE id = ?",
            (now, session_id),
        )
        await self.db.commit()


class InviteCodeRepository:
    """Repository for invite code management."""

    def __init__(self, db) -> None:
        """Initialize repository with database connection.

        Args:
            db: Database instance.
        """
        self.db = db

    async def create_invite_code(
        self,
        code: str,
        created_by: int,
        expires_at: datetime,
        max_uses: int = 1,
    ) -> int:
        """Create a new invite code.

        Args:
            code: Invite code.
            created_by: User ID who created the code.
            expires_at: Expiration time.
            max_uses: Maximum number of uses.

        Returns:
            Invite code ID.
        """
        now = datetime.utcnow().isoformat()
        result = await self.db.execute(
            """
            INSERT INTO invite_codes (code, created_by, expires_at, max_uses, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (code, created_by, expires_at.isoformat(), max_uses, now),
        )
        await self.db.commit()
        logger.info(f"Created invite code: {code[:8]}...")
        return result.lastrowid

    async def get_invite_code(self, code: str) -> InviteCode | None:
        """Get invite code.

        Args:
            code: Invite code.

        Returns:
            InviteCode instance or None.
        """
        row = await self.db.fetchone(
            "SELECT * FROM invite_codes WHERE code = ?",
            (code,),
        )
        return InviteCode(**row) if row else None

    async def use_invite_code(self, code: str, used_by: int) -> bool:
        """Mark invite code as used.

        Args:
            code: Invite code.
            used_by: User ID who used the code.

        Returns:
            True if successful, False if code is invalid or expired.
        """
        now = datetime.utcnow()
        row = await self.db.fetchone(
            "SELECT * FROM invite_codes WHERE code = ? AND used_by IS NULL AND expires_at > ? AND (SELECT COUNT(*) FROM users WHERE id = ?) < max_uses",
            (code, now.isoformat(), used_by),
        )
        if not row:
            return False

        await self.db.execute(
            "UPDATE invite_codes SET used_by = ?, used_at = ? WHERE code = ?",
            (used_by, now.isoformat(), code),
        )
        await self.db.commit()
        logger.info(f"Used invite code: {code[:8]}... by user {used_by}")
        return True

    async def delete_invite_code(self, code_id: int) -> None:
        """Delete an invite code.

        Args:
            code_id: Invite code ID.
        """
        await self.db.execute("DELETE FROM invite_codes WHERE id = ?", (code_id,))
        await self.db.commit()

    async def list_invite_codes(self, created_by: int | None = None) -> list[InviteCode]:
        """List invite codes.

        Args:
            created_by: Filter by creator user ID.

        Returns:
            List of invite codes.
        """
        if created_by:
            rows = await self.db.fetchall(
                "SELECT * FROM invite_codes WHERE created_by = ? ORDER BY created_at DESC",
                (created_by,),
            )
        else:
            rows = await self.db.fetchall(
                "SELECT * FROM invite_codes ORDER BY created_at DESC",
            )
        return [InviteCode(**row) for row in rows]


class LoginAttemptRepository:
    """Repository for tracking login attempts."""

    def __init__(self, db) -> None:
        """Initialize repository with database connection.

        Args:
            db: Database instance.
        """
        self.db = db

    async def record_failed_attempt(self, username: str, ip_address: str | None = None) -> None:
        """Record a failed login attempt.

        Args:
            username: Username that failed to login.
            ip_address: Client IP address.
        """
        now = datetime.utcnow().isoformat()
        await self.db.execute(
            """
            INSERT INTO login_attempts (username, ip_address, attempt_time, success)
            VALUES (?, ?, ?, 0)
            """,
            (username, ip_address, now),
        )
        await self.db.commit()

    async def record_success_attempt(self, username: str, ip_address: str | None = None) -> None:
        """Record a successful login.

        Args:
            username: Username that logged in.
            ip_address: Client IP address.
        """
        now = datetime.utcnow().isoformat()
        await self.db.execute(
            """
            INSERT INTO login_attempts (username, ip_address, attempt_time, success)
            VALUES (?, ?, ?, 1)
            """,
            (username, ip_address, now),
        )
        await self.db.commit()

    async def get_failed_attempt_count(self, username: str, minutes: int = 15) -> int:
        """Get number of failed attempts in time window.

        Args:
            username: Username to check.
            minutes: Time window in minutes.

        Returns:
            Number of failed attempts.
        """
        from datetime import timedelta

        cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
        row = await self.db.fetchone(
            """
            SELECT COUNT(*) as count FROM login_attempts
            WHERE username = ? AND attempt_time > ? AND success = 0
            """,
            (username, cutoff),
        )
        return row["count"] if row else 0

    async def clear_attempts(self, username: str) -> None:
        """Clear login attempts for a user.

        Args:
            username: Username.
        """
        await self.db.execute(
            "DELETE FROM login_attempts WHERE username = ?",
            (username,),
        )
        await self.db.commit()


class AuditRepository:
    """Repository for audit log."""

    def __init__(self, db) -> None:
        """Initialize repository with database connection.

        Args:
            db: Database instance.
        """
        self.db = db

    async def log_event(
        self,
        event_type: AuditEventType,
        user_id: int | None = None,
        username: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> int:
        """Log an audit event.

        Args:
            event_type: Type of event.
            user_id: User ID.
            username: Username.
            ip_address: Client IP address.
            user_agent: Client user agent.
            resource_type: Type of resource affected.
            resource_id: ID of resource affected.
            details: Additional details.

        Returns:
            Event ID.
        """
        now = datetime.utcnow().isoformat()
        details_json = str(details) if details else None
        result = await self.db.execute(
            """
            INSERT INTO audit_logs (event_type, user_id, username, ip_address, user_agent, resource_type, resource_id, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_type.value,
                user_id,
                username,
                ip_address,
                user_agent,
                resource_type,
                resource_id,
                details_json,
                now,
            ),
        )
        await self.db.commit()
        return result.lastrowid

    async def get_events(
        self,
        user_id: int | None = None,
        event_type: AuditEventType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """Get audit events.

        Args:
            user_id: Filter by user ID.
            event_type: Filter by event type.
            limit: Maximum number of events.
            offset: Number of events to skip.

        Returns:
            List of audit events.
        """
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []

        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.value)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = await self.db.fetchall(query, params)
        return [AuditEvent(**row) for row in rows]


class UserDirectoryRepository:
    """Repository for user directory management."""

    def __init__(self, db) -> None:
        """Initialize repository with database connection.

        Args:
            db: Database instance.
        """
        self.db = db

    async def create_user_directory(self, user_id: int, path: str, directory_type: str) -> int:
        """Create a user directory entry.

        Args:
            user_id: User ID.
            path: Directory path.
            type: Directory type (groups, sessions, memory, archives, config).

        Returns:
            Directory entry ID.
        """
        result = await self.db.execute(
            """
            INSERT INTO user_directories (user_id, path, directory_type)
            VALUES (?, ?, ?)
            """,
            (user_id, path, directory_type),
        )
        await self.db.commit()
        return result.lastrowid

    async def get_user_directories(self, user_id: int) -> list[dict[str, Any]]:
        """Get all directories for a user.

        Args:
            user_id: User ID.

        Returns:
            List of directory entries.
        """
        rows = await self.db.fetchall(
            "SELECT * FROM user_directories WHERE user_id = ?",
            (user_id,),
        )
        return rows

    async def delete_user_directories(self, user_id: int) -> None:
        """Delete all directories for a user.

        Args:
            user_id: User ID.
        """
        await self.db.execute(
            "DELETE FROM user_directories WHERE user_id = ?",
            (user_id,),
        )
        await self.db.commit()
