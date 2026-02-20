use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::enums::{ScheduleType, TaskStatus};

/// Scheduled task configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScheduledTask {
    #[serde(default)]
    pub id: Option<i64>,
    pub group_folder: String,
    pub prompt: String,
    pub schedule_type: ScheduleType,
    pub schedule_value: String,
    #[serde(default)]
    pub status: TaskStatus,
    #[serde(default)]
    pub next_run: Option<DateTime<Utc>>,
    #[serde(default = "default_context_mode")]
    pub context_mode: String,
    #[serde(default)]
    pub target_chat_jid: Option<String>,
}

fn default_context_mode() -> String {
    "group".to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn task_serde_roundtrip() {
        let task = ScheduledTask {
            id: Some(1),
            group_folder: "test_group".to_string(),
            prompt: "Run daily report".to_string(),
            schedule_type: ScheduleType::Cron,
            schedule_value: "0 9 * * *".to_string(),
            status: TaskStatus::Active,
            next_run: Some(Utc::now()),
            context_mode: "group".to_string(),
            target_chat_jid: Some("telegram:123".to_string()),
        };

        let json = serde_json::to_string(&task).unwrap();
        let back: ScheduledTask = serde_json::from_str(&json).unwrap();
        assert_eq!(back.id, Some(1));
        assert_eq!(back.schedule_type, ScheduleType::Cron);
        assert_eq!(back.status, TaskStatus::Active);
    }

    #[test]
    fn task_defaults() {
        let json = r#"{
            "group_folder": "g1",
            "prompt": "hello",
            "schedule_type": "interval",
            "schedule_value": "60"
        }"#;
        let task: ScheduledTask = serde_json::from_str(json).unwrap();
        assert!(task.id.is_none());
        assert_eq!(task.status, TaskStatus::Active);
        assert_eq!(task.context_mode, "group");
        assert!(task.next_run.is_none());
        assert!(task.target_chat_jid.is_none());
    }
}
