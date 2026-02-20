use std::sync::Arc;

use ngb_config::Config;
use ngb_db::{BindingRepository, Database, WorkspaceRepository};
use ngb_types::{Message, NanoGridBotError, Result};
use tracing::{debug, error, info, warn};

use crate::ipc_handler::ChannelSender;

/// Format messages for agent consumption with timestamps and sender names.
///
/// Each message is formatted as `[Mon DD H:MM AM/PM] Sender: Content`.
pub fn format_messages(messages: &[Message]) -> String {
    messages
        .iter()
        .map(|m| {
            let ts = m.timestamp.format("%b %d %-I:%M %p");
            let sender = m.sender_name.as_deref().unwrap_or(&m.sender);
            format!("[{}] {}: {}", ts, sender, m.content)
        })
        .collect::<Vec<_>>()
        .join("\n")
}

/// Token prefix used for workspace binding tokens.
const TOKEN_PREFIX: &str = "ngb-";

/// Message router that looks up channel bindings to find the target workspace,
/// and dispatches responses to the appropriate channels.
pub struct MessageRouter {
    config: Config,
    db: Arc<Database>,
    channels: Arc<Vec<Box<dyn ChannelSender>>>,
}

/// Action determined by routing a message.
#[derive(Debug, PartialEq)]
pub enum RouteAction {
    /// Route to workspace container for processing.
    Process,
    /// Token binding request from IM.
    BindToken { token: String },
    /// Built-in command (e.g. /status).
    BuiltinCommand { command: String },
    /// Channel is not bound to any workspace — send guidance.
    Unbound,
}

/// Result of routing a message.
#[derive(Debug)]
pub struct RouteResult {
    /// The action to take.
    pub action: RouteAction,
    /// The workspace ID (if bound).
    pub workspace_id: Option<String>,
    /// The workspace folder (if bound).
    pub workspace_folder: Option<String>,
}

impl MessageRouter {
    /// Create a new message router.
    pub fn new(
        config: Config,
        db: Arc<Database>,
        channels: Arc<Vec<Box<dyn ChannelSender>>>,
    ) -> Self {
        Self {
            config,
            db,
            channels,
        }
    }

    /// Route an incoming message.
    ///
    /// Two-step lookup:
    /// 1. Check if message is a token or built-in command → special action
    /// 2. Look up channel_bindings → route to workspace or return Unbound
    pub async fn route_message(&self, message: &Message) -> Result<RouteResult> {
        let content = message.content.trim();

        // Check for token binding request
        if content.starts_with(TOKEN_PREFIX) && content.len() <= 20 && !content.contains(' ') {
            debug!(jid = %message.chat_jid, "Token binding request detected");
            return Ok(RouteResult {
                action: RouteAction::BindToken {
                    token: content.to_string(),
                },
                workspace_id: None,
                workspace_folder: None,
            });
        }

        // Check for built-in commands
        if content.starts_with('/') {
            let command = content.split_whitespace().next().unwrap_or(content);
            match command {
                "/status" | "/help" | "/unbind" => {
                    debug!(jid = %message.chat_jid, command, "Built-in command detected");
                    return Ok(RouteResult {
                        action: RouteAction::BuiltinCommand {
                            command: command.to_string(),
                        },
                        workspace_id: None,
                        workspace_folder: None,
                    });
                }
                _ => {} // Not a built-in command, fall through to binding lookup
            }
        }

        // Look up channel binding
        let binding_repo = BindingRepository::new(&self.db);
        match binding_repo.get_by_jid(&message.chat_jid).await? {
            Some(binding) => {
                // Found binding — look up workspace
                let ws_repo = WorkspaceRepository::new(&self.db);
                match ws_repo.get(&binding.workspace_id).await? {
                    Some(ws) => {
                        info!(
                            jid = %message.chat_jid,
                            workspace = %ws.name,
                            folder = %ws.folder,
                            "Message routed to workspace"
                        );
                        Ok(RouteResult {
                            action: RouteAction::Process,
                            workspace_id: Some(ws.id),
                            workspace_folder: Some(ws.folder),
                        })
                    }
                    None => {
                        warn!(
                            jid = %message.chat_jid,
                            workspace_id = %binding.workspace_id,
                            "Binding references non-existent workspace, treating as unbound"
                        );
                        Ok(RouteResult {
                            action: RouteAction::Unbound,
                            workspace_id: None,
                            workspace_folder: None,
                        })
                    }
                }
            }
            None => {
                debug!(jid = %message.chat_jid, "No binding found, channel is unbound");
                Ok(RouteResult {
                    action: RouteAction::Unbound,
                    workspace_id: None,
                    workspace_folder: None,
                })
            }
        }
    }

    /// Send a response message to a specific JID via the appropriate channel.
    pub async fn send_response(&self, jid: &str, text: &str) -> Result<()> {
        for channel in self.channels.iter() {
            if channel.owns_jid(jid) {
                channel.send_message(jid, text).await?;
                debug!(jid, "Response sent via channel");
                return Ok(());
            }
        }

        warn!(jid, "No channel found to send response");
        Err(NanoGridBotError::Channel(format!(
            "No channel owns JID: {jid}"
        )))
    }

    /// Broadcast a text message to multiple workspaces via their bound channels.
    pub async fn broadcast_to_workspaces(
        &self,
        text: &str,
        workspace_ids: &[String],
    ) -> Result<Vec<String>> {
        let binding_repo = BindingRepository::new(&self.db);
        let mut sent_to = Vec::new();

        for ws_id in workspace_ids {
            let bindings = binding_repo.get_by_workspace(ws_id).await?;
            for binding in &bindings {
                match self.send_response(&binding.channel_jid, text).await {
                    Ok(()) => {
                        sent_to.push(binding.channel_jid.clone());
                    }
                    Err(e) => {
                        error!(
                            jid = %binding.channel_jid,
                            error = %e,
                            "Failed to broadcast to channel"
                        );
                    }
                }
            }
        }

        info!(
            count = sent_to.len(),
            total = workspace_ids.len(),
            "Broadcast completed"
        );
        Ok(sent_to)
    }

    /// Get a reference to the config.
    pub fn config(&self) -> &Config {
        &self.config
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{TimeZone, Utc};
    use ngb_db::{BindingRepository, WorkspaceRepository};
    use ngb_types::{MessageRole, Workspace};
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
        let base = std::path::PathBuf::from("/tmp/ngb-router-test");
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

    fn make_message(jid: &str, content: &str) -> Message {
        Message {
            id: uuid::Uuid::new_v4().to_string(),
            chat_jid: jid.to_string(),
            sender: "user1".to_string(),
            sender_name: Some("Alice".to_string()),
            content: content.to_string(),
            timestamp: Utc::now(),
            is_from_me: false,
            role: MessageRole::User,
        }
    }

    fn make_workspace(id: &str, name: &str) -> Workspace {
        Workspace {
            id: id.to_string(),
            name: name.to_string(),
            owner: "test-user".to_string(),
            folder: name.to_string(),
            shared: false,
            container_config: None,
        }
    }

    #[tokio::test]
    async fn route_bound_channel() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        // Create workspace and binding
        let ws_repo = WorkspaceRepository::new(&db);
        ws_repo.save(&make_workspace("ws-1", "my-agent")).await.unwrap();
        let binding_repo = BindingRepository::new(&db);
        binding_repo.bind("telegram:123", "ws-1").await.unwrap();

        let channels: Arc<Vec<Box<dyn ChannelSender>>> = Arc::new(vec![]);
        let router = MessageRouter::new(test_config(), db, channels);

        let msg = make_message("telegram:123", "hello agent");
        let result = router.route_message(&msg).await.unwrap();
        assert_eq!(result.action, RouteAction::Process);
        assert_eq!(result.workspace_id, Some("ws-1".to_string()));
        assert_eq!(result.workspace_folder, Some("my-agent".to_string()));
    }

    #[tokio::test]
    async fn route_unbound_channel() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let channels: Arc<Vec<Box<dyn ChannelSender>>> = Arc::new(vec![]);
        let router = MessageRouter::new(test_config(), db, channels);

        let msg = make_message("telegram:999", "hello");
        let result = router.route_message(&msg).await.unwrap();
        assert_eq!(result.action, RouteAction::Unbound);
        assert!(result.workspace_id.is_none());
    }

    #[tokio::test]
    async fn route_token_binding() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let channels: Arc<Vec<Box<dyn ChannelSender>>> = Arc::new(vec![]);
        let router = MessageRouter::new(test_config(), db, channels);

        let msg = make_message("telegram:123", "ngb-a1b2c3d4e5f6");
        let result = router.route_message(&msg).await.unwrap();
        assert_eq!(
            result.action,
            RouteAction::BindToken {
                token: "ngb-a1b2c3d4e5f6".to_string()
            }
        );
    }

    #[tokio::test]
    async fn route_builtin_command() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let channels: Arc<Vec<Box<dyn ChannelSender>>> = Arc::new(vec![]);
        let router = MessageRouter::new(test_config(), db, channels);

        let msg = make_message("telegram:123", "/status");
        let result = router.route_message(&msg).await.unwrap();
        assert_eq!(
            result.action,
            RouteAction::BuiltinCommand {
                command: "/status".to_string()
            }
        );
    }

    #[tokio::test]
    async fn route_unknown_slash_command_falls_through() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        // Bind the channel so it routes to Process
        let ws_repo = WorkspaceRepository::new(&db);
        ws_repo.save(&make_workspace("ws-1", "agent")).await.unwrap();
        let binding_repo = BindingRepository::new(&db);
        binding_repo.bind("telegram:123", "ws-1").await.unwrap();

        let channels: Arc<Vec<Box<dyn ChannelSender>>> = Arc::new(vec![]);
        let router = MessageRouter::new(test_config(), db, channels);

        let msg = make_message("telegram:123", "/custom-command arg1");
        let result = router.route_message(&msg).await.unwrap();
        assert_eq!(result.action, RouteAction::Process);
    }

    #[tokio::test]
    async fn route_stale_binding() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        // Create binding without workspace
        let binding_repo = BindingRepository::new(&db);
        binding_repo.bind("telegram:123", "ws-deleted").await.unwrap();

        let channels: Arc<Vec<Box<dyn ChannelSender>>> = Arc::new(vec![]);
        let router = MessageRouter::new(test_config(), db, channels);

        let msg = make_message("telegram:123", "hello");
        let result = router.route_message(&msg).await.unwrap();
        assert_eq!(result.action, RouteAction::Unbound);
    }

    #[tokio::test]
    async fn send_response_routes_to_channel() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let tg = MockChannel::new("telegram:");
        let tg_count = tg.send_count.clone();
        let channels: Arc<Vec<Box<dyn ChannelSender>>> = Arc::new(vec![Box::new(tg)]);
        let router = MessageRouter::new(test_config(), db, channels);

        router
            .send_response("telegram:123", "Hello!")
            .await
            .unwrap();
        assert_eq!(tg_count.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn format_messages_basic() {
        let messages = vec![
            Message {
                id: "1".to_string(),
                chat_jid: "tg:123".to_string(),
                sender: "user1".to_string(),
                sender_name: Some("Alice".to_string()),
                content: "Hello everyone".to_string(),
                timestamp: Utc.with_ymd_and_hms(2026, 1, 31, 14, 32, 0).unwrap(),
                is_from_me: false,
                role: MessageRole::User,
            },
            Message {
                id: "2".to_string(),
                chat_jid: "tg:123".to_string(),
                sender: "user2".to_string(),
                sender_name: Some("Bob".to_string()),
                content: "@Bot help me".to_string(),
                timestamp: Utc.with_ymd_and_hms(2026, 1, 31, 14, 35, 0).unwrap(),
                is_from_me: false,
                role: MessageRole::User,
            },
        ];
        let result = format_messages(&messages);
        assert!(result.contains("[Jan 31 2:32 PM] Alice: Hello everyone"));
        assert!(result.contains("[Jan 31 2:35 PM] Bob: @Bot help me"));
    }

    #[test]
    fn format_messages_empty() {
        let result = format_messages(&[]);
        assert!(result.is_empty());
    }

    #[test]
    fn format_messages_uses_sender_fallback() {
        let msg = Message {
            id: "1".to_string(),
            chat_jid: "tg:123".to_string(),
            sender: "user123".to_string(),
            sender_name: None,
            content: "hi".to_string(),
            timestamp: Utc.with_ymd_and_hms(2026, 3, 15, 9, 5, 0).unwrap(),
            is_from_me: false,
            role: MessageRole::User,
        };
        let result = format_messages(&[msg]);
        assert!(result.contains("user123: hi"));
    }
}
