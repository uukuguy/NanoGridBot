"""Configuration management for NanoGridBot."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Project settings
    project_name: str = "NanoGridBot"
    version: str = "0.1.0-alpha"
    debug: bool = False

    # Paths
    base_dir: Path = Field(default_factory=lambda: Path.cwd())
    data_dir: Path = Field(default_factory=lambda: Path.cwd() / "data")
    store_dir: Path = Field(default_factory=lambda: Path.cwd() / "store")
    groups_dir: Path = Field(default_factory=lambda: Path.cwd() / "groups")

    # Database
    db_path: Path = Field(default_factory=lambda: Path.cwd() / "store" / "messages.db")

    # API keys (can be set via environment variables or direct assignment)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Channel configurations
    telegram_bot_token: str | None = None
    slack_bot_token: str | None = None
    slack_signing_secret: str | None = None
    discord_bot_token: str | None = None

    # WhatsApp (Baileys)
    whatsapp_session_path: Path = Field(
        default_factory=lambda: Path.cwd() / "store" / "whatsapp_session"
    )

    # QQ (NoneBot2)
    qq_host: str = "127.0.0.1"
    qq_port: int = 20000

    # Feishu
    feishu_app_id: str | None = None
    feishu_app_secret: str | None = None

    # WeCom
    wecom_corp_id: str | None = None
    wecom_agent_id: str | None = None
    wecom_secret: str | None = None

    # DingTalk
    dingtalk_app_key: str | None = None
    dingtalk_app_secret: str | None = None

    # Claude settings
    claude_api_url: str = "https://api.anthropic.com"
    claude_api_version: str = "2023-06-01"
    claude_model: str = "claude-sonnet-4-20250514"
    claude_max_tokens: int = 4096

    # Container settings
    container_timeout: int = 300
    container_max_output_size: int = 100000
    container_max_concurrent_containers: int = 5
    container_image: str = "nanogridbot-agent:latest"

    # Assistant settings
    assistant_name: str = "Andy"
    trigger_pattern: str | None = None

    # Poll interval (ms)
    poll_interval: int = 2000

    # Rate limiting
    max_messages_per_minute: int = 10

    # Logging
    log_level: str = "INFO"
    log_format: str = (
        "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )
    log_rotation: str = "10 MB"
    log_retention: str = "7 days"

    # Web server
    web_host: str = "0.0.0.0"
    web_port: int = 8080

    # Performance tuning
    message_cache_size: int = 1000
    batch_size: int = 100
    db_connection_pool_size: int = 5
    ipc_file_buffer_size: int = 8192

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._create_directories()

    def _create_directories(self) -> None:
        """Create required directories if they don't exist."""
        directories = [
            self.data_dir,
            self.store_dir,
            self.groups_dir,
            self.data_dir / "ipc",
            self.data_dir / "sessions",
            self.data_dir / "env",
            self.store_dir / "auth",
            self.whatsapp_session_path,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def get_channel_config(self, channel: str) -> dict:
        """Get configuration for a specific channel."""
        return {
            "telegram": {
                "bot_token": self.telegram_bot_token,
            },
            "slack": {
                "bot_token": self.slack_bot_token,
                "signing_secret": self.slack_signing_secret,
            },
            "discord": {
                "bot_token": self.discord_bot_token,
            },
            "whatsapp": {
                "session_path": str(self.whatsapp_session_path),
            },
            "qq": {
                "host": self.qq_host,
                "port": self.qq_port,
            },
            "feishu": {
                "app_id": self.feishu_app_id,
                "app_secret": self.feishu_app_secret,
            },
            "wecom": {
                "corp_id": self.wecom_corp_id,
                "agent_id": self.wecom_agent_id,
                "secret": self.wecom_secret,
            },
            "dingtalk": {
                "app_key": self.dingtalk_app_key,
                "app_secret": self.dingtalk_app_secret,
            },
        }.get(channel, {})


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config() -> Config:
    """Reload configuration from environment."""
    global _config
    _config = Config()
    return _config
