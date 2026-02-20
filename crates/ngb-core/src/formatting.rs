use std::collections::HashMap;

use chrono::{DateTime, Utc};

/// Escape XML special characters.
pub fn escape_xml(text: &str) -> String {
    text.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

/// Format messages into XML for Claude input.
pub fn format_messages_xml(messages: &[MessageData]) -> String {
    let mut lines = vec!["<messages>".to_string()];

    for msg in messages {
        let sender_name = msg.sender_name.as_deref().unwrap_or(&msg.sender);
        let ts_str = msg.timestamp.to_rfc3339();
        let role = if msg.is_from_me { "assistant" } else { "user" };
        let content = escape_xml(&msg.content);
        let sender_escaped = escape_xml(sender_name);

        lines.push(format!(
            "  <message role=\"{role}\" sender=\"{sender_escaped}\" timestamp=\"{ts_str}\">"
        ));
        lines.push(format!("    {content}"));
        lines.push("  </message>".to_string());
    }

    lines.push("</messages>".to_string());
    lines.join("\n")
}

/// Format container output into XML.
pub fn format_output_xml(
    status: &str,
    result: Option<&str>,
    error: Option<&str>,
    new_session_id: Option<&str>,
) -> String {
    let mut lines = vec!["<output>".to_string()];

    lines.push(format!("  <status>{status}</status>"));

    if let Some(r) = result {
        lines.push(format!("  <result>{}</result>", escape_xml(r)));
    }
    if let Some(e) = error {
        lines.push(format!("  <error>{}</error>", escape_xml(e)));
    }
    if let Some(sid) = new_session_id {
        lines.push(format!(
            "  <new_session_id>{}</new_session_id>",
            escape_xml(sid)
        ));
    }

    lines.push("</output>".to_string());
    lines.join("\n")
}

/// Parse JSON input string into a HashMap.
pub fn parse_input_json(input: &str) -> Result<HashMap<String, serde_json::Value>, String> {
    serde_json::from_str(input).map_err(|e| format!("Invalid JSON input: {e}"))
}

/// Serialize output data to JSON string.
pub fn serialize_output(data: &HashMap<String, serde_json::Value>) -> Result<String, String> {
    serde_json::to_string(data).map_err(|e| format!("JSON serialization error: {e}"))
}

/// Simple message data for formatting.
pub struct MessageData {
    pub sender: String,
    pub sender_name: Option<String>,
    pub content: String,
    pub timestamp: DateTime<Utc>,
    pub is_from_me: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn escape_xml_special_chars() {
        assert_eq!(escape_xml("a & b"), "a &amp; b");
        assert_eq!(escape_xml("<tag>"), "&lt;tag&gt;");
        assert_eq!(escape_xml("\"quoted\""), "&quot;quoted&quot;");
        assert_eq!(escape_xml("it's"), "it&apos;s");
    }

    #[test]
    fn escape_xml_empty() {
        assert_eq!(escape_xml(""), "");
    }

    #[test]
    fn format_messages_xml_basic() {
        let messages = vec![MessageData {
            sender: "user1".to_string(),
            sender_name: Some("Alice".to_string()),
            content: "Hello <world>".to_string(),
            timestamp: Utc::now(),
            is_from_me: false,
        }];

        let xml = format_messages_xml(&messages);
        assert!(xml.starts_with("<messages>"));
        assert!(xml.ends_with("</messages>"));
        assert!(xml.contains("role=\"user\""));
        assert!(xml.contains("sender=\"Alice\""));
        assert!(xml.contains("Hello &lt;world&gt;"));
    }

    #[test]
    fn format_output_xml_success() {
        let xml = format_output_xml("success", Some("Done"), None, None);
        assert!(xml.contains("<status>success</status>"));
        assert!(xml.contains("<result>Done</result>"));
        assert!(!xml.contains("<error>"));
    }

    #[test]
    fn format_output_xml_error() {
        let xml = format_output_xml("error", None, Some("Timeout"), None);
        assert!(xml.contains("<status>error</status>"));
        assert!(xml.contains("<error>Timeout</error>"));
    }

    #[test]
    fn format_output_xml_with_session() {
        let xml = format_output_xml("success", Some("OK"), None, Some("sess-123"));
        assert!(xml.contains("<new_session_id>sess-123</new_session_id>"));
    }

    #[test]
    fn parse_input_json_valid() {
        let result = parse_input_json(r#"{"key": "value", "num": 42}"#).unwrap();
        assert_eq!(result.get("key").unwrap(), "value");
        assert_eq!(result.get("num").unwrap(), 42);
    }

    #[test]
    fn parse_input_json_invalid() {
        let result = parse_input_json("not json");
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Invalid JSON input"));
    }

    #[test]
    fn serialize_output_roundtrip() {
        let mut data = HashMap::new();
        data.insert(
            "status".to_string(),
            serde_json::Value::String("ok".to_string()),
        );
        data.insert(
            "count".to_string(),
            serde_json::Value::Number(serde_json::Number::from(5)),
        );

        let json = serialize_output(&data).unwrap();
        let back: HashMap<String, serde_json::Value> = serde_json::from_str(&json).unwrap();
        assert_eq!(back.get("status").unwrap(), "ok");
    }
}
