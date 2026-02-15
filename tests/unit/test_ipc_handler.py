"""Unit tests for IpcHandler."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.core.ipc_handler import IpcHandler
from nanogridbot.database import Database
from nanogridbot.types import RegisteredGroup


@pytest.fixture
def mock_config(tmp_path):
    """Mock configuration."""
    config = MagicMock()
    config.data_dir = tmp_path
    return config


@pytest.fixture
def mock_db():
    """Mock database."""
    db = AsyncMock(spec=Database)
    db.get_registered_groups = AsyncMock(return_value=[])
    return db


@pytest.fixture
def mock_channel():
    """Mock channel."""
    channel = AsyncMock()
    channel.name = "test_channel"
    channel.owns_jid = MagicMock(return_value=True)
    channel.send_message = AsyncMock()
    return channel


@pytest.fixture
def ipc_handler(mock_config, mock_db, mock_channel):
    """Create IpcHandler instance."""
    return IpcHandler(mock_config, mock_db, [mock_channel])


class TestIpcHandlerInit:
    """Test IpcHandler initialization."""

    def test_init(self, ipc_handler, mock_config, mock_db, mock_channel):
        """Test IPC handler initialization."""
        assert ipc_handler.config == mock_config
        assert ipc_handler.db == mock_db
        assert len(ipc_handler.channels) == 1
        assert ipc_handler.channels[0] == mock_channel
        assert ipc_handler._running is False
        assert ipc_handler._watchers == {}


class TestIpcHandlerLifecycle:
    """Test IpcHandler start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start(self, ipc_handler, mock_db):
        """Test starting IPC handler."""
        await ipc_handler.start()

        assert ipc_handler._running is True
        mock_db.get_registered_groups.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_with_groups(self, ipc_handler, mock_db):
        """Test starting IPC handler with registered groups."""
        groups = [
            RegisteredGroup(jid="jid1", name="Group 1", folder="folder1", requires_trigger=False),
            RegisteredGroup(jid="jid2", name="Group 2", folder="folder2", requires_trigger=False),
        ]
        mock_db.get_registered_groups = AsyncMock(return_value=groups)

        await ipc_handler.start()

        assert ipc_handler._running is True
        assert len(ipc_handler._watchers) == 2
        assert "jid1" in ipc_handler._watchers
        assert "jid2" in ipc_handler._watchers

        # Cleanup
        await ipc_handler.stop()

    @pytest.mark.asyncio
    async def test_stop(self, ipc_handler, mock_db):
        """Test stopping IPC handler."""
        await ipc_handler.start()
        await ipc_handler.stop()

        assert ipc_handler._running is False
        assert len(ipc_handler._watchers) == 0

    @pytest.mark.asyncio
    async def test_stop_cancels_watchers(self, ipc_handler, mock_db):
        """Test stopping cancels all watchers."""
        groups = [
            RegisteredGroup(jid="jid1", name="Group 1", folder="folder1", requires_trigger=False),
        ]
        mock_db.get_registered_groups = AsyncMock(return_value=groups)

        await ipc_handler.start()
        assert len(ipc_handler._watchers) == 1

        await ipc_handler.stop()
        assert len(ipc_handler._watchers) == 0


class TestWatchGroup:
    """Test group watching."""

    @pytest.mark.asyncio
    async def test_watch_group(self, ipc_handler):
        """Test starting to watch a group."""
        await ipc_handler._watch_group("jid1")

        assert "jid1" in ipc_handler._watchers
        assert not ipc_handler._watchers["jid1"].done()

        # Cleanup
        ipc_handler._watchers["jid1"].cancel()
        try:
            await ipc_handler._watchers["jid1"]
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_watch_group_duplicate(self, ipc_handler):
        """Test watching same group twice."""
        await ipc_handler._watch_group("jid1")
        first_task = ipc_handler._watchers["jid1"]

        await ipc_handler._watch_group("jid1")
        second_task = ipc_handler._watchers["jid1"]

        assert first_task is second_task

        # Cleanup
        first_task.cancel()
        try:
            await first_task
        except asyncio.CancelledError:
            pass


class TestIpcDirectories:
    """Test IPC directory creation."""

    @pytest.mark.asyncio
    async def test_watch_group_creates_directories(self, ipc_handler, mock_config):
        """Test that watching a group creates IPC directories."""
        ipc_handler._running = True

        # Start watching
        task = asyncio.create_task(ipc_handler._watch_group_loop("jid1"))

        # Give it time to create directories
        await asyncio.sleep(0.1)

        # Cancel the task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Check directories exist
        ipc_dir = mock_config.data_dir / "ipc" / "jid1"
        assert (ipc_dir / "input").exists()
        assert (ipc_dir / "output").exists()


class TestWriteInput:
    """Test writing input files."""

    @pytest.mark.asyncio
    async def test_write_input(self, ipc_handler, mock_config):
        """Test writing input IPC file."""
        filename = await ipc_handler.write_input("jid1", "user1", "test message")

        assert filename.endswith(".json")

        # Check file exists and content
        ipc_dir = mock_config.data_dir / "ipc" / "jid1" / "input"
        file_path = ipc_dir / filename

        assert file_path.exists()

        content = json.loads(file_path.read_text())
        assert content["sender"] == "user1"
        assert content["text"] == "test message"
        assert "timestamp" in content


class TestWriteOutput:
    """Test writing output files."""

    @pytest.mark.asyncio
    async def test_write_output(self, ipc_handler, mock_config):
        """Test writing output IPC file."""
        filename = await ipc_handler.write_output("jid1", "test result")

        assert filename.endswith(".json")

        # Check file exists and content
        ipc_dir = mock_config.data_dir / "ipc" / "jid1" / "output"
        file_path = ipc_dir / filename

        assert file_path.exists()

        content = json.loads(file_path.read_text())
        assert content["result"] == "test result"
        assert "timestamp" in content
        assert "sessionId" not in content

    @pytest.mark.asyncio
    async def test_write_output_with_session(self, ipc_handler, mock_config):
        """Test writing output IPC file with session ID."""
        filename = await ipc_handler.write_output("jid1", "test result", "session123")

        # Check file content
        ipc_dir = mock_config.data_dir / "ipc" / "jid1" / "output"
        file_path = ipc_dir / filename

        content = json.loads(file_path.read_text())
        assert content["result"] == "test result"
        assert content["sessionId"] == "session123"


class TestProcessInputFile:
    """Test processing input files."""

    @pytest.mark.asyncio
    async def test_process_input_file(self, ipc_handler, mock_config):
        """Test processing an input file."""
        # Create input file
        ipc_dir = mock_config.data_dir / "ipc" / "jid1" / "input"
        ipc_dir.mkdir(parents=True, exist_ok=True)

        file_path = ipc_dir / "test.json"
        file_path.write_text(
            json.dumps(
                {
                    "sender": "user1",
                    "text": "test message",
                    "timestamp": "2024-01-01T00:00:00",
                }
            )
        )

        # Process file (currently just logs)
        await ipc_handler._process_input_file("jid1", file_path)

        # No exception means success

    @pytest.mark.asyncio
    async def test_process_input_file_invalid_json(self, ipc_handler, mock_config):
        """Test processing invalid JSON input file."""
        # Create invalid input file
        ipc_dir = mock_config.data_dir / "ipc" / "jid1" / "input"
        ipc_dir.mkdir(parents=True, exist_ok=True)

        file_path = ipc_dir / "test.json"
        file_path.write_text("invalid json")

        # Should handle error gracefully
        await ipc_handler._process_input_file("jid1", file_path)


class TestProcessOutputFile:
    """Test processing output files."""

    @pytest.mark.asyncio
    async def test_process_output_file(self, ipc_handler, mock_config, mock_channel):
        """Test processing an output file."""
        # Create output file
        ipc_dir = mock_config.data_dir / "ipc" / "jid1" / "output"
        ipc_dir.mkdir(parents=True, exist_ok=True)

        file_path = ipc_dir / "test.json"
        file_path.write_text(
            json.dumps(
                {
                    "result": "test result",
                    "timestamp": "2024-01-01T00:00:00",
                }
            )
        )

        # Process file
        await ipc_handler._process_output_file("jid1", file_path)

        # Should send to channel
        mock_channel.send_message.assert_called_once_with("jid1", "test result")

    @pytest.mark.asyncio
    async def test_process_output_file_with_text_field(self, ipc_handler, mock_config, mock_channel):
        """Test processing output file with 'text' field instead of 'result'."""
        # Create output file
        ipc_dir = mock_config.data_dir / "ipc" / "jid1" / "output"
        ipc_dir.mkdir(parents=True, exist_ok=True)

        file_path = ipc_dir / "test.json"
        file_path.write_text(
            json.dumps(
                {
                    "text": "test text",
                    "timestamp": "2024-01-01T00:00:00",
                }
            )
        )

        # Process file
        await ipc_handler._process_output_file("jid1", file_path)

        # Should send to channel
        mock_channel.send_message.assert_called_once_with("jid1", "test text")

    @pytest.mark.asyncio
    async def test_process_output_file_no_result(self, ipc_handler, mock_config, mock_channel):
        """Test processing output file without result."""
        # Create output file
        ipc_dir = mock_config.data_dir / "ipc" / "jid1" / "output"
        ipc_dir.mkdir(parents=True, exist_ok=True)

        file_path = ipc_dir / "test.json"
        file_path.write_text(
            json.dumps(
                {
                    "timestamp": "2024-01-01T00:00:00",
                }
            )
        )

        # Process file
        await ipc_handler._process_output_file("jid1", file_path)

        # Should not send to channel
        mock_channel.send_message.assert_not_called()


class TestSendToChannel:
    """Test sending to channels."""

    @pytest.mark.asyncio
    async def test_send_to_channel(self, ipc_handler, mock_channel):
        """Test sending message to channel."""
        await ipc_handler._send_to_channel("jid1", "test message")

        mock_channel.owns_jid.assert_called_once_with("jid1")
        mock_channel.send_message.assert_called_once_with("jid1", "test message")

    @pytest.mark.asyncio
    async def test_send_to_channel_no_owner(self, ipc_handler, mock_channel):
        """Test sending message when no channel owns JID."""
        mock_channel.owns_jid = MagicMock(return_value=False)

        await ipc_handler._send_to_channel("jid1", "test message")

        mock_channel.owns_jid.assert_called_once_with("jid1")
        mock_channel.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_to_channel_error(self, ipc_handler, mock_channel):
        """Test sending message with channel error."""
        mock_channel.send_message = AsyncMock(side_effect=Exception("Send failed"))

        # Should handle error gracefully
        await ipc_handler._send_to_channel("jid1", "test message")

        mock_channel.send_message.assert_called_once()
