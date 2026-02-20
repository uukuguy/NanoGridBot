"""Unit tests for authentication module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from nanogridbot.auth.password import PasswordManager
from nanogridbot.auth.session import SessionManager
from nanogridbot.auth.login_lock import LoginLockManager
from nanogridbot.auth.invite import InviteCodeManager
from nanogridbot.auth.exceptions import (
    InvalidCredentialsError,
    LoginLockedError,
    InviteCodeError,
)


class TestPasswordManager:
    """Test PasswordManager class."""

    def test_hash_password_returns_string(self):
        """Test that hash_password returns a non-empty string."""
        hashed = PasswordManager.hash_password("testpassword123")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_password_different_hashes(self):
        """Test that same password produces different hashes (salt)."""
        hash1 = PasswordManager.hash_password("samepassword")
        hash2 = PasswordManager.hash_password("samepassword")
        assert hash1 != hash2  # Different salts

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "correctpassword"
        hashed = PasswordManager.hash_password(password)
        assert PasswordManager.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        hashed = PasswordManager.hash_password("correctpassword")
        assert PasswordManager.verify_password("wrongpassword", hashed) is False

    def test_verify_password_invalid_hash(self):
        """Test password verification with invalid hash."""
        assert PasswordManager.verify_password("anypassword", "invalidhash") is False

    def test_verify_password_empty(self):
        """Test password verification with empty password."""
        hashed = PasswordManager.hash_password("password")
        assert PasswordManager.verify_password("", hashed) is False


class TestSessionManager:
    """Test SessionManager class."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = MagicMock()
        session_repo = MagicMock()
        db.get_session_repository.return_value = session_repo
        return db

    @pytest.mark.asyncio
    async def test_generate_token(self, mock_db):
        """Test token generation."""
        manager = SessionManager(mock_db)
        token = manager.generate_token()
        assert isinstance(token, str)
        assert len(token) > 20  # 32 bytes base64 encoded

    @pytest.mark.asyncio
    async def test_create_session(self, mock_db):
        """Test session creation."""
        session_repo = mock_db.get_session_repository()
        session_repo.create_session = AsyncMock()

        manager = SessionManager(mock_db)
        token = await manager.create_session(user_id=1, ip_address="127.0.0.1")

        assert isinstance(token, str)
        session_repo.create_session.assert_called_once()
        call_kwargs = session_repo.create_session.call_args.kwargs
        assert call_kwargs["user_id"] == 1
        assert call_kwargs["ip_address"] == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, mock_db):
        """Test getting non-existent session."""
        session_repo = mock_db.get_session_repository()
        session_repo.get_session_by_token = AsyncMock(return_value=None)

        manager = SessionManager(mock_db)
        result = await manager.get_session("invalid_token")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_expired(self, mock_db):
        """Test getting expired session."""
        from datetime import datetime, timedelta

        session_repo = mock_db.get_session_repository()
        session_repo.get_session_by_token = AsyncMock(
            return_value=MagicMock(
                id=1,
                user_id=1,
                session_token="token",
                expires_at=(datetime.utcnow() - timedelta(days=1)).isoformat(),
                created_at=datetime.utcnow().isoformat(),
                last_activity=datetime.utcnow().isoformat(),
                ip_address=None,
                user_agent=None,
            )
        )
        session_repo.delete_session_by_token = AsyncMock()

        manager = SessionManager(mock_db)
        result = await manager.get_session("expired_token")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_session(self, mock_db):
        """Test session deletion."""
        session_repo = mock_db.get_session_repository()
        session_repo.delete_session_by_token = AsyncMock()

        manager = SessionManager(mock_db)
        await manager.delete_session("test_token")

        session_repo.delete_session_by_token.assert_called_once_with("test_token")

    @pytest.mark.asyncio
    async def test_delete_user_sessions(self, mock_db):
        """Test deleting all user sessions."""
        session_repo = mock_db.get_session_repository()
        session_repo.delete_user_sessions = AsyncMock()

        manager = SessionManager(mock_db)
        await manager.delete_user_sessions(user_id=1)

        session_repo.delete_user_sessions.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, mock_db):
        """Test expired session cleanup."""
        session_repo = mock_db.get_session_repository()
        session_repo.cleanup_expired_sessions = AsyncMock(return_value=5)

        manager = SessionManager(mock_db)
        count = await manager.cleanup_expired()

        assert count == 5


class TestLoginLockManager:
    """Test LoginLockManager class."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = MagicMock()
        login_repo = MagicMock()
        db.get_login_attempt_repository.return_value = login_repo
        return db

    @pytest.mark.asyncio
    async def test_record_failed_attempt(self, mock_db):
        """Test recording failed login attempt."""
        login_repo = mock_db.get_login_attempt_repository()
        login_repo.record_failed_attempt = AsyncMock()
        login_repo.get_failed_attempt_count = AsyncMock(return_value=1)

        manager = LoginLockManager(mock_db, max_failed_attempts=5, lockout_minutes=15)
        count = await manager.record_failed_attempt(username="testuser", ip_address="192.168.1.1")

        assert count == 1
        login_repo.record_failed_attempt.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_success(self, mock_db):
        """Test recording successful login."""
        login_repo = mock_db.get_login_attempt_repository()
        login_repo.record_success_attempt = AsyncMock()
        login_repo.clear_attempts = AsyncMock()

        manager = LoginLockManager(mock_db)
        await manager.record_success(username="testuser")

        login_repo.clear_attempts.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_lockout_not_locked(self, mock_db):
        """Test checking when not locked."""
        login_repo = mock_db.get_login_attempt_repository()
        login_repo.get_failed_attempt_count = AsyncMock(return_value=2)

        manager = LoginLockManager(mock_db, max_failed_attempts=5, lockout_minutes=15)
        # Should not raise exception
        await manager.check_lockout(username="testuser")

    @pytest.mark.asyncio
    async def test_check_lockout_exceeds_limit(self, mock_db):
        """Test checking when locked."""
        login_repo = mock_db.get_login_attempt_repository()
        login_repo.get_failed_attempt_count = AsyncMock(return_value=6)

        manager = LoginLockManager(mock_db, max_failed_attempts=5, lockout_minutes=15)
        with pytest.raises(LoginLockedError):
            await manager.check_lockout(username="testuser")


class TestInviteCodeManager:
    """Test InviteCodeManager class."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = MagicMock()
        invite_repo = MagicMock()
        db.get_invite_code_repository.return_value = invite_repo
        return db

    @pytest.mark.asyncio
    async def test_generate_code(self, mock_db):
        """Test code generation."""
        manager = InviteCodeManager(mock_db)
        code = manager.generate_code()

        assert isinstance(code, str)
        assert len(code) == 16

    @pytest.mark.asyncio
    async def test_create_code(self, mock_db):
        """Test creating invite code."""
        invite_repo = mock_db.get_invite_code_repository()
        invite_repo.create_invite_code = AsyncMock(return_value=1)

        manager = InviteCodeManager(mock_db)
        result = await manager.create_code(created_by=1)

        assert result["code"] is not None
        assert result["created_by"] == 1

    @pytest.mark.asyncio
    async def test_validate_valid_code(self, mock_db):
        """Test validating valid invite code."""
        from datetime import datetime, timedelta

        invite_repo = mock_db.get_invite_code_repository()
        invite_repo.get_invite_code = AsyncMock(
            return_value=MagicMock(
                code="validcode",
                max_uses=5,
                used_by=None,
                expires_at=(datetime.utcnow() + timedelta(days=1)).isoformat(),
            )
        )

        manager = InviteCodeManager(mock_db)
        result = await manager.validate_code("validcode")

        assert result["code"] == "validcode"

    @pytest.mark.asyncio
    async def test_validate_invalid_code(self, mock_db):
        """Test validating invalid invite code."""
        invite_repo = mock_db.get_invite_code_repository()
        invite_repo.get_invite_code = AsyncMock(return_value=None)

        manager = InviteCodeManager(mock_db)
        with pytest.raises(InviteCodeError):
            await manager.validate_code("invalidcode")

    @pytest.mark.asyncio
    async def test_validate_expired_code(self, mock_db):
        """Test validating expired invite code."""
        from datetime import datetime, timedelta

        invite_repo = mock_db.get_invite_code_repository()
        invite_repo.get_invite_code = AsyncMock(
            return_value=MagicMock(
                code="expiredcode",
                max_uses=1,
                used_by=None,
                expires_at=(datetime.utcnow() - timedelta(days=1)).isoformat(),
            )
        )

        manager = InviteCodeManager(mock_db)
        with pytest.raises(InviteCodeError):
            await manager.validate_code("expiredcode")

    @pytest.mark.asyncio
    async def test_use_code(self, mock_db):
        """Test using invite code."""
        from datetime import datetime, timedelta

        invite_repo = mock_db.get_invite_code_repository()
        invite_repo.get_invite_code = AsyncMock(
            return_value=MagicMock(
                code="validcode",
                max_uses=5,
                used_by=None,
                expires_at=(datetime.utcnow() + timedelta(days=1)).isoformat(),
            )
        )
        invite_repo.use_invite_code = AsyncMock(return_value=True)

        manager = InviteCodeManager(mock_db)
        result = await manager.use_code("validcode", used_by=2)

        assert result is True

    @pytest.mark.asyncio
    async def test_list_codes(self, mock_db):
        """Test listing invite codes."""
        from datetime import datetime

        invite_repo = mock_db.get_invite_code_repository()
        invite_repo.list_invite_codes = AsyncMock(
            return_value=[
                MagicMock(
                    id=1, code="code1", created_by=1, used_by=None,
                    used_at=None, expires_at=datetime.utcnow().isoformat(),
                    max_uses=5, created_at=datetime.utcnow().isoformat(),
                )
            ]
        )

        manager = InviteCodeManager(mock_db)
        codes = await manager.list_codes(created_by=1)

        assert len(codes) == 1
