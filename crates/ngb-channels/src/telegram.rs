//! Telegram channel adapter using teloxide.
//!
//! Receives messages via long polling, stores them in the database,
//! and implements ChannelSender for outbound messages.

use std::pin::Pin;
use std::sync::Arc;

use chrono::Utc;
use ngb_core::ipc_handler::ChannelSender;
use ngb_db::{Database, MessageRepository};
use ngb_types::{Message, MessageRole, Result};
use teloxide::prelude::*;
use teloxide::types::ChatId;
use tracing::{debug, error, info};

/// Telegram channel adapter.
pub struct TelegramChannel {
    bot: Bot,
    db: Arc<Database>,
}

impl TelegramChannel {
    /// Create a new Telegram channel with the given bot token.
    pub fn new(token: &str, db: Arc<Database>) -> Self {
        let bot = Bot::new(token);
        Self { bot, db }
    }

    /// Start listening for incoming messages via long polling.
    ///
    /// Incoming messages are stored in the database with JID format `telegram:{chat_id}`.
    /// Returns a JoinHandle that can be used to await or abort the listener.
    pub fn start(&self) -> tokio::task::JoinHandle<()> {
        let bot = self.bot.clone();
        let db = self.db.clone();

        tokio::spawn(async move {
            info!("Telegram channel listener starting");

            teloxide::repl(bot, move |_bot: Bot, msg: TeloxideMessage| {
                let db = db.clone();
                async move {
                    if let Some(text) = msg.text() {
                        let chat_id = msg.chat.id.0;
                        let jid = format!("telegram:{chat_id}");

                        let sender_name = msg.from.as_ref().map(|u| {
                            u.last_name
                                .as_ref()
                                .map(|ln| format!("{} {ln}", u.first_name))
                                .unwrap_or_else(|| u.first_name.clone())
                        });

                        let sender_id = msg
                            .from
                            .as_ref()
                            .map(|u| u.id.0.to_string())
                            .unwrap_or_else(|| "unknown".to_string());

                        let message = Message {
                            id: uuid::Uuid::new_v4().to_string(),
                            chat_jid: jid.clone(),
                            sender: sender_id,
                            sender_name,
                            content: text.to_string(),
                            timestamp: Utc::now(),
                            is_from_me: false,
                            role: MessageRole::User,
                        };

                        let repo = MessageRepository::new(&db, 1000);
                        if let Err(e) = repo.store_message(&message).await {
                            error!(jid = %jid, error = %e, "Failed to store Telegram message");
                        } else {
                            debug!(jid = %jid, sender = %message.sender, "Telegram message stored");
                        }
                    }

                    Ok(())
                }
            })
            .await;
        })
    }

    /// Get a reference to the underlying bot.
    pub fn bot(&self) -> &Bot {
        &self.bot
    }
}

// Type alias to avoid confusion with our Message type
use teloxide::types::Message as TeloxideMessage;

impl ChannelSender for TelegramChannel {
    fn owns_jid(&self, jid: &str) -> bool {
        jid.starts_with("telegram:")
    }

    fn send_message(
        &self,
        jid: &str,
        text: &str,
    ) -> Pin<Box<dyn std::future::Future<Output = Result<()>> + Send + '_>> {
        let jid = jid.to_string();
        let text = text.to_string();
        Box::pin(async move {
            let chat_id_str = jid.strip_prefix("telegram:").ok_or_else(|| {
                ngb_types::NanoGridBotError::Channel(format!("Invalid Telegram JID: {jid}"))
            })?;

            let chat_id: i64 = chat_id_str.parse().map_err(|e| {
                ngb_types::NanoGridBotError::Channel(format!("Invalid chat ID in JID {jid}: {e}"))
            })?;

            // Split long messages (Telegram limit is 4096 chars)
            let max_len = 4096;
            if text.len() <= max_len {
                self.bot
                    .send_message(ChatId(chat_id), &text)
                    .await
                    .map_err(|e| {
                        ngb_types::NanoGridBotError::Channel(format!("Telegram send failed: {e}"))
                    })?;
            } else {
                // Split into chunks
                for chunk in text.as_bytes().chunks(max_len) {
                    let chunk_str = String::from_utf8_lossy(chunk);
                    self.bot
                        .send_message(ChatId(chat_id), chunk_str.as_ref())
                        .await
                        .map_err(|e| {
                            ngb_types::NanoGridBotError::Channel(format!(
                                "Telegram send failed: {e}"
                            ))
                        })?;
                }
            }

            debug!(jid = %jid, "Telegram message sent");
            Ok(())
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn owns_jid_telegram() {
        // We can't create a real TelegramChannel without a token,
        // but we can test the JID matching logic directly.
        let jid = "telegram:123456789";
        assert!(jid.starts_with("telegram:"));

        let jid2 = "slack:C123";
        assert!(!jid2.starts_with("telegram:"));
    }

    #[test]
    fn parse_chat_id_from_jid() {
        let jid = "telegram:123456789";
        let chat_id_str = jid.strip_prefix("telegram:").unwrap();
        let chat_id: i64 = chat_id_str.parse().unwrap();
        assert_eq!(chat_id, 123456789);
    }

    #[test]
    fn parse_negative_chat_id() {
        // Group chats have negative IDs
        let jid = "telegram:-1001234567890";
        let chat_id_str = jid.strip_prefix("telegram:").unwrap();
        let chat_id: i64 = chat_id_str.parse().unwrap();
        assert_eq!(chat_id, -1001234567890);
    }

    #[tokio::test]
    async fn channel_sender_owns_jid() {
        // Create with a dummy token (won't connect)
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();
        let channel = TelegramChannel::new("dummy:token", db);

        assert!(channel.owns_jid("telegram:123"));
        assert!(channel.owns_jid("telegram:-1001234567890"));
        assert!(!channel.owns_jid("slack:C123"));
        assert!(!channel.owns_jid("whatsapp:123"));
    }
}
