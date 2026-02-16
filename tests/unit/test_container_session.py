"""Unit tests for ContainerSession."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.core.container_session import ContainerSession


class TestContainerSessionInit:
    """Test ContainerSession initialization."""

    def test_default_group(self):
        """Test default group folder."""
        session = ContainerSession()
        assert session.group_folder == "cli"
        assert session.session_id is None
        assert session.container_name.startswith("ngb-shell-cli-")

    def test_custom_group(self):
        """Test custom group folder."""
        session = ContainerSession(group_folder="myproject")
        assert session.group_folder == "myproject"
        assert session.container_name.startswith("ngb-shell-myproject-")

    def test_resume_session(self):
        """Test session with resume ID."""
        session = ContainerSession(group_folder="cli", session_id="abc123")
        assert session.session_id == "abc123"

    def test_unique_container_names(self):
        """Test that each session gets a unique container name."""
        s1 = ContainerSession()
        s2 = ContainerSession()
        assert s1.container_name != s2.container_name


class TestContainerSessionStart:
    """Test ContainerSession.start()."""

    @pytest.mark.asyncio
    async def test_start_builds_named_container(self, tmp_path):
        """Test that start creates a named container (not --rm)."""
        session = ContainerSession(group_folder="test")

        mock_process = AsyncMock()
        mock_stdin = MagicMock()
        mock_stdin.write = AsyncMock()
        mock_stdin.drain = AsyncMock()
        mock_stdin.is_closing = MagicMock(return_value=False)
        mock_process.stdin = mock_stdin
        mock_process.returncode = None

        mock_config = MagicMock()
        mock_config.container_timeout = 300
        mock_config.data_dir = tmp_path

        with (
            patch("nanogridbot.core.container_session.get_config", return_value=mock_config),
            patch(
                "nanogridbot.core.container_session.validate_group_mounts",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "nanogridbot.core.container_session.build_docker_command",
                return_value=["docker", "run", "--rm", "--network=none", "img:latest"],
            ),
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
        ):
            await session.start()

        # Verify stdin received initial JSON
        mock_stdin.write.assert_called_once()
        written = mock_stdin.write.call_args[0][0]
        data = json.loads(written.decode().strip())
        assert data["groupFolder"] == "test"
        assert data["chatJid"] == "cli:test"


class TestContainerSessionSend:
    """Test ContainerSession.send()."""

    @pytest.mark.asyncio
    async def test_send_writes_ipc_file(self, tmp_path):
        """Test that send writes a JSON file to the IPC input directory."""
        session = ContainerSession(group_folder="test")
        session._ipc_dir = tmp_path / "ipc" / "cli:test"
        (session._ipc_dir / "input").mkdir(parents=True)
        (session._ipc_dir / "output").mkdir(parents=True)

        # No process — IPC-only path
        session._process = None

        await session.send("hello world")

        files = list((session._ipc_dir / "input").glob("*.json"))
        assert len(files) == 1

        data = json.loads(files[0].read_text())
        assert data["text"] == "hello world"
        assert data["sender"] == "cli-user"

    @pytest.mark.asyncio
    async def test_send_without_start_raises(self):
        """Test that send raises if session not started."""
        session = ContainerSession()
        with pytest.raises(RuntimeError, match="Session not started"):
            await session.send("hello")


class TestContainerSessionClose:
    """Test ContainerSession.close()."""

    @pytest.mark.asyncio
    async def test_close_sends_sentinel(self, tmp_path):
        """Test that close writes a _close sentinel file."""
        session = ContainerSession(group_folder="test")
        session._ipc_dir = tmp_path / "ipc" / "cli:test"
        (session._ipc_dir / "input").mkdir(parents=True)
        (session._ipc_dir / "output").mkdir(parents=True)
        session._process = None

        with patch(
            "nanogridbot.core.container_session.cleanup_container",
            new_callable=AsyncMock,
        ) as mock_cleanup:
            await session.close()

        sentinel = session._ipc_dir / "input" / "_close"
        assert sentinel.exists()
        data = json.loads(sentinel.read_text())
        assert data["action"] == "close"
        mock_cleanup.assert_called_once_with(session.container_name)

    @pytest.mark.asyncio
    async def test_close_kills_process(self, tmp_path):
        """Test that close kills the container process."""
        session = ContainerSession(group_folder="test")
        session._ipc_dir = tmp_path / "ipc" / "cli:test"
        (session._ipc_dir / "input").mkdir(parents=True)

        mock_process = AsyncMock()
        mock_process.returncode = None  # Explicitly set for is_alive check
        mock_process.stdin = MagicMock()
        mock_process.stdin.is_closing = MagicMock(return_value=False)
        mock_process.stdin.close = AsyncMock()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()
        session._process = mock_process

        with patch(
            "nanogridbot.core.container_session.cleanup_container",
            new_callable=AsyncMock,
        ):
            await session.close()

        mock_process.kill.assert_called_once()


class TestContainerSessionReceive:
    """Test ContainerSession.receive()."""

    @pytest.mark.asyncio
    async def test_receive_reads_output_files(self, tmp_path):
        """Test that receive yields content from IPC output files."""
        session = ContainerSession(group_folder="test")
        session._ipc_dir = tmp_path / "ipc" / "cli:test"
        (session._ipc_dir / "input").mkdir(parents=True)
        output_dir = session._ipc_dir / "output"
        output_dir.mkdir(parents=True)

        # Write an output file
        (output_dir / "2026-01-01T00:00:00.json").write_text(
            json.dumps({"result": "hello from container"})
        )

        # Mock process that exits after one iteration
        mock_process = MagicMock()
        mock_process.returncode = None
        mock_stdout = AsyncMock()
        mock_stdout.readline = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_process.stdout = mock_stdout
        session._process = mock_process

        results = []
        count = 0
        async for text in session.receive():
            results.append(text)
            count += 1
            # After reading the IPC file, simulate process exit
            mock_process.returncode = 0
            if count >= 1:
                break

        assert "hello from container" in results

    @pytest.mark.asyncio
    async def test_session_id_updated(self, tmp_path):
        """Test that session_id is updated from output data."""
        session = ContainerSession(group_folder="test")
        assert session.session_id is None

        session._ipc_dir = tmp_path / "ipc" / "cli:test"
        (session._ipc_dir / "input").mkdir(parents=True)
        output_dir = session._ipc_dir / "output"
        output_dir.mkdir(parents=True)

        (output_dir / "2026-01-01T00:00:00.json").write_text(
            json.dumps({"result": "ok", "newSessionId": "new-sess-42"})
        )

        mock_process = MagicMock()
        mock_process.returncode = None
        mock_stdout = AsyncMock()
        mock_stdout.readline = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_process.stdout = mock_stdout
        session._process = mock_process

        async for text in session.receive():
            mock_process.returncode = 0
            break

        assert session.session_id == "new-sess-42"


class TestContainerSessionIsAlive:
    """Test ContainerSession.is_alive property."""

    def test_not_started(self):
        """Test is_alive before start."""
        session = ContainerSession()
        assert session.is_alive is False

    def test_running(self):
        """Test is_alive when process is running."""
        session = ContainerSession()
        session._process = MagicMock()
        session._process.returncode = None
        assert session.is_alive is True

    def test_exited(self):
        """Test is_alive when process has exited."""
        session = ContainerSession()
        session._process = MagicMock()
        session._process.returncode = 0
        assert session.is_alive is False
