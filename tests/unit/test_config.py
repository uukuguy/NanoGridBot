"""Tests for configuration module."""

import pytest
from pathlib import Path

from nanogridbot.config import Config, get_config, reload_config


class TestConfig:
    """Test Config class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = Config()
        assert config.project_name == "NanoGridBot"
        assert config.version == "0.1.0-alpha"
        assert config.debug is False

    def test_config_with_custom_values(self, temp_dir):
        """Test configuration with custom values."""
        config = Config(
            project_name="TestBot",
            debug=True,
            base_dir=temp_dir,
            data_dir=temp_dir / "data",
            store_dir=temp_dir / "store",
            groups_dir=temp_dir / "groups",
        )
        assert config.project_name == "TestBot"
        assert config.debug is True

    def test_directories_created(self, temp_dir):
        """Test that required directories are created."""
        config = Config(
            base_dir=temp_dir,
            data_dir=temp_dir / "data",
            store_dir=temp_dir / "store",
            groups_dir=temp_dir / "groups",
        )
        assert temp_dir.exists()
        assert (temp_dir / "data").exists()
        assert (temp_dir / "store").exists()
        assert (temp_dir / "groups").exists()

    def test_channel_config_telegram(self, temp_dir):
        """Test Telegram channel configuration."""
        config = Config(
            base_dir=temp_dir,
            data_dir=temp_dir / "data",
            store_dir=temp_dir / "store",
            groups_dir=temp_dir / "groups",
            telegram_bot_token="test_token",
        )
        telegram_config = config.get_channel_config("telegram")
        assert telegram_config["bot_token"] == "test_token"

    def test_channel_config_unknown(self, temp_dir):
        """Test unknown channel returns empty dict."""
        config = Config(
            base_dir=temp_dir,
            data_dir=temp_dir / "data",
            store_dir=temp_dir / "store",
            groups_dir=temp_dir / "groups",
        )
        unknown_config = config.get_channel_config("unknown")
        assert unknown_config == {}


class TestConfigGlobal:
    """Test global config functions."""

    def test_get_config(self):
        """Test get_config returns Config instance."""
        config = get_config()
        assert isinstance(config, Config)

    def test_reload_config(self):
        """Test reload_config creates new Config."""
        config1 = get_config()
        config2 = reload_config()
        assert isinstance(config2, Config)
