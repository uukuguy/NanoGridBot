"""User channel configuration database operations."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nanogridbot.database.connection import Database

from nanogridbot.types import ChannelType, UserChannelConfig


class UserChannelConfigRepository:
    """Repository for user channel configuration storage."""

    def __init__(self, database: "Database") -> None:
        """Initialize repository.

        Args:
            database: Database connection instance.
        """
        self._db = database

    async def save_config(self, config: UserChannelConfig) -> None:
        """Save or update user channel configuration.

        Args:
            config: User channel configuration to save.
        """
        now = datetime.utcnow().isoformat()

        await self._db.execute(
            """
            INSERT OR REPLACE INTO user_channel_configs
            (user_id, channel, telegram_bot_token, slack_bot_token, slack_signing_secret,
             discord_bot_token, whatsapp_session_path, qq_host, qq_port,
             feishu_app_id, feishu_app_secret, wecom_corp_id, wecom_agent_id, wecom_secret,
             dingtalk_app_key, dingtalk_app_secret, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                config.user_id,
                config.channel.value if isinstance(config.channel, ChannelType) else config.channel,
                config.telegram_bot_token,
                config.slack_bot_token,
                config.slack_signing_secret,
                config.discord_bot_token,
                config.whatsapp_session_path,
                config.qq_host,
                config.qq_port,
                config.feishu_app_id,
                config.feishu_app_secret,
                config.wecom_corp_id,
                config.wecom_agent_id,
                config.wecom_secret,
                config.dingtalk_app_key,
                config.dingtalk_app_secret,
                int(config.is_active),
                config.created_at.isoformat() if config.created_at else now,
                now,
            ),
        )
        await self._db.commit()

    async def get_config(self, user_id: int, channel: ChannelType | str) -> UserChannelConfig | None:
        """Get user channel configuration.

        Args:
            user_id: User ID.
            channel: Channel type.

        Returns:
            UserChannelConfig if found, None otherwise.
        """
        channel_value = channel.value if isinstance(channel, ChannelType) else channel

        row = await self._db.fetchone(
            """
            SELECT * FROM user_channel_configs
            WHERE user_id = ? AND channel = ?
            """,
            (user_id, channel_value),
        )
        return self._row_to_config(row) if row else None

    async def get_configs_by_user(self, user_id: int) -> list[UserChannelConfig]:
        """Get all channel configurations for a user.

        Args:
            user_id: User ID.

        Returns:
            List of user channel configurations.
        """
        rows = await self._db.fetchall(
            """
            SELECT * FROM user_channel_configs
            WHERE user_id = ? AND is_active = 1
            """,
            (user_id,),
        )
        return [self._row_to_config(row) for row in rows]

    async def get_active_configs(self) -> list[UserChannelConfig]:
        """Get all active channel configurations.

        Returns:
            List of all active channel configurations.
        """
        rows = await self._db.fetchall(
            """
            SELECT * FROM user_channel_configs
            WHERE is_active = 1
            """,
        )
        return [self._row_to_config(row) for row in rows]

    async def delete_config(self, user_id: int, channel: ChannelType | str) -> bool:
        """Delete user channel configuration.

        Args:
            user_id: User ID.
            channel: Channel type.

        Returns:
            True if deleted, False if not found.
        """
        channel_value = channel.value if isinstance(channel, ChannelType) else channel

        cursor = await self._db.execute(
            "DELETE FROM user_channel_configs WHERE user_id = ? AND channel = ?",
            (user_id, channel_value),
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def set_active(self, user_id: int, channel: ChannelType | str, is_active: bool) -> None:
        """Set channel configuration active status.

        Args:
            user_id: User ID.
            channel: Channel type.
            is_active: Active status.
        """
        channel_value = channel.value if isinstance(channel, ChannelType) else channel
        now = datetime.utcnow().isoformat()

        await self._db.execute(
            "UPDATE user_channel_configs SET is_active = ?, updated_at = ? WHERE user_id = ? AND channel = ?",
            (int(is_active), now, user_id, channel_value),
        )
        await self._db.commit()

    @staticmethod
    def _row_to_config(row: dict[str, Any]) -> UserChannelConfig:
        """Convert database row to UserChannelConfig model.

        Args:
            row: Database row dictionary.

        Returns:
            UserChannelConfig instance.
        """
        return UserChannelConfig(
            user_id=row["user_id"],
            channel=row["channel"],
            telegram_bot_token=row.get("telegram_bot_token"),
            slack_bot_token=row.get("slack_bot_token"),
            slack_signing_secret=row.get("slack_signing_secret"),
            discord_bot_token=row.get("discord_bot_token"),
            whatsapp_session_path=row.get("whatsapp_session_path"),
            qq_host=row.get("qq_host"),
            qq_port=row.get("qq_port"),
            feishu_app_id=row.get("feishu_app_id"),
            feishu_app_secret=row.get("feishu_app_secret"),
            wecom_corp_id=row.get("wecom_corp_id"),
            wecom_agent_id=row.get("wecom_agent_id"),
            wecom_secret=row.get("wecom_secret"),
            dingtalk_app_key=row.get("dingtalk_app_key"),
            dingtalk_app_secret=row.get("dingtalk_app_secret"),
            is_active=bool(row.get("is_active", 1)),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
        )
