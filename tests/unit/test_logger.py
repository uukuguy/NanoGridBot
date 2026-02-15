"""Unit tests for logger module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from loguru import logger

from nanogridbot.logger import (
    DEFAULT_FORMAT,
    STRUCTURED_FORMAT,
    StructuredLogger,
    get_logger,
    get_structured_logger,
    init,
    setup_logger,
)


class TestSetupLogger:
    """Test setup_logger function."""

    def test_setup_logger_default(self, mock_config):
        """Test default logger setup."""
        with patch("nanogridbot.logger.get_config", return_value=mock_config):
            setup_logger()
            # Should not raise

    def test_setup_logger_with_level(self, mock_config):
        """Test logger setup with custom level."""
        with patch("nanogridbot.logger.get_config", return_value=mock_config):
            setup_logger(log_level="DEBUG")

    def test_setup_logger_with_file(self, mock_config, tmp_path):
        """Test logger setup with file output."""
        log_file = tmp_path / "logs" / "test.log"
        with patch("nanogridbot.logger.get_config", return_value=mock_config):
            setup_logger(log_file=log_file)
            assert log_file.parent.exists()

    def test_setup_logger_structured(self, mock_config):
        """Test structured logging mode."""
        with patch("nanogridbot.logger.get_config", return_value=mock_config):
            setup_logger(structured=True)

    def test_setup_logger_structured_with_file(self, mock_config, tmp_path):
        """Test structured logging with file output."""
        log_file = tmp_path / "structured.log"
        with patch("nanogridbot.logger.get_config", return_value=mock_config):
            setup_logger(log_file=log_file, structured=True)

    def test_setup_logger_custom_format(self, mock_config):
        """Test logger with custom format string."""
        with patch("nanogridbot.logger.get_config", return_value=mock_config):
            setup_logger(format_string="{message}")

    def test_setup_logger_custom_rotation_retention(self, mock_config, tmp_path):
        """Test logger with custom rotation and retention."""
        log_file = tmp_path / "rotated.log"
        with patch("nanogridbot.logger.get_config", return_value=mock_config):
            setup_logger(
                log_file=log_file,
                rotation="5 MB",
                retention="3 days",
            )


class TestGetLogger:
    """Test get_logger function."""

    def test_get_logger_with_name(self):
        """Test getting named logger."""
        result = get_logger("test_module")
        assert result is not None

    def test_get_logger_without_name(self):
        """Test getting default logger."""
        result = get_logger()
        assert result is logger

    def test_get_logger_none_name(self):
        """Test getting logger with None name."""
        result = get_logger(None)
        assert result is logger


class TestInit:
    """Test init function."""

    def test_init_returns_logger(self, mock_config):
        """Test init returns logger instance."""
        with patch("nanogridbot.logger.get_config", return_value=mock_config):
            result = init()
            assert result is logger


class TestStructuredLogger:
    """Test StructuredLogger class."""

    def test_init(self):
        """Test StructuredLogger initialization."""
        sl = StructuredLogger("test_module")
        assert sl.module == "test_module"

    def test_debug(self, capsys):
        """Test debug logging."""
        sl = StructuredLogger("test")
        sl.debug("debug message")

    def test_info(self):
        """Test info logging."""
        sl = StructuredLogger("test")
        sl.info("info message")

    def test_warning(self):
        """Test warning logging."""
        sl = StructuredLogger("test")
        sl.warning("warning message")

    def test_error(self):
        """Test error logging."""
        sl = StructuredLogger("test")
        sl.error("error message")

    def test_critical(self):
        """Test critical logging."""
        sl = StructuredLogger("test")
        sl.critical("critical message")

    def test_log_with_context(self):
        """Test logging with context kwargs."""
        sl = StructuredLogger("test")
        sl.info("message", user="alice", action="login")

    def test_log_without_context(self):
        """Test logging without context."""
        sl = StructuredLogger("test")
        sl.info("plain message")

    def test_exception(self):
        """Test exception logging."""
        sl = StructuredLogger("test")
        try:
            raise ValueError("test error")
        except ValueError:
            sl.exception("caught error")

    def test_exception_with_context(self):
        """Test exception logging with context."""
        sl = StructuredLogger("test")
        try:
            raise ValueError("test error")
        except ValueError:
            sl.exception("caught error", user="bob", code=500)

    def test_exception_without_context(self):
        """Test exception logging without context."""
        sl = StructuredLogger("test")
        sl.exception("no context exception")

    def test_log_formats_context_string(self):
        """Test that _log formats context as key=value pairs."""
        sl = StructuredLogger("test")
        with patch.object(sl._logger, "info") as mock_info:
            sl.info("msg", key1="val1", key2="val2")
            call_args = mock_info.call_args[0][0]
            assert "key1=val1" in call_args
            assert "key2=val2" in call_args
            assert "msg |" in call_args


class TestGetStructuredLogger:
    """Test get_structured_logger function."""

    def test_returns_structured_logger(self):
        """Test returns StructuredLogger instance."""
        result = get_structured_logger("my_module")
        assert isinstance(result, StructuredLogger)
        assert result.module == "my_module"
