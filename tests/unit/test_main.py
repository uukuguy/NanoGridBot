"""Unit tests for __main__ module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.__main__ import create_channels, main, start_web_server


class TestCreateChannels:
    """Test create_channels function."""

    @pytest.mark.asyncio
    async def test_no_channels_available(self):
        """Test when no channels are available."""
        config = MagicMock()
        db = MagicMock()
        with patch("nanogridbot.__main__.ChannelRegistry") as mock_reg:
            mock_reg.available_channels.return_value = []
            result = await create_channels(config, db)
            assert result == []

    @pytest.mark.asyncio
    async def test_channel_not_enabled(self):
        """Test channel that is not enabled is skipped."""
        config = MagicMock()
        config.get_channel_config.return_value = {"enabled": False}
        config.model_dump.return_value = {}
        db = MagicMock()

        mock_type = MagicMock()
        mock_type.value = "telegram"

        with patch("nanogridbot.__main__.ChannelRegistry") as mock_reg:
            mock_reg.available_channels.return_value = [mock_type]
            result = await create_channels(config, db)
            assert result == []

    @pytest.mark.asyncio
    async def test_channel_enabled_and_created(self):
        """Test enabled channel is created."""
        config = MagicMock()
        config.get_channel_config.return_value = {"enabled": True}
        db = MagicMock()

        mock_type = MagicMock()
        mock_type.value = "telegram"
        mock_channel = MagicMock(spec=[])  # No configure/set_config

        with patch("nanogridbot.__main__.ChannelRegistry") as mock_reg:
            mock_reg.available_channels.return_value = [mock_type]
            mock_reg.create.return_value = mock_channel
            result = await create_channels(config, db)
            assert len(result) == 1
            assert result[0] is mock_channel

    @pytest.mark.asyncio
    async def test_channel_with_configure_method(self):
        """Test channel with configure method gets configured."""
        config = MagicMock()
        channel_config = {"enabled": True, "bot_token": "test"}
        config.get_channel_config.return_value = channel_config
        db = MagicMock()

        mock_type = MagicMock()
        mock_type.value = "telegram"
        mock_channel = MagicMock()
        mock_channel.configure = MagicMock()

        with patch("nanogridbot.__main__.ChannelRegistry") as mock_reg:
            mock_reg.available_channels.return_value = [mock_type]
            mock_reg.create.return_value = mock_channel
            result = await create_channels(config, db)
            mock_channel.configure.assert_called_once_with(channel_config)

    @pytest.mark.asyncio
    async def test_channel_with_set_config_method(self):
        """Test channel with set_config method gets configured."""
        config = MagicMock()
        channel_config = {"enabled": True}
        config.get_channel_config.return_value = channel_config
        db = MagicMock()

        mock_type = MagicMock()
        mock_type.value = "slack"
        mock_channel = MagicMock(spec=["set_config"])
        mock_channel.set_config = MagicMock()

        with patch("nanogridbot.__main__.ChannelRegistry") as mock_reg:
            mock_reg.available_channels.return_value = [mock_type]
            mock_reg.create.return_value = mock_channel
            result = await create_channels(config, db)
            mock_channel.set_config.assert_called_once_with(channel_config)

    @pytest.mark.asyncio
    async def test_channel_create_returns_none(self):
        """Test when ChannelRegistry.create returns None."""
        config = MagicMock()
        config.get_channel_config.return_value = {"enabled": True}
        db = MagicMock()

        mock_type = MagicMock()
        mock_type.value = "telegram"

        with patch("nanogridbot.__main__.ChannelRegistry") as mock_reg:
            mock_reg.available_channels.return_value = [mock_type]
            mock_reg.create.return_value = None
            result = await create_channels(config, db)
            assert result == []

    @pytest.mark.asyncio
    async def test_legacy_env_enabled(self):
        """Test channel enabled via legacy environment variable."""
        config = MagicMock()
        config.get_channel_config.return_value = {"enabled": False}
        config.model_dump.return_value = {"telegram_enabled": True}
        db = MagicMock()

        mock_type = MagicMock()
        mock_type.value = "telegram"
        mock_channel = MagicMock(spec=[])

        with patch("nanogridbot.__main__.ChannelRegistry") as mock_reg:
            mock_reg.available_channels.return_value = [mock_type]
            mock_reg.create.return_value = mock_channel
            result = await create_channels(config, db)
            assert len(result) == 1


class TestStartWebServer:
    """Test start_web_server function."""

    @pytest.mark.asyncio
    async def test_starts_uvicorn(self):
        """Test web server starts with uvicorn."""
        config = MagicMock()
        config.web_host = "127.0.0.1"
        config.web_port = 8080
        orchestrator = MagicMock()

        with patch("nanogridbot.__main__.create_app") as mock_create_app:
            with patch("nanogridbot.__main__.uvicorn", create=True) as mock_uvicorn:
                mock_server = MagicMock()
                mock_server.serve = AsyncMock()
                mock_uvicorn.Config.return_value = MagicMock()
                mock_uvicorn.Server.return_value = mock_server

                # Need to patch uvicorn import inside the function
                import nanogridbot.__main__ as main_mod

                with patch.dict("sys.modules", {"uvicorn": mock_uvicorn}):
                    await start_web_server(config, orchestrator)
                    mock_server.serve.assert_called_once()


class TestMain:
    """Test main function."""

    @pytest.mark.asyncio
    async def test_main_initializes_components(self, mock_config):
        """Test main initializes all components."""
        mock_db = MagicMock()
        mock_db.initialize = AsyncMock()
        mock_db.close = AsyncMock()

        mock_orchestrator = MagicMock()
        mock_orchestrator.start = AsyncMock(side_effect=asyncio.CancelledError)
        mock_orchestrator.stop = AsyncMock()

        with patch("nanogridbot.__main__.get_config", return_value=mock_config):
            with patch("nanogridbot.__main__.setup_logger"):
                with patch("nanogridbot.__main__.Database", return_value=mock_db):
                    with patch("nanogridbot.__main__.create_channels", new_callable=AsyncMock, return_value=[]):
                        with patch("nanogridbot.__main__.Orchestrator", return_value=mock_orchestrator):
                            with patch("nanogridbot.__main__.start_web_server", new_callable=AsyncMock):
                                with patch("asyncio.sleep", new_callable=AsyncMock):
                                    with patch("asyncio.get_event_loop") as mock_loop:
                                        mock_loop.return_value.add_signal_handler = MagicMock()
                                        try:
                                            await main()
                                        except (asyncio.CancelledError, Exception):
                                            pass

                                        mock_db.initialize.assert_called_once()
                                        mock_db.close.assert_called_once()
