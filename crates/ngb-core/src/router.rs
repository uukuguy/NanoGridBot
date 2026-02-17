use std::sync::Arc;

use ngb_config::Config;
use ngb_db::{Database, GroupRepository};
use ngb_types::{Message, NanoGridBotError, Result};
use regex::Regex;
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

/// Message router that matches incoming messages against group triggers
/// and dispatches responses to the appropriate channels.
pub struct MessageRouter {
    config: Config,
    db: Arc<Database>,
    channels: Arc<Vec<Box<dyn ChannelSender>>>,
}

/// Result of routing a message.
#[derive(Debug)]
pub struct RouteResult {
    /// Whether the message matched a trigger.
    pub matched: bool,
    /// The group folder the message was routed to (if matched).
    pub group_folder: Option<String>,
    /// The group JID.
    pub group_jid: Option<String>,
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

    /// Route an incoming message to the appropriate group.
    ///
    /// Returns a `RouteResult` indicating whether the message was matched.
    /// A message matches if:
    /// 1. The group has `requires_trigger == false`, OR
    /// 2. The message content matches the group's trigger pattern.
    pub async fn route_message(&self, message: &Message) -> Result<RouteResult> {
        let repo = GroupRepository::new(&self.db);
        let groups = repo.get_all().await?;

        for group in &groups {
            // Check if this group handles this JID
            if group.jid != message.chat_jid {
                continue;
            }

            // Check trigger
            if group.requires_trigger {
                let pattern = self.build_trigger_pattern(&group.trigger_pattern);
                if !matches_trigger(&pattern, &message.content) {
                    debug!(
                        jid = %message.chat_jid,
                        content_prefix = &message.content[..message.content.len().min(50)],
                        "Message did not match trigger"
                    );
                    return Ok(RouteResult {
                        matched: false,
                        group_folder: None,
                        group_jid: None,
                    });
                }
            }

            info!(
                jid = %message.chat_jid,
                group = %group.name,
                folder = %group.folder,
                "Message routed to group"
            );

            return Ok(RouteResult {
                matched: true,
                group_folder: Some(group.folder.clone()),
                group_jid: Some(group.jid.clone()),
            });
        }

        // No group found for this JID
        debug!(jid = %message.chat_jid, "No registered group for JID");
        Ok(RouteResult {
            matched: false,
            group_folder: None,
            group_jid: None,
        })
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

    /// Broadcast a text message to multiple groups.
    pub async fn broadcast_to_groups(
        &self,
        text: &str,
        group_folders: &[String],
    ) -> Result<Vec<String>> {
        let repo = GroupRepository::new(&self.db);
        let all_groups = repo.get_all().await?;
        let mut sent_to = Vec::new();

        for group in &all_groups {
            if group_folders.contains(&group.folder) {
                match self.send_response(&group.jid, text).await {
                    Ok(()) => {
                        sent_to.push(group.jid.clone());
                    }
                    Err(e) => {
                        error!(
                            jid = %group.jid,
                            error = %e,
                            "Failed to broadcast to group"
                        );
                    }
                }
            }
        }

        info!(
            count = sent_to.len(),
            total = group_folders.len(),
            "Broadcast completed"
        );
        Ok(sent_to)
    }

    /// Build the trigger regex pattern.
    ///
    /// If the group has a custom trigger_pattern, use that.
    /// Otherwise, default to `^@{assistant_name}\b` (case-insensitive).
    fn build_trigger_pattern(&self, custom_pattern: &Option<String>) -> String {
        match custom_pattern {
            Some(pattern) if !pattern.is_empty() => pattern.clone(),
            _ => format!(r"(?i)^@{}\b", regex::escape(&self.config.assistant_name)),
        }
    }
}

/// Check if message content matches a trigger regex.
fn matches_trigger(pattern: &str, content: &str) -> bool {
    match Regex::new(pattern) {
        Ok(re) => re.is_match(content),
        Err(e) => {
            warn!(pattern, error = %e, "Invalid trigger regex, defaulting to no match");
            false
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{TimeZone, Utc};
    use ngb_db::GroupRepository;
    use ngb_types::{MessageRole, RegisteredGroup};
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

    #[test]
    fn trigger_default_pattern() {
        assert!(matches_trigger(r"(?i)^@Andy\b", "@Andy hello"));
        assert!(matches_trigger(r"(?i)^@Andy\b", "@andy help me"));
        assert!(!matches_trigger(r"(?i)^@Andy\b", "hello @Andy"));
        assert!(!matches_trigger(r"(?i)^@Andy\b", "random message"));
    }

    #[test]
    fn trigger_custom_pattern() {
        assert!(matches_trigger(r"^!bot\b", "!bot do something"));
        assert!(!matches_trigger(r"^!bot\b", "hello !bot"));
    }

    #[test]
    fn trigger_invalid_regex() {
        assert!(!matches_trigger(r"[invalid", "test"));
    }

    #[tokio::test]
    async fn route_message_with_trigger() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        // Register a group
        let repo = GroupRepository::new(&db);
        repo.save_group(&RegisteredGroup {
            jid: "telegram:123".to_string(),
            name: "Test Group".to_string(),
            folder: "test_group".to_string(),
            trigger_pattern: None,
            container_config: None,
            requires_trigger: true,
        })
        .await
        .unwrap();

        let channels: Arc<Vec<Box<dyn ChannelSender>>> = Arc::new(vec![]);
        let cfg = test_config();
        let router = MessageRouter::new(cfg, db, channels);

        // Should match — default trigger @Andy
        let msg = make_message("telegram:123", "@Andy what's up?");
        let result = router.route_message(&msg).await.unwrap();
        assert!(result.matched);
        assert_eq!(result.group_folder, Some("test_group".to_string()));

        // Should NOT match
        let msg2 = make_message("telegram:123", "hello everyone");
        let result2 = router.route_message(&msg2).await.unwrap();
        assert!(!result2.matched);
    }

    #[tokio::test]
    async fn route_message_no_trigger_required() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let repo = GroupRepository::new(&db);
        repo.save_group(&RegisteredGroup {
            jid: "slack:C1".to_string(),
            name: "Open Group".to_string(),
            folder: "open_group".to_string(),
            trigger_pattern: None,
            container_config: None,
            requires_trigger: false,
        })
        .await
        .unwrap();

        let channels: Arc<Vec<Box<dyn ChannelSender>>> = Arc::new(vec![]);
        let router = MessageRouter::new(test_config(), db, channels);

        let msg = make_message("slack:C1", "any message");
        let result = router.route_message(&msg).await.unwrap();
        assert!(result.matched);
    }

    #[tokio::test]
    async fn route_message_unknown_jid() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let channels: Arc<Vec<Box<dyn ChannelSender>>> = Arc::new(vec![]);
        let router = MessageRouter::new(test_config(), db, channels);

        let msg = make_message("unknown:999", "hello");
        let result = router.route_message(&msg).await.unwrap();
        assert!(!result.matched);
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
