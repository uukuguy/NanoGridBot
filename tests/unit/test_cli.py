"""Unit tests for CLI module."""

import argparse
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.cli import build_parser, create_channels, main, start_web_server


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
                call_kwargs = mock_uvicorn.Config.call_args
                assert (
                    call_kwargs[1]["host"] == "127.0.0.1"
                    or call_kwargs.kwargs.get("host") == "127.0.0.1"
                )


class TestBuildParser:
    """Test CLI argument parser construction."""

    def test_three_subcommands(self):
        """Test parser has exactly serve, shell, run subcommands."""
        parser = build_parser()
        # Parse each subcommand to verify they exist
        args = parser.parse_args(["serve"])
        assert args.command == "serve"

        args = parser.parse_args(["shell"])
        assert args.command == "shell"

        args = parser.parse_args(["run", "-p", "test"])
        assert args.command == "run"

    def test_no_chat_subcommand(self):
        """Test that old 'chat' subcommand is removed."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["chat"])

    def test_serve_args(self):
        """Test serve subcommand arguments."""
        parser = build_parser()
        args = parser.parse_args(["serve", "--host", "127.0.0.1", "--port", "9090"])
        assert args.host == "127.0.0.1"
        assert args.port == 9090

    def test_shell_args(self):
        """Test shell subcommand arguments."""
        parser = build_parser()
        args = parser.parse_args(["shell", "-g", "myproject", "--resume", "sess123"])
        assert args.group == "myproject"
        assert args.resume == "sess123"
        assert args.attach is False

    def test_shell_attach(self):
        """Test shell --attach flag."""
        parser = build_parser()
        args = parser.parse_args(["shell", "--attach"])
        assert args.attach is True

    def test_run_args(self):
        """Test run subcommand arguments."""
        parser = build_parser()
        args = parser.parse_args([
            "run", "-p", "hello", "-g", "deploy",
            "--context", "5", "--send", "--timeout", "60", "-v",
        ])
        assert args.prompt == "hello"
        assert args.group == "deploy"
        assert args.context == 5
        assert args.send is True
        assert args.timeout == 60
        assert args.verbose is True

    def test_run_no_llm_args(self):
        """Test that run has no LLM-specific args (--model, --temperature, etc.)."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["run", "--model", "gpt-4"])
        with pytest.raises(SystemExit):
            parser.parse_args(["run", "--temperature", "0.5"])

    def test_default_command_is_serve(self):
        """Test that no subcommand defaults to serve."""
        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None  # main() maps None -> "serve"


class TestCliMain:
    """Test CLI main function."""

    def test_main_returns_zero_on_keyboard_interrupt(self):
        """Test main returns 0 on KeyboardInterrupt."""
        with patch("nanogridbot.cli.build_parser") as mock_bp:
            mock_bp.return_value.parse_args.return_value = argparse.Namespace(
                command="serve", host=None, port=None, debug=False
            )
            with patch("nanogridbot.cli.asyncio.run", side_effect=KeyboardInterrupt):
                result = main()
                assert result == 0

    def test_main_returns_one_on_error(self):
        """Test main returns 1 on fatal error."""
        with patch("nanogridbot.cli.build_parser") as mock_bp:
            mock_bp.return_value.parse_args.return_value = argparse.Namespace(
                command="serve", host=None, port=None, debug=False
            )
            with patch("nanogridbot.cli.asyncio.run", side_effect=RuntimeError("fatal")):
                result = main()
                assert result == 1

    def test_main_debug_sets_env(self):
        """Test --debug flag sets LOG_LEVEL env var."""
        import os

        with patch("nanogridbot.cli.build_parser") as mock_bp:
            mock_bp.return_value.parse_args.return_value = argparse.Namespace(
                command="serve", host=None, port=None, debug=True
            )
            with patch("nanogridbot.cli.asyncio.run", side_effect=KeyboardInterrupt):
                main()
                assert os.environ.get("LOG_LEVEL") == "DEBUG"
                os.environ.pop("LOG_LEVEL", None)

    def test_main_version_flag(self):
        """Test --version flag."""
        with patch("sys.argv", ["nanogridbot", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_main_dispatches_run(self):
        """Test main dispatches to cmd_run."""
        with patch("nanogridbot.cli.build_parser") as mock_bp:
            mock_bp.return_value.parse_args.return_value = argparse.Namespace(
                command="run", prompt="test", group=None, context=0,
                send=False, timeout=None, verbose=False, debug=False,
            )
            with patch("nanogridbot.cli.asyncio.run") as mock_run:
                main()
                mock_run.assert_called_once()


class TestCmdRun:
    """Test cmd_run function."""

    @pytest.mark.asyncio
    async def test_run_success(self):
        """Test successful run command."""
        from nanogridbot.cli import cmd_run
        from nanogridbot.types import ContainerOutput

        args = argparse.Namespace(
            prompt="hello", group=None, context=0,
            send=False, timeout=None, verbose=False,
        )

        mock_result = ContainerOutput(status="success", result="world")
        mock_config = MagicMock()
        mock_config.cli_default_group = "cli"
        mock_config.log_level = "INFO"

        with (
            patch("nanogridbot.cli.get_config", return_value=mock_config),
            patch("nanogridbot.cli.setup_logger"),
            patch("nanogridbot.cli.run_container_agent", new_callable=AsyncMock, return_value=mock_result),
        ):
            with patch("builtins.print") as mock_print:
                await cmd_run(args)
                mock_print.assert_called_with("world")

    @pytest.mark.asyncio
    async def test_run_error(self):
        """Test run command with error result."""
        from nanogridbot.cli import cmd_run
        from nanogridbot.types import ContainerOutput

        args = argparse.Namespace(
            prompt="hello", group=None, context=0,
            send=False, timeout=None, verbose=False,
        )

        mock_result = ContainerOutput(status="error", error="container failed")
        mock_config = MagicMock()
        mock_config.cli_default_group = "cli"
        mock_config.log_level = "INFO"

        with (
            patch("nanogridbot.cli.get_config", return_value=mock_config),
            patch("nanogridbot.cli.setup_logger"),
            patch("nanogridbot.cli.run_container_agent", new_callable=AsyncMock, return_value=mock_result),
        ):
            with pytest.raises(SystemExit) as exc_info:
                await cmd_run(args)
            assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_run_no_prompt_exits(self):
        """Test run with no prompt exits with error."""
        from nanogridbot.cli import cmd_run

        args = argparse.Namespace(
            prompt=None, group=None, context=0,
            send=False, timeout=None, verbose=False,
        )

        mock_config = MagicMock()
        mock_config.cli_default_group = "cli"
        mock_config.log_level = "INFO"

        with (
            patch("nanogridbot.cli.get_config", return_value=mock_config),
            patch("nanogridbot.cli.setup_logger"),
            patch("sys.stdin") as mock_stdin,
        ):
            mock_stdin.read.return_value = ""
            with pytest.raises(SystemExit) as exc_info:
                await cmd_run(args)
            assert exc_info.value.code == 1
