use std::sync::Mutex;

use chrono::{DateTime, Utc};
use lru::LruCache;
use std::num::NonZeroUsize;
use tracing::debug;

use ngb_types::{Message, MessageRole, NanoGridBotError, Result};

use crate::connection::Database;

/// Repository for message storage and retrieval.
pub struct MessageRepository<'a> {
    db: &'a Database,
    cache: Mutex<LruCache<String, Message>>,
}

impl<'a> MessageRepository<'a> {
    pub fn new(db: &'a Database, cache_size: usize) -> Self {
        let cap = NonZeroUsize::new(cache_size).unwrap_or(NonZeroUsize::new(1000).unwrap());
        Self {
            db,
            cache: Mutex::new(LruCache::new(cap)),
        }
    }

    /// Store a message.
    pub async fn store_message(&self, message: &Message) -> Result<()> {
        let role_str = match message.role {
            MessageRole::User => "user",
            MessageRole::Assistant => "assistant",
            MessageRole::System => "system",
        };

        sqlx::query(
            "INSERT OR REPLACE INTO messages
             (id, chat_jid, sender, sender_name, content, timestamp, is_from_me, role)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        )
        .bind(&message.id)
        .bind(&message.chat_jid)
        .bind(&message.sender)
        .bind(&message.sender_name)
        .bind(&message.content)
        .bind(message.timestamp.to_rfc3339())
        .bind(message.is_from_me as i32)
        .bind(role_str)
        .execute(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Store message: {e}")))?;

        // Update cache
        if let Ok(mut cache) = self.cache.lock() {
            cache.put(message.id.clone(), message.clone());
        }

        Ok(())
    }

    /// Get messages for a chat since a timestamp.
    pub async fn get_messages_since(
        &self,
        chat_jid: &str,
        since: DateTime<Utc>,
    ) -> Result<Vec<Message>> {
        let rows: Vec<MessageRow> = sqlx::query_as(
            "SELECT id, chat_jid, sender, sender_name, content, timestamp, is_from_me, role
             FROM messages
             WHERE chat_jid = ? AND timestamp > ?
             ORDER BY timestamp ASC",
        )
        .bind(chat_jid)
        .bind(since.to_rfc3339())
        .fetch_all(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Get messages since: {e}")))?;

        Ok(rows.into_iter().map(row_to_message).collect())
    }

    /// Get all new messages since a timestamp.
    pub async fn get_new_messages(&self, since: Option<DateTime<Utc>>) -> Result<Vec<Message>> {
        let rows: Vec<MessageRow> = if let Some(since) = since {
            sqlx::query_as(
                "SELECT id, chat_jid, sender, sender_name, content, timestamp, is_from_me, role
                 FROM messages
                 WHERE timestamp > ?
                 ORDER BY timestamp ASC",
            )
            .bind(since.to_rfc3339())
            .fetch_all(self.db.pool())
            .await
        } else {
            sqlx::query_as(
                "SELECT id, chat_jid, sender, sender_name, content, timestamp, is_from_me, role
                 FROM messages
                 ORDER BY timestamp ASC",
            )
            .fetch_all(self.db.pool())
            .await
        }
        .map_err(|e| NanoGridBotError::Database(format!("Get new messages: {e}")))?;

        Ok(rows.into_iter().map(row_to_message).collect())
    }

    /// Get recent messages for a chat.
    pub async fn get_recent_messages(&self, chat_jid: &str, limit: i64) -> Result<Vec<Message>> {
        let rows: Vec<MessageRow> = sqlx::query_as(
            "SELECT id, chat_jid, sender, sender_name, content, timestamp, is_from_me, role
             FROM messages
             WHERE chat_jid = ?
             ORDER BY timestamp DESC
             LIMIT ?",
        )
        .bind(chat_jid)
        .bind(limit)
        .fetch_all(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Get recent messages: {e}")))?;

        // Return in chronological order
        let mut msgs: Vec<Message> = rows.into_iter().map(row_to_message).collect();
        msgs.reverse();
        Ok(msgs)
    }

    /// Delete messages older than a timestamp.
    pub async fn delete_old_messages(&self, before: DateTime<Utc>) -> Result<u64> {
        let result = sqlx::query("DELETE FROM messages WHERE timestamp < ?")
            .bind(before.to_rfc3339())
            .execute(self.db.pool())
            .await
            .map_err(|e| NanoGridBotError::Database(format!("Delete old messages: {e}")))?;

        debug!("Deleted {} old messages", result.rows_affected());
        Ok(result.rows_affected())
    }

    /// Check if a message is in the cache.
    pub fn cache_contains(&self, id: &str) -> bool {
        self.cache
            .lock()
            .map(|mut c| c.get(id).is_some())
            .unwrap_or(false)
    }
}

// Internal row type for sqlx mapping
#[derive(sqlx::FromRow)]
struct MessageRow {
    id: String,
    chat_jid: String,
    sender: String,
    sender_name: Option<String>,
    content: String,
    timestamp: String,
    is_from_me: i32,
    role: String,
}

fn row_to_message(row: MessageRow) -> Message {
    let role = match row.role.as_str() {
        "assistant" => MessageRole::Assistant,
        "system" => MessageRole::System,
        _ => MessageRole::User,
    };

    let ts = DateTime::parse_from_rfc3339(&row.timestamp)
        .map(|dt| dt.with_timezone(&Utc))
        .unwrap_or_else(|_| Utc::now());

    Message {
        id: row.id,
        chat_jid: row.chat_jid,
        sender: row.sender,
        sender_name: row.sender_name,
        content: row.content,
        timestamp: ts,
        is_from_me: row.is_from_me != 0,
        role,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::connection::Database;

    async fn setup() -> Database {
        let db = Database::in_memory().await.unwrap();
        db.initialize().await.unwrap();
        db
    }

    fn make_message(id: &str, chat: &str, content: &str) -> Message {
        Message {
            id: id.to_string(),
            chat_jid: chat.to_string(),
            sender: "user1".to_string(),
            sender_name: Some("Alice".to_string()),
            content: content.to_string(),
            timestamp: Utc::now(),
            is_from_me: false,
            role: MessageRole::User,
        }
    }

    #[tokio::test]
    async fn store_and_retrieve_message() {
        let db = setup().await;
        let repo = MessageRepository::new(&db, 100);

        let msg = make_message("m1", "chat1", "Hello");
        repo.store_message(&msg).await.unwrap();

        let msgs = repo.get_new_messages(None).await.unwrap();
        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].id, "m1");
        assert_eq!(msgs[0].content, "Hello");
    }

    #[tokio::test]
    async fn get_messages_since() {
        let db = setup().await;
        let repo = MessageRepository::new(&db, 100);

        let old_time = Utc::now() - chrono::Duration::hours(2);
        let recent_time = Utc::now();

        let mut old_msg = make_message("m1", "chat1", "Old");
        old_msg.timestamp = old_time;
        repo.store_message(&old_msg).await.unwrap();

        let mut new_msg = make_message("m2", "chat1", "New");
        new_msg.timestamp = recent_time;
        repo.store_message(&new_msg).await.unwrap();

        let since = Utc::now() - chrono::Duration::hours(1);
        let msgs = repo.get_messages_since("chat1", since).await.unwrap();
        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].id, "m2");
    }

    #[tokio::test]
    async fn get_recent_messages() {
        let db = setup().await;
        let repo = MessageRepository::new(&db, 100);

        for i in 0..5 {
            let mut msg = make_message(&format!("m{i}"), "chat1", &format!("Msg {i}"));
            msg.timestamp = Utc::now() + chrono::Duration::seconds(i as i64);
            repo.store_message(&msg).await.unwrap();
        }

        let msgs = repo.get_recent_messages("chat1", 3).await.unwrap();
        assert_eq!(msgs.len(), 3);
        // Should be in chronological order
        assert_eq!(msgs[0].id, "m2");
        assert_eq!(msgs[2].id, "m4");
    }

    #[tokio::test]
    async fn delete_old_messages() {
        let db = setup().await;
        let repo = MessageRepository::new(&db, 100);

        let mut old = make_message("m1", "chat1", "Old");
        old.timestamp = Utc::now() - chrono::Duration::hours(2);
        repo.store_message(&old).await.unwrap();

        let new = make_message("m2", "chat1", "New");
        repo.store_message(&new).await.unwrap();

        let cutoff = Utc::now() - chrono::Duration::hours(1);
        let deleted = repo.delete_old_messages(cutoff).await.unwrap();
        assert_eq!(deleted, 1);

        let remaining = repo.get_new_messages(None).await.unwrap();
        assert_eq!(remaining.len(), 1);
        assert_eq!(remaining[0].id, "m2");
    }

    #[tokio::test]
    async fn cache_hit() {
        let db = setup().await;
        let repo = MessageRepository::new(&db, 100);

        let msg = make_message("cached-1", "chat1", "Hello");
        repo.store_message(&msg).await.unwrap();

        assert!(repo.cache_contains("cached-1"));
        assert!(!repo.cache_contains("nonexistent"));
    }
}
