use std::collections::HashMap;
use std::time::Instant;

use ngb_config::Config;
use ngb_db::{Database, MetricsRepository};
use ngb_types::{ContainerOutput, NanoGridBotError, Result};
use serde_json::json;
use tokio::process::Command;
use tracing::{debug, error, info, warn};

use crate::mount_security::validate_group_mounts;

/// Marker written by the agent container to delimit its JSON output.
pub const OUTPUT_START_MARKER: &str = "---NGB_OUTPUT_START---";
/// End marker.
pub const OUTPUT_END_MARKER: &str = "---NGB_OUTPUT_END---";

/// Run an agent container and return its output.
///
/// Flow: validate mounts → merge env → build docker command →
/// execute with timeout → parse output → record metrics.
#[allow(clippy::too_many_arguments)]
pub async fn run_container_agent(
    group_folder: &str,
    prompt: &str,
    session_id: &str,
    chat_jid: &str,
    is_main: bool,
    additional_mounts: &[HashMap<String, serde_json::Value>],
    timeout_secs: Option<u64>,
    env: &HashMap<String, String>,
    config: &Config,
    db: &Database,
) -> Result<ContainerOutput> {
    let metrics = MetricsRepository::new(db);
    let channel = chat_jid.split(':').next().unwrap_or("unknown");
    let metric_id = metrics
        .record_container_start(group_folder, channel)
        .await?;
    let start = Instant::now();

    let result = run_container_inner(
        group_folder,
        prompt,
        session_id,
        chat_jid,
        is_main,
        additional_mounts,
        timeout_secs,
        env,
        config,
    )
    .await;

    let duration = start.elapsed().as_secs_f64();

    match &result {
        Ok(output) => {
            info!(
                group_folder,
                status = %output.status,
                duration_secs = duration,
                "Container execution completed"
            );
            metrics
                .record_container_end(metric_id, &output.status, Some(duration), None, None, None)
                .await?;
        }
        Err(e) => {
            error!(group_folder, error = %e, "Container execution failed");
            let status = if matches!(e, NanoGridBotError::Timeout(_)) {
                "timeout"
            } else {
                "error"
            };
            metrics
                .record_container_end(
                    metric_id,
                    status,
                    Some(duration),
                    None,
                    None,
                    Some(&e.to_string()),
                )
                .await?;
        }
    }

    result
}

/// Inner function that handles the actual container invocation.
#[allow(clippy::too_many_arguments)]
async fn run_container_inner(
    group_folder: &str,
    prompt: &str,
    session_id: &str,
    chat_jid: &str,
    is_main: bool,
    additional_mounts: &[HashMap<String, serde_json::Value>],
    timeout_secs: Option<u64>,
    env: &HashMap<String, String>,
    config: &Config,
) -> Result<ContainerOutput> {
    // Validate mounts
    let mounts = validate_group_mounts(group_folder, chat_jid, is_main, additional_mounts, config)?;

    // Build the docker command
    let args = build_docker_args(group_folder, &mounts, env, config);

    // Build input JSON
    let input = json!({
        "prompt": prompt,
        "sessionId": session_id,
        "groupFolder": group_folder,
        "chatJid": chat_jid,
        "isMain": is_main,
    });
    let input_bytes = serde_json::to_vec(&input)?;

    debug!(group_folder, args = ?args, "Launching container");

    let timeout = std::time::Duration::from_secs(timeout_secs.unwrap_or(config.container_timeout));

    // Spawn the process
    let mut child = Command::new("docker")
        .args(&args)
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|e| NanoGridBotError::Container(format!("Failed to spawn docker: {e}")))?;

    // Write input to stdin
    if let Some(mut stdin) = child.stdin.take() {
        use tokio::io::AsyncWriteExt;
        stdin.write_all(&input_bytes).await.map_err(|e| {
            NanoGridBotError::Container(format!("Failed to write to container stdin: {e}"))
        })?;
        drop(stdin);
    }

    // Wait with timeout
    let output = tokio::time::timeout(timeout, child.wait_with_output())
        .await
        .map_err(|_| {
            NanoGridBotError::Timeout(format!(
                "Container timed out after {}s for group {group_folder}",
                timeout.as_secs()
            ))
        })?
        .map_err(|e| NanoGridBotError::Container(format!("Container process error: {e}")))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);

    if !output.status.success() {
        warn!(
            group_folder,
            exit_code = ?output.status.code(),
            stderr = %stderr,
            "Container exited with non-zero status"
        );
    }

    // Parse output between markers
    parse_container_output(&stdout, &stderr)
}

/// Build docker run arguments (without the "docker" binary itself).
pub fn build_docker_args(
    group_folder: &str,
    mounts: &[crate::mount_security::MountSpec],
    env: &HashMap<String, String>,
    config: &Config,
) -> Vec<String> {
    let container_name = format!("ngb-{}-{}", group_folder, uuid::Uuid::new_v4());
    let mut args = vec![
        "run".to_string(),
        "--rm".to_string(),
        "--name".to_string(),
        container_name,
        "--network=none".to_string(),
        "--memory=2g".to_string(),
        "--cpus=1.0".to_string(),
        "-i".to_string(), // allow stdin
    ];

    // Volume mounts
    for mount in mounts {
        args.push("-v".to_string());
        args.push(mount.to_docker_arg());
    }

    // Environment variables
    for (k, v) in env {
        args.push("-e".to_string());
        args.push(format!("{k}={v}"));
    }

    // Image
    args.push(config.container_image.clone());

    args
}

/// Parse the container stdout for marker-delimited JSON output.
pub fn parse_container_output(stdout: &str, stderr: &str) -> Result<ContainerOutput> {
    // Look for output between markers
    if let Some(start) = stdout.find(OUTPUT_START_MARKER) {
        let after_marker = &stdout[start + OUTPUT_START_MARKER.len()..];
        if let Some(end) = after_marker.find(OUTPUT_END_MARKER) {
            let json_str = after_marker[..end].trim();
            match serde_json::from_str::<ContainerOutput>(json_str) {
                Ok(output) => return Ok(output),
                Err(e) => {
                    warn!(error = %e, "Failed to parse container JSON output");
                }
            }
        }
    }

    // Fallback: try parsing stdout as JSON directly
    if let Ok(output) = serde_json::from_str::<ContainerOutput>(stdout.trim()) {
        return Ok(output);
    }

    // If there's any stdout, treat it as the result
    let trimmed = stdout.trim();
    if !trimmed.is_empty() {
        return Ok(ContainerOutput {
            status: "success".to_string(),
            result: Some(trimmed.to_string()),
            error: None,
            new_session_id: None,
        });
    }

    // No useful output
    let error_msg = if stderr.trim().is_empty() {
        "Container produced no output".to_string()
    } else {
        stderr.trim().to_string()
    };

    Ok(ContainerOutput {
        status: "error".to_string(),
        result: None,
        error: Some(error_msg),
        new_session_id: None,
    })
}

/// Check if Docker is available on the system.
pub async fn check_docker_available() -> Result<bool> {
    match Command::new("docker")
        .arg("version")
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .await
    {
        Ok(status) => Ok(status.success()),
        Err(_) => Ok(false),
    }
}

/// Get the status of a named container.
pub async fn get_container_status(name: &str) -> Result<String> {
    let output = Command::new("docker")
        .args(["inspect", "--format", "{{.State.Status}}", name])
        .output()
        .await
        .map_err(|e| NanoGridBotError::Container(format!("Failed to inspect container: {e}")))?;

    if output.status.success() {
        Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
    } else {
        Ok("not_found".to_string())
    }
}

/// Forcibly remove a container by name.
pub async fn cleanup_container(name: &str) -> Result<()> {
    let output = Command::new("docker")
        .args(["rm", "-f", name])
        .output()
        .await
        .map_err(|e| NanoGridBotError::Container(format!("Failed to cleanup container: {e}")))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        // Ignore "no such container" errors
        if !stderr.contains("No such container") {
            warn!(name, stderr = %stderr, "Container cleanup warning");
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_output_with_markers() {
        let stdout = format!(
            "some log line\n{}\n{{\"status\":\"success\",\"result\":\"Hello\"}}\n{}\ntrailing",
            OUTPUT_START_MARKER, OUTPUT_END_MARKER
        );
        let output = parse_container_output(&stdout, "").unwrap();
        assert_eq!(output.status, "success");
        assert_eq!(output.result, Some("Hello".to_string()));
    }

    #[test]
    fn parse_output_plain_json() {
        let stdout = r#"{"status":"success","result":"Done"}"#;
        let output = parse_container_output(stdout, "").unwrap();
        assert_eq!(output.status, "success");
        assert_eq!(output.result, Some("Done".to_string()));
    }

    #[test]
    fn parse_output_plain_text() {
        let stdout = "Hello, world!";
        let output = parse_container_output(stdout, "").unwrap();
        assert_eq!(output.status, "success");
        assert_eq!(output.result, Some("Hello, world!".to_string()));
    }

    #[test]
    fn parse_output_empty_with_stderr() {
        let output = parse_container_output("", "something went wrong").unwrap();
        assert_eq!(output.status, "error");
        assert_eq!(output.error, Some("something went wrong".to_string()));
    }

    #[test]
    fn parse_output_empty_no_stderr() {
        let output = parse_container_output("", "").unwrap();
        assert_eq!(output.status, "error");
        assert!(output.error.unwrap().contains("no output"));
    }

    #[test]
    fn parse_output_with_new_session_id() {
        let stdout = format!(
            "{}\n{{\"status\":\"success\",\"result\":\"ok\",\"new_session_id\":\"sess-42\"}}\n{}",
            OUTPUT_START_MARKER, OUTPUT_END_MARKER
        );
        let output = parse_container_output(&stdout, "").unwrap();
        assert_eq!(output.new_session_id, Some("sess-42".to_string()));
    }

    #[test]
    fn build_docker_args_basic() {
        use crate::mount_security::{MountMode, MountSpec};
        use std::path::PathBuf;

        let mounts = vec![MountSpec {
            host_path: PathBuf::from("/host/data"),
            container_path: "/workspace/data".to_string(),
            mode: MountMode::ReadOnly,
        }];

        let mut env_map = HashMap::new();
        env_map.insert("API_KEY".to_string(), "secret".to_string());

        let cfg = test_config();
        let args = build_docker_args("test_group", &mounts, &env_map, &cfg);

        assert!(args.contains(&"run".to_string()));
        assert!(args.contains(&"--rm".to_string()));
        assert!(args.contains(&"--network=none".to_string()));
        assert!(args.contains(&"--memory=2g".to_string()));
        assert!(args.contains(&"-v".to_string()));
        assert!(args.contains(&"/host/data:/workspace/data:ro".to_string()));
        assert!(args.contains(&"-e".to_string()));
        assert!(args.contains(&"API_KEY=secret".to_string()));
        assert!(args.contains(&"nanogridbot-agent:latest".to_string()));
    }

    #[test]
    fn build_docker_args_no_env() {
        let cfg = test_config();
        let args = build_docker_args("grp", &[], &HashMap::new(), &cfg);
        // Should not contain -e flag when no env vars
        let e_positions: Vec<_> = args
            .iter()
            .enumerate()
            .filter(|(_, a)| *a == "-e")
            .collect();
        assert!(e_positions.is_empty());
    }

    #[test]
    fn build_docker_args_container_name_format() {
        let cfg = test_config();
        let args = build_docker_args("my_group", &[], &HashMap::new(), &cfg);
        let name_idx = args.iter().position(|a| a == "--name").unwrap();
        let name = &args[name_idx + 1];
        assert!(name.starts_with("ngb-my_group-"));
    }

    #[test]
    fn markers_are_distinct() {
        assert_ne!(OUTPUT_START_MARKER, OUTPUT_END_MARKER);
        assert!(!OUTPUT_START_MARKER.is_empty());
        assert!(!OUTPUT_END_MARKER.is_empty());
    }

    fn test_config() -> Config {
        let base = std::path::PathBuf::from("/tmp/ngb-test");
        Config {
            project_name: "test".to_string(),
            version: "0.0.1".to_string(),
            debug: false,
            base_dir: base.clone(),
            data_dir: base.join("data"),
            store_dir: base.join("store"),
            groups_dir: base.join("groups"),
            db_path: base.join("store/messages.db"),
            whatsapp_session_path: base.join("store/whatsapp_session"),
            openai_api_key: None,
            anthropic_api_key: None,
            telegram_bot_token: None,
            slack_bot_token: None,
            slack_signing_secret: None,
            discord_bot_token: None,
            qq_host: "127.0.0.1".to_string(),
            qq_port: 20000,
            feishu_app_id: None,
            feishu_app_secret: None,
            wecom_corp_id: None,
            wecom_agent_id: None,
            wecom_secret: None,
            dingtalk_app_key: None,
            dingtalk_app_secret: None,
            claude_api_url: "https://api.anthropic.com".to_string(),
            claude_api_version: "2023-06-01".to_string(),
            claude_model: "claude-sonnet-4-20250514".to_string(),
            claude_max_tokens: 4096,
            cli_default_group: "cli".to_string(),
            container_timeout: 300,
            container_max_output_size: 100_000,
            container_max_concurrent: 5,
            container_image: "nanogridbot-agent:latest".to_string(),
            assistant_name: "Andy".to_string(),
            trigger_pattern: None,
            poll_interval: 2000,
            max_messages_per_minute: 10,
            message_cache_size: 1000,
            batch_size: 100,
            db_connection_pool_size: 5,
            ipc_file_buffer_size: 8192,
            log_level: "INFO".to_string(),
            log_format: "default".to_string(),
            log_rotation: "10 MB".to_string(),
            log_retention: "7 days".to_string(),
            web_host: "0.0.0.0".to_string(),
            web_port: 8080,
        }
    }
}
