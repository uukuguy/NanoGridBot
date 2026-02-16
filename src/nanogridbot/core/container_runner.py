"""Docker container runner for executing Claude Agent."""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Literal

from nanogridbot.config import get_config
from nanogridbot.core.mount_security import validate_group_mounts
from nanogridbot.types import ContainerConfig, ContainerOutput
from nanogridbot.utils.formatting import format_messages_xml

# Output markers for parsing
OUTPUT_START_MARKER = "---NANOGRIDBOT_OUTPUT_START---"
OUTPUT_END_MARKER = "---NANOGRIDBOT_OUTPUT_END---"


async def run_container_agent(
    group_folder: str,
    prompt: str,
    session_id: str | None,
    chat_jid: str,
    is_main: bool = False,
    container_config: ContainerConfig | None = None,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> ContainerOutput:
    """Run Claude Agent in a Docker container.

    Args:
        group_folder: Group folder name
        prompt: Prompt to send to the agent
        session_id: Existing session ID if any
        chat_jid: Chat JID for context
        is_main: Whether this is the main group
        container_config: Optional container configuration
        timeout: Optional timeout in seconds
        env: Optional environment variables for container

    Returns:
        ContainerOutput with execution result
    """
    from loguru import logger

    config = get_config()

    # Merge environment variables from container_config and explicit env parameter
    merged_env: dict[str, str] = {}
    if container_config and container_config.env:
        merged_env.update(container_config.env)
    if env:
        merged_env.update(env)

    # Extract channel from chat_jid
    channel = chat_jid.split(":")[0] if ":" in chat_jid else "unknown"

    # Record container start for metrics
    metric_id = None
    start_time = time.time()
    try:
        from nanogridbot.database import metrics as metrics_db

        metric_id = await metrics_db.record_container_start(group_folder, channel)
    except Exception:
        # Metrics are optional, don't fail if they can't be recorded
        pass

    # Build mounts
    try:
        mounts = await validate_group_mounts(
            group_folder=group_folder,
            container_config=container_config.model_dump() if container_config else None,
            is_main=is_main,
        )
    except Exception as e:
        logger.error(f"Mount validation failed: {e}")
        # Record failure
        if metric_id:
            try:
                await metrics_db.record_container_end(metric_id, "error", error=str(e))
            except Exception:
                pass
        return ContainerOutput(status="error", error=str(e))

    # Prepare input data
    input_data = {
        "prompt": prompt,
        "sessionId": session_id,
        "groupFolder": group_folder,
        "chatJid": chat_jid,
        "isMain": is_main,
    }

    # Build docker command
    cmd = build_docker_command(
        mounts=mounts,
        input_data=input_data,
        timeout=timeout or config.container_timeout,
        env=merged_env,
    )

    logger.debug(f"Starting container for {group_folder}")

    try:
        result = await _execute_container(cmd, input_data)
        # Record container end for metrics
        duration = time.time() - start_time
        status = "success" if result.status == "success" else "error"
        if metric_id:
            try:
                await metrics_db.record_container_end(
                    metric_id,
                    status=status,
                    duration_seconds=duration,
                    error=result.error,
                )
            except Exception:
                pass
        return result
    except Exception as e:
        logger.error(f"Container error: {e}")
        # Record failure
        duration = time.time() - start_time
        if metric_id:
            try:
                await metrics_db.record_container_end(metric_id, "error", duration_seconds=duration, error=str(e))
            except Exception:
                pass
        return ContainerOutput(status="error", error=str(e))


async def _execute_container(
    cmd: list[str],
    input_data: dict[str, Any],
) -> ContainerOutput:
    """Execute docker container and capture output.

    Args:
        cmd: Docker command arguments
        input_data: Input data to send to container

    Returns:
        ContainerOutput with result
    """
    from loguru import logger

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Write input to stdin
        input_json = json.dumps(input_data)
        process.stdin.write(input_json.encode())
        await process.stdin.drain()
        process.stdin.close()

        # Read output
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=get_config().container_timeout,
        )

        # Parse output
        if stdout:
            output_str = stdout.decode("utf-8", errors="replace")
            result = _parse_output(output_str)
            if result:
                return result

        # Check for stderr errors
        if stderr:
            error_str = stderr.decode("utf-8", errors="replace")
            if error_str:
                logger.error(f"Container stderr: {error_str}")

        return ContainerOutput(
            status="error",
            error="No output from container",
        )

    except asyncio.TimeoutError:
        # Try to kill the process
        try:
            process.kill()
        except Exception:
            pass
        return ContainerOutput(
            status="error",
            error="Container execution timed out",
        )
    except FileNotFoundError:
        return ContainerOutput(
            status="error",
            error="Docker not found. Please install Docker.",
        )
    except Exception as e:
        return ContainerOutput(
            status="error",
            error=str(e),
        )


def _parse_output(output: str) -> ContainerOutput | None:
    """Parse container output.

    Args:
        output: Raw output string

    Returns:
        ContainerOutput or None if parsing fails
    """
    import json

    in_output = False
    output_lines = []

    for line in output.split("\n"):
        if OUTPUT_START_MARKER in line:
            in_output = True
            continue
        elif OUTPUT_END_MARKER in line:
            in_output = False
            break

        if in_output:
            output_lines.append(line)

    if output_lines:
        try:
            output_json = "\n".join(output_lines)
            data = json.loads(output_json)
            return ContainerOutput(
                status=data.get("status", "success"),
                result=data.get("result"),
                error=data.get("error"),
                new_session_id=data.get("newSessionId"),
            )
        except json.JSONDecodeError:
            # If not JSON, treat as result text
            return ContainerOutput(
                status="success",
                result="\n".join(output_lines),
            )

    return None


def build_docker_command(
    mounts: list[tuple[str, str, str]],
    input_data: dict[str, Any],
    timeout: int,
    env: dict[str, str] | None = None,
) -> list[str]:
    """Build docker run command.

    Args:
        mounts: List of (host_path, container_path, mode) tuples
        input_data: Input data to pass to container
        timeout: Timeout in seconds
        env: Optional environment variables for container

    Returns:
        Command as list of strings
    """
    from nanogridbot.config import get_config

    config = get_config()

    cmd = ["docker", "run", "--rm", "--network=none"]

    # Add mounts
    for host_path, container_path, mode in mounts:
        cmd.extend(["-v", f"{host_path}:{container_path}:{mode}"])

    # Add environment variables
    cmd.extend(["-e", f"NANOGRIDBOT_IS_MAIN={str(input_data.get('isMain', False)).lower()}"])
    cmd.extend(["-e", f"NANOGRIDBOT_GROUP={input_data.get('groupFolder', '')}"])

    # Add custom environment variables
    if env:
        for key, value in env.items():
            cmd.extend(["-e", f"{key}={value}"])

    # Set timeout
    cmd.extend(["--stop-timeout", str(timeout)])

    # Memory limit
    cmd.extend(["--memory", "2g"])

    # CPU limit
    cmd.extend(["--cpus", "1.0"])

    # Use image
    cmd.append(
        config.container_image if hasattr(config, "container_image") else "nanogridbot-agent:latest"
    )

    return cmd


async def check_docker_available() -> bool:
    """Check if Docker is available.

    Returns:
        True if Docker is available, False otherwise
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "docker",
            "version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        return process.returncode == 0
    except FileNotFoundError:
        return False


async def get_container_status(container_name: str) -> Literal["running", "exited", "not_found"]:
    """Get container status.

    Args:
        container_name: Name of container

    Returns:
        Container status
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "docker",
            "inspect",
            "--format={{.State.Status}}",
            container_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        if process.returncode == 0:
            status = stdout.decode().strip()
            return status  # type: ignore
        return "not_found"
    except FileNotFoundError:
        return "not_found"


async def cleanup_container(container_name: str) -> None:
    """Clean up a container.

    Args:
        container_name: Name of container to remove
    """
    from loguru import logger

    try:
        process = await asyncio.create_subprocess_exec(
            "docker",
            "rm",
            "-f",
            container_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        if process.returncode == 0:
            logger.info(f"Cleaned up container: {container_name}")
    except Exception as e:
        logger.warning(f"Failed to cleanup container {container_name}: {e}")
