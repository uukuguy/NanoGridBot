"""Tests for the CLI module."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import sys


class TestCLI:
    """Tests for CLI entry point."""

    def test_cli_main_import(self):
        """Test that CLI module can be imported."""
        from nanogridbot import cli

        assert hasattr(cli, "main")
        assert callable(cli.main)

    def test_cli_argument_parsing_version(self):
        """Test version argument."""
        from nanogridbot.cli import main

        with patch("sys.argv", ["nanogridbot", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_cli_argument_parsing_help(self):
        """Test help argument."""
        from nanogridbot.cli import main

        with patch("sys.argv", ["nanogridbot", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_cli_custom_host_port(self):
        """Test custom host and port arguments."""
        from nanogridbot.cli import main, run_async

        # Test that custom host/port are parsed correctly
        with patch("sys.argv", ["nanogridbot", "--host", "0.0.0.0", "--port", "8080"]):
            with patch("nanogridbot.cli.run_async") as mock_run:
                mock_run.side_effect = KeyboardInterrupt()  # Stop after parsing
                try:
                    main()
                except KeyboardInterrupt:
                    pass

                # Verify run_async was called with correct args
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert args.host == "0.0.0.0"
                assert args.port == 8080

    @pytest.mark.asyncio
    async def test_create_channels_no_enabled(self):
        """Test create_channels with no enabled channels."""
        from nanogridbot.cli import create_channels

        mock_config = MagicMock()
        mock_config.get_channel_config.return_value = {"enabled": False}
        mock_config.model_dump.return_value = {}
        mock_db = MagicMock()

        with patch("nanogridbot.cli.ChannelRegistry") as mock_registry:
            mock_registry.available_channels.return_value = []
            mock_registry.create.return_value = None

            channels = await create_channels(mock_config, mock_db)

            assert channels == []

    @pytest.mark.asyncio
    async def test_create_channels_with_enabled(self):
        """Test create_channels with enabled channel."""
        from nanogridbot.cli import create_channels
        from nanogridbot.types import ChannelType

        mock_config = MagicMock()
        mock_config.get_channel_config.return_value = {"enabled": True}
        mock_config.model_dump.return_value = {}
        mock_db = MagicMock()

        mock_channel = MagicMock()
        mock_channel.name = "whatsapp"

        with patch("nanogridbot.cli.ChannelRegistry") as mock_registry:
            mock_registry.available_channels.return_value = [ChannelType.WHATSAPP]
            mock_registry.create.return_value = mock_channel

            channels = await create_channels(mock_config, mock_db)

            assert len(channels) == 1
            assert channels[0] == mock_channel
            mock_channel.configure.assert_called_once()


class TestCLIIntegration:
    """Integration tests for CLI."""

    def test_cli_module_entry_point(self):
        """Test CLI entry point is properly configured."""
        # This test verifies the entry point is properly configured
        from nanogridbot import cli

        # Verify main function exists and is callable
        assert callable(cli.main)
        assert callable(cli.run_async)
        assert callable(cli.create_channels)
        assert callable(cli.start_web_server)
