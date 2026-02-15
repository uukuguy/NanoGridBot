"""Unit tests for channel factory module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.channels.factory import ChannelFactory
from nanogridbot.types import ChannelType


@pytest.fixture(autouse=True)
def clear_factory():
    """Clear factory instances before each test."""
    ChannelFactory.clear()
    yield
    ChannelFactory.clear()


class TestChannelFactory:
    """Test ChannelFactory class."""

    def test_create_returns_none_for_unknown(self):
        """Test create returns None for unregistered channel."""
        with patch("nanogridbot.channels.factory.ChannelRegistry.create", return_value=None):
            result = ChannelFactory.create(ChannelType.TELEGRAM)
            assert result is None

    def test_create_caches_instance(self):
        """Test create caches the channel instance."""
        mock_channel = MagicMock()
        with patch("nanogridbot.channels.factory.ChannelRegistry.create", return_value=mock_channel) as mock_create:
            first = ChannelFactory.create(ChannelType.TELEGRAM)
            second = ChannelFactory.create(ChannelType.TELEGRAM)
            assert first is second
            # Registry.create should only be called once
            mock_create.assert_called_once()

    def test_get_existing(self):
        """Test get returns existing instance."""
        mock_channel = MagicMock()
        with patch("nanogridbot.channels.factory.ChannelRegistry.create", return_value=mock_channel):
            ChannelFactory.create(ChannelType.SLACK)
            result = ChannelFactory.get(ChannelType.SLACK)
            assert result is mock_channel

    def test_get_nonexistent(self):
        """Test get returns None for non-existing."""
        result = ChannelFactory.get(ChannelType.TELEGRAM)
        assert result is None

    def test_get_or_create(self):
        """Test get_or_create creates if not exists."""
        mock_channel = MagicMock()
        with patch("nanogridbot.channels.factory.ChannelRegistry.create", return_value=mock_channel):
            result = ChannelFactory.get_or_create(ChannelType.DISCORD)
            assert result is mock_channel

    def test_get_or_create_returns_existing(self):
        """Test get_or_create returns existing instance."""
        mock_channel = MagicMock()
        with patch("nanogridbot.channels.factory.ChannelRegistry.create", return_value=mock_channel):
            ChannelFactory.create(ChannelType.DISCORD)
            result = ChannelFactory.get_or_create(ChannelType.DISCORD)
            assert result is mock_channel

    def test_remove(self):
        """Test remove deletes instance."""
        mock_channel = MagicMock()
        with patch("nanogridbot.channels.factory.ChannelRegistry.create", return_value=mock_channel):
            ChannelFactory.create(ChannelType.TELEGRAM)
            ChannelFactory.remove(ChannelType.TELEGRAM)
            assert ChannelFactory.get(ChannelType.TELEGRAM) is None

    def test_remove_nonexistent(self):
        """Test remove on non-existing is safe."""
        ChannelFactory.remove(ChannelType.TELEGRAM)  # Should not raise

    def test_clear(self):
        """Test clear removes all instances."""
        mock_channel = MagicMock()
        with patch("nanogridbot.channels.factory.ChannelRegistry.create", return_value=mock_channel):
            ChannelFactory.create(ChannelType.TELEGRAM)
            ChannelFactory.create(ChannelType.SLACK)
            ChannelFactory.clear()
            assert ChannelFactory.get(ChannelType.TELEGRAM) is None
            assert ChannelFactory.get(ChannelType.SLACK) is None

    @pytest.mark.asyncio
    async def test_connect_all(self):
        """Test connect_all connects all channels."""
        ch1 = MagicMock()
        ch1.connect = AsyncMock()
        ch2 = MagicMock()
        ch2.connect = AsyncMock()

        ChannelFactory._instances = {
            ChannelType.TELEGRAM: ch1,
            ChannelType.SLACK: ch2,
        }

        results = await ChannelFactory.connect_all()
        assert results[ChannelType.TELEGRAM] is True
        assert results[ChannelType.SLACK] is True

    @pytest.mark.asyncio
    async def test_connect_all_with_failure(self):
        """Test connect_all handles connection failures."""
        ch1 = MagicMock()
        ch1.connect = AsyncMock(side_effect=Exception("fail"))

        ChannelFactory._instances = {ChannelType.TELEGRAM: ch1}

        results = await ChannelFactory.connect_all()
        assert results[ChannelType.TELEGRAM] is False

    @pytest.mark.asyncio
    async def test_disconnect_all(self):
        """Test disconnect_all disconnects all channels."""
        ch1 = MagicMock()
        ch1.disconnect = AsyncMock()

        ChannelFactory._instances = {ChannelType.TELEGRAM: ch1}

        await ChannelFactory.disconnect_all()
        ch1.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_all_handles_errors(self):
        """Test disconnect_all handles errors gracefully."""
        ch1 = MagicMock()
        ch1.disconnect = AsyncMock(side_effect=Exception("fail"))

        ChannelFactory._instances = {ChannelType.TELEGRAM: ch1}

        await ChannelFactory.disconnect_all()  # Should not raise

    def test_available_channels(self):
        """Test available_channels delegates to registry."""
        with patch("nanogridbot.channels.factory.ChannelRegistry.available_channels", return_value=[ChannelType.TELEGRAM]):
            result = ChannelFactory.available_channels()
            assert result == [ChannelType.TELEGRAM]

    def test_connected_channels(self):
        """Test connected_channels returns connected ones."""
        ch1 = MagicMock()
        ch1.is_connected = True
        ch2 = MagicMock()
        ch2.is_connected = False

        ChannelFactory._instances = {
            ChannelType.TELEGRAM: ch1,
            ChannelType.SLACK: ch2,
        }

        result = ChannelFactory.connected_channels()
        assert ChannelType.TELEGRAM in result
        assert ChannelType.SLACK not in result
