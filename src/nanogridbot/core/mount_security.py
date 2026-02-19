"""Mount security validation for container volumes."""

import shutil
from pathlib import Path
from typing import Any

from nanogridbot.utils.security import MountSecurityError, validate_mounts


async def validate_group_mounts(
    group_folder: str,
    container_config: dict[str, Any] | None = None,
    is_main: bool = False,
    user_id: int | None = None,
) -> list[tuple[str, str, str]]:
    """Validate mounts for a group container.

    Args:
        group_folder: Group folder name
        container_config: Optional container configuration
        is_main: Whether this is the main group
        user_id: Optional user ID for user-specific mounts

    Returns:
        List of validated mount tuples

    Raises:
        MountSecurityError: If validation fails
    """
    from nanogridbot.config import get_config

    config = get_config()
    mounts: list[dict[str, Any]] = []

    # User-specific base directory
    user_base = config.data_dir / "users" / str(user_id) if user_id else None

    # Mount user's directory if user_id is provided
    if user_base:
        user_dir = user_base / "groups"
        user_dir.mkdir(parents=True, exist_ok=True)

        # Mount user's groups directory
        group_path = user_dir / group_folder
        if group_path.exists():
            mounts.append(
                {
                    "host_path": str(group_path),
                    "container_path": "/workspace/group",
                    "mode": "rw",
                }
            )

        # Mount user memory directory
        memory_path = user_base / "memory"
        memory_path.mkdir(parents=True, exist_ok=True)
        mounts.append(
            {
                "host_path": str(memory_path),
                "container_path": "/workspace/memory",
                "mode": "rw",
            }
        )

        # Mount user's archives directory
        archives_path = user_base / "archives"
        archives_path.mkdir(parents=True, exist_ok=True)
        mounts.append(
            {
                "host_path": str(archives_path),
                "container_path": "/workspace/archives",
                "mode": "rw",
            }
        )

        # Mount user config
        user_config_path = user_base / "config.json"
        if user_config_path.exists():
            mounts.append(
                {
                    "host_path": str(user_config_path),
                    "container_path": "/workspace/user_config.json",
                    "mode": "ro",
                }
            )
    else:
        # Fall back to shared groups directory
        group_path = config.groups_dir / group_folder
        if group_path.exists():
            mounts.append(
                {
                    "host_path": str(group_path),
                    "container_path": "/workspace/group",
                    "mode": "rw",
                }
            )

    # Mount global directory (read-only) - always available
    global_path = config.groups_dir / "global"
    if global_path.exists():
        mounts.append(
            {
                "host_path": str(global_path),
                "container_path": "/workspace/global",
                "mode": "ro",
            }
        )

    # Mount sessions directory (user-specific or group-specific)
    if user_base:
        session_path = user_base / "sessions" / group_folder / ".claude"
    else:
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
    if user_base:
        ipc_path = user_base / "ipc" / group_folder
    else:
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

    # Add detailed mount configuration logging
    from loguru import logger

    logger.debug(
        "Container mount configuration: group={group}, is_main={is_main}, user_id={user_id}, mounts={mounts}",
        group=group_folder,
        is_main=is_main,
        user_id=user_id,
        mounts=[
            {"host": m["host_path"], "container": m["container_path"], "mode": m["mode"]}
            for m in mounts
        ],
    )

    # Sync skills for this group
    sync_group_skills(group_folder, user_id)

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


def create_group_env_file(
    group_folder: str,
    allowed_vars: list[str] | None = None,
) -> tuple[str, str, str] | None:
    """Create a filtered env file for a group's container.

    Args:
        group_folder: Group folder name
        allowed_vars: List of env vars to expose (default: ANTHROPIC_*)

    Returns:
        Mount tuple (host_path, container_path, mode) or None if no env vars
    """
    from nanogridbot.config import get_config

    config = get_config()
    allowed = allowed_vars or ["ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_API_URL"]

    env_file = config.store_dir / "env" / f"{group_folder}.env"
    env_file.parent.mkdir(parents=True, exist_ok=True)

    env_content: list[str] = []
    env_path = config.base_dir / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                for var in allowed:
                    if line.startswith(f"{var}="):
                        env_content.append(line)
                        break

    if not env_content:
        return None

    env_file.write_text("\n".join(env_content) + "\n")
    return (str(env_file), "/workspace/env", "ro")


def sync_group_skills(group_folder: str, user_id: int | None = None) -> Path | None:
    """Sync skills from container/skills to group's .claude/skills.

    Args:
        group_folder: Group folder name
        user_id: Optional user ID for user-specific skills

    Returns:
        Path to synced skills directory or None if no skills exist
    """
    from nanogridbot.config import get_config

    config = get_config()

    # Source: container/skills/
    skills_src = config.base_dir / "container" / "skills"
    if not skills_src.exists():
        return None

    # Determine destination based on user_id
    if user_id:
        skills_dst = config.data_dir / "users" / str(user_id) / "sessions" / group_folder / ".claude" / "skills"
    else:
        skills_dst = config.data_dir / "sessions" / group_folder / ".claude" / "skills"
    skills_dst.mkdir(parents=True, exist_ok=True)

    # Sync each skill directory
    for skill_dir in skills_src.iterdir():
        if not skill_dir.is_dir():
            continue
        dst = skills_dst / skill_dir.name
        dst.mkdir(exist_ok=True)
        for file in skill_dir.iterdir():
            if file.is_file():
                shutil.copy2(file, dst / file.name)

    return skills_dst
