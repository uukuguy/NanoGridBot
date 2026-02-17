//! Pipe transport - communicates with Claude Code via stdin/stdout pipes

use super::{OutputChunk, Transport};
use async_trait::async_trait;
use futures::stream::Stream;
use std::pin::Pin;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::process::{Child, Command};

/// Pipe transport - uses docker run -i for interactive stdin/stdout communication
pub struct PipeTransport {
    /// The child process (Claude Code container)
    child: Option<Child>,
    /// Writer for stdin
    stdin: Option<tokio::process::ChildStdin>,
    /// Flag to indicate stream is done
    done: Arc<AtomicBool>,
}

impl PipeTransport {
    /// Create a new PipeTransport by starting a Claude Code container
    pub async fn new(workspace_id: &str, image: &str) -> anyhow::Result<Self> {
        // Start docker run -i
        let mut child = Command::new("docker")
            .args([
                "run",
                "-i",
                "--rm",
                "--network",
                "host",
                "-e",
                &format!("WORKSPACE={}", workspace_id),
                "-e",
                "ANTHROPIC_API_KEY", // Will be read from env
                image,
                "bash", // Start bash to keep container alive
                "-c",
                "exec claude", // Run claude in interactive mode
            ])
            .stdout(std::process::Stdio::piped())
            .stdin(std::process::Stdio::piped())
            .stderr(std::process::Stdio::null())
            .spawn()?;

        // Take ownership of stdin for writing
        let stdin = child.stdin.take();
        // Keep stdout in the child

        Ok(Self {
            child: Some(child),
            stdin,
            done: Arc::new(AtomicBool::new(false)),
        })
    }

    /// Create a PipeTransport that uses an existing container
    pub async fn from_container(container_id: &str) -> anyhow::Result<Self> {
        // Use docker exec -i to connect to running container
        let mut child = Command::new("docker")
            .args(["exec", "-i", container_id, "claude"])
            .stdout(std::process::Stdio::piped())
            .stdin(std::process::Stdio::piped())
            .stderr(std::process::Stdio::null())
            .spawn()?;

        let stdin = child.stdin.take();

        Ok(Self {
            child: Some(child),
            stdin,
            done: Arc::new(AtomicBool::new(false)),
        })
    }

    /// Check if the stream is done
    pub fn is_done(&self) -> bool {
        self.done.load(Ordering::SeqCst)
    }

    /// Mark the stream as done
    pub fn set_done(&self) {
        self.done.store(true, Ordering::SeqCst);
    }
}

#[async_trait]
impl Transport for PipeTransport {
    async fn send(&mut self, msg: &str) -> anyhow::Result<()> {
        if let Some(stdin) = self.stdin.as_mut() {
            // Write message + newline to stdin
            stdin.write_all(msg.as_bytes()).await?;
            stdin.write_all(b"\n").await?;
            stdin.flush().await?;
        }
        Ok(())
    }

    fn recv_stream(&mut self) -> Pin<Box<dyn Stream<Item = OutputChunk> + Send>> {
        // Take ownership of child for the stream
        let child = self.child.take();
        let done = self.done.clone();

        Box::pin(async_stream::stream! {
            if child.is_none() {
                yield OutputChunk::Done;
                return;
            }

            let mut child = child.unwrap();

            loop {
                if done.load(Ordering::SeqCst) {
                    yield OutputChunk::Done;
                    break;
                }

                // Try to read from stdout
                if let Some(stdout) = child.stdout.as_mut() {
                    let mut buffer = [0u8; 1024];

                    // Use read_with_timeout pattern via tokio::select
                    tokio::select! {
                        result = stdout.read(&mut buffer) => {
                            match result {
                                Ok(0) => {
                                    // EOF - process exited
                                    done.store(true, Ordering::SeqCst);
                                    yield OutputChunk::Done;
                                    break;
                                }
                                Ok(n) => {
                                    let data = String::from_utf8_lossy(&buffer[..n]).to_string();
                                    // Parse each line as a separate chunk
                                    for line in data.lines() {
                                        if let Some(chunk) = OutputChunk::parse_line(line) {
                                            yield chunk;
                                        } else if !line.is_empty() {
                                            yield OutputChunk::Text(line.to_string());
                                        }
                                    }
                                }
                                Err(e) => {
                                    if e.kind() != std::io::ErrorKind::WouldBlock {
                                        yield OutputChunk::Error(format!("Read error: {}", e));
                                        done.store(true, Ordering::SeqCst);
                                        break;
                                    }
                                }
                            }
                        }
                        _ = tokio::time::sleep(std::time::Duration::from_millis(50)) => {
                            // Yield control periodically
                        }
                    }
                } else {
                    yield OutputChunk::Done;
                    break;
                }
            }
        })
    }

    async fn interrupt(&mut self) -> anyhow::Result<()> {
        if let Some(child) = self.child.as_mut() {
            child.kill().await?;
        }
        self.set_done();
        Ok(())
    }

    async fn close(&mut self) -> anyhow::Result<()> {
        // Drop stdin to send EOF
        self.stdin = None;
        // Wait for process to exit gracefully
        if let Some(child) = self.child.as_mut() {
            let _ = child.wait().await;
        }
        self.set_done();
        Ok(())
    }
}
