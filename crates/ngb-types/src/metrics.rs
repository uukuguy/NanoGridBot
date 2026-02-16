use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Container execution metric.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContainerMetric {
    #[serde(default)]
    pub id: Option<i64>,
    pub group_folder: String,
    pub channel: String,
    pub start_time: DateTime<Utc>,
    #[serde(default)]
    pub end_time: Option<DateTime<Utc>>,
    #[serde(default)]
    pub duration_seconds: Option<f64>,
    #[serde(default = "default_status")]
    pub status: String,
    #[serde(default)]
    pub prompt_tokens: Option<i64>,
    #[serde(default)]
    pub completion_tokens: Option<i64>,
    #[serde(default)]
    pub total_tokens: Option<i64>,
    #[serde(default)]
    pub error: Option<String>,
}

fn default_status() -> String {
    "running".to_string()
}

/// Request statistics metric.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RequestMetric {
    #[serde(default)]
    pub id: Option<i64>,
    pub channel: String,
    #[serde(default)]
    pub group_folder: Option<String>,
    pub timestamp: DateTime<Utc>,
    pub request_type: String,
    pub success: bool,
    #[serde(default)]
    pub error: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn container_metric_serde_roundtrip() {
        let metric = ContainerMetric {
            id: Some(1),
            group_folder: "test".to_string(),
            channel: "telegram".to_string(),
            start_time: Utc::now(),
            end_time: Some(Utc::now()),
            duration_seconds: Some(2.5),
            status: "success".to_string(),
            prompt_tokens: Some(100),
            completion_tokens: Some(200),
            total_tokens: Some(300),
            error: None,
        };

        let json = serde_json::to_string(&metric).unwrap();
        let back: ContainerMetric = serde_json::from_str(&json).unwrap();
        assert_eq!(back.id, Some(1));
        assert_eq!(back.status, "success");
        assert_eq!(back.total_tokens, Some(300));
    }

    #[test]
    fn container_metric_defaults() {
        let json = r#"{
            "group_folder": "g1",
            "channel": "slack",
            "start_time": "2025-01-01T00:00:00Z"
        }"#;
        let metric: ContainerMetric = serde_json::from_str(json).unwrap();
        assert!(metric.id.is_none());
        assert_eq!(metric.status, "running");
        assert!(metric.end_time.is_none());
        assert!(metric.prompt_tokens.is_none());
    }

    #[test]
    fn request_metric_serde_roundtrip() {
        let metric = RequestMetric {
            id: Some(1),
            channel: "discord".to_string(),
            group_folder: Some("test".to_string()),
            timestamp: Utc::now(),
            request_type: "message".to_string(),
            success: true,
            error: None,
        };

        let json = serde_json::to_string(&metric).unwrap();
        let back: RequestMetric = serde_json::from_str(&json).unwrap();
        assert_eq!(back.channel, "discord");
        assert!(back.success);
        assert!(back.error.is_none());
    }
}
