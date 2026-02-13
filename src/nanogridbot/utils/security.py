"""Security utilities for mount validation and path safety."""

from pathlib import Path
from typing import Any


class MountSecurityError(Exception):
    """Raised when mount validation fails."""

    pass


async def validate_mounts(
    mounts: list[dict[str, Any]],
    is_main: bool = False,
    allowlist: list[Path] | None = None,
) -> list[tuple[str, str, str]]:
    """Validate and filter mount configurations.

    Args:
        mounts: List of mount dictionaries with keys:
            - host_path: str
            - container_path: str
            - mode: str ("ro" or "rw")
        is_main: Whether this is the main group (more restrictive)
        allowlist: Additional allowed paths (defaults to project root)

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
        mode = mount.get("mode", "ro")

        # Validate host path exists
        if not host_path.exists():
            logger.warning(f"Mount path does not exist: {host_path}")
            continue

        # Resolve to absolute path
        host_path = host_path.resolve()

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

        validated.append((str(host_path), container_path, mode))

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
