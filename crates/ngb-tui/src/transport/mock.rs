//! Mock transport for development and demo mode.
//!
//! Simulates agent responses without requiring Docker or external services.
//! Cycles through 3 preset response patterns, yielding chunks with
//! 100-300ms delays to mimic real streaming.

use super::{OutputChunk, Transport};
use async_trait::async_trait;
use futures::stream::Stream;
use std::pin::Pin;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Duration;

/// Mock transport that simulates Claude Code responses for development/demo use.
pub struct MockTransport {
    /// Cycle counter — determines which preset response to yield next
    cycle: Arc<AtomicUsize>,
    /// Shared flag indicating the current response stream is done
    done: Arc<AtomicBool>,
    /// Whether a send has been triggered (the stream reads this to start yielding)
    triggered: Arc<AtomicBool>,
}

impl MockTransport {
    /// Create a new MockTransport.
    pub fn new() -> Self {
        Self {
            cycle: Arc::new(AtomicUsize::new(0)),
            done: Arc::new(AtomicBool::new(false)),
            triggered: Arc::new(AtomicBool::new(false)),
        }
    }

    /// Build preset response chunks for a given cycle index.
    fn preset_chunks(cycle: usize) -> Vec<OutputChunk> {
        match cycle % 3 {
            0 => vec![
                OutputChunk::ThinkingStart,
                OutputChunk::ThinkingText(
                    "Let me analyze your request and think about the best approach...".to_string(),
                ),
                OutputChunk::ThinkingEnd,
                OutputChunk::Text(
                    "I've analyzed your request. Here's a summary of what I found:\n\n\
                     1. The project structure looks well-organized\n\
                     2. All tests are passing\n\
                     3. No security issues detected\n\n\
                     Let me know if you'd like me to dive deeper into any area."
                        .to_string(),
                ),
                OutputChunk::Done,
            ],
            1 => vec![
                OutputChunk::Text("Let me read the relevant file first.\n".to_string()),
                OutputChunk::ToolStart {
                    name: "Read".to_string(),
                    args: r#"{"file_path": "src/main.rs"}"#.to_string(),
                },
                OutputChunk::ToolEnd {
                    name: "Read".to_string(),
                    success: true,
                },
                OutputChunk::Text(
                    "I've read the file. The main entry point sets up the CLI parser, \
                     loads configuration, and dispatches to the appropriate subcommand handler. \
                     The code follows standard Rust async patterns with `tokio::main`."
                        .to_string(),
                ),
                OutputChunk::Done,
            ],
            _ => vec![
                OutputChunk::ThinkingStart,
                OutputChunk::ThinkingText(
                    "I need to run a command to check the current state...".to_string(),
                ),
                OutputChunk::ThinkingEnd,
                OutputChunk::ToolStart {
                    name: "Bash".to_string(),
                    args: r#"{"command": "cargo test --lib 2>&1 | tail -5"}"#.to_string(),
                },
                OutputChunk::ToolEnd {
                    name: "Bash".to_string(),
                    success: true,
                },
                OutputChunk::Text(
                    "All tests passed successfully. The test suite covers the core modules \
                     with good coverage. No regressions detected."
                        .to_string(),
                ),
                OutputChunk::Done,
            ],
        }
    }
}

impl Default for MockTransport {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl Transport for MockTransport {
    async fn send(&mut self, _msg: &str) -> anyhow::Result<()> {
        // Reset done flag and trigger the stream
        self.done.store(false, Ordering::SeqCst);
        self.triggered.store(true, Ordering::SeqCst);
        Ok(())
    }

    fn recv_stream(&mut self) -> Pin<Box<dyn Stream<Item = OutputChunk> + Send + '_>> {
        let cycle = self.cycle.clone();
        let done = self.done.clone();
        let triggered = self.triggered.clone();

        Box::pin(async_stream::stream! {
            loop {
                // Wait until a send() triggers us
                if !triggered.load(Ordering::SeqCst) {
                    if done.load(Ordering::SeqCst) {
                        break;
                    }
                    tokio::time::sleep(Duration::from_millis(50)).await;
                    continue;
                }

                // Get current cycle and advance
                let current = cycle.fetch_add(1, Ordering::SeqCst);
                let chunks = MockTransport::preset_chunks(current);

                // Yield each chunk with a random-ish delay (100-300ms)
                for (i, chunk) in chunks.into_iter().enumerate() {
                    let delay_ms = 100 + ((current * 37 + i * 73) % 200) as u64;
                    tokio::time::sleep(Duration::from_millis(delay_ms)).await;
                    yield chunk;
                }

                // Reset trigger, wait for next send()
                triggered.store(false, Ordering::SeqCst);
            }
        })
    }

    async fn interrupt(&mut self) -> anyhow::Result<()> {
        self.triggered.store(false, Ordering::SeqCst);
        Ok(())
    }

    async fn close(&mut self) -> anyhow::Result<()> {
        self.done.store(true, Ordering::SeqCst);
        self.triggered.store(false, Ordering::SeqCst);
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use futures::StreamExt;

    #[tokio::test]
    async fn test_mock_transport_send_and_receive() {
        let mut transport = MockTransport::new();

        // Send a message
        transport.send("Hello").await.unwrap();

        // Collect chunks from stream (with timeout)
        let mut stream = transport.recv_stream();
        let mut chunks = Vec::new();

        loop {
            tokio::select! {
                chunk = stream.next() => {
                    match chunk {
                        Some(OutputChunk::Done) => {
                            chunks.push(OutputChunk::Done);
                            break;
                        }
                        Some(c) => chunks.push(c),
                        None => break,
                    }
                }
                _ = tokio::time::sleep(Duration::from_secs(10)) => {
                    panic!("Timeout waiting for mock response");
                }
            }
        }

        // First cycle: ThinkingStart → ThinkingText → ThinkingEnd → Text → Done
        assert!(chunks.len() >= 4, "Expected at least 4 chunks, got {}", chunks.len());
        assert!(matches!(chunks[0], OutputChunk::ThinkingStart));
        assert!(matches!(chunks[1], OutputChunk::ThinkingText(_)));
        assert!(matches!(chunks[2], OutputChunk::ThinkingEnd));
        assert!(matches!(chunks[3], OutputChunk::Text(_)));
        assert!(matches!(chunks.last(), Some(OutputChunk::Done)));
    }

    #[tokio::test]
    async fn test_mock_cycles_through_presets() {
        // Verify that 3 different cycle indices produce different chunk patterns
        let chunks_0 = MockTransport::preset_chunks(0);
        let chunks_1 = MockTransport::preset_chunks(1);
        let chunks_2 = MockTransport::preset_chunks(2);

        // Cycle 0: starts with ThinkingStart
        assert!(matches!(chunks_0[0], OutputChunk::ThinkingStart));
        // Cycle 1: starts with Text
        assert!(matches!(chunks_1[0], OutputChunk::Text(_)));
        // Cycle 2: starts with ThinkingStart (but different content)
        assert!(matches!(chunks_2[0], OutputChunk::ThinkingStart));

        // Cycle 1 has ToolStart(Read), Cycle 2 has ToolStart(Bash)
        let has_read = chunks_1.iter().any(|c| matches!(c, OutputChunk::ToolStart { name, .. } if name == "Read"));
        let has_bash = chunks_2.iter().any(|c| matches!(c, OutputChunk::ToolStart { name, .. } if name == "Bash"));
        assert!(has_read);
        assert!(has_bash);
    }

    #[test]
    fn test_preset_wraps_around() {
        // Cycles 0,1,2 should equal 3,4,5
        let a = MockTransport::preset_chunks(0).len();
        let b = MockTransport::preset_chunks(3).len();
        assert_eq!(a, b);
    }
}
