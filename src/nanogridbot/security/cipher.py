"""Cryptography utilities for NanoGridBot security."""

import base64
import os
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def generate_key(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """Generate an encryption key from a password using PBKDF2.

    Args:
        password: Password to derive key from.
        salt: Salt for key derivation. If None, generates random salt.

    Returns:
        Tuple of (key, salt).
    """
    if salt is None:
        salt = os.urandom(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = kdf.derive(password.encode())
    return key, salt


def get_fernet(key: bytes) -> Fernet:
    """Get a Fernet instance from a key.

    Args:
        key: Encryption key (32 bytes).

    Returns:
        Fernet instance.
    """
    # Ensure key is 32 bytes for Fernet (it expects URL-safe base64 encoded 32-byte key)
    if len(key) != 32:
        # Re-derive to get proper format
        fernet_key = base64.urlsafe_b64encode(key)
        return Fernet(fernet_key)
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)


def encrypt(data: str, key: bytes) -> str:
    """Encrypt data using AES-256-GCM (via Fernet).

    Args:
        data: Plain text data to encrypt.
        key: Encryption key.

    Returns:
        Encrypted data as base64 string.
    """
    fernet = get_fernet(key)
    encrypted = fernet.encrypt(data.encode())
    return base64.b64encode(encrypted).decode()


def decrypt(encrypted_data: str, key: bytes) -> str:
    """Decrypt data using AES-256-GCM (via Fernet).

    Args:
        encrypted_data: Base64 encoded encrypted data.
        key: Encryption key.

    Returns:
        Decrypted plain text.
    """
    fernet = get_fernet(key)
    data = base64.b64decode(encrypted_data.encode())
    decrypted = fernet.decrypt(data)
    return decrypted.decode()


class Cipher:
    """Simple cipher wrapper for encrypt/decrypt operations."""

    def __init__(self, key: bytes) -> None:
        """Initialize cipher with key.

        Args:
            key: Encryption key.
        """
        self.key = key

    def encrypt(self, data: str) -> str:
        """Encrypt data.

        Args:
            data: Plain text to encrypt.

        Returns:
            Encrypted data.
        """
        return encrypt(data, self.key)

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data.

        Args:
            encrypted_data: Encrypted data to decrypt.

        Returns:
            Decrypted plain text.
        """
        return decrypt(encrypted_data, self.key)
