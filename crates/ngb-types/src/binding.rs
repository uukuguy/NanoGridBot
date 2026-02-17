use serde::{Deserialize, Serialize};

/// ChannelBinding — maps an IM chat to a workspace.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChannelBinding {
    pub channel_jid: String,
    pub workspace_id: String,
}

/// AccessToken — used by IM users to bind a chat to a workspace.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AccessToken {
    pub token: String,
    pub workspace_id: String,
    #[serde(default)]
    pub used: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn binding_serde_roundtrip() {
        let binding = ChannelBinding {
            channel_jid: "telegram:group123".to_string(),
            workspace_id: "ws-abc".to_string(),
        };

        let json = serde_json::to_string(&binding).unwrap();
        let back: ChannelBinding = serde_json::from_str(&json).unwrap();
        assert_eq!(back.channel_jid, "telegram:group123");
        assert_eq!(back.workspace_id, "ws-abc");
    }

    #[test]
    fn token_serde_roundtrip() {
        let token = AccessToken {
            token: "ngb-a1b2c3d4e5f6".to_string(),
            workspace_id: "ws-abc".to_string(),
            used: false,
        };

        let json = serde_json::to_string(&token).unwrap();
        let back: AccessToken = serde_json::from_str(&json).unwrap();
        assert_eq!(back.token, "ngb-a1b2c3d4e5f6");
        assert!(!back.used);
    }

    #[test]
    fn token_defaults() {
        let json = r#"{
            "token": "ngb-test",
            "workspace_id": "ws-1"
        }"#;
        let token: AccessToken = serde_json::from_str(json).unwrap();
        assert!(!token.used);
    }
}
