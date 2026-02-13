"""Command-line interface for NanoGridBot."""

import argparse
import asyncio
import signal
import sys
from typing import Any

from loguru import logger

from nanogridbot import setup_logger
from nanogridbot.channels import (
    ChannelRegistry,
)
from nanogridbot.config import get_config
from nanogridbot.core.orchestrator import Orchestrator
from nanogridbot.database import Database
from nanogridbot.web.app import create_app


async def create_channels(config: Any, db: Database) -> list[Any]:
    """Create and configure channel instances.

    Args:
        config: Application configuration
        db: Database instance

    Returns:
        List of configured channel instances
    """
    channels = []
    available = ChannelRegistry.available_channels()

    # Check each channel type and create if configured
    for channel_type in available:
        channel_config = config.get_channel_config(channel_type.value)

        # Check if channel is enabled
        enabled = channel_config.get("enabled", False)
        if not enabled:
            # Check environment variable for legacy support
            env_key = f"{channel_type.value.upper()}_ENABLED"
            enabled = config.model_dump().get(env_key.lower(), False)

        if enabled:
            # Create channel with config
            channel = ChannelRegistry.create(channel_type)
            if channel:
                # Pass config to channel if it accepts config parameter
                if hasattr(channel, "configure"):
                    channel.configure(channel_config)
                elif hasattr(channel, "set_config"):
                    channel.set_config(channel_config)
                channels.append(channel)
                logger.info(f"Created channel: {channel_type.value}")

    return channels


async def start_web_server(config: Any, orchestrator: Orchestrator, host: str | None = None, port: int | None = None) -> None:
    """Start the web server.

    Args:
        config: Application configuration
        orchestrator: Orchestrator instance
        host: Override host from config
        port: Override port from config
    """
    import uvicorn

    # Create FastAPI app with orchestrator
    app = create_app(orchestrator)

    # Configure uvicorn
    server_config = uvicorn.Config(
        app,
        host=host or config.web_host,
        port=port or config.web_port,
        log_level="info",
    )

    server = uvicorn.Server(server_config)
    await server.serve()


async def run_async(args: argparse.Namespace) -> None:
    """Run the application asynchronously.

    Args:
        args: Parsed command-line arguments
    """
    # Setup logging
    config = get_config()
    setup_logger(config.log_level)

    logger.info("Starting NanoGridBot")
    logger.info(f"Version: 0.1.0-alpha")
    logger.info(f"Web server: {args.host or config.web_host}:{args.port or config.web_port}")

    # Initialize database
    db = Database(config.db_path)
    await db.initialize()

    try:
        # Create channels
        channels = await create_channels(config, db)

        # Create orchestrator
        orchestrator = Orchestrator(config, db, channels)

        # Start web server in background
        web_task = asyncio.create_task(start_web_server(config, orchestrator, args.host, args.port))

        # Wait for web server to start
        await asyncio.sleep(1)

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        stop_event = asyncio.Event()

        def signal_handler() -> None:
            logger.info("Received shutdown signal")
            stop_event.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)

        # Start orchestrator (blocking)
        orchestrator_task = asyncio.create_task(orchestrator.start())

        # Wait for either signal or error
        try:
            await asyncio.gather(orchestrator_task, web_task, stop_event.wait())
        except Exception as e:
            logger.error(f"Error in main loop: {e}")

        # Stop orchestrator
        await orchestrator.stop()

    finally:
        # Close database
        await db.close()
        logger.info("NanoGridBot stopped")


def main() -> int:
    """Main entry point for CLI.

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="NanoGridBot - Multi-platform messaging bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0-alpha",
    )

    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Web server host (default: from config)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Web server port (default: from config)",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Override log level if debug is set
    if args.debug:
        import os
        os.environ["LOG_LEVEL"] = "DEBUG"

    try:
        asyncio.run(run_async(args))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
