"""Logging setup for NanoGridBot."""

import sys
from pathlib import Path

from loguru import logger

from nanogridbot.config import get_config


def setup_logger(
    log_level: str | None = None,
    log_file: Path | None = None,
    rotation: str | None = None,
    retention: str | None = None,
    format_string: str | None = None,
) -> None:
    """
    Configure loguru logger for the application.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        rotation: Log rotation setting (e.g., "10 MB", "1 day")
        retention: Log retention setting (e.g., "7 days", "1 month")
        format_string: Custom log format string
    """
    config = get_config()

    # Use provided values or fall back to config
    level = log_level or config.log_level
    rotation = rotation or config.log_rotation
    retention = retention or config.log_retention
    format_str = format_string or config.log_format

    # Remove default handler
    logger.remove()

    # Console handler with color
    logger.add(
        sys.stderr,
        format=format_str,
        level=level,
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # File handler if log_file is specified
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file,
            format=format_str,
            level=level,
            rotation=rotation,
            retention=retention,
            compression="zip",
            backtrace=True,
            diagnose=True,
        )

    # Set global logger level
    logger.level(level)


def get_logger(name: str | None = None):
    """
    Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    if name:
        return logger.bind(name=name)
    return logger


# Convenience function for quick setup
def init():
    """Initialize logger with default configuration."""
    setup_logger()
    return logger
