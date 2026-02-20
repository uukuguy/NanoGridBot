use std::collections::HashMap;

use serde::{Deserialize, Serialize};

/// Workspace — an isolated development environment for an AI agent project.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Workspace {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub owner: String,
    pub folder: String,
    #[serde(default)]
    pub shared: bool,
    #[serde(default)]
    pub container_config: Option<HashMap<String, serde_json::Value>>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn workspace_serde_roundtrip() {
        let ws = Workspace {
            id: "ws-abc123".to_string(),
            name: "my-agent".to_string(),
            owner: "user1".to_string(),
            folder: "my-agent".to_string(),
            shared: false,
            container_config: None,
        };

        let json = serde_json::to_string(&ws).unwrap();
        let back: Workspace = serde_json::from_str(&json).unwrap();
        assert_eq!(back.id, "ws-abc123");
        assert_eq!(back.name, "my-agent");
        assert_eq!(back.owner, "user1");
        assert!(!back.shared);
    }

    #[test]
    fn workspace_defaults() {
        let json = r#"{
            "id": "ws-1",
            "name": "test",
            "folder": "test"
        }"#;
        let ws: Workspace = serde_json::from_str(json).unwrap();
        assert_eq!(ws.owner, "");
        assert!(!ws.shared);
        assert!(ws.container_config.is_none());
    }

    #[test]
    fn workspace_with_container_config() {
        let json = r#"{
            "id": "ws-2",
            "name": "custom",
            "folder": "custom",
            "owner": "admin",
            "shared": true,
            "container_config": {"memory": "512m", "cpu": 2}
        }"#;
        let ws: Workspace = serde_json::from_str(json).unwrap();
        assert!(ws.shared);
        let cfg = ws.container_config.unwrap();
        assert_eq!(cfg["memory"], "512m");
    }
}
