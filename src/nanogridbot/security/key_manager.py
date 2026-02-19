"""Key management for encryption."""

import base64
import json
from pathlib import Path
from typing import Any

from loguru import logger

from nanogridbot.security.cipher import generate_key


class KeyManager:
    """Manages encryption keys for user data."""

    def __init__(self, key_dir: Path) -> None:
        """Initialize key manager.

        Args:
            key_dir: Directory to store keys.
        """
        self.key_dir = key_dir
        self.key_dir.mkdir(parents=True, exist_ok=True)

    def get_user_key(self, user_id: int, password: str | None = None) -> bytes | None:
        """Get or create encryption key for a user.

        Args:
            user_id: User ID.
            password: Optional password to derive key. If None, uses master key.

        Returns:
            Encryption key or None if not available.
        """
        key_file = self.key_dir / f"user_{user_id}.key"

        if password:
            # Derive key from password
            # Check if salt exists
            salt_file = self.key_dir / f"user_{user_id}.salt"
            if salt_file.exists():
                salt = salt_file.read_bytes()
            else:
                # Generate new salt
                salt = None
                key, salt = generate_key(password, salt)
                salt_file.write_bytes(salt)
                # Store derived key
                key_file.write_bytes(key)
                return key

            key, _ = generate_key(password, salt)
            return key

        if key_file.exists():
            return key_file.read_bytes()

        return None

    def create_user_key(self, user_id: int, password: str) -> bytes:
        """Create a new encryption key for a user.

        Args:
            user_id: User ID.
            password: Password to derive key from.

        Returns:
            Created encryption key.
        """
        key, salt = generate_key(password)

        key_file = self.key_dir / f"user_{user_id}.key"
        salt_file = self.key_dir / f"user_{user_id}.salt"

        key_file.write_bytes(key)
        salt_file.write_bytes(salt)

        logger.info(f"Created encryption key for user {user_id}")
        return key

    def delete_user_key(self, user_id: int) -> None:
        """Delete encryption key for a user.

        Args:
            user_id: User ID.
        """
        key_file = self.key_dir / f"user_{user_id}.key"
        salt_file = self.key_dir / f"user_{user_id}.salt"

        if key_file.exists():
            key_file.unlink()
        if salt_file.exists():
            salt_file.unlink()

        logger.info(f"Deleted encryption key for user {user_id}")

    def get_master_key(self) -> bytes | None:
        """Get the master encryption key.

        Returns:
            Master key or None if not set up.
        """
        master_key_file = self.key_dir / "master.key"

        if master_key_file.exists():
            return master_key_file.read_bytes()

        return None

    def setup_master_key(self, password: str) -> bytes:
        """Set up master encryption key.

        Args:
            password: Password to derive master key from.

        Returns:
            Master encryption key.
        """
        key, salt = generate_key(password)

        master_key_file = self.key_dir / "master.key"
        salt_file = self.key_dir / "master.salt"

        master_key_file.write_bytes(key)
        salt_file.write_bytes(salt)

        logger.info("Master encryption key set up")
        return key
