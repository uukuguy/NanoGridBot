use std::collections::HashMap;
use std::sync::Arc;
use std::time::Instant;

use chrono::{DateTime, Utc};
use ngb_config::Config;
use ngb_db::{BindingRepository, Database, MessageRepository, TokenRepository, WorkspaceRepository};
use ngb_types::{Message, NanoGridBotError, Result, Workspace};
use serde::{Deserialize, Serialize};
use tokio::sync::Mutex;
use tracing::{debug, error, info, warn};

use crate::group_queue::GroupQueue;
use crate::ipc_handler::{ChannelSender, IpcHandler};
use crate::router::{MessageRouter, RouteAction};
use crate::task_scheduler::TaskScheduler;

/// System health status snapshot.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthStatus {
    pub healthy: bool,
    pub channels_connected: usize,
    pub channels_total: usize,
    pub registered_groups: usize,
    pub active_containers: usize,
    pub pending_tasks: usize,
    pub uptime_seconds: f64,
}

/// Main orchestrator that ties all subsystems together.
///
/// Responsible for:
/// - Loading workspaces from DB
/// - Starting/stopping subsystems (scheduler, IPC handler)
/// - Running the message polling loop
/// - Handling token binding and guidance messages
/// - Providing health status
pub struct Orchestrator {
    config: Config,
    db: Arc<Database>,
    channels: Arc<Vec<Box<dyn ChannelSender>>>,
    queue: Arc<GroupQueue>,
    scheduler: Mutex<TaskScheduler>,
    ipc_handler: Mutex<IpcHandler>,
    router: MessageRouter,
    workspaces: Mutex<HashMap<String, Workspace>>,
    last_timestamp: Mutex<Option<DateTime<Utc>>>,
    start_time: Mutex<Option<Instant>>,
    healthy: Mutex<bool>,
    shutdown: tokio::sync::watch::Sender<bool>,
    shutdown_rx: tokio::sync::watch::Receiver<bool>,
}

impl Orchestrator {
    /// Create a new orchestrator instance.
    pub fn new(config: Config, db: Arc<Database>, channels: Vec<Box<dyn ChannelSender>>) -> Self {
        let channels = Arc::new(channels);
        let queue = Arc::new(GroupQueue::new(config.clone(), db.clone()));
        let scheduler = TaskScheduler::new(db.clone(), queue.clone());
        let ipc_handler = IpcHandler::new(channels.clone(), &config);
        let router = MessageRouter::new(config.clone(), db.clone(), channels.clone());
        let (shutdown_tx, shutdown_rx) = tokio::sync::watch::channel(false);

        Self {
            config,
            db,
            channels,
            queue,
            scheduler: Mutex::new(scheduler),
            ipc_handler: Mutex::new(ipc_handler),
            router,
            workspaces: Mutex::new(HashMap::new()),
            last_timestamp: Mutex::new(None),
            start_time: Mutex::new(None),
            healthy: Mutex::new(false),
            shutdown: shutdown_tx,
            shutdown_rx,
        }
    }

    /// Start the orchestrator and all subsystems.
    ///
    /// Flow: load workspaces from DB → start scheduler → start IPC handler →
    /// set healthy → begin message loop.
    pub async fn start(&self) -> Result<()> {
        info!("Starting orchestrator");

        // Load workspaces from DB
        let ws_repo = WorkspaceRepository::new(&self.db);
        let all_ws = ws_repo.get_all().await?;
        {
            let mut ws_map = self.workspaces.lock().await;
            for ws in &all_ws {
                ws_map.insert(ws.id.clone(), ws.clone());
            }
        }
        info!(count = all_ws.len(), "Loaded workspaces");

        // Load bindings to get JIDs for IPC handler
        let binding_repo = BindingRepository::new(&self.db);
        let mut jids = Vec::new();
        for ws in &all_ws {
            let bindings = binding_repo.get_by_workspace(&ws.id).await?;
            for b in bindings {
                jids.push(b.channel_jid);
            }
        }

        // Start subsystems
        {
            let mut scheduler = self.scheduler.lock().await;
            scheduler.start();
        }
        {
            let mut ipc = self.ipc_handler.lock().await;
            ipc.start(&jids);
        }

        // Mark healthy
        *self.healthy.lock().await = true;
        *self.start_time.lock().await = Some(Instant::now());

        info!("Orchestrator started successfully");
        Ok(())
    }

    /// Run the message polling loop.
    pub async fn run_message_loop(&self) -> Result<()> {
        let poll_ms = self.config.poll_interval;
        let mut shutdown_rx = self.shutdown_rx.clone();

        info!(poll_ms, "Message loop started");

        loop {
            tokio::select! {
                _ = tokio::time::sleep(std::time::Duration::from_millis(poll_ms)) => {
                    if let Err(e) = self.poll_messages().await {
                        error!(error = %e, "Message poll failed");
                    }
                }
                _ = shutdown_rx.changed() => {
                    if *shutdown_rx.borrow() {
                        info!("Shutdown signal received, exiting message loop");
                        break;
                    }
                }
            }
        }

        Ok(())
    }

    /// Poll for new messages and route them.
    async fn poll_messages(&self) -> Result<()> {
        let since = { *self.last_timestamp.lock().await };
        let msg_repo = MessageRepository::new(&self.db, self.config.message_cache_size);
        let messages = msg_repo.get_new_messages(since).await?;

        if messages.is_empty() {
            return Ok(());
        }

        debug!(count = messages.len(), "Polled new messages");

        // Group messages by chat JID
        let mut by_jid: HashMap<String, Vec<&Message>> = HashMap::new();
        for msg in &messages {
            by_jid.entry(msg.chat_jid.clone()).or_default().push(msg);
        }

        // Update last_timestamp to the most recent message
        if let Some(latest) = messages.iter().map(|m| m.timestamp).max() {
            *self.last_timestamp.lock().await = Some(latest);
        }

        // Route each channel's messages
        for jid_messages in by_jid.values() {
            if let Some(last_msg) = jid_messages.last() {
                let route_result = self.router.route_message(last_msg).await?;
                match route_result.action {
                    RouteAction::Process => {
                        if let (Some(folder), Some(_ws_id)) =
                            (route_result.workspace_folder, route_result.workspace_id)
                        {
                            let session_id =
                                format!("msg-{}", last_msg.timestamp.timestamp_millis());
                            let ts_str = last_msg.timestamp.to_rfc3339();

                            self.queue
                                .enqueue_message_check(
                                    &last_msg.chat_jid,
                                    &folder,
                                    &session_id,
                                    Some(&ts_str),
                                )
                                .await?;
                        }
                    }
                    RouteAction::BindToken { token } => {
                        let token_repo = TokenRepository::new(&self.db);
                        match token_repo.validate_and_consume(&token).await? {
                            Some(workspace_id) => {
                                let binding_repo = BindingRepository::new(&self.db);
                                binding_repo
                                    .bind(&last_msg.chat_jid, &workspace_id)
                                    .await?;

                                // Reload workspace into cache
                                let ws_repo = WorkspaceRepository::new(&self.db);
                                if let Some(ws) = ws_repo.get(&workspace_id).await? {
                                    let ws_name = ws.name.clone();
                                    self.workspaces
                                        .lock()
                                        .await
                                        .insert(workspace_id, ws);

                                    if let Err(e) = self.router.send_response(
                                        &last_msg.chat_jid,
                                        &format!(
                                            "Bound to workspace \"{}\". You can now send messages to interact with the agent.",
                                            ws_name
                                        ),
                                    ).await {
                                        warn!(error = %e, "Failed to send bind success response");
                                    }
                                }
                            }
                            None => {
                                if let Err(e) = self.router.send_response(
                                    &last_msg.chat_jid,
                                    "Invalid or expired token. Run `ngb workspace create <name>` to get a new token.",
                                ).await {
                                    warn!(error = %e, "Failed to send bind failure response");
                                }
                            }
                        }
                    }
                    RouteAction::Unbound => {
                        if let Err(e) = self.router.send_response(
                            &last_msg.chat_jid,
                            "Welcome to NanoGridBot!\nThis chat is not bound to a workspace.\nRun `ngb workspace create <name>` in CLI, then send the generated token here to bind.",
                        ).await {
                            warn!(error = %e, "Failed to send guidance response");
                        }
                    }
                    RouteAction::BuiltinCommand { ref command } => {
                        self.handle_builtin_command(&last_msg.chat_jid, command)
                            .await;
                    }
                }
            }
        }

        Ok(())
    }

    /// Handle built-in commands.
    async fn handle_builtin_command(&self, jid: &str, command: &str) {
        let response = match command {
            "/status" => {
                let health = self.get_health_status().await;
                format!(
                    "Status: {}\nWorkspaces: {}\nActive containers: {}\nUptime: {:.0}s",
                    if health.healthy { "healthy" } else { "unhealthy" },
                    health.registered_groups,
                    health.active_containers,
                    health.uptime_seconds,
                )
            }
            "/help" => {
                "Commands:\n/status - Show system status\n/help - Show this help\n/unbind - Unbind this chat from its workspace".to_string()
            }
            "/unbind" => {
                let binding_repo = BindingRepository::new(&self.db);
                match binding_repo.unbind(jid).await {
                    Ok(true) => "Chat unbound from workspace.".to_string(),
                    Ok(false) => "This chat is not bound to any workspace.".to_string(),
                    Err(e) => format!("Error: {e}"),
                }
            }
            _ => format!("Unknown command: {command}"),
        };

        if let Err(e) = self.router.send_response(jid, &response).await {
            warn!(error = %e, command, "Failed to send command response");
        }
    }

    /// Stop the orchestrator and all subsystems.
    pub async fn stop(&self) -> Result<()> {
        info!("Stopping orchestrator");

        let _ = self.shutdown.send(true);

        {
            let mut scheduler = self.scheduler.lock().await;
            scheduler.stop();
        }
        {
            let mut ipc = self.ipc_handler.lock().await;
            ipc.stop();
        }

        *self.healthy.lock().await = false;
        info!("Orchestrator stopped");
        Ok(())
    }

    /// Register a workspace.
    pub async fn register_workspace(&self, ws: Workspace) -> Result<()> {
        let ws_repo = WorkspaceRepository::new(&self.db);
        ws_repo.save(&ws).await?;

        let id = ws.id.clone();
        self.workspaces.lock().await.insert(id.clone(), ws);

        info!(workspace_id = %id, "Workspace registered");
        Ok(())
    }

    /// Unregister a workspace.
    pub async fn unregister_workspace(&self, workspace_id: &str) -> Result<bool> {
        let ws_repo = WorkspaceRepository::new(&self.db);
        let deleted = ws_repo.delete(workspace_id).await?;

        if deleted {
            self.workspaces.lock().await.remove(workspace_id);
            info!(workspace_id, "Workspace unregistered");
        }

        Ok(deleted)
    }

    /// Send a prompt directly to a workspace's container.
    pub async fn send_to_workspace(
        &self,
        workspace_folder: &str,
        _prompt: &str,
        session_id: &str,
    ) -> Result<()> {
        let ws_map = self.workspaces.lock().await;
        let ws = ws_map
            .values()
            .find(|w| w.folder == workspace_folder)
            .ok_or_else(|| {
                NanoGridBotError::Other(format!("Workspace not found: {workspace_folder}"))
            })?;

        let ws_id = ws.id.clone();
        drop(ws_map);

        // Find a bound JID for this workspace (use workspace_id as fallback)
        let binding_repo = BindingRepository::new(&self.db);
        let bindings = binding_repo.get_by_workspace(&ws_id).await?;
        let jid = bindings
            .first()
            .map(|b| b.channel_jid.clone())
            .unwrap_or_else(|| format!("cli:{workspace_folder}"));

        self.queue
            .enqueue_message_check(&jid, workspace_folder, session_id, None)
            .await
    }

    /// Get the current health status.
    pub async fn get_health_status(&self) -> HealthStatus {
        let healthy = *self.healthy.lock().await;
        let ws_count = self.workspaces.lock().await.len();
        let active_containers = self.queue.get_active_count().await;
        let uptime = self
            .start_time
            .lock()
            .await
            .map(|t| t.elapsed().as_secs_f64())
            .unwrap_or(0.0);

        HealthStatus {
            healthy,
            channels_connected: self.channels.len(),
            channels_total: self.channels.len(),
            registered_groups: ws_count,
            active_containers,
            pending_tasks: self.queue.get_waiting_count().await,
            uptime_seconds: uptime,
        }
    }

    /// Get a reference to the group queue.
    pub fn queue(&self) -> &Arc<GroupQueue> {
        &self.queue
    }

    /// Get a reference to the database.
    pub fn db(&self) -> &Arc<Database> {
        &self.db
    }

    /// Get a reference to the router.
    pub fn router(&self) -> &MessageRouter {
        &self.router
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ngb_db::WorkspaceRepository;
    use std::sync::atomic::{AtomicU32, Ordering};

    struct MockChannel {
        prefix: String,
        send_count: Arc<AtomicU32>,
    }

    impl MockChannel {
        fn new(prefix: &str) -> Self {
            Self {
                prefix: prefix.to_string(),
                send_count: Arc::new(AtomicU32::new(0)),
            }
        }
    }

    impl ChannelSender for MockChannel {
        fn owns_jid(&self, jid: &str) -> bool {
            jid.starts_with(&self.prefix)
        }

        fn send_message(
            &self,
            _jid: &str,
            _text: &str,
        ) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<()>> + Send + '_>> {
            Box::pin(async move {
                self.send_count.fetch_add(1, Ordering::SeqCst);
                Ok(())
            })
        }
    }

    fn test_config() -> Config {
        let base = std::path::PathBuf::from("/tmp/ngb-orch-test");
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

    fn make_workspace(id: &str, name: &str) -> Workspace {
        Workspace {
            id: id.to_string(),
            name: name.to_string(),
            owner: "test".to_string(),
            folder: name.to_string(),
            shared: false,
            container_config: None,
        }
    }

    #[tokio::test]
    async fn orchestrator_new() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let tg = MockChannel::new("telegram:");
        let channels: Vec<Box<dyn ChannelSender>> = vec![Box::new(tg)];
        let orch = Orchestrator::new(test_config(), db, channels);

        let health = orch.get_health_status().await;
        assert!(!health.healthy);
        assert_eq!(health.channels_total, 1);
        assert_eq!(health.registered_groups, 0);
    }

    #[tokio::test]
    async fn orchestrator_start_stop() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let channels: Vec<Box<dyn ChannelSender>> = vec![];
        let orch = Orchestrator::new(test_config(), db, channels);

        orch.start().await.unwrap();
        let health = orch.get_health_status().await;
        assert!(health.healthy);
        assert!(health.uptime_seconds >= 0.0);

        orch.stop().await.unwrap();
        let health = orch.get_health_status().await;
        assert!(!health.healthy);
    }

    #[tokio::test]
    async fn register_and_unregister_workspace() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let channels: Vec<Box<dyn ChannelSender>> = vec![];
        let orch = Orchestrator::new(test_config(), db, channels);

        let ws = make_workspace("ws-1", "test-agent");
        orch.register_workspace(ws).await.unwrap();
        assert_eq!(orch.get_health_status().await.registered_groups, 1);

        let deleted = orch.unregister_workspace("ws-1").await.unwrap();
        assert!(deleted);
        assert_eq!(orch.get_health_status().await.registered_groups, 0);
    }

    #[tokio::test]
    async fn unregister_nonexistent_workspace() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let channels: Vec<Box<dyn ChannelSender>> = vec![];
        let orch = Orchestrator::new(test_config(), db, channels);

        let deleted = orch.unregister_workspace("nonexistent").await.unwrap();
        assert!(!deleted);
    }

    #[tokio::test]
    async fn health_status_reflects_workspaces() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let ws_repo = WorkspaceRepository::new(&db);
        ws_repo.save(&make_workspace("ws-1", "agent1")).await.unwrap();
        ws_repo.save(&make_workspace("ws-2", "agent2")).await.unwrap();

        let channels: Vec<Box<dyn ChannelSender>> = vec![];
        let orch = Orchestrator::new(test_config(), db, channels);
        orch.start().await.unwrap();

        let health = orch.get_health_status().await;
        assert_eq!(health.registered_groups, 2);
        assert!(health.healthy);

        orch.stop().await.unwrap();
    }

    #[tokio::test]
    async fn send_to_workspace_unknown() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let channels: Vec<Box<dyn ChannelSender>> = vec![];
        let orch = Orchestrator::new(test_config(), db, channels);

        let result = orch.send_to_workspace("nonexistent", "hello", "s1").await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn send_to_registered_workspace() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let channels: Vec<Box<dyn ChannelSender>> = vec![];
        let orch = Orchestrator::new(test_config(), db, channels);

        orch.register_workspace(make_workspace("ws-1", "test_folder"))
            .await
            .unwrap();

        let result = orch.send_to_workspace("test_folder", "hello", "s1").await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn health_status_serialization() {
        let health = HealthStatus {
            healthy: true,
            channels_connected: 3,
            channels_total: 5,
            registered_groups: 10,
            active_containers: 2,
            pending_tasks: 5,
            uptime_seconds: 3600.5,
        };

        let json = serde_json::to_string(&health).unwrap();
        let back: HealthStatus = serde_json::from_str(&json).unwrap();
        assert!(back.healthy);
        assert_eq!(back.channels_connected, 3);
        assert_eq!(back.registered_groups, 10);
    }

    #[tokio::test]
    async fn poll_messages_empty() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let channels: Vec<Box<dyn ChannelSender>> = vec![];
        let orch = Orchestrator::new(test_config(), db, channels);

        let result = orch.poll_messages().await;
        assert!(result.is_ok());
    }
}
