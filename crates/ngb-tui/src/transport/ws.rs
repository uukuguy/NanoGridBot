//! WebSocket transport - communicates with Claude Code via WebSocket
//!
//! This transport connects to a WebSocket server running inside the container.
//! The container is expected to start a WebSocket server on a specified port.
//!
//! Latency: Real-time (WebSocket push)

use super::{OutputChunk, Transport};
use async_trait::async_trait;
use futures::Stream;
use futures::stream::StreamExt;
use futures::SinkExt;
use std::pin::Pin;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tokio::sync::mpsc;
use tokio_tungstenite::{connect_async, tungstenite::Message};

/// WebSocket transport configuration
#[derive(Clone)]
pub struct WsTransportConfig {
    /// WebSocket server URL (e.g., ws://localhost:8080/ws)
    pub url: String,
    /// Connection timeout in seconds
    pub timeout_secs: u64,
    /// Maximum connection retries (0 = no retry)
    pub max_retries: u32,
}

impl Default for WsTransportConfig {
    fn default() -> Self {
        Self {
            url: String::from("ws://localhost:8080/ws"),
            timeout_secs: 10,
            max_retries: 2,
        }
    }
}

/// WebSocket transport - WebSocket based communication
pub struct WsTransport {
    /// Configuration
    config: WsTransportConfig,
    /// Flag to indicate stream is done
    done: Arc<AtomicBool>,
    /// Sender for passing messages to the stream
    sender: Option<mpsc::Sender<String>>,
}

impl WsTransport {
    /// Create a new WebSocket transport
    pub fn new(config: WsTransportConfig) -> Self {
        Self {
            config,
            done: Arc::new(AtomicBool::new(false)),
            sender: None,
        }
    }

    /// Mark the transport as done
    pub fn set_done(&self) {
        self.done.store(true, Ordering::SeqCst);
    }

    /// Check if done
    pub fn is_done(&self) -> bool {
        self.done.load(Ordering::SeqCst)
    }
}

#[async_trait]
impl Transport for WsTransport {
    async fn send(&mut self, _msg: &str) -> anyhow::Result<()> {
        // Note: WebSocket send requires the stream to be initialized first
        // This is handled in recv_stream() which sets up the channel
        if let Some(sender) = &self.sender {
            sender.send(_msg.to_string()).await.map_err(|e| anyhow::anyhow!("{}", e))?;
        }
        Ok(())
    }

    fn recv_stream(&mut self) -> Pin<Box<dyn Stream<Item = OutputChunk> + Send + '_>> {
        let url = self.config.url.clone();
        let timeout_secs = self.config.timeout_secs;
        let max_retries = self.config.max_retries;
        let done = self.done.clone();

        Box::pin(async_stream::stream! {
            // Connect to WebSocket server with timeout and retry
            let mut ws_stream_opt = None;
            let mut last_error = String::new();

            for attempt in 0..=max_retries {
                match tokio::time::timeout(
                    std::time::Duration::from_secs(timeout_secs),
                    connect_async(&url)
                ).await {
                    Ok(Ok((stream, _))) => {
                        ws_stream_opt = Some(stream);
                        break;
                    }
                    Ok(Err(e)) => {
                        last_error = format!("WebSocket connection failed: {}", e);
                        if attempt < max_retries {
                            let backoff = std::time::Duration::from_millis(500 * 2u64.pow(attempt));
                            yield OutputChunk::Error(format!(
                                "{} (retry {}/{} in {}ms)",
                                last_error, attempt + 1, max_retries, backoff.as_millis()
                            ));
                            tokio::time::sleep(backoff).await;
                        }
                    }
                    Err(_) => {
                        last_error = "WebSocket connection timeout".to_string();
                        if attempt < max_retries {
                            let backoff = std::time::Duration::from_millis(500 * 2u64.pow(attempt));
                            yield OutputChunk::Error(format!(
                                "{} (retry {}/{} in {}ms)",
                                last_error, attempt + 1, max_retries, backoff.as_millis()
                            ));
                            tokio::time::sleep(backoff).await;
                        }
                    }
                }
            }

            let ws_stream = match ws_stream_opt {
                Some(s) => s,
                None => {
                    yield OutputChunk::Error(last_error);
                    yield OutputChunk::Done;
                    return;
                }
            };

            tracing::info!(url = %url, "WebSocket connected");

            let (mut write, mut read) = ws_stream.split();

            // Create channel for sending messages
            let (tx, mut rx) = mpsc::channel::<String>(100);
            self.sender = Some(tx);

            // Spawn task to handle sending
            let done_clone = done.clone();
            tokio::spawn(async move {
                while !done_clone.load(Ordering::SeqCst) {
                    match tokio::time::timeout(
                        std::time::Duration::from_millis(100),
                        rx.recv()
                    ).await {
                        Ok(Some(msg)) => {
                            if let Err(e) = write.send(Message::Text(msg)).await {
                                tracing::error!(error = %e, "WebSocket send error");
                                break;
                            }
                        }
                        Ok(None) => break,
                        Err(_) => {
                            // Timeout, continue loop
                        }
                    }
                }
            });

            // Read messages from WebSocket
            while !done.load(Ordering::SeqCst) {
                match tokio::time::timeout(
                    std::time::Duration::from_millis(100),
                    read.next()
                ).await {
                    Ok(Some(Ok(Message::Text(text)))) => {
                        // Parse as OutputChunk
                        if let Some(chunk) = OutputChunk::parse_line(&text) {
                            yield chunk;
                        } else if !text.is_empty() {
                            yield OutputChunk::Text(text);
                        }
                    }
                    Ok(Some(Ok(Message::Close(_)))) | Ok(Some(Ok(Message::Ping(_)))) | Ok(None) => {
                        done.store(true, Ordering::SeqCst);
                        yield OutputChunk::Done;
                        break;
                    }
                    Ok(Some(Err(e))) => {
                        yield OutputChunk::Error(format!("WebSocket error: {}", e));
                        done.store(true, Ordering::SeqCst);
                        break;
                    }
                    Err(_) => {
                        // Timeout, continue polling
                    }
                    _ => {}
                }
            }

            tracing::info!("WebSocket stream ended");
        })
    }

    async fn interrupt(&mut self) -> anyhow::Result<()> {
        self.set_done();
        Ok(())
    }

    async fn close(&mut self) -> anyhow::Result<()> {
        self.set_done();
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ws_config_default_retries() {
        let config = WsTransportConfig::default();
        assert_eq!(config.max_retries, 2);
        assert_eq!(config.timeout_secs, 10);
        assert_eq!(config.url, "ws://localhost:8080/ws");
    }

    #[test]
    fn test_ws_config_custom_retries() {
        let config = WsTransportConfig {
            url: "ws://example.com/ws".to_string(),
            timeout_secs: 5,
            max_retries: 5,
        };
        assert_eq!(config.max_retries, 5);
    }
}
