//! Pre-launch preparation for agent containers.
//!
//! Before spawning a container, the host must:
//! 1. Ensure group workspace directory exists
//! 2. Initialize .claude/settings.json (if first run)
//! 3. Sync shared skills from container/skills/ to group's .claude/skills/
//! 4. Write current_tasks.json snapshot to IPC directory
//! 5. Write available_groups.json snapshot to IPC directory
//! 6. Filter environment variables (only ANTHROPIC_API_KEY etc.)

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use ngb_config::Config;
use ngb_types::{NanoGridBotError, RegisteredGroup, Result, ScheduledTask};
use tracing::{debug, info};

/// Ensure the group workspace and IPC directories exist.
pub fn ensure_workspace_dirs(config: &Config, group_folder: &str) -> Result<PathBuf> {
    let group_dir = config.groups_dir.join(group_folder);
    std::fs::create_dir_all(&group_dir).map_err(|e| {
        NanoGridBotError::Container(format!(
            "Failed to create group dir {}: {e}",
            group_dir.display()
        ))
    })?;

    // Session state directory (.claude/)
    let sessions_dir = config.data_dir.join("sessions").join(group_folder);
    let claude_dir = sessions_dir.join(".claude");
    std::fs::create_dir_all(&claude_dir).map_err(|e| {
        NanoGridBotError::Container(format!(
            "Failed to create .claude dir {}: {e}",
            claude_dir.display()
        ))
    })?;

    // IPC directories
    let ipc_dir = config.data_dir.join("ipc").join(group_folder);
    for sub in ["messages", "tasks", "input"] {
        std::fs::create_dir_all(ipc_dir.join(sub)).map_err(|e| {
            NanoGridBotError::Container(format!(
                "Failed to create IPC dir {}/{sub}: {e}",
                ipc_dir.display()
            ))
        })?;
    }

    debug!(group = group_folder, "Group directories ensured");
    Ok(group_dir)
}

/// Initialize .claude/settings.json if it doesn't exist yet.
///
/// Creates a minimal settings file that allows the agent to run
/// with appropriate permissions inside the container.
pub fn init_settings_json(sessions_dir: &Path, group_folder: &str) -> Result<()> {
    let claude_dir = sessions_dir.join(group_folder).join(".claude");
    let settings_path = claude_dir.join("settings.json");

    if settings_path.exists() {
        debug!(
            group = group_folder,
            "settings.json already exists, skipping"
        );
        return Ok(());
    }

    std::fs::create_dir_all(&claude_dir)
        .map_err(|e| NanoGridBotError::Container(format!("Failed to create .claude dir: {e}")))?;

    let settings = serde_json::json!({
        "permissions": {
            "allow": ["Bash", "Read", "Write", "Edit", "Glob", "Grep",
                      "WebSearch", "WebFetch", "Task", "TaskOutput", "TaskStop",
                      "NotebookEdit", "mcp__ngb__*"],
            "deny": []
        }
    });

    let content = serde_json::to_string_pretty(&settings)
        .map_err(|e| NanoGridBotError::Container(format!("Failed to serialize settings: {e}")))?;

    std::fs::write(&settings_path, content).map_err(|e| {
        NanoGridBotError::Container(format!(
            "Failed to write settings.json at {}: {e}",
            settings_path.display()
        ))
    })?;

    info!(group = group_folder, "Initialized settings.json");
    Ok(())
}

/// Sync shared skills from container/skills/ to the group's .claude/skills/ directory.
pub fn sync_skills(skills_src: &Path, sessions_dir: &Path, group_folder: &str) -> Result<()> {
    if !skills_src.exists() {
        debug!("Skills source directory does not exist, skipping sync");
        return Ok(());
    }

    let target_dir = sessions_dir
        .join(group_folder)
        .join(".claude")
        .join("skills");
    std::fs::create_dir_all(&target_dir)
        .map_err(|e| NanoGridBotError::Container(format!("Failed to create skills dir: {e}")))?;

    let entries = std::fs::read_dir(skills_src)
        .map_err(|e| NanoGridBotError::Container(format!("Failed to read skills source: {e}")))?;

    let mut count = 0;
    for entry in entries {
        let entry = entry.map_err(|e| {
            NanoGridBotError::Container(format!("Failed to read skills entry: {e}"))
        })?;
        let path = entry.path();
        if path.is_file() {
            let filename = path.file_name().unwrap();
            let dest = target_dir.join(filename);
            std::fs::copy(&path, &dest).map_err(|e| {
                NanoGridBotError::Container(format!("Failed to copy skill {}: {e}", path.display()))
            })?;
            count += 1;
        }
    }

    if count > 0 {
        debug!(group = group_folder, count, "Skills synced");
    }
    Ok(())
}

/// Write a snapshot of current tasks to the IPC directory.
pub fn write_tasks_snapshot(
    ipc_dir: &Path,
    group_folder: &str,
    is_main: bool,
    tasks: &[ScheduledTask],
) -> Result<()> {
    let filtered: Vec<&ScheduledTask> = if is_main {
        tasks.iter().collect()
    } else {
        tasks
            .iter()
            .filter(|t| t.group_folder == group_folder)
            .collect()
    };

    let group_ipc = ipc_dir.join(group_folder);
    std::fs::create_dir_all(&group_ipc)
        .map_err(|e| NanoGridBotError::Container(format!("Failed to create IPC dir: {e}")))?;

    let path = group_ipc.join("current_tasks.json");
    let content = serde_json::to_string_pretty(&filtered)
        .map_err(|e| NanoGridBotError::Container(format!("Failed to serialize tasks: {e}")))?;

    std::fs::write(&path, content)
        .map_err(|e| NanoGridBotError::Container(format!("Failed to write tasks snapshot: {e}")))?;

    debug!(
        group = group_folder,
        count = filtered.len(),
        "Tasks snapshot written"
    );
    Ok(())
}

/// Write a snapshot of available groups to the IPC directory.
pub fn write_workspaces_snapshot(
    ipc_dir: &Path,
    group_folder: &str,
    is_main: bool,
    groups: &[RegisteredGroup],
) -> Result<()> {
    // Only main group gets the full list
    if !is_main {
        return Ok(());
    }

    let group_ipc = ipc_dir.join(group_folder);
    std::fs::create_dir_all(&group_ipc)
        .map_err(|e| NanoGridBotError::Container(format!("Failed to create IPC dir: {e}")))?;

    let path = group_ipc.join("available_groups.json");
    let content = serde_json::to_string_pretty(groups)
        .map_err(|e| NanoGridBotError::Container(format!("Failed to serialize groups: {e}")))?;

    std::fs::write(&path, content).map_err(|e| {
        NanoGridBotError::Container(format!("Failed to write groups snapshot: {e}"))
    })?;

    debug!(
        group = group_folder,
        count = groups.len(),
        "Groups snapshot written"
    );
    Ok(())
}

/// Filter environment variables to only pass safe ones to the container.
pub fn filter_env_vars(config: &Config) -> HashMap<String, String> {
    let mut env = HashMap::new();

    if let Some(ref key) = config.anthropic_api_key {
        env.insert("ANTHROPIC_API_KEY".to_string(), key.clone());
    }

    if let Some(ref key) = config.openai_api_key {
        env.insert("OPENAI_API_KEY".to_string(), key.clone());
    }

    env
}

/// Run all preparation steps before container launch.
///
/// Returns the filtered environment variables to pass to the container.
pub fn prepare_container_launch(
    config: &Config,
    group_folder: &str,
    is_main: bool,
    tasks: &[ScheduledTask],
    groups: &[RegisteredGroup],
) -> Result<HashMap<String, String>> {
    // 1. Ensure directories
    ensure_workspace_dirs(config, group_folder)?;

    // 2. Init settings.json
    let sessions_dir = config.data_dir.join("sessions");
    init_settings_json(&sessions_dir, group_folder)?;

    // 3. Sync skills
    let skills_src = config.base_dir.join("container").join("skills");
    sync_skills(&skills_src, &sessions_dir, group_folder)?;

    // 4. Write tasks snapshot
    let ipc_dir = config.data_dir.join("ipc");
    write_tasks_snapshot(&ipc_dir, group_folder, is_main, tasks)?;

    // 5. Write groups snapshot
    write_workspaces_snapshot(&ipc_dir, group_folder, is_main, groups)?;

    // 6. Filter env vars
    let env = filter_env_vars(config);

    info!(
        group = group_folder,
        is_main,
        env_count = env.len(),
        "Container launch prepared"
    );
    Ok(env)
}

#[cfg(test)]
mod tests {
    use super::*;
    use ngb_types::{ScheduleType, TaskStatus};
    use tempfile::TempDir;

    fn test_config(base: &Path) -> Config {
        Config {
            project_name: "test".to_string(),
            version: "0.0.1".to_string(),
            debug: false,
            base_dir: base.to_path_buf(),
            data_dir: base.join("data"),
            store_dir: base.join("store"),
            groups_dir: base.join("groups"),
            workspaces_dir: base.join("workspaces"),
            db_path: base.join("store/messages.db"),
            whatsapp_session_path: base.join("store/whatsapp_session"),
            openai_api_key: Some("sk-test-openai".to_string()),
            anthropic_api_key: Some("sk-ant-test".to_string()),
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
    fn ensure_workspace_dirs_creates_all() {
        let tmp = TempDir::new().unwrap();
        let config = test_config(tmp.path());

        let group_dir = ensure_workspace_dirs(&config, "test-group").unwrap();
        assert!(group_dir.exists());
        assert!(config.data_dir.join("sessions/test-group/.claude").exists());
        assert!(config.data_dir.join("ipc/test-group/messages").exists());
        assert!(config.data_dir.join("ipc/test-group/tasks").exists());
        assert!(config.data_dir.join("ipc/test-group/input").exists());
    }

    #[test]
    fn init_settings_json_creates_file() {
        let tmp = TempDir::new().unwrap();
        let sessions_dir = tmp.path().join("sessions");

        init_settings_json(&sessions_dir, "main").unwrap();

        let path = sessions_dir.join("main/.claude/settings.json");
        assert!(path.exists());

        let content: serde_json::Value =
            serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
        assert!(content["permissions"]["allow"].is_array());
    }

    #[test]
    fn init_settings_json_idempotent() {
        let tmp = TempDir::new().unwrap();
        let sessions_dir = tmp.path().join("sessions");

        init_settings_json(&sessions_dir, "main").unwrap();

        // Write custom content
        let path = sessions_dir.join("main/.claude/settings.json");
        std::fs::write(&path, r#"{"custom": true}"#).unwrap();

        // Should not overwrite
        init_settings_json(&sessions_dir, "main").unwrap();
        let content = std::fs::read_to_string(&path).unwrap();
        assert!(content.contains("custom"));
    }

    #[test]
    fn sync_skills_copies_files() {
        let tmp = TempDir::new().unwrap();
        let skills_src = tmp.path().join("skills");
        std::fs::create_dir_all(&skills_src).unwrap();
        std::fs::write(skills_src.join("browser.md"), "# Browser skill").unwrap();
        std::fs::write(skills_src.join("search.md"), "# Search skill").unwrap();

        let sessions_dir = tmp.path().join("sessions");
        sync_skills(&skills_src, &sessions_dir, "main").unwrap();

        let target = sessions_dir.join("main/.claude/skills");
        assert!(target.join("browser.md").exists());
        assert!(target.join("search.md").exists());
    }

    #[test]
    fn sync_skills_no_source_dir() {
        let tmp = TempDir::new().unwrap();
        let sessions_dir = tmp.path().join("sessions");
        // Should not error when source doesn't exist
        sync_skills(&tmp.path().join("nonexistent"), &sessions_dir, "main").unwrap();
    }

    #[test]
    fn write_tasks_snapshot_main_sees_all() {
        let tmp = TempDir::new().unwrap();
        let ipc_dir = tmp.path().join("ipc");

        let tasks = vec![
            ScheduledTask {
                id: Some(1),
                group_folder: "main".to_string(),
                prompt: "task 1".to_string(),
                schedule_type: ScheduleType::Cron,
                schedule_value: "0 9 * * *".to_string(),
                status: TaskStatus::Active,
                next_run: None,
                context_mode: "group".to_string(),
                target_chat_jid: None,
            },
            ScheduledTask {
                id: Some(2),
                group_folder: "dev".to_string(),
                prompt: "task 2".to_string(),
                schedule_type: ScheduleType::Interval,
                schedule_value: "300000".to_string(),
                status: TaskStatus::Active,
                next_run: None,
                context_mode: "isolated".to_string(),
                target_chat_jid: None,
            },
        ];

        write_tasks_snapshot(&ipc_dir, "main", true, &tasks).unwrap();

        let content = std::fs::read_to_string(ipc_dir.join("main/current_tasks.json")).unwrap();
        let parsed: Vec<serde_json::Value> = serde_json::from_str(&content).unwrap();
        assert_eq!(parsed.len(), 2);
    }

    #[test]
    fn write_tasks_snapshot_non_main_filtered() {
        let tmp = TempDir::new().unwrap();
        let ipc_dir = tmp.path().join("ipc");

        let tasks = vec![
            ScheduledTask {
                id: Some(1),
                group_folder: "main".to_string(),
                prompt: "task 1".to_string(),
                schedule_type: ScheduleType::Cron,
                schedule_value: "0 9 * * *".to_string(),
                status: TaskStatus::Active,
                next_run: None,
                context_mode: "group".to_string(),
                target_chat_jid: None,
            },
            ScheduledTask {
                id: Some(2),
                group_folder: "dev".to_string(),
                prompt: "task 2".to_string(),
                schedule_type: ScheduleType::Interval,
                schedule_value: "300000".to_string(),
                status: TaskStatus::Active,
                next_run: None,
                context_mode: "isolated".to_string(),
                target_chat_jid: None,
            },
        ];

        write_tasks_snapshot(&ipc_dir, "dev", false, &tasks).unwrap();

        let content = std::fs::read_to_string(ipc_dir.join("dev/current_tasks.json")).unwrap();
        let parsed: Vec<serde_json::Value> = serde_json::from_str(&content).unwrap();
        assert_eq!(parsed.len(), 1);
        assert_eq!(parsed[0]["group_folder"], "dev");
    }

    #[test]
    fn filter_env_vars_includes_api_keys() {
        let tmp = TempDir::new().unwrap();
        let config = test_config(tmp.path());

        let env = filter_env_vars(&config);
        assert_eq!(env.get("ANTHROPIC_API_KEY").unwrap(), "sk-ant-test");
        assert_eq!(env.get("OPENAI_API_KEY").unwrap(), "sk-test-openai");
        assert!(!env.contains_key("TELEGRAM_BOT_TOKEN"));
    }

    #[test]
    fn prepare_container_launch_full() {
        let tmp = TempDir::new().unwrap();
        let config = test_config(tmp.path());

        // Create skills source
        let skills_dir = tmp.path().join("container/skills");
        std::fs::create_dir_all(&skills_dir).unwrap();
        std::fs::write(skills_dir.join("test.md"), "# Test").unwrap();

        let env = prepare_container_launch(
            &config,
            "main",
            true,
            &[],
            &[RegisteredGroup {
                jid: "telegram:123".to_string(),
                name: "Main".to_string(),
                folder: "main".to_string(),
                trigger_pattern: None,
                container_config: None,
                requires_trigger: true,
            }],
        )
        .unwrap();

        // Verify directories created
        assert!(config.groups_dir.join("main").exists());
        assert!(config.data_dir.join("sessions/main/.claude").exists());

        // Verify settings.json
        assert!(config
            .data_dir
            .join("sessions/main/.claude/settings.json")
            .exists());

        // Verify skills synced
        assert!(config
            .data_dir
            .join("sessions/main/.claude/skills/test.md")
            .exists());

        // Verify snapshots
        assert!(config.data_dir.join("ipc/main/current_tasks.json").exists());
        assert!(config
            .data_dir
            .join("ipc/main/available_groups.json")
            .exists());

        // Verify env
        assert!(env.contains_key("ANTHROPIC_API_KEY"));
    }
}
