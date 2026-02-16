"""Command-line interface for NanoGridBot.

Supports three modes:
  serve  - Start the full orchestrator + web dashboard (default)
  shell  - Interactive multi-turn conversation via container
  run    - Non-interactive single-shot execution via container
"""

import argparse
import asyncio
import signal
import sys
from typing import Any

from loguru import logger

from nanogridbot import setup_logger
from nanogridbot.channels import ChannelRegistry
from nanogridbot.config import Config, get_config
from nanogridbot.core.container_runner import run_container_agent
from nanogridbot.core.container_session import ContainerSession
from nanogridbot.core.orchestrator import Orchestrator
from nanogridbot.database import Database
from nanogridbot.web.app import create_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def create_channels(config: Config, db: Database) -> list[Any]:
    """Create and configure channel instances based on config."""
    channels = []
    available = ChannelRegistry.available_channels()

    for channel_type in available:
        channel_config = config.get_channel_config(channel_type.value)
        enabled = channel_config.get("enabled", False)
        if not enabled:
            env_key = f"{channel_type.value.upper()}_ENABLED"
            enabled = config.model_dump().get(env_key.lower(), False)

        if enabled:
            channel = ChannelRegistry.create(channel_type)
            if channel:
                if hasattr(channel, "configure"):
                    channel.configure(channel_config)
                elif hasattr(channel, "set_config"):
                    channel.set_config(channel_config)
                channels.append(channel)
                logger.info(f"Created channel: {channel_type.value}")

    return channels


async def start_web_server(
    config: Config,
    orchestrator: Orchestrator,
    host: str | None = None,
    port: int | None = None,
) -> None:
    """Start the uvicorn web server."""
    import uvicorn

    app = create_app(orchestrator)
    server_config = uvicorn.Config(
        app,
        host=host or config.web_host,
        port=port or config.web_port,
        log_level="info",
    )
    server = uvicorn.Server(server_config)
    await server.serve()


# ---------------------------------------------------------------------------
# serve mode
# ---------------------------------------------------------------------------


async def cmd_serve(args: argparse.Namespace) -> None:
    """Run the full orchestrator + web dashboard."""
    config = get_config()
    setup_logger(config.log_level)

    logger.info("Starting NanoGridBot (serve mode)")
    logger.info(f"Version: {config.version}")
    logger.info(f"Web server: {args.host or config.web_host}:{args.port or config.web_port}")

    db = Database(config.db_path)
    await db.initialize()

    try:
        channels = await create_channels(config, db)
        orchestrator = Orchestrator(config, db, channels)

        web_task = asyncio.create_task(
            start_web_server(config, orchestrator, args.host, args.port)
        )
        await asyncio.sleep(1)

        loop = asyncio.get_event_loop()
        stop_event = asyncio.Event()

        def signal_handler() -> None:
            logger.info("Received shutdown signal")
            stop_event.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)

        orchestrator_task = asyncio.create_task(orchestrator.start())

        try:
            await asyncio.gather(orchestrator_task, web_task, stop_event.wait())
        except Exception as e:
            logger.error(f"Error in main loop: {e}")

        await orchestrator.stop()
    finally:
        await db.close()
        logger.info("NanoGridBot stopped")


# ---------------------------------------------------------------------------
# shell mode  (interactive, container-backed)
# ---------------------------------------------------------------------------


def _read_input() -> str | None:
    """Read a line from stdin (blocking). Returns None on EOF."""
    try:
        return input("\n> ").strip()
    except (EOFError, KeyboardInterrupt):
        return None


async def _print_output(session: ContainerSession) -> None:
    """Background task: print container output as it arrives."""
    try:
        async for text in session.receive():
            print(text)
    except asyncio.CancelledError:
        pass


def _print_shell_help() -> None:
    """Print available shell commands."""
    print(
        "Commands:\n"
        "  /quit     Exit the shell\n"
        "  /status   Show container status\n"
        "  /attach   Attach to container shell\n"
        "  /clear    Clear local display\n"
        "  /help     Show this help\n"
        "\n"
        "Any other input (including unrecognized /commands)\n"
        "is sent directly to the container."
    )


def _print_status(session: ContainerSession) -> None:
    """Print session status."""
    print(
        f"  container: {session.container_name}\n"
        f"  group:     {session.group_folder}\n"
        f"  session:   {session.session_id or '(none)'}\n"
        f"  alive:     {session.is_alive}"
    )


async def cmd_shell(args: argparse.Namespace) -> None:
    """Interactive multi-turn conversation via container."""
    config = get_config()
    setup_logger("WARNING")

    group = args.group or config.cli_default_group

    if args.attach:
        # Direct attach mode — just exec into an existing container
        session = ContainerSession(group_folder=group)
        await session.attach()
        return

    session = ContainerSession(group_folder=group, session_id=args.resume)

    print(f"NanoGridBot shell  (group: {group}, /help for commands)")
    print("-" * 60)

    await session.start()
    output_task = asyncio.create_task(_print_output(session))

    try:
        while session.is_alive:
            user_input = await asyncio.get_event_loop().run_in_executor(None, _read_input)
            if user_input is None:
                break

            if user_input == "/quit":
                break
            elif user_input == "/attach":
                await session.attach()
            elif user_input == "/status":
                _print_status(session)
            elif user_input == "/clear":
                print("(conversation continues in container, local display cleared)")
            elif user_input == "/help":
                _print_shell_help()
            elif user_input:
                # Everything else (including unrecognized /xxx) goes to container
                await session.send(user_input)
    finally:
        output_task.cancel()
        try:
            await output_task
        except asyncio.CancelledError:
            pass
        await session.close()
        print("\nSession ended.")


# ---------------------------------------------------------------------------
# run mode  (non-interactive, single-shot)
# ---------------------------------------------------------------------------


async def cmd_run(args: argparse.Namespace) -> None:
    """Non-interactive single-shot execution via container."""
    config = get_config()
    setup_logger(config.log_level if args.verbose else "WARNING")

    group = args.group or config.cli_default_group

    prompt = args.prompt
    if not prompt:
        prompt = sys.stdin.read().strip()
    if not prompt:
        print("Error: no prompt. Use -p or pipe via stdin.", file=sys.stderr)
        sys.exit(1)

    result = await run_container_agent(
        group_folder=group,
        prompt=prompt,
        session_id=None,
        chat_jid=f"cli:{group}",
        timeout=args.timeout,
    )

    if result.status == "error":
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)

    print(result.result or "")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="nanogridbot",
        description="NanoGridBot - Multi-platform AI messaging bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  nanogridbot serve                              Start orchestrator + web dashboard\n"
            "  nanogridbot shell                              Interactive container session\n"
            "  nanogridbot shell -g myproject                 Shell for a specific group\n"
            '  nanogridbot run -p "Explain JID format"        Single-shot query\n'
            '  git diff | nanogridbot run -p "review this"    Pipe input\n'
            "  nanogridbot run -g deploy -p \"check config\" --timeout 60\n"
        ),
    )

    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0-alpha")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- serve ---
    serve_parser = subparsers.add_parser(
        "serve", help="Start the full orchestrator + web dashboard"
    )
    serve_parser.add_argument("--host", type=str, default=None, help="Web server host")
    serve_parser.add_argument("--port", type=int, default=None, help="Web server port")

    # --- shell ---
    shell_parser = subparsers.add_parser(
        "shell", help="Interactive multi-turn conversation via container"
    )
    shell_parser.add_argument(
        "-g", "--group", type=str, default=None, help="Group folder (default: cli)"
    )
    shell_parser.add_argument(
        "--resume", type=str, default=None, help="Resume a previous session by ID"
    )
    shell_parser.add_argument(
        "--attach", action="store_true", help="Attach directly to container shell"
    )

    # --- run ---
    run_parser = subparsers.add_parser(
        "run", help="Non-interactive single-shot execution via container"
    )
    run_parser.add_argument(
        "-p", "--prompt", type=str, default=None, help="Prompt text (or pipe via stdin)"
    )
    run_parser.add_argument(
        "-g", "--group", type=str, default=None, help="Group folder (default: cli)"
    )
    run_parser.add_argument(
        "--context", type=int, default=0, help="Number of recent messages as context"
    )
    run_parser.add_argument(
        "--send", action="store_true", help="Send result back to the group channel"
    )
    run_parser.add_argument(
        "--timeout", type=int, default=None, help="Container timeout in seconds"
    )
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Show verbose logging")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Main entry point for CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if args.debug:
        import os

        os.environ["LOG_LEVEL"] = "DEBUG"

    command = args.command or "serve"

    dispatch = {
        "serve": cmd_serve,
        "shell": cmd_shell,
        "run": cmd_run,
    }

    handler = dispatch.get(command)
    if not handler:
        parser.print_help()
        return 1

    try:
        asyncio.run(handler(args))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
