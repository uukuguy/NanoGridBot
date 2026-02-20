use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::enums::MessageRole;

/// Chat message model.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub id: String,
    pub chat_jid: String,
    pub sender: String,
    #[serde(default)]
    pub sender_name: Option<String>,
    pub content: String,
    pub timestamp: DateTime<Utc>,
    #[serde(default)]
    pub is_from_me: bool,
    #[serde(default)]
    pub role: MessageRole,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn message_serde_roundtrip() {
        let msg = Message {
            id: "msg-001".to_string(),
            chat_jid: "telegram:123456".to_string(),
            sender: "user1".to_string(),
            sender_name: Some("Alice".to_string()),
            content: "Hello world".to_string(),
            timestamp: Utc::now(),
            is_from_me: false,
            role: MessageRole::User,
        };

        let json = serde_json::to_string(&msg).unwrap();
        let back: Message = serde_json::from_str(&json).unwrap();
        assert_eq!(back.id, "msg-001");
        assert_eq!(back.chat_jid, "telegram:123456");
        assert!(!back.is_from_me);
        assert_eq!(back.role, MessageRole::User);
    }

    #[test]
    fn message_defaults() {
        let json = r#"{
            "id": "1",
            "chat_jid": "slack:C123",
            "sender": "U1",
            "content": "hi",
            "timestamp": "2025-01-01T00:00:00Z"
        }"#;
        let msg: Message = serde_json::from_str(json).unwrap();
        assert!(!msg.is_from_me);
        assert_eq!(msg.role, MessageRole::User);
        assert!(msg.sender_name.is_none());
    }
}
