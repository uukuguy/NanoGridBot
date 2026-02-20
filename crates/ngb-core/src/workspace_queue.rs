use std::collections::{HashMap, VecDeque};
use std::sync::Arc;

use ngb_config::Config;
use ngb_db::Database;
use ngb_types::{Result, ScheduledTask};
use tokio::sync::Mutex;
use tracing::{debug, error, warn};

use crate::container_runner::run_container_agent;

/// Maximum number of retry attempts per group.
const MAX_RETRIES: u32 = 5;

/// Per-workspace processing state.
#[derive(Debug)]
struct WorkspaceState {
    #[allow(dead_code)]
    jid: String,
    active: bool,
    pending_messages: VecDeque<PendingMessage>,
    pending_tasks: VecDeque<ScheduledTask>,
    workspace_folder: String,
    retry_count: u32,
}

/// A pending message-check request.
#[derive(Debug, Clone)]
struct PendingMessage {
    session_id: String,
    last_timestamp: Option<String>,
}

/// Concurrent workspace processing queue with state machine, retry, and priority.
///
/// Manages which workspaces are actively running containers and queues overflow.
/// Concurrency is capped at `container_max_concurrent`.
pub struct WorkspaceQueue {
    inner: Arc<Mutex<QueueInner>>,
    config: Config,
    db: Arc<Database>,
}

struct QueueInner {
    states: HashMap<String, WorkspaceState>,
    active_count: usize,
    waiting_workspaces: VecDeque<String>,
    max_concurrent: usize,
}

/// Ensure a WorkspaceState entry exists for the given JID.
fn ensure_state(states: &mut HashMap<String, WorkspaceState>, jid: &str, workspace_folder: &str) {
    states.entry(jid.to_string()).or_insert_with(|| WorkspaceState {
        jid: jid.to_string(),
        active: false,
        pending_messages: VecDeque::new(),
        pending_tasks: VecDeque::new(),
        workspace_folder: workspace_folder.to_string(),
        retry_count: 0,
    });
}

/// Try to activate a group. Returns true if the group was activated.
/// Must be called with mutable access to the entire QueueInner.
fn try_activate(inner: &mut QueueInner, jid: &str) -> bool {
    let state = inner.states.get(jid).unwrap();
    if !state.active && inner.active_count < inner.max_concurrent {
        let state = inner.states.get_mut(jid).unwrap();
        state.active = true;
        inner.active_count += 1;
        true
    } else if !state.active && !inner.waiting_workspaces.contains(&jid.to_string()) {
        inner.waiting_workspaces.push_back(jid.to_string());
        false
    } else {
        false
    }
}

impl WorkspaceQueue {
    /// Create a new workspace queue.
    pub fn new(config: Config, db: Arc<Database>) -> Self {
        let max_concurrent = config.container_max_concurrent;
        Self {
            inner: Arc::new(Mutex::new(QueueInner {
                states: HashMap::new(),
                active_count: 0,
                waiting_workspaces: VecDeque::new(),
                max_concurrent,
            })),
            config,
            db,
        }
    }

    /// Enqueue a message-check for a group.
    ///
    /// If the group is idle and capacity is available, starts processing
    /// immediately. Otherwise queues the request.
    pub async fn enqueue_message_check(
        &self,
        jid: &str,
        workspace_folder: &str,
        session_id: &str,
        last_timestamp: Option<&str>,
    ) -> Result<()> {
        let should_start = {
            let mut inner = self.inner.lock().await;
            ensure_state(&mut inner.states, jid, workspace_folder);
            let state = inner.states.get_mut(jid).unwrap();

            state.pending_messages.push_back(PendingMessage {
                session_id: session_id.to_string(),
                last_timestamp: last_timestamp.map(|s| s.to_string()),
            });

            try_activate(&mut inner, jid)
        };
        // Lock is dropped here

        if should_start {
            self.process_workspace(jid.to_string()).await;
        }

        Ok(())
    }

    /// Enqueue a scheduled task for a group.
    ///
    /// Tasks have higher priority than messages and are drained first.
    pub async fn enqueue_task(
        &self,
        jid: &str,
        workspace_folder: &str,
        task: ScheduledTask,
        session_id: &str,
    ) -> Result<()> {
        let should_start = {
            let mut inner = self.inner.lock().await;
            ensure_state(&mut inner.states, jid, workspace_folder);
            let state = inner.states.get_mut(jid).unwrap();

            state.pending_tasks.push_back(task);

            // Also enqueue a dummy message entry so the session_id is available
            if state.pending_messages.is_empty() {
                state.pending_messages.push_back(PendingMessage {
                    session_id: session_id.to_string(),
                    last_timestamp: None,
                });
            }

            try_activate(&mut inner, jid)
        };

        if should_start {
            self.process_workspace(jid.to_string()).await;
        }

        Ok(())
    }

    /// Get the number of currently active (running) groups.
    pub async fn get_active_count(&self) -> usize {
        self.inner.lock().await.active_count
    }

    /// Get the number of groups waiting for a slot.
    pub async fn get_waiting_count(&self) -> usize {
        self.inner.lock().await.waiting_workspaces.len()
    }

    /// Process a workspace: drain tasks first, then messages.
    ///
    /// Uses `tokio::spawn` internally to avoid holding the Mutex during
    /// container execution.
    async fn process_workspace(&self, jid: String) {
        let inner = self.inner.clone();
        let config = self.config.clone();
        let db = self.db.clone();

        tokio::spawn(async move {
            loop {
                // Extract next work item (drop lock before await)
                let work = {
                    let mut guard = inner.lock().await;
                    let state = match guard.states.get_mut(&jid) {
                        Some(s) => s,
                        None => break,
                    };

                    // Priority: tasks first, then messages
                    if let Some(task) = state.pending_tasks.pop_front() {
                        let session_id = state
                            .pending_messages
                            .front()
                            .map(|m| m.session_id.clone())
                            .unwrap_or_else(|| "default".to_string());
                        Some(WorkItem::Task {
                            task,
                            workspace_folder: state.workspace_folder.clone(),
                            session_id,
                        })
                    } else if let Some(msg) = state.pending_messages.pop_front() {
                        Some(WorkItem::Message {
                            workspace_folder: state.workspace_folder.clone(),
                            session_id: msg.session_id,
                            last_timestamp: msg.last_timestamp,
                        })
                    } else {
                        None
                    }
                };
                // Lock is dropped

                match work {
                    Some(WorkItem::Task {
                        task,
                        workspace_folder,
                        session_id,
                    }) => {
                        debug!(jid = %jid, prompt = %task.prompt, "Processing scheduled task");
                        let result = run_container_agent(
                            &workspace_folder,
                            &task.prompt,
                            &session_id,
                            &jid,
                            false,
                            &[],
                            None,
                            &std::collections::HashMap::new(),
                            &config,
                            &db,
                        )
                        .await;

                        handle_result(&inner, &jid, result.is_ok()).await;
                    }
                    Some(WorkItem::Message {
                        workspace_folder,
                        session_id,
                        last_timestamp,
                    }) => {
                        let prompt = format!(
                            "Check messages{}",
                            last_timestamp
                                .as_deref()
                                .map(|t| format!(" since {t}"))
                                .unwrap_or_default()
                        );
                        debug!(jid = %jid, "Processing message check");
                        let result = run_container_agent(
                            &workspace_folder,
                            &prompt,
                            &session_id,
                            &jid,
                            false,
                            &[],
                            None,
                            &std::collections::HashMap::new(),
                            &config,
                            &db,
                        )
                        .await;

                        handle_result(&inner, &jid, result.is_ok()).await;
                    }
                    None => {
                        // No more work — deactivate group, start next waiting
                        let next = {
                            let mut guard = inner.lock().await;
                            if let Some(state) = guard.states.get_mut(&jid) {
                                state.active = false;
                            }
                            guard.active_count = guard.active_count.saturating_sub(1);

                            // Find next waiting workspace
                            guard.waiting_workspaces.pop_front()
                        };

                        if let Some(next_jid) = next {
                            let mut guard = inner.lock().await;
                            if let Some(state) = guard.states.get_mut(&next_jid) {
                                state.active = true;
                                guard.active_count += 1;
                            }
                            drop(guard);

                            // Recursively process the next group in a new task
                            let inner2 = inner.clone();
                            let config2 = config.clone();
                            let db2 = db.clone();
                            tokio::spawn(async move {
                                // Re-enter the process loop for the next group
                                // We create a temporary WorkspaceQueue-like driver
                                process_workspace_loop(inner2, next_jid, config2, db2).await;
                            });
                        }

                        break;
                    }
                }
            }
        });
    }
}

/// Standalone processing loop used when promoting a waiting workspace.
async fn process_workspace_loop(
    inner: Arc<Mutex<QueueInner>>,
    jid: String,
    config: Config,
    db: Arc<Database>,
) {
    loop {
        let work = {
            let mut guard = inner.lock().await;
            let state = match guard.states.get_mut(&jid) {
                Some(s) => s,
                None => break,
            };

            if let Some(task) = state.pending_tasks.pop_front() {
                let session_id = state
                    .pending_messages
                    .front()
                    .map(|m| m.session_id.clone())
                    .unwrap_or_else(|| "default".to_string());
                Some(WorkItem::Task {
                    task,
                    workspace_folder: state.workspace_folder.clone(),
                    session_id,
                })
            } else if let Some(msg) = state.pending_messages.pop_front() {
                Some(WorkItem::Message {
                    workspace_folder: state.workspace_folder.clone(),
                    session_id: msg.session_id,
                    last_timestamp: msg.last_timestamp,
                })
            } else {
                None
            }
        };

        match work {
            Some(WorkItem::Task {
                task,
                workspace_folder,
                session_id,
            }) => {
                let result = run_container_agent(
                    &workspace_folder,
                    &task.prompt,
                    &session_id,
                    &jid,
                    false,
                    &[],
                    None,
                    &std::collections::HashMap::new(),
                    &config,
                    &db,
                )
                .await;
                handle_result(&inner, &jid, result.is_ok()).await;
            }
            Some(WorkItem::Message {
                workspace_folder,
                session_id,
                ..
            }) => {
                let result = run_container_agent(
                    &workspace_folder,
                    "Check messages",
                    &session_id,
                    &jid,
                    false,
                    &[],
                    None,
                    &std::collections::HashMap::new(),
                    &config,
                    &db,
                )
                .await;
                handle_result(&inner, &jid, result.is_ok()).await;
            }
            None => {
                let mut guard = inner.lock().await;
                if let Some(state) = guard.states.get_mut(&jid) {
                    state.active = false;
                }
                guard.active_count = guard.active_count.saturating_sub(1);
                break;
            }
        }
    }
}

/// Handle the result of a container execution: reset or increment retry count.
async fn handle_result(inner: &Arc<Mutex<QueueInner>>, jid: &str, success: bool) {
    let mut guard = inner.lock().await;
    if let Some(state) = guard.states.get_mut(jid) {
        if success {
            state.retry_count = 0;
        } else {
            state.retry_count += 1;
            if state.retry_count >= MAX_RETRIES {
                error!(
                    jid,
                    retries = state.retry_count,
                    "Workspace reached max retries, clearing pending work"
                );
                state.pending_messages.clear();
                state.pending_tasks.clear();
                state.retry_count = 0;
            } else {
                let delay_secs = retry_delay(state.retry_count);
                warn!(
                    jid,
                    retry = state.retry_count,
                    delay_secs,
                    "Container failed, scheduling retry"
                );
                // Drop the lock before sleeping
                drop(guard);
                tokio::time::sleep(std::time::Duration::from_secs(delay_secs)).await;
            }
        }
    }
}

/// Exponential backoff: `5 * 2^(n-1)` seconds.
fn retry_delay(retry_count: u32) -> u64 {
    5 * 2u64.pow(retry_count.saturating_sub(1))
}

/// Internal work-item enum for the processing loop.
enum WorkItem {
    Task {
        task: ScheduledTask,
        workspace_folder: String,
        session_id: String,
    },
    Message {
        workspace_folder: String,
        session_id: String,
        last_timestamp: Option<String>,
    },
}

#[cfg(test)]
mod tests {
    use super::*;
    use ngb_types::{ScheduleType, TaskStatus};

    fn test_config() -> Config {
        let base = std::path::PathBuf::from("/tmp/ngb-queue-test");
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

    fn make_task(prompt: &str) -> ScheduledTask {
        ScheduledTask {
            id: Some(1),
            group_folder: "g1".to_string(),
            prompt: prompt.to_string(),
            schedule_type: ScheduleType::Once,
            schedule_value: "".to_string(),
            status: TaskStatus::Active,
            next_run: None,
            context_mode: "group".to_string(),
            target_chat_jid: None,
        }
    }

    #[test]
    fn retry_delay_calculation() {
        assert_eq!(retry_delay(1), 5); // 5 * 2^0 = 5
        assert_eq!(retry_delay(2), 10); // 5 * 2^1 = 10
        assert_eq!(retry_delay(3), 20); // 5 * 2^2 = 20
        assert_eq!(retry_delay(4), 40); // 5 * 2^3 = 40
        assert_eq!(retry_delay(5), 80); // 5 * 2^4 = 80
    }

    #[test]
    fn retry_delay_zero_count() {
        assert_eq!(retry_delay(0), 5); // saturating_sub(1) -> 0, 2^0 = 1
    }

    #[tokio::test]
    async fn queue_initial_state() {
        let cfg = test_config();
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let queue = WorkspaceQueue::new(cfg, db);
        assert_eq!(queue.get_active_count().await, 0);
        assert_eq!(queue.get_waiting_count().await, 0);
    }

    #[tokio::test]
    async fn queue_state_tracking() {
        let cfg = test_config();
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let queue = WorkspaceQueue::new(cfg, db);

        // Enqueue will attempt to start, which will try docker and fail
        // but the state tracking should still work
        let _ = queue.enqueue_message_check("tg:1", "g1", "s1", None).await;

        // Give the spawned task a moment
        tokio::time::sleep(std::time::Duration::from_millis(50)).await;

        // The spawned task will fail (no docker) but that's OK for state tests
        let inner = queue.inner.lock().await;
        assert!(inner.states.contains_key("tg:1"));
        assert_eq!(inner.states["tg:1"].workspace_folder, "g1");
    }

    #[tokio::test]
    async fn enqueue_message_creates_state() {
        let cfg = test_config();
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let queue = WorkspaceQueue::new(cfg, db);
        let _ = queue
            .enqueue_message_check("slack:C1", "group1", "sess1", Some("2025-01-01T00:00:00Z"))
            .await;

        let inner = queue.inner.lock().await;
        let state = inner.states.get("slack:C1").unwrap();
        assert_eq!(state.workspace_folder, "group1");
    }

    #[tokio::test]
    async fn enqueue_task_creates_state() {
        let cfg = test_config();
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let queue = WorkspaceQueue::new(cfg, db);
        let task = make_task("daily report");
        let _ = queue.enqueue_task("tg:2", "g2", task, "s2").await;

        let inner = queue.inner.lock().await;
        let state = inner.states.get("tg:2").unwrap();
        assert_eq!(state.workspace_folder, "g2");
    }

    #[tokio::test]
    async fn max_concurrent_enforced() {
        let mut cfg = test_config();
        cfg.container_max_concurrent = 2;
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let queue = WorkspaceQueue::new(cfg, db);

        // Manually set up the inner state to simulate concurrency
        {
            let mut inner = queue.inner.lock().await;
            // Simulate 2 active workspaces
            inner.states.insert(
                "tg:1".to_string(),
                WorkspaceState {
                    jid: "tg:1".to_string(),
                    active: true,
                    pending_messages: VecDeque::new(),
                    pending_tasks: VecDeque::new(),
                    workspace_folder: "g1".to_string(),
                    retry_count: 0,
                },
            );
            inner.states.insert(
                "tg:2".to_string(),
                WorkspaceState {
                    jid: "tg:2".to_string(),
                    active: true,
                    pending_messages: VecDeque::new(),
                    pending_tasks: VecDeque::new(),
                    workspace_folder: "g2".to_string(),
                    retry_count: 0,
                },
            );
            inner.active_count = 2;
        }

        // Enqueue for a third group — should go to waiting
        let _ = queue.enqueue_message_check("tg:3", "g3", "s3", None).await;

        let inner = queue.inner.lock().await;
        assert_eq!(inner.active_count, 2);
        assert!(inner.waiting_workspaces.contains(&"tg:3".to_string()));
    }

    #[tokio::test]
    async fn handle_result_resets_on_success() {
        let inner = Arc::new(Mutex::new(QueueInner {
            states: HashMap::new(),
            active_count: 0,
            waiting_workspaces: VecDeque::new(),
            max_concurrent: 5,
        }));

        {
            let mut guard = inner.lock().await;
            guard.states.insert(
                "tg:1".to_string(),
                WorkspaceState {
                    jid: "tg:1".to_string(),
                    active: true,
                    pending_messages: VecDeque::new(),
                    pending_tasks: VecDeque::new(),
                    workspace_folder: "g1".to_string(),
                    retry_count: 3,
                },
            );
        }

        handle_result(&inner, "tg:1", true).await;

        let guard = inner.lock().await;
        assert_eq!(guard.states["tg:1"].retry_count, 0);
    }

    #[tokio::test]
    async fn handle_result_increments_on_failure() {
        let inner = Arc::new(Mutex::new(QueueInner {
            states: HashMap::new(),
            active_count: 0,
            waiting_workspaces: VecDeque::new(),
            max_concurrent: 5,
        }));

        {
            let mut guard = inner.lock().await;
            guard.states.insert(
                "tg:1".to_string(),
                WorkspaceState {
                    jid: "tg:1".to_string(),
                    active: true,
                    pending_messages: VecDeque::new(),
                    pending_tasks: VecDeque::new(),
                    workspace_folder: "g1".to_string(),
                    retry_count: 0,
                },
            );
        }

        // Use timeout to prevent the retry delay from blocking
        let _ = tokio::time::timeout(
            std::time::Duration::from_millis(100),
            handle_result(&inner, "tg:1", false),
        )
        .await;

        let guard = inner.lock().await;
        assert!(guard.states["tg:1"].retry_count >= 1);
    }

    #[tokio::test]
    async fn handle_result_clears_on_max_retries() {
        let inner = Arc::new(Mutex::new(QueueInner {
            states: HashMap::new(),
            active_count: 0,
            waiting_workspaces: VecDeque::new(),
            max_concurrent: 5,
        }));

        {
            let mut guard = inner.lock().await;
            let mut msgs = VecDeque::new();
            msgs.push_back(PendingMessage {
                session_id: "s1".to_string(),
                last_timestamp: None,
            });
            guard.states.insert(
                "tg:1".to_string(),
                WorkspaceState {
                    jid: "tg:1".to_string(),
                    active: true,
                    pending_messages: msgs,
                    pending_tasks: VecDeque::new(),
                    workspace_folder: "g1".to_string(),
                    retry_count: MAX_RETRIES - 1,
                },
            );
        }

        handle_result(&inner, "tg:1", false).await;

        let guard = inner.lock().await;
        let state = &guard.states["tg:1"];
        assert_eq!(state.retry_count, 0);
        assert!(state.pending_messages.is_empty());
    }

    #[test]
    fn max_retries_constant() {
        assert_eq!(MAX_RETRIES, 5);
    }
}
