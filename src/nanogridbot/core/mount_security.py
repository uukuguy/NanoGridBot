"""Mount security validation for container volumes."""

from pathlib import Path
from typing import Any

from nanogridbot.utils.security import MountSecurityError, validate_mounts


async def validate_group_mounts(
    group_folder: str,
    container_config: dict[str, Any] | None = None,
    is_main: bool = False,
) -> list[tuple[str, str, str]]:
    """Validate mounts for a group container.

    Args:
        group_folder: Group folder name
        container_config: Optional container configuration
        is_main: Whether this is the main group

    Returns:
        List of validated mount tuples

    Raises:
        MountSecurityError: If validation fails
    """
    from nanogridbot.config import get_config

    config = get_config()
    mounts: list[dict[str, Any]] = []

    # Always mount group directory
    group_path = config.groups_dir / group_folder
    if group_path.exists():
        mounts.append(
            {
                "host_path": str(group_path),
                "container_path": "/workspace/group",
                "mode": "rw",
            }
        )

    # Mount global directory (read-only)
    global_path = config.groups_dir / "global"
    if global_path.exists():
        mounts.append(
            {
                "host_path": str(global_path),
                "container_path": "/workspace/global",
                "mode": "ro",
            }
        )

    # Mount sessions directory
    session_path = config.data_dir / "sessions" / group_folder / ".claude"
    session_path.mkdir(parents=True, exist_ok=True)
    mounts.append(
        {
            "host_path": str(session_path),
            "container_path": "/home/node/.claude",
            "mode": "rw",
        }
    )

    # Mount IPC directory
    ipc_path = config.data_dir / "ipc" / group_folder
    ipc_path.mkdir(parents=True, exist_ok=True)
    mounts.append(
        {
            "host_path": str(ipc_path),
            "container_path": "/workspace/ipc",
            "mode": "rw",
        }
    )

    # For main group, also mount project root
    if is_main:
        project_root = config.base_dir
        mounts.append(
            {
                "host_path": str(project_root),
                "container_path": "/workspace/project",
                "mode": "ro",
            }
        )

    # Add additional mounts from config
    if container_config and container_config.get("additional_mounts"):
        mounts.extend(container_config["additional_mounts"])

    # Validate all mounts
    return await validate_mounts(mounts, is_main=is_main)


def check_path_traversal(path: str) -> bool:
    """Check if path contains traversal attempts.

    Args:
        path: Path to check

    Returns:
        True if safe, False if suspicious
    """
    import re

    # Check for path traversal patterns
    if ".." in path:
        return False

    # Check for absolute path escapes
    if path.startswith("/workspace/../") or path.startswith("/home/../"):
        return False

    # Check for null bytes
    if "\x00" in path:
        return False

    # Check for unusual characters
    if re.search(r"[^\w\-./:]", path):
        return False

    return True


def get_allowed_mount_paths() -> list[Path]:
    """Get list of paths that are allowed for mounting.

    Returns:
        List of allowed paths
    """
    from nanogridbot.config import get_config

    config = get_config()

    allowed = [
        config.base_dir,  # Project root
        config.groups_dir,
        config.data_dir,
        config.store_dir,
    ]

    return allowed
