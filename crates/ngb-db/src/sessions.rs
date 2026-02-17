use std::collections::HashMap;

use ngb_types::{NanoGridBotError, Result};

use crate::Database;

/// Repository for per-group Claude session ID persistence.
pub struct SessionRepository<'a> {
    db: &'a Database,
}

impl<'a> SessionRepository<'a> {
    pub fn new(db: &'a Database) -> Self {
        Self { db }
    }

    /// Get the session ID for a group, if one exists.
    pub async fn get_session(&self, group_folder: &str) -> Result<Option<String>> {
        let row: Option<(String,)> =
            sqlx::query_as("SELECT session_id FROM sessions WHERE group_folder = ?")
                .bind(group_folder)
                .fetch_optional(self.db.pool())
                .await
                .map_err(|e| NanoGridBotError::Database(format!("Get session: {e}")))?;

        Ok(row.map(|r| r.0))
    }

    /// Set (insert or update) the session ID for a group.
    pub async fn set_session(&self, group_folder: &str, session_id: &str) -> Result<()> {
        sqlx::query(
            "INSERT INTO sessions (group_folder, session_id, updated_at)
             VALUES (?, ?, datetime('now'))
             ON CONFLICT(group_folder) DO UPDATE SET
                session_id = excluded.session_id,
                updated_at = excluded.updated_at",
        )
        .bind(group_folder)
        .bind(session_id)
        .execute(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Set session: {e}")))?;

        Ok(())
    }

    /// Get all stored sessions as a map of group_folder → session_id.
    pub async fn get_all_sessions(&self) -> Result<HashMap<String, String>> {
        let rows: Vec<(String, String)> =
            sqlx::query_as("SELECT group_folder, session_id FROM sessions")
                .fetch_all(self.db.pool())
                .await
                .map_err(|e| NanoGridBotError::Database(format!("Get all sessions: {e}")))?;

        Ok(rows.into_iter().collect())
    }

    /// Delete the session for a group.
    pub async fn delete_session(&self, group_folder: &str) -> Result<()> {
        sqlx::query("DELETE FROM sessions WHERE group_folder = ?")
            .bind(group_folder)
            .execute(self.db.pool())
            .await
            .map_err(|e| NanoGridBotError::Database(format!("Delete session: {e}")))?;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn session_roundtrip() {
        let db = Database::in_memory().await.unwrap();
        db.initialize().await.unwrap();
        let repo = SessionRepository::new(&db);

        // Initially empty
        assert!(repo.get_session("main").await.unwrap().is_none());

        // Insert
        repo.set_session("main", "sess-123").await.unwrap();
        assert_eq!(
            repo.get_session("main").await.unwrap(),
            Some("sess-123".to_string())
        );

        // Update (upsert)
        repo.set_session("main", "sess-456").await.unwrap();
        assert_eq!(
            repo.get_session("main").await.unwrap(),
            Some("sess-456".to_string())
        );
    }

    #[tokio::test]
    async fn get_all_sessions() {
        let db = Database::in_memory().await.unwrap();
        db.initialize().await.unwrap();
        let repo = SessionRepository::new(&db);

        repo.set_session("main", "sess-a").await.unwrap();
        repo.set_session("dev", "sess-b").await.unwrap();

        let all = repo.get_all_sessions().await.unwrap();
        assert_eq!(all.len(), 2);
        assert_eq!(all.get("main").unwrap(), "sess-a");
        assert_eq!(all.get("dev").unwrap(), "sess-b");
    }

    #[tokio::test]
    async fn delete_session() {
        let db = Database::in_memory().await.unwrap();
        db.initialize().await.unwrap();
        let repo = SessionRepository::new(&db);

        repo.set_session("main", "sess-123").await.unwrap();
        assert!(repo.get_session("main").await.unwrap().is_some());

        repo.delete_session("main").await.unwrap();
        assert!(repo.get_session("main").await.unwrap().is_none());
    }
}
