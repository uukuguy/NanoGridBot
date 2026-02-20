//! Pipe transport - communicates with Claude Code via stdin/stdout pipes
//!
//! When a `Config` is provided, the transport performs secure mount validation
//! and environment filtering via `ngb-core` before starting the container.

use super::{OutputChunk, Transport};
use async_trait::async_trait;
use futures::stream::Stream;
use ngb_config::Config;
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
    /// Create a new PipeTransport by starting a Claude Code container.
    ///
    /// When `config` is provided, the transport:
    /// 1. Prepares the container launch (directories, settings, skills) via `spawn_blocking`
    /// 2. Validates workspace mounts for security
    /// 3. Filters environment variables (only API keys)
    /// 4. Adds resource limits (`--memory=2g`, `--cpus=1.0`)
    ///
    /// When `config` is `None`, falls back to the simple `docker run` with no mounts.
    pub async fn new(
        workspace_id: &str,
        image: &str,
        config: Option<&Config>,
    ) -> anyhow::Result<Self> {
        let mut args = vec![
            "run".to_string(),
            "-i".to_string(),
            "--rm".to_string(),
        ];

        if let Some(cfg) = config {
            // Prepare container launch (directory creation, settings.json, skill sync)
            let cfg_clone = cfg.clone();
            let ws_id = workspace_id.to_string();
            let env_vars = tokio::task::spawn_blocking(move || {
                ngb_core::prepare_container_launch(&cfg_clone, &ws_id, false, &[], &[])
            })
            .await??;

            // Validate workspace mounts
            let mounts = ngb_core::validate_workspace_mounts(
                workspace_id,
                &format!("pipe:{workspace_id}"),
                false,
                &[],
                cfg,
            )?;

            // Add volume mounts
            for mount in &mounts {
                args.push("-v".to_string());
                args.push(mount.to_docker_arg());
            }

            // Add filtered environment variables
            for (key, val) in &env_vars {
                args.push("-e".to_string());
                args.push(format!("{key}={val}"));
            }

            // Resource limits
            args.push("--memory=2g".to_string());
            args.push("--cpus=1.0".to_string());

            // Interactive mode needs network for API access
            args.push("--network".to_string());
            args.push("host".to_string());
        } else {
            // Legacy simple mode — no mounts, just forward ANTHROPIC_API_KEY from env
            args.push("--network".to_string());
            args.push("host".to_string());
            args.push("-e".to_string());
            args.push(format!("WORKSPACE={workspace_id}"));
            args.push("-e".to_string());
            args.push("ANTHROPIC_API_KEY".to_string());
        }

        // Image and command
        args.push(image.to_string());
        args.push("bash".to_string());
        args.push("-c".to_string());
        args.push("exec claude".to_string());

        let mut child = Command::new("docker")
            .args(&args)
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
