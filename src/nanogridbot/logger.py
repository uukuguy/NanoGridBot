"""Logging setup for NanoGridBot."""

import json
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from nanogridbot.config import get_config

# Default format with contextual information
DEFAULT_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

# Structured format for JSON logging
STRUCTURED_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | " "{level: <8} | " "{name}:{function}:{line} | " "{message}"
)


def setup_logger(
    log_level: str | None = None,
    log_file: Path | None = None,
    rotation: str | None = None,
    retention: str | None = None,
    format_string: str | None = None,
    structured: bool = False,
) -> None:
    """
    Configure loguru logger for the application.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        rotation: Log rotation setting (e.g., "10 MB", "1 day")
        retention: Log retention setting (e.g., "7 days", "1 month")
        format_string: Custom log format string
        structured: Enable structured (JSON) logging
    """
    config = get_config()

    # Use provided values or fall back to config
    level = log_level or config.log_level
    rotation = rotation or config.log_rotation
    retention = retention or config.log_retention
    format_str = format_string or config.log_format

    # Remove default handler
    logger.remove()

    # Determine format
    if structured:
        # Use simpler format for structured logging
        console_format = STRUCTURED_FORMAT
    else:
        console_format = format_str or DEFAULT_FORMAT

    # Console handler with color (only if not structured)
    logger.add(
        sys.stderr,
        format=console_format,
        level=level,
        colorize=not structured,
        backtrace=True,
        diagnose=True,
    )

    # File handler if log_file is specified
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Use structured format for file logs
        file_format = STRUCTURED_FORMAT if structured else format_str

        logger.add(
            log_file,
            format=file_format,
            level=level,
            rotation=rotation,
            retention=retention,
            compression="zip",
            backtrace=True,
            diagnose=True,
            serialize=True if structured else False,
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


class StructuredLogger:
    """Structured logger for consistent log formatting across modules.

    Provides methods for logging with consistent context and structure.
    """

    def __init__(self, module: str):
        """Initialize structured logger.

        Args:
            module: Module name (typically __name__)
        """
        self.module = module
        self._logger = logger.bind(module=module)

    def _log(self, level: str, message: str, **context: Any) -> None:
        """Log with structured context.

        Args:
            level: Log level
            message: Log message
            **context: Additional context to log
        """
        if context:
            # Format context as key=value pairs
            context_str = " | ".join(f"{k}={v}" for k, v in context.items())
            full_message = f"{message} | {context_str}"
        else:
            full_message = message

        getattr(self._logger, level.lower())(full_message)

    def debug(self, message: str, **context: Any) -> None:
        """Log debug message with context."""
        self._log("DEBUG", message, **context)

    def info(self, message: str, **context: Any) -> None:
        """Log info message with context."""
        self._log("INFO", message, **context)

    def warning(self, message: str, **context: Any) -> None:
        """Log warning message with context."""
        self._log("WARNING", message, **context)

    def error(self, message: str, **context: Any) -> None:
        """Log error message with context."""
        self._log("ERROR", message, **context)

    def critical(self, message: str, **context: Any) -> None:
        """Log critical message with context."""
        self._log("CRITICAL", message, **context)

    def exception(self, message: str, **context: Any) -> None:
        """Log exception with traceback."""
        if context:
            context_str = " | ".join(f"{k}={v}" for k, v in context.items())
            full_message = f"{message} | {context_str}"
        else:
            full_message = message
        self._logger.exception(full_message)


def get_structured_logger(module: str) -> StructuredLogger:
    """Get a structured logger instance.

    Args:
        module: Module name (typically __name__)

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(module)
