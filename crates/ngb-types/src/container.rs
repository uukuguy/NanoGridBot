use std::collections::HashMap;

use serde::{Deserialize, Serialize};

/// Container execution configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContainerConfig {
    #[serde(default)]
    pub additional_mounts: Vec<HashMap<String, serde_json::Value>>,
    #[serde(default)]
    pub timeout: Option<i64>,
    #[serde(default)]
    pub max_output_size: Option<i64>,
    #[serde(default)]
    pub env: HashMap<String, String>,
}

/// Container execution result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContainerOutput {
    pub status: String,
    #[serde(default)]
    pub result: Option<String>,
    #[serde(default)]
    pub error: Option<String>,
    #[serde(default)]
    pub new_session_id: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn container_config_serde_roundtrip() {
        let mut env = HashMap::new();
        env.insert("API_KEY".to_string(), "secret".to_string());

        let config = ContainerConfig {
            additional_mounts: vec![],
            timeout: Some(300),
            max_output_size: Some(100_000),
            env,
        };

        let json = serde_json::to_string(&config).unwrap();
        let back: ContainerConfig = serde_json::from_str(&json).unwrap();
        assert_eq!(back.timeout, Some(300));
        assert_eq!(back.env.get("API_KEY").unwrap(), "secret");
    }

    #[test]
    fn container_config_defaults() {
        let json = "{}";
        let config: ContainerConfig = serde_json::from_str(json).unwrap();
        assert!(config.additional_mounts.is_empty());
        assert!(config.timeout.is_none());
        assert!(config.env.is_empty());
    }

    #[test]
    fn container_output_serde_roundtrip() {
        let output = ContainerOutput {
            status: "success".to_string(),
            result: Some("Done".to_string()),
            error: None,
            new_session_id: Some("sess-123".to_string()),
        };

        let json = serde_json::to_string(&output).unwrap();
        let back: ContainerOutput = serde_json::from_str(&json).unwrap();
        assert_eq!(back.status, "success");
        assert_eq!(back.result, Some("Done".to_string()));
        assert!(back.error.is_none());
    }
}
