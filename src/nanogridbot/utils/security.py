"""Security utilities for mount validation and path safety."""

import os
from pathlib import Path
from typing import Any


class MountSecurityError(Exception):
    """Raised when mount validation fails."""

    pass


# Sensitive directories that should be read-only even for main group
READONLY_DIRECTORIES = {
    ".ssh",
    ".gnupg",
    ".aws",
    "credentials",
    "secrets",
    ".env",
    ".env.local",
    "keys",
    "certificates",
}

# Directories that require read-write access
RW_REQUIRED_DIRECTORIES = {
    "ipc",
    "sessions",
    ".claude",
}


async def validate_mounts(
    mounts: list[dict[str, Any]],
    is_main: bool = False,
    allowlist: list[Path] | None = None,
    enforce_readonly: bool = True,
) -> list[tuple[str, str, str]]:
    """Validate and filter mount configurations.

    Args:
        mounts: List of mount dictionaries with keys:
            - host_path: str
            - container_path: str
            - mode: str ("ro" or "rw")
        is_main: Whether this is the main group (more restrictive)
        allowlist: Additional allowed paths (defaults to project root)
        enforce_readonly: Whether to enforce read-only for non-main groups

    Returns:
        List of validated (host_path, container_path, mode) tuples

    Raises:
        MountSecurityError: If any mount is not allowed
    """
    from loguru import logger

    validated = []
    allowlist = allowlist or []

    for mount in mounts:
        host_path = Path(mount.get("host_path", ""))
        container_path = mount.get("container_path", "")
        requested_mode = mount.get("mode", "ro")

        # Validate host path exists
        if not host_path.exists():
            logger.warning(f"Mount path does not exist: {host_path}")
            continue

        # Resolve to absolute path
        host_path = host_path.resolve()

        # Check for symlinks (security enhancement)
        if check_symlink(host_path):
            logger.info(f"Detected symlink in mount path: {host_path}")
            validate_no_symlink_escape(host_path)

        # Check against allowlist
        if not _is_path_allowed(host_path, allowlist):
            raise MountSecurityError(
                f"Mount path not in allowlist: {host_path}. "
                f"Only paths under project root or in allowlist are allowed."
            )

        # For non-main groups, enforce stricter rules
        if not is_main:
            # Only allow mounts within groups directory
            if not _is_path_under_directory(host_path, "groups"):
                raise MountSecurityError(
                    f"Non-main groups can only mount paths under groups/ directory: {host_path}"
                )

            # Enforce read-only for non-main groups (unless explicitly rw required)
            if enforce_readonly:
                if not check_rw_required_directory(host_path):
                    # Force read-only for non-main groups
                    if requested_mode == "rw":
                        logger.info(
                            f"Forcing read-only mount for non-main group: {host_path}"
                        )
                        requested_mode = "ro"

        # Check for sensitive directories that should always be read-only
        if check_readonly_directory(host_path):
            logger.info(f"Detected sensitive directory, enforcing read-only: {host_path}")
            requested_mode = "ro"

        validated.append((str(host_path), container_path, requested_mode))

    return validated


def _is_path_allowed(path: Path, allowlist: list[Path]) -> bool:
    """Check if path is in allowlist or under project root.

    Args:
        path: Path to check
        allowlist: Additional allowed paths

    Returns:
        True if allowed, False otherwise
    """
    from nanogridbot.config import get_config

    config = get_config()
    project_root = config.base_dir.resolve()

    # Allow if under project root
    try:
        path.relative_to(project_root)
        return True
    except ValueError:
        pass

    # Check against allowlist
    for allowed in allowlist:
        try:
            path.relative_to(allowed.resolve())
            return True
        except ValueError:
            continue

    return False


def _is_path_under_directory(path: Path, directory_name: str) -> bool:
    """Check if path is under a directory with given name.

    Args:
        path: Path to check
        directory_name: Name of directory to check against

    Returns:
        True if path is under directory, False otherwise
    """
    from nanogridbot.config import get_config

    config = get_config()
    target_dir = (config.base_dir / directory_name).resolve()

    try:
        path.relative_to(target_dir)
        return True
    except ValueError:
        return False


def validate_container_path(container_path: str) -> bool:
    """Validate container path is safe (no escape attempts).

    Args:
        container_path: Path inside container

    Returns:
        True if safe, False otherwise
    """
    # No absolute paths
    if container_path.startswith("/"):
        # Allow known safe absolute paths
        safe_paths = ["/workspace", "/home", "/tmp", "/app"]
        if not any(container_path.startswith(safe) for safe in safe_paths):
            return False

    # No parent directory references
    if ".." in container_path:
        return False

    # No special device paths
    if container_path.startswith("/dev") or container_path.startswith("/proc"):
        return False

    return True


def check_symlink(path: Path) -> bool:
    """Check if path or any parent is a symbolic link.

    Args:
        path: Path to check

    Returns:
        True if path contains symlink, False otherwise
    """
    # Check the path itself before resolving
    if path.is_symlink():
        return True

    # Check parent directories (before resolving)
    current = path
    while current != current.parent:
        if current.is_symlink():
            return True
        current = current.parent

    # Also check after resolving to catch any symlinks in the chain
    try:
        resolved = path.resolve()
        if resolved != path:
            current = resolved
            while current != current.parent:
                if current.is_symlink():
                    return True
                current = current.parent
    except (OSError, RuntimeError):
        pass

    return False


def validate_no_symlink_escape(host_path: Path) -> bool:
    """Validate that symlinks don't escape allowed directories.

    Args:
        host_path: Host path to validate

    Returns:
        True if safe, False if symlink escapes

    Raises:
        MountSecurityError: If symlink escapes allowed directories
    """
    from nanogridbot.config import get_config

    config = get_config()
    project_root = config.base_dir.resolve()
    data_root = config.data_dir.resolve()
    groups_root = config.groups_dir.resolve()

    # Resolve the actual path (following symlinks)
    resolved = host_path.resolve()

    # Check if resolved path is within allowed roots
    allowed_roots = [project_root, data_root, groups_root, config.store_dir.resolve()]

    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue

    raise MountSecurityError(
        f"Symlink escapes allowed directories: {host_path} -> {resolved}"
    )


def check_readonly_directory(path: Path) -> bool:
    """Check if path is under a sensitive directory that should be read-only.

    Args:
        path: Path to check

    Returns:
        True if path should be read-only
    """
    parts = path.parts
    for part in parts:
        if part in READONLY_DIRECTORIES:
            return True
    return False


def check_rw_required_directory(path: Path) -> bool:
    """Check if path requires read-write access.

    Args:
        path: Path to check

    Returns:
        True if path requires read-write access
    """
    parts = path.parts
    for part in parts:
        if part in RW_REQUIRED_DIRECTORIES:
            return True
    return False


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    import re

    # Remove any path components
    filename = Path(filename).name

    # Remove potentially dangerous characters
    filename = re.sub(r"[^\w\s\-.]", "", filename)

    # Limit length
    if len(filename) > 255:
        filename = filename[:255]

    return filename
