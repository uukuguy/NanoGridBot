"""Encryption service for sensitive configuration data."""

import json
from pathlib import Path
from typing import Any

from loguru import logger

from nanogridbot.security.cipher import Cipher, encrypt, decrypt
from nanogridbot.security.key_manager import KeyManager


# Default sensitive keys that should be encrypted
SENSITIVE_KEYS = [
    "anthropic_api_key",
    "telegram_bot_token",
    "slack_bot_token",
    "discord_bot_token",
    "feishu_app_secret",
    "wecom_secret",
    "dingtalk_secret",
    "whatsapp_phone_id",
    "whatsapp_business_account_id",
    "qq_password",
]


class EncryptionService:
    """Service for encrypting and decrypting sensitive configuration."""

    def __init__(self, key_manager: KeyManager) -> None:
        """Initialize encryption service.

        Args:
            key_manager: Key manager instance.
        """
        self.key_manager = key_manager
        self._cipher_cache: dict[int, Cipher] = {}

    def get_cipher(self, user_id: int, password: str | None = None) -> Cipher | None:
        """Get cipher for a user.

        Args:
            user_id: User ID.
            password: Optional password to derive key.

        Returns:
            Cipher instance or None if no key available.
        """
        if user_id in self._cipher_cache:
            return self._cipher_cache[user_id]

        key = self.key_manager.get_user_key(user_id, password)
        if key:
            cipher = Cipher(key)
            self._cipher_cache[user_id] = cipher
            return cipher

        return None

    def encrypt_config(
        self,
        config: dict[str, Any],
        user_id: int,
        password: str | None = None,
    ) -> dict[str, Any]:
        """Encrypt sensitive values in configuration.

        Args:
            config: Configuration dictionary.
            user_id: User ID.
            password: Optional password to derive key.

        Returns:
            Configuration with sensitive values encrypted.
        """
        cipher = self.get_cipher(user_id, password)
        if not cipher:
            logger.warning(f"No encryption key for user {user_id}, returning config as-is")
            return config

        encrypted = config.copy()
        for key in SENSITIVE_KEYS:
            if key in encrypted and encrypted[key]:
                encrypted[key] = cipher.encrypt(str(encrypted[key]))
                logger.debug(f"Encrypted config key: {key}")

        return encrypted

    def decrypt_config(
        self,
        config: dict[str, Any],
        user_id: int,
        password: str | None = None,
    ) -> dict[str, Any]:
        """Decrypt sensitive values in configuration.

        Args:
            config: Configuration dictionary with encrypted values.
            user_id: User ID.
            password: Optional password to derive key.

        Returns:
            Configuration with sensitive values decrypted.
        """
        cipher = self.get_cipher(user_id, password)
        if not cipher:
            logger.warning(f"No encryption key for user {user_id}, returning config as-is")
            return config

        decrypted = config.copy()
        for key in SENSITIVE_KEYS:
            if key in decrypted and decrypted[key]:
                try:
                    decrypted[key] = cipher.decrypt(str(decrypted[key]))
                    logger.debug(f"Decrypted config key: {key}")
                except Exception as e:
                    logger.warning(f"Failed to decrypt {key}: {e}")

        return decrypted


# Global encryption service instance
_encryption_service: EncryptionService | None = None
_key_manager: KeyManager | None = None


def get_key_manager(key_dir: Path | None = None) -> KeyManager:
    """Get or create key manager.

    Args:
        key_dir: Directory for keys. If None, uses default.

    Returns:
        KeyManager instance.
    """
    global _key_manager

    if _key_manager is None:
        if key_dir is None:
            from nanogridbot.config import get_config

            config = get_config()
            key_dir = config.store_dir / "keys"

        _key_manager = KeyManager(key_dir)

    return _key_manager


def get_encryption_service() -> EncryptionService | None:
    """Get encryption service.

    Returns:
        EncryptionService instance or None if not initialized.
    """
    global _encryption_service

    if _encryption_service is None:
        try:
            key_manager = get_key_manager()
            _encryption_service = EncryptionService(key_manager)
        except Exception as e:
            logger.warning(f"Failed to initialize encryption service: {e}")
            return None

    return _encryption_service


def encrypt_value(value: str, user_id: int, password: str | None = None) -> str | None:
    """Encrypt a single value.

    Args:
        value: Value to encrypt.
        user_id: User ID.
        password: Optional password.

    Returns:
        Encrypted value or None if encryption fails.
    """
    service = get_encryption_service()
    if not service:
        return None

    cipher = service.get_cipher(user_id, password)
    if cipher:
        return cipher.encrypt(value)

    return None


def decrypt_value(encrypted_value: str, user_id: int, password: str | None = None) -> str | None:
    """Decrypt a single value.

    Args:
        encrypted_value: Encrypted value.
        user_id: User ID.
        password: Optional password.

    Returns:
        Decrypted value or None if decryption fails.
    """
    service = get_encryption_service()
    if not service:
        return None

    cipher = service.get_cipher(user_id, password)
    if cipher:
        try:
            return cipher.decrypt(encrypted_value)
        except Exception:
            return None

    return None
