"""Command-line interface for NanoGridBot.

Supports four modes:
  serve  - Start the full orchestrator + web dashboard (default)
  shell  - Interactive REPL for chatting with the LLM
  chat   - Single-shot message, print response, exit
  exec   - Run a prompt against a registered group
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
from nanogridbot.core.orchestrator import Orchestrator
from nanogridbot.database import Database
from nanogridbot.llm import LLMManager, LLMMessage
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


def _build_llm_manager(config: Config) -> LLMManager:
    """Build an LLMManager from the current config."""
    return LLMManager.from_config(config)


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
# shell mode  (interactive REPL)
# ---------------------------------------------------------------------------


async def cmd_shell(args: argparse.Namespace) -> None:
    """Interactive REPL for chatting with the LLM."""
    config = get_config()
    setup_logger("WARNING")  # quiet logs in interactive mode

    llm = _build_llm_manager(config)
    history: list[LLMMessage] = []

    system_prompt = args.system or f"You are {config.assistant_name}, a helpful AI assistant."
    history.append(LLMMessage(role="system", content=system_prompt))

    model_name = args.model or config.llm_model
    print(f"NanoGridBot shell  (model: {model_name}, Ctrl+D to quit)")
    print("-" * 60)

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue

        if user_input in ("/quit", "/exit", "/q"):
            print("Bye!")
            break
        if user_input == "/clear":
            history = [history[0]]  # keep system prompt
            print("(conversation cleared)")
            continue
        if user_input == "/history":
            for i, msg in enumerate(history):
                tag = msg.role.upper()
                preview = msg.content[:80].replace("\n", " ")
                print(f"  [{i}] {tag}: {preview}...")
            continue

        history.append(LLMMessage(role="user", content=user_input))

        try:
            if args.stream:
                print()
                collected: list[str] = []
                provider = llm.get_provider()
                async for chunk in provider.stream(
                    history,
                    max_tokens=args.max_tokens or config.llm_max_tokens,
                    temperature=args.temperature or config.llm_temperature,
                ):
                    print(chunk, end="", flush=True)
                    collected.append(chunk)
                print()
                assistant_text = "".join(collected)
            else:
                response = await llm.complete(
                    history,
                    max_tokens=args.max_tokens or config.llm_max_tokens,
                    temperature=args.temperature or config.llm_temperature,
                )
                assistant_text = response.content
                print(f"\n{assistant_text}")

            history.append(LLMMessage(role="assistant", content=assistant_text))

        except Exception as e:
            print(f"\n[error] {e}")
            history.pop()  # remove failed user message


# ---------------------------------------------------------------------------
# chat mode  (single-shot)
# ---------------------------------------------------------------------------


async def cmd_chat(args: argparse.Namespace) -> None:
    """Send a single message, print the response, and exit."""
    config = get_config()
    setup_logger("WARNING")

    llm = _build_llm_manager(config)

    messages: list[LLMMessage] = []
    system_prompt = args.system or f"You are {config.assistant_name}, a helpful AI assistant."
    messages.append(LLMMessage(role="system", content=system_prompt))

    if args.message:
        user_text = args.message
    else:
        user_text = sys.stdin.read().strip()
        if not user_text:
            print("Error: no message provided. Use -m or pipe via stdin.", file=sys.stderr)
            sys.exit(1)

    messages.append(LLMMessage(role="user", content=user_text))

    try:
        if args.stream:
            provider = llm.get_provider()
            async for chunk in provider.stream(
                messages,
                max_tokens=args.max_tokens or config.llm_max_tokens,
                temperature=args.temperature or config.llm_temperature,
            ):
                print(chunk, end="", flush=True)
            print()
        else:
            response = await llm.complete(
                messages,
                max_tokens=args.max_tokens or config.llm_max_tokens,
                temperature=args.temperature or config.llm_temperature,
            )
            print(response.content)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# run mode  (run prompt against a group)
# ---------------------------------------------------------------------------


async def cmd_run(args: argparse.Namespace) -> None:
    """Run a prompt against a registered group and print the result."""
    config = get_config()
    setup_logger(config.log_level if args.verbose else "WARNING")

    db = Database(config.db_path)
    await db.initialize()

    try:
        llm = _build_llm_manager(config)

        from nanogridbot.database.groups import GroupRepository

        group_repo = GroupRepository(db)
        groups = await group_repo.get_groups_by_folder(args.group)

        if not groups:
            print(f"Error: group '{args.group}' not found.", file=sys.stderr)
            sys.exit(1)

        group = groups[0]

        messages: list[LLMMessage] = []
        system_prompt = (
            f"You are {config.assistant_name}, an AI assistant for the group '{group.name}'. "
            f"Group folder: {group.folder}."
        )
        messages.append(LLMMessage(role="system", content=system_prompt))

        if args.context > 0:
            from nanogridbot.database.messages import MessageRepository

            msg_repo = MessageRepository(db)
            recent = await msg_repo.get_recent_messages(group.jid, limit=args.context)
            for msg in recent:
                role = "assistant" if msg.is_from_me else "user"
                name_prefix = f"[{msg.sender_name}] " if msg.sender_name else ""
                messages.append(LLMMessage(role=role, content=f"{name_prefix}{msg.content}"))

        prompt = args.prompt
        if not prompt:
            prompt = sys.stdin.read().strip()
        if not prompt:
            print("Error: no prompt provided. Use -p or pipe via stdin.", file=sys.stderr)
            sys.exit(1)

        messages.append(LLMMessage(role="user", content=prompt))

        response = await llm.complete(
            messages,
            max_tokens=args.max_tokens or config.llm_max_tokens,
            temperature=args.temperature or config.llm_temperature,
        )
        print(response.content)

        if args.send:
            channels = await create_channels(config, db)
            if channels:
                from nanogridbot.core.router import MessageRouter

                router = MessageRouter(config, db, channels)
                await router.send_response(group.jid, response.content)
                logger.info(f"Response sent to group {group.jid}")
            else:
                print("Warning: no channels configured, cannot send.", file=sys.stderr)

    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _add_common_llm_args(parser: argparse.ArgumentParser) -> None:
    """Add common LLM-related arguments to a subparser."""
    parser.add_argument("--model", type=str, default=None, help="Override LLM model name")
    parser.add_argument("--max-tokens", type=int, default=None, help="Max tokens for LLM response")
    parser.add_argument(
        "--temperature", type=float, default=None, help="Sampling temperature (0.0-2.0)"
    )
    parser.add_argument("--system", type=str, default=None, help="Custom system prompt")
    parser.add_argument("--stream", action="store_true", help="Stream the response token by token")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="nanogridbot",
        description="NanoGridBot - Multi-platform AI messaging bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  nanogridbot serve                          Start orchestrator + web dashboard\n"
            "  nanogridbot shell                          Interactive chat REPL\n"
            "  nanogridbot shell --stream                 Interactive chat with streaming\n"
            '  nanogridbot chat -m "Hello!"               Single-shot message\n'
            "  echo 'Summarize this' | nanogridbot chat   Pipe input\n"
            '  nanogridbot run -g mygroup -p "Status report"\n'
        ),
    )

    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0-alpha")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- serve ---
    serve_parser = subparsers.add_parser("serve", help="Start the full orchestrator + web dashboard")
    serve_parser.add_argument("--host", type=str, default=None, help="Web server host")
    serve_parser.add_argument("--port", type=int, default=None, help="Web server port")

    # --- shell ---
    shell_parser = subparsers.add_parser("shell", help="Interactive REPL for chatting with the LLM")
    _add_common_llm_args(shell_parser)

    # --- chat ---
    chat_parser = subparsers.add_parser("chat", help="Send a single message and print the response")
    chat_parser.add_argument(
        "-m", "--message", type=str, default=None, help="Message to send (or pipe via stdin)"
    )
    _add_common_llm_args(chat_parser)

    # --- run ---
    run_parser = subparsers.add_parser("run", help="Run a prompt against a registered group")
    run_parser.add_argument("-g", "--group", type=str, required=True, help="Group folder name")
    run_parser.add_argument(
        "-p", "--prompt", type=str, default=None, help="Prompt to run (or pipe via stdin)"
    )
    run_parser.add_argument(
        "--context", type=int, default=0, help="Number of recent messages to include as context"
    )
    run_parser.add_argument(
        "--send", action="store_true", help="Send the LLM response back to the group channel"
    )
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Show verbose logging")
    _add_common_llm_args(run_parser)

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
        "chat": cmd_chat,
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
