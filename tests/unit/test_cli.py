"""Unit tests for CLI module."""

import argparse
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.cli import create_channels, main, run_async, start_web_server


class TestCliCreateChannels:
    """Test CLI create_channels function."""

    @pytest.mark.asyncio
    async def test_no_channels(self):
        """Test with no available channels."""
        config = MagicMock()
        db = MagicMock()
        with patch("nanogridbot.cli.ChannelRegistry") as mock_reg:
            mock_reg.available_channels.return_value = []
            result = await create_channels(config, db)
            assert result == []

    @pytest.mark.asyncio
    async def test_enabled_channel(self):
        """Test enabled channel is created."""
        config = MagicMock()
        config.get_channel_config.return_value = {"enabled": True}
        db = MagicMock()

        mock_type = MagicMock()
        mock_type.value = "telegram"
        mock_channel = MagicMock(spec=[])

        with patch("nanogridbot.cli.ChannelRegistry") as mock_reg:
            mock_reg.available_channels.return_value = [mock_type]
            mock_reg.create.return_value = mock_channel
            result = await create_channels(config, db)
            assert len(result) == 1


class TestCliStartWebServer:
    """Test CLI start_web_server function."""

    @pytest.mark.asyncio
    async def test_uses_override_host_port(self):
        """Test host/port override."""
        config = MagicMock()
        config.web_host = "0.0.0.0"
        config.web_port = 8080
        orchestrator = MagicMock()

        mock_uvicorn = MagicMock()
        mock_server = MagicMock()
        mock_server.serve = AsyncMock()
        mock_uvicorn.Config.return_value = MagicMock()
        mock_uvicorn.Server.return_value = mock_server

        with patch.dict("sys.modules", {"uvicorn": mock_uvicorn}):
            with patch("nanogridbot.cli.create_app"):
                await start_web_server(config, orchestrator, host="127.0.0.1", port=9090)
                # Verify Config was called with overridden values
                call_kwargs = mock_uvicorn.Config.call_args
                assert call_kwargs[1]["host"] == "127.0.0.1" or call_kwargs.kwargs.get("host") == "127.0.0.1"


class TestCliMain:
    """Test CLI main function."""

    def test_main_returns_zero_on_success(self):
        """Test main returns 0 on success."""
        with patch("nanogridbot.cli.argparse.ArgumentParser.parse_args") as mock_parse:
            mock_parse.return_value = argparse.Namespace(
                host=None, port=None, debug=False
            )
            with patch("nanogridbot.cli.asyncio.run", side_effect=KeyboardInterrupt):
                result = main()
                assert result == 0

    def test_main_returns_one_on_error(self):
        """Test main returns 1 on fatal error."""
        with patch("nanogridbot.cli.argparse.ArgumentParser.parse_args") as mock_parse:
            mock_parse.return_value = argparse.Namespace(
                host=None, port=None, debug=False
            )
            with patch("nanogridbot.cli.asyncio.run", side_effect=RuntimeError("fatal")):
                result = main()
                assert result == 1

    def test_main_debug_sets_env(self):
        """Test --debug flag sets LOG_LEVEL env var."""
        import os

        with patch("nanogridbot.cli.argparse.ArgumentParser.parse_args") as mock_parse:
            mock_parse.return_value = argparse.Namespace(
                host=None, port=None, debug=True
            )
            with patch("nanogridbot.cli.asyncio.run", side_effect=KeyboardInterrupt):
                main()
                assert os.environ.get("LOG_LEVEL") == "DEBUG"
                # Cleanup
                os.environ.pop("LOG_LEVEL", None)

    def test_main_version_flag(self):
        """Test --version flag."""
        with patch("sys.argv", ["nanogridbot", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0


class TestRunAsync:
    """Test run_async function."""

    @pytest.mark.asyncio
    async def test_run_async_initializes(self, mock_config):
        """Test run_async initializes all components."""
        args = argparse.Namespace(host=None, port=None, debug=False)

        mock_db = MagicMock()
        mock_db.initialize = AsyncMock()
        mock_db.close = AsyncMock()

        mock_orchestrator = MagicMock()
        mock_orchestrator.start = AsyncMock(side_effect=asyncio.CancelledError)
        mock_orchestrator.stop = AsyncMock()

        with patch("nanogridbot.cli.get_config", return_value=mock_config):
            with patch("nanogridbot.cli.setup_logger"):
                with patch("nanogridbot.cli.Database", return_value=mock_db):
                    with patch("nanogridbot.cli.create_channels", new_callable=AsyncMock, return_value=[]):
                        with patch("nanogridbot.cli.Orchestrator", return_value=mock_orchestrator):
                            with patch("nanogridbot.cli.start_web_server", new_callable=AsyncMock):
                                with patch("asyncio.sleep", new_callable=AsyncMock):
                                    with patch("asyncio.get_event_loop") as mock_loop:
                                        mock_loop.return_value.add_signal_handler = MagicMock()
                                        try:
                                            await run_async(args)
                                        except (asyncio.CancelledError, Exception):
                                            pass

                                        mock_db.initialize.assert_called_once()
                                        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_async_with_host_port(self, mock_config):
        """Test run_async with custom host/port."""
        args = argparse.Namespace(host="127.0.0.1", port=9090, debug=False)

        mock_db = MagicMock()
        mock_db.initialize = AsyncMock()
        mock_db.close = AsyncMock()

        mock_orchestrator = MagicMock()
        mock_orchestrator.start = AsyncMock(side_effect=asyncio.CancelledError)
        mock_orchestrator.stop = AsyncMock()

        with patch("nanogridbot.cli.get_config", return_value=mock_config):
            with patch("nanogridbot.cli.setup_logger"):
                with patch("nanogridbot.cli.Database", return_value=mock_db):
                    with patch("nanogridbot.cli.create_channels", new_callable=AsyncMock, return_value=[]):
                        with patch("nanogridbot.cli.Orchestrator", return_value=mock_orchestrator):
                            with patch("nanogridbot.cli.start_web_server", new_callable=AsyncMock) as mock_web:
                                with patch("asyncio.sleep", new_callable=AsyncMock):
                                    with patch("asyncio.get_event_loop") as mock_loop:
                                        mock_loop.return_value.add_signal_handler = MagicMock()
                                        try:
                                            await run_async(args)
                                        except (asyncio.CancelledError, Exception):
                                            pass

                                        # Verify host/port passed to web server
                                        mock_web.assert_called_once()
                                        call_args = mock_web.call_args
                                        assert call_args[0][2] == "127.0.0.1"
                                        assert call_args[0][3] == 9090
