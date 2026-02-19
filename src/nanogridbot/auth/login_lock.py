"""Login lockout management."""

from loguru import logger

from nanogridbot.auth.exceptions import LoginLockedError
from nanogridbot.database.connection import Database


class LoginLockManager:
    """Manages login attempt tracking and account lockout."""

    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_MINUTES = 15

    def __init__(
        self,
        db: Database,
        max_failed_attempts: int = MAX_FAILED_ATTEMPTS,
        lockout_minutes: int = LOCKOUT_MINUTES,
    ) -> None:
        """Initialize login lock manager.

        Args:
            db: Database instance.
            max_failed_attempts: Maximum failed attempts before lockout.
            lockout_minutes: Lockout duration in minutes.
        """
        self.db = db
        self.max_failed_attempts = max_failed_attempts
        self.lockout_minutes = lockout_minutes

    async def record_failed_attempt(
        self,
        username: str,
        ip_address: str | None = None,
    ) -> int:
        """Record a failed login attempt.

        Args:
            username: Username that failed to login.
            ip_address: Client IP address.

        Returns:
            Current failed attempt count.
        """
        attempt_repo = self.db.get_login_attempt_repository()
        await attempt_repo.record_failed_attempt(username, ip_address)

        count = await attempt_repo.get_failed_attempt_count(username, self.lockout_minutes)
        logger.warning(
            f"Failed login attempt for {username}: "
            f"{count}/{self.max_failed_attempts} attempts"
        )
        return count

    async def record_success(self, username: str, ip_address: str | None = None) -> None:
        """Record a successful login and clear failed attempts.

        Args:
            username: Username that logged in successfully.
            ip_address: Client IP address.
        """
        attempt_repo = self.db.get_login_attempt_repository()
        await attempt_repo.record_success_attempt(username, ip_address)
        await attempt_repo.clear_attempts(username)
        logger.info(f"Successful login for {username}, cleared failed attempts")

    async def check_lockout(self, username: str) -> None:
        """Check if account is locked out.

        Args:
            username: Username to check.

        Raises:
            LoginLockedError: If account is locked out.
        """
        attempt_repo = self.db.get_login_attempt_repository()
        count = await attempt_repo.get_failed_attempt_count(username, self.lockout_minutes)

        if count >= self.max_failed_attempts:
            logger.warning(f"Account locked out for {username}")
            raise LoginLockedError(
                f"Too many failed login attempts. "
                f"Account locked for {self.lockout_minutes} minutes."
            )
