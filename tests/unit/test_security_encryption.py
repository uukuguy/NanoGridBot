"""Unit tests for security encryption module."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from nanogridbot.security.cipher import (
    generate_key,
    get_fernet,
    encrypt,
    decrypt,
    Cipher,
)
from nanogridbot.security.encryption import (
    EncryptionService,
    SENSITIVE_KEYS,
)
from nanogridbot.security.key_manager import KeyManager


class TestGenerateKey:
    """Test generate_key function."""

    def test_generate_key_returns_tuple(self):
        """Test that generate_key returns a tuple."""
        key, salt = generate_key("password123")
        assert isinstance(key, bytes)
        assert isinstance(salt, bytes)

    def test_generate_key_salt_length(self):
        """Test that salt is 16 bytes."""
        _, salt = generate_key("password123")
        assert len(salt) == 16

    def test_generate_key_with_custom_salt(self):
        """Test generating key with custom salt."""
        custom_salt = b"1234567890123456"
        key1, _ = generate_key("password123", salt=custom_salt)
        key2, _ = generate_key("password123", salt=custom_salt)
        # Same password + same salt = same key
        assert key1 == key2

    def test_generate_key_different_salts(self):
        """Test that different salts produce different keys."""
        key1, salt1 = generate_key("password123")
        key2, salt2 = generate_key("password123")
        # Different salts should produce different keys
        assert salt1 != salt2
        assert key1 != key2


class TestGetFernet:
    """Test get_fernet function."""

    def test_get_fernet_with_32_byte_key(self):
        """Test getting Fernet with 32-byte key."""
        key = b"0" * 32
        fernet = get_fernet(key)
        assert fernet is not None

    def test_get_fernet_with_different_key_length(self):
        """Test getting Fernet with non-32-byte key uses urlsafe_b64encode."""
        # Test with a key that's not exactly 32 bytes - should still work
        # due to the urlsafe_b64encode in get_fernet
        key, _ = generate_key("password")
        fernet = get_fernet(key)
        assert fernet is not None


class TestEncryptDecrypt:
    """Test encrypt and decrypt functions."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypt/decrypt roundtrip works."""
        key, _ = generate_key("password123")
        original = "Hello, World!"
        encrypted = encrypt(original, key)
        decrypted = decrypt(encrypted, key)
        assert decrypted == original

    def test_encrypt_produces_different_output(self):
        """Test that encrypting same data produces different output (due to salt)."""
        key1, _ = generate_key("password123")
        key2, _ = generate_key("password123")
        original = "Hello, World!"
        encrypted1 = encrypt(original, key1)
        encrypted2 = encrypt(original, key2)
        assert encrypted1 != encrypted2

    def test_encrypt_unicode(self):
        """Test encrypting unicode text."""
        key, _ = generate_key("password123")
        original = "你好世界！🚀"
        encrypted = encrypt(original, key)
        decrypted = decrypt(encrypted, key)
        assert decrypted == original

    def test_decrypt_invalid_data(self):
        """Test decrypting invalid data raises error."""
        key, _ = generate_key("password123")
        with pytest.raises(Exception):
            decrypt("invalid_data", key)


class TestCipher:
    """Test Cipher class."""

    def test_cipher_encrypt_decrypt(self):
        """Test Cipher encrypt/decrypt."""
        key, _ = generate_key("password123")
        cipher = Cipher(key)
        original = "Secret message"
        encrypted = cipher.encrypt(original)
        decrypted = cipher.decrypt(encrypted)
        assert decrypted == original

    def test_cipher_with_empty_string(self):
        """Test Cipher with empty string."""
        key, _ = generate_key("password123")
        cipher = Cipher(key)
        encrypted = cipher.encrypt("")
        decrypted = cipher.decrypt(encrypted)
        assert decrypted == ""


class TestEncryptionService:
    """Test EncryptionService class."""

    @pytest.fixture
    def mock_key_manager(self):
        """Create mock key manager."""
        km = MagicMock(spec=KeyManager)
        return km

    def test_encrypt_config_sensitive_keys(self, mock_key_manager):
        """Test encrypting config with sensitive keys."""
        mock_key_manager.get_user_key.return_value = b"0" * 32
        service = EncryptionService(mock_key_manager)
        config = {
            "anthropic_api_key": "sk-xxx",
            "telegram_bot_token": "12345:abcde",
            "database_url": "sqlite:///data.db",  # Not sensitive
        }
        encrypted = service.encrypt_config(config, user_id=1)
        assert encrypted["anthropic_api_key"] != "sk-xxx"
        assert encrypted["telegram_bot_token"] != "12345:abcde"
        assert encrypted["database_url"] == "sqlite:///data.db"

    def test_decrypt_config_sensitive_keys(self, mock_key_manager):
        """Test decrypting config with sensitive keys."""
        # Use the same key for both encryption and decryption
        key, _ = generate_key("password")
        mock_key_manager.get_user_key.return_value = key

        service = EncryptionService(mock_key_manager)
        cipher = Cipher(key)

        # First encrypt the config
        original_config = {
            "anthropic_api_key": "sk-xxx",
            "database_url": "sqlite:///data.db",
        }
        encrypted_config = service.encrypt_config(original_config, user_id=1)

        # Then decrypt it
        decrypted = service.decrypt_config(encrypted_config, user_id=1)
        assert decrypted["anthropic_api_key"] == "sk-xxx"
        assert decrypted["database_url"] == "sqlite:///data.db"

    def test_encrypt_config_no_key(self, mock_key_manager):
        """Test encrypting config when no key available."""
        mock_key_manager.get_user_key.return_value = None
        service = EncryptionService(mock_key_manager)
        config = {"anthropic_api_key": "sk-xxx"}
        result = service.encrypt_config(config, user_id=1)
        # Should return original config when no key
        assert result["anthropic_api_key"] == "sk-xxx"

    def test_encrypt_config_empty_value(self, mock_key_manager):
        """Test encrypting config with empty sensitive value."""
        mock_key_manager.get_user_key.return_value = b"0" * 32
        service = EncryptionService(mock_key_manager)
        config = {"anthropic_api_key": "", "telegram_bot_token": None}
        encrypted = service.encrypt_config(config, user_id=1)
        # Empty values should not be encrypted
        assert encrypted["anthropic_api_key"] == ""
        assert encrypted["telegram_bot_token"] is None

    def test_decrypt_config_invalid_value(self, mock_key_manager):
        """Test decrypting config with invalid encrypted value."""
        mock_key_manager.get_user_key.return_value = b"0" * 32
        service = EncryptionService(mock_key_manager)
        config = {"anthropic_api_key": "invalid_encrypted"}
        decrypted = service.decrypt_config(config, user_id=1)
        # Should return original value when decryption fails
        assert decrypted["anthropic_api_key"] == "invalid_encrypted"

    def test_get_cipher_caching(self, mock_key_manager):
        """Test that cipher is cached."""
        mock_key_manager.get_user_key.return_value = b"0" * 32
        service = EncryptionService(mock_key_manager)
        cipher1 = service.get_cipher(user_id=1)
        cipher2 = service.get_cipher(user_id=1)
        assert cipher1 is cipher2

    def test_get_cipher_different_users(self, mock_key_manager):
        """Test getting cipher for different users."""
        mock_key_manager.get_user_key.return_value = b"0" * 32
        service = EncryptionService(mock_key_manager)
        cipher1 = service.get_cipher(user_id=1)
        cipher2 = service.get_cipher(user_id=2)
        # Different users should get different ciphers (cached separately)
        assert cipher1 is not cipher2


class TestSensitiveKeys:
    """Test SENSITIVE_KEYS constant."""

    def test_sensitive_keys_contains_expected(self):
        """Test that SENSITIVE_KEYS contains expected keys."""
        assert "anthropic_api_key" in SENSITIVE_KEYS
        assert "telegram_bot_token" in SENSITIVE_KEYS
        assert "slack_bot_token" in SENSITIVE_KEYS
        assert "discord_bot_token" in SENSITIVE_KEYS

    def test_sensitive_keys_all_strings(self):
        """Test that all SENSITIVE_KEYS are strings."""
        for key in SENSITIVE_KEYS:
            assert isinstance(key, str)
