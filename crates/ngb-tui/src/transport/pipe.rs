//! Pipe transport - communicates with Claude Code via stdin/stdout pipes

use super::{OutputChunk, Transport};
use async_trait::async_trait;
use futures::stream::{self, Stream};
use std::pin::Pin;
use tokio::io::BufReader;
use tokio::process::{Child, Command};

/// Pipe transport - uses docker run -i for interactive stdin/stdout communication
#[allow(dead_code)]
pub struct PipeTransport {
    /// The child process (Claude Code container)
    child: Child,
    /// Reader for stdout
    reader: Option<BufReader<tokio::process::ChildStdout>>,
    /// Channel for sending messages
    #[allow(dead_code)]
    sender: Option<tokio::sync::mpsc::Sender<String>>,
}

impl PipeTransport {
    /// Create a new PipeTransport by starting a Claude Code container
    pub async fn new(workspace_id: &str, image: &str) -> anyhow::Result<Self> {
        // Create a channel for sending messages to the process
        let (sender, _receiver) = tokio::sync::mpsc::channel::<String>(32);

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

        // Take ownership of stdout for reading
        let reader = child.stdout.take().map(BufReader::new);

        Ok(Self {
            child,
            reader,
            sender: Some(sender),
        })
    }

    /// Create a PipeTransport that uses an existing container
    pub async fn from_container(container_id: &str) -> anyhow::Result<Self> {
        let (sender, _receiver) = tokio::sync::mpsc::channel::<String>(32);

        // Use docker exec -i to connect to running container
        let mut child = Command::new("docker")
            .args(["exec", "-i", container_id, "claude"])
            .stdout(std::process::Stdio::piped())
            .stdin(std::process::Stdio::piped())
            .stderr(std::process::Stdio::null())
            .spawn()?;

        let reader = child.stdout.take().map(BufReader::new);

        Ok(Self {
            child,
            reader,
            sender: Some(sender),
        })
    }
}

#[async_trait]
impl Transport for PipeTransport {
    async fn send(&mut self, _msg: &str) -> anyhow::Result<()> {
        // For now, just return Ok(())
        // Full implementation would write to stdin
        Ok(())
    }

    fn recv_stream(&mut self) -> Pin<Box<dyn Stream<Item = OutputChunk> + Send>> {
        // Create a stream that reads from stdout
        // For now, return a simple done signal
        Box::pin(stream::iter(vec![OutputChunk::Done]))
    }

    async fn interrupt(&mut self) -> anyhow::Result<()> {
        self.child.kill().await?;
        Ok(())
    }

    async fn close(&mut self) -> anyhow::Result<()> {
        // Send EOF to stdin to gracefully shutdown
        // Then wait for process to exit
        self.child.wait().await?;
        Ok(())
    }
}
