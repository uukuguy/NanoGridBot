use std::path::PathBuf;

use ngb_config::Config;
use ngb_types::{NanoGridBotError, Result};
use serde::{Deserialize, Serialize};

use crate::security::check_path_traversal;

/// Mount permission mode for Docker volumes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MountMode {
    ReadOnly,
    ReadWrite,
}

impl MountMode {
    /// Docker volume suffix string.
    pub fn as_docker_flag(&self) -> &str {
        match self {
            Self::ReadOnly => "ro",
            Self::ReadWrite => "rw",
        }
    }
}

/// A validated Docker bind-mount specification.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MountSpec {
    pub host_path: PathBuf,
    pub container_path: String,
    pub mode: MountMode,
}

impl MountSpec {
    /// Format as Docker `-v` argument value: `host:container:mode`.
    pub fn to_docker_arg(&self) -> String {
        format!(
            "{}:{}:{}",
            self.host_path.display(),
            self.container_path,
            self.mode.as_docker_flag()
        )
    }
}

/// Return the set of host paths allowed as mount sources.
pub fn get_allowed_mount_paths(config: &Config) -> Vec<PathBuf> {
    vec![
        config.groups_dir.clone(),
        config.data_dir.clone(),
        config.store_dir.clone(),
        config.base_dir.clone(),
    ]
}

/// Build and validate the mount list for a container run.
///
/// Standard mounts:
/// - `{groups_dir}/{group_folder}` → `/workspace/group` (rw)
/// - `{data_dir}/global`           → `/workspace/global` (ro)
/// - `{data_dir}/sessions`         → `/workspace/sessions` (rw)
/// - `{data_dir}/ipc/{chat_jid}`   → `/workspace/ipc` (rw)
/// - If `is_main`: `{base_dir}`    → `/workspace/project` (ro)
///
/// Additional mounts come from `ContainerConfig::additional_mounts`.
pub fn validate_workspace_mounts(
    group_folder: &str,
    chat_jid: &str,
    is_main: bool,
    additional_mounts: &[std::collections::HashMap<String, serde_json::Value>],
    config: &Config,
) -> Result<Vec<MountSpec>> {
    let allowed = get_allowed_mount_paths(config);
    let mut mounts = Vec::new();

    // Group folder — read/write
    let group_host = config.groups_dir.join(group_folder);
    mounts.push(MountSpec {
        host_path: group_host,
        container_path: "/workspace/group".to_string(),
        mode: MountMode::ReadWrite,
    });

    // Global data — read-only
    let global_host = config.data_dir.join("global");
    mounts.push(MountSpec {
        host_path: global_host,
        container_path: "/workspace/global".to_string(),
        mode: MountMode::ReadOnly,
    });

    // Sessions — read/write
    let sessions_host = config.data_dir.join("sessions");
    mounts.push(MountSpec {
        host_path: sessions_host,
        container_path: "/workspace/sessions".to_string(),
        mode: MountMode::ReadWrite,
    });

    // IPC directory — read/write
    let ipc_host = config.data_dir.join("ipc").join(chat_jid);
    mounts.push(MountSpec {
        host_path: ipc_host,
        container_path: "/workspace/ipc".to_string(),
        mode: MountMode::ReadWrite,
    });

    // Project root for main container — read-only
    if is_main {
        mounts.push(MountSpec {
            host_path: config.base_dir.clone(),
            container_path: "/workspace/project".to_string(),
            mode: MountMode::ReadOnly,
        });
    }

    // Merge additional mounts from ContainerConfig
    for mount_map in additional_mounts {
        let host = mount_map
            .get("host_path")
            .and_then(|v| v.as_str())
            .unwrap_or_default();
        let container = mount_map
            .get("container_path")
            .and_then(|v| v.as_str())
            .unwrap_or_default();
        let mode_str = mount_map
            .get("mode")
            .and_then(|v| v.as_str())
            .unwrap_or("ro");

        if host.is_empty() || container.is_empty() {
            continue;
        }

        // Security: reject path traversal
        if check_path_traversal(host) || check_path_traversal(container) {
            return Err(NanoGridBotError::Security(format!(
                "Path traversal detected in mount: {host} -> {container}"
            )));
        }

        let host_path = PathBuf::from(host);

        // Security: host path must be under an allowed prefix
        let is_allowed = allowed.iter().any(|a| host_path.starts_with(a));
        if !is_allowed {
            return Err(NanoGridBotError::Security(format!(
                "Mount host path not in allowed list: {host}"
            )));
        }

        let mode = if mode_str == "rw" {
            MountMode::ReadWrite
        } else {
            MountMode::ReadOnly
        };

        mounts.push(MountSpec {
            host_path,
            container_path: container.to_string(),
            mode,
        });
    }

    Ok(mounts)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_config() -> Config {
        let base = PathBuf::from("/tmp/ngb-test");
        Config {
            project_name: "test".to_string(),
            version: "0.0.1".to_string(),
            debug: false,
            base_dir: base.clone(),
            data_dir: base.join("data"),
            store_dir: base.join("store"),
            groups_dir: base.join("groups"),
            workspaces_dir: base.join("workspaces"),
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

    #[test]
    fn standard_mounts_non_main() {
        let cfg = test_config();
        let mounts = validate_workspace_mounts("my_group", "telegram:123", false, &[], &cfg).unwrap();
        assert_eq!(mounts.len(), 4);
        assert_eq!(mounts[0].container_path, "/workspace/group");
        assert_eq!(mounts[0].mode, MountMode::ReadWrite);
        assert_eq!(mounts[1].container_path, "/workspace/global");
        assert_eq!(mounts[1].mode, MountMode::ReadOnly);
    }

    #[test]
    fn standard_mounts_main_includes_project() {
        let cfg = test_config();
        let mounts = validate_workspace_mounts("g1", "slack:C1", true, &[], &cfg).unwrap();
        assert_eq!(mounts.len(), 5);
        assert_eq!(mounts[4].container_path, "/workspace/project");
        assert_eq!(mounts[4].mode, MountMode::ReadOnly);
    }

    #[test]
    fn additional_mount_allowed() {
        let cfg = test_config();
        let mut extra = std::collections::HashMap::new();
        extra.insert(
            "host_path".to_string(),
            serde_json::json!("/tmp/ngb-test/data/custom"),
        );
        extra.insert(
            "container_path".to_string(),
            serde_json::json!("/workspace/custom"),
        );
        extra.insert("mode".to_string(), serde_json::json!("rw"));

        let mounts = validate_workspace_mounts("g1", "tg:1", false, &[extra], &cfg).unwrap();
        assert_eq!(mounts.len(), 5);
        assert_eq!(mounts[4].container_path, "/workspace/custom");
        assert_eq!(mounts[4].mode, MountMode::ReadWrite);
    }

    #[test]
    fn additional_mount_disallowed_path() {
        let cfg = test_config();
        let mut extra = std::collections::HashMap::new();
        extra.insert("host_path".to_string(), serde_json::json!("/etc/passwd"));
        extra.insert(
            "container_path".to_string(),
            serde_json::json!("/workspace/bad"),
        );

        let result = validate_workspace_mounts("g1", "tg:1", false, &[extra], &cfg);
        assert!(result.is_err());
        let msg = result.unwrap_err().to_string();
        assert!(msg.contains("not in allowed list"));
    }

    #[test]
    fn path_traversal_rejected() {
        let cfg = test_config();
        let mut extra = std::collections::HashMap::new();
        extra.insert(
            "host_path".to_string(),
            serde_json::json!("/tmp/ngb-test/data/../../../etc"),
        );
        extra.insert(
            "container_path".to_string(),
            serde_json::json!("/workspace/exploit"),
        );

        let result = validate_workspace_mounts("g1", "tg:1", false, &[extra], &cfg);
        assert!(result.is_err());
        let msg = result.unwrap_err().to_string();
        assert!(msg.contains("traversal"));
    }

    #[test]
    fn mount_spec_docker_arg_format() {
        let spec = MountSpec {
            host_path: PathBuf::from("/host/dir"),
            container_path: "/container/dir".to_string(),
            mode: MountMode::ReadOnly,
        };
        assert_eq!(spec.to_docker_arg(), "/host/dir:/container/dir:ro");

        let spec_rw = MountSpec {
            host_path: PathBuf::from("/host/rw"),
            container_path: "/container/rw".to_string(),
            mode: MountMode::ReadWrite,
        };
        assert_eq!(spec_rw.to_docker_arg(), "/host/rw:/container/rw:rw");
    }
}
