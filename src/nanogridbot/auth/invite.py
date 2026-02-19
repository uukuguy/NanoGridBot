"""Invite code management."""

import secrets
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from nanogridbot.auth.exceptions import InviteCodeError
from nanogridbot.database.connection import Database


class InviteCodeManager:
    """Manages invite codes for user registration."""

    CODE_LENGTH = 16

    def __init__(self, db: Database) -> None:
        """Initialize invite code manager.

        Args:
            db: Database instance.
        """
        self.db = db

    def generate_code(self) -> str:
        """Generate a secure invite code.

        Returns:
            Invite code.
        """
        return secrets.token_urlsafe(self.CODE_LENGTH)[:self.CODE_LENGTH]

    async def create_code(
        self,
        created_by: int,
        expires_in_days: int = 7,
        max_uses: int = 1,
    ) -> dict[str, Any]:
        """Create a new invite code.

        Args:
            created_by: User ID who created the code.
            expires_in_days: Days until code expires.
            max_uses: Maximum number of uses.

        Returns:
            Created invite code data.
        """
        code = self.generate_code()
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        repo = self.db.get_invite_code_repository()
        code_id = await repo.create_invite_code(
            code=code,
            created_by=created_by,
            expires_at=expires_at,
            max_uses=max_uses,
        )

        logger.info(f"Created invite code {code[:8]}... by user {created_by}")

        return {
            "id": code_id,
            "code": code,
            "created_by": created_by,
            "expires_at": expires_at.isoformat(),
            "max_uses": max_uses,
        }

    async def validate_code(self, code: str) -> dict[str, Any]:
        """Validate an invite code.

        Args:
            code: Invite code to validate.

        Returns:
            Invite code data.

        Raises:
            InviteCodeError: If code is invalid or expired.
        """
        repo = self.db.get_invite_code_repository()
        invite = await repo.get_invite_code(code)

        if not invite:
            raise InviteCodeError("Invalid invite code")

        # Check expiration
        expires_at = datetime.fromisoformat(invite.expires_at)
        if expires_at < datetime.utcnow():
            raise InviteCodeError("Invite code has expired")

        # Check if already used (for single-use codes)
        if invite.used_by is not None and invite.max_uses == 1:
            raise InviteCodeError("Invite code has already been used")

        return {
            "id": invite.id,
            "code": invite.code,
            "created_by": invite.created_by,
            "expires_at": invite.expires_at,
            "max_uses": invite.max_uses,
            "used_by": invite.used_by,
        }

    async def use_code(self, code: str, used_by: int) -> bool:
        """Mark an invite code as used.

        Args:
            code: Invite code.
            used_by: User ID who used the code.

        Returns:
            True if successful.

        Raises:
            InviteCodeError: If code cannot be used.
        """
        # First validate
        await self.validate_code(code)

        # Then mark as used
        repo = self.db.get_invite_code_repository()
        success = await repo.use_invite_code(code, used_by)

        if not success:
            raise InviteCodeError("Failed to use invite code")

        logger.info(f"Invite code {code[:8]}... used by user {used_by}")
        return True

    async def delete_code(self, code_id: int) -> None:
        """Delete an invite code.

        Args:
            code_id: Invite code ID.
        """
        repo = self.db.get_invite_code_repository()
        await repo.delete_invite_code(code_id)
        logger.info(f"Deleted invite code {code_id}")

    async def list_codes(self, created_by: int | None = None) -> list[dict[str, Any]]:
        """List invite codes.

        Args:
            created_by: Filter by creator.

        Returns:
            List of invite codes.
        """
        repo = self.db.get_invite_code_repository()
        codes = await repo.list_invite_codes(created_by)

        return [
            {
                "id": c.id,
                "code": c.code[:8] + "...",
                "created_by": c.created_by,
                "used_by": c.used_by,
                "used_at": c.used_at,
                "expires_at": c.expires_at,
                "max_uses": c.max_uses,
                "created_at": c.created_at,
            }
            for c in codes
        ]
