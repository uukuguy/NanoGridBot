//! Output chunk types for streaming responses

use serde::{Deserialize, Serialize};

/// Represents different types of output from Claude Code
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum OutputChunk {
    /// Plain text output
    Text(String),
    /// Tool call started
    ToolStart {
        /// Tool name
        name: String,
        /// Tool arguments (JSON string)
        args: String,
    },
    /// Tool call completed
    ToolEnd {
        /// Tool name
        name: String,
        /// Whether the tool succeeded
        success: bool,
    },
    /// Claude started thinking
    ThinkingStart,
    /// Thinking text (reasoning)
    ThinkingText(String),
    /// Claude finished thinking
    ThinkingEnd,
    /// Response complete
    Done,
    /// Error occurred
    Error(String),
}

impl OutputChunk {
    /// Parse a line from stdout into OutputChunk
    /// Claude Code outputs JSON lines (JSONL) format
    pub fn parse_line(line: &str) -> Option<Self> {
        // Try to parse as JSON
        if let Ok(chunk) = serde_json::from_str::<OutputChunk>(line) {
            return Some(chunk);
        }

        // If not JSON, treat as plain text
        if !line.is_empty() {
            Some(OutputChunk::Text(line.to_string()))
        } else {
            None
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_text() {
        let line = r#"{"type":"Text","data":"Hello world"}"#;
        let chunk = OutputChunk::parse_line(line).unwrap();
        assert!(matches!(chunk, OutputChunk::Text(s) if s == "Hello world"));
    }

    #[test]
    fn test_parse_tool_start() {
        let line = r#"{"type":"ToolStart","data":{"name":"Read","args":"file.txt"}}"#;
        let chunk = OutputChunk::parse_line(line).unwrap();
        match chunk {
            OutputChunk::ToolStart { name, args } => {
                assert_eq!(name, "Read");
                assert_eq!(args, "file.txt");
            }
            _ => panic!("Expected ToolStart"),
        }
    }

    #[test]
    fn test_parse_plain_text() {
        let line = "Just some plain text";
        let chunk = OutputChunk::parse_line(line).unwrap();
        assert!(matches!(chunk, OutputChunk::Text(s) if s == "Just some plain text"));
    }
}
