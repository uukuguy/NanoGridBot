use std::collections::HashMap;

use serde::{Deserialize, Serialize};

/// Registered group/chat configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegisteredGroup {
    pub jid: String,
    pub name: String,
    pub folder: String,
    #[serde(default)]
    pub trigger_pattern: Option<String>,
    #[serde(default)]
    pub container_config: Option<HashMap<String, serde_json::Value>>,
    #[serde(default = "default_true")]
    pub requires_trigger: bool,
}

fn default_true() -> bool {
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn group_serde_roundtrip() {
        let group = RegisteredGroup {
            jid: "telegram:group123".to_string(),
            name: "Test Group".to_string(),
            folder: "test_group".to_string(),
            trigger_pattern: Some("!bot".to_string()),
            container_config: None,
            requires_trigger: true,
        };

        let json = serde_json::to_string(&group).unwrap();
        let back: RegisteredGroup = serde_json::from_str(&json).unwrap();
        assert_eq!(back.jid, "telegram:group123");
        assert_eq!(back.trigger_pattern, Some("!bot".to_string()));
        assert!(back.requires_trigger);
    }

    #[test]
    fn group_defaults() {
        let json = r#"{
            "jid": "slack:C1",
            "name": "General",
            "folder": "general"
        }"#;
        let group: RegisteredGroup = serde_json::from_str(json).unwrap();
        assert!(group.requires_trigger);
        assert!(group.trigger_pattern.is_none());
        assert!(group.container_config.is_none());
    }
}
