use serde::{Deserialize, Serialize};

/// Supported messaging platforms.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ChannelType {
    Whatsapp,
    Telegram,
    Slack,
    Discord,
    Qq,
    Feishu,
    Wecom,
    Dingtalk,
}

impl std::fmt::Display for ChannelType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = match self {
            Self::Whatsapp => "whatsapp",
            Self::Telegram => "telegram",
            Self::Slack => "slack",
            Self::Discord => "discord",
            Self::Qq => "qq",
            Self::Feishu => "feishu",
            Self::Wecom => "wecom",
            Self::Dingtalk => "dingtalk",
        };
        write!(f, "{s}")
    }
}

/// Message sender role.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum MessageRole {
    #[default]
    User,
    Assistant,
    System,
}

/// Task schedule type.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ScheduleType {
    Cron,
    Interval,
    Once,
}

/// Scheduled task status.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TaskStatus {
    #[default]
    Active,
    Paused,
    Completed,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn channel_type_serde_roundtrip() {
        for ct in [
            ChannelType::Whatsapp,
            ChannelType::Telegram,
            ChannelType::Slack,
            ChannelType::Discord,
            ChannelType::Qq,
            ChannelType::Feishu,
            ChannelType::Wecom,
            ChannelType::Dingtalk,
        ] {
            let json = serde_json::to_string(&ct).unwrap();
            let back: ChannelType = serde_json::from_str(&json).unwrap();
            assert_eq!(ct, back);
        }
    }

    #[test]
    fn channel_type_serializes_lowercase() {
        assert_eq!(
            serde_json::to_string(&ChannelType::Whatsapp).unwrap(),
            "\"whatsapp\""
        );
        assert_eq!(serde_json::to_string(&ChannelType::Qq).unwrap(), "\"qq\"");
    }

    #[test]
    fn message_role_default_is_user() {
        assert_eq!(MessageRole::default(), MessageRole::User);
    }

    #[test]
    fn message_role_serde_roundtrip() {
        for role in [
            MessageRole::User,
            MessageRole::Assistant,
            MessageRole::System,
        ] {
            let json = serde_json::to_string(&role).unwrap();
            let back: MessageRole = serde_json::from_str(&json).unwrap();
            assert_eq!(role, back);
        }
    }

    #[test]
    fn schedule_type_serde_roundtrip() {
        for st in [
            ScheduleType::Cron,
            ScheduleType::Interval,
            ScheduleType::Once,
        ] {
            let json = serde_json::to_string(&st).unwrap();
            let back: ScheduleType = serde_json::from_str(&json).unwrap();
            assert_eq!(st, back);
        }
    }

    #[test]
    fn task_status_default_is_active() {
        assert_eq!(TaskStatus::default(), TaskStatus::Active);
    }

    #[test]
    fn task_status_serde_roundtrip() {
        for ts in [
            TaskStatus::Active,
            TaskStatus::Paused,
            TaskStatus::Completed,
        ] {
            let json = serde_json::to_string(&ts).unwrap();
            let back: TaskStatus = serde_json::from_str(&json).unwrap();
            assert_eq!(ts, back);
        }
    }
}
