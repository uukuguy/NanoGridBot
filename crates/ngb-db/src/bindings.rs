use ngb_types::{ChannelBinding, NanoGridBotError, Result};

use crate::connection::Database;

/// Repository for channel-to-workspace binding management.
pub struct BindingRepository<'a> {
    db: &'a Database,
}

impl<'a> BindingRepository<'a> {
    pub fn new(db: &'a Database) -> Self {
        Self { db }
    }

    /// Bind a channel to a workspace (upsert).
    pub async fn bind(&self, channel_jid: &str, workspace_id: &str) -> Result<()> {
        sqlx::query(
            "INSERT OR REPLACE INTO channel_bindings (channel_jid, workspace_id)
             VALUES (?, ?)",
        )
        .bind(channel_jid)
        .bind(workspace_id)
        .execute(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Bind channel: {e}")))?;

        Ok(())
    }

    /// Unbind a channel.
    pub async fn unbind(&self, channel_jid: &str) -> Result<bool> {
        let result = sqlx::query("DELETE FROM channel_bindings WHERE channel_jid = ?")
            .bind(channel_jid)
            .execute(self.db.pool())
            .await
            .map_err(|e| NanoGridBotError::Database(format!("Unbind channel: {e}")))?;

        Ok(result.rows_affected() > 0)
    }

    /// Get binding by channel JID.
    pub async fn get_by_jid(&self, channel_jid: &str) -> Result<Option<ChannelBinding>> {
        let row: Option<BindingRow> = sqlx::query_as(
            "SELECT channel_jid, workspace_id FROM channel_bindings WHERE channel_jid = ?",
        )
        .bind(channel_jid)
        .fetch_optional(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Get binding: {e}")))?;

        Ok(row.map(|r| ChannelBinding {
            channel_jid: r.channel_jid,
            workspace_id: r.workspace_id,
        }))
    }

    /// Get all bindings for a workspace.
    pub async fn get_by_workspace(&self, workspace_id: &str) -> Result<Vec<ChannelBinding>> {
        let rows: Vec<BindingRow> = sqlx::query_as(
            "SELECT channel_jid, workspace_id FROM channel_bindings WHERE workspace_id = ?",
        )
        .bind(workspace_id)
        .fetch_all(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Get bindings by workspace: {e}")))?;

        Ok(rows
            .into_iter()
            .map(|r| ChannelBinding {
                channel_jid: r.channel_jid,
                workspace_id: r.workspace_id,
            })
            .collect())
    }

    /// Check if a channel is bound.
    pub async fn exists(&self, channel_jid: &str) -> Result<bool> {
        let row: Option<(i32,)> =
            sqlx::query_as("SELECT 1 FROM channel_bindings WHERE channel_jid = ?")
                .bind(channel_jid)
                .fetch_optional(self.db.pool())
                .await
                .map_err(|e| NanoGridBotError::Database(format!("Check binding exists: {e}")))?;

        Ok(row.is_some())
    }
}

#[derive(sqlx::FromRow)]
struct BindingRow {
    channel_jid: String,
    workspace_id: String,
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

    #[tokio::test]
    async fn bind_and_get() {
        let db = setup().await;
        let repo = BindingRepository::new(&db);

        repo.bind("telegram:group123", "ws-abc").await.unwrap();

        let binding = repo.get_by_jid("telegram:group123").await.unwrap().unwrap();
        assert_eq!(binding.workspace_id, "ws-abc");
    }

    #[tokio::test]
    async fn bind_upsert() {
        let db = setup().await;
        let repo = BindingRepository::new(&db);

        repo.bind("telegram:group123", "ws-old").await.unwrap();
        repo.bind("telegram:group123", "ws-new").await.unwrap();

        let binding = repo.get_by_jid("telegram:group123").await.unwrap().unwrap();
        assert_eq!(binding.workspace_id, "ws-new");
    }

    #[tokio::test]
    async fn unbind() {
        let db = setup().await;
        let repo = BindingRepository::new(&db);

        repo.bind("telegram:group123", "ws-abc").await.unwrap();
        assert!(repo.exists("telegram:group123").await.unwrap());

        let removed = repo.unbind("telegram:group123").await.unwrap();
        assert!(removed);
        assert!(!repo.exists("telegram:group123").await.unwrap());

        let removed_again = repo.unbind("telegram:group123").await.unwrap();
        assert!(!removed_again);
    }

    #[tokio::test]
    async fn get_by_workspace() {
        let db = setup().await;
        let repo = BindingRepository::new(&db);

        repo.bind("telegram:g1", "ws-shared").await.unwrap();
        repo.bind("slack:c1", "ws-shared").await.unwrap();
        repo.bind("telegram:g2", "ws-other").await.unwrap();

        let bindings = repo.get_by_workspace("ws-shared").await.unwrap();
        assert_eq!(bindings.len(), 2);
    }

    #[tokio::test]
    async fn not_found() {
        let db = setup().await;
        let repo = BindingRepository::new(&db);

        let binding = repo.get_by_jid("nonexistent").await.unwrap();
        assert!(binding.is_none());
        assert!(!repo.exists("nonexistent").await.unwrap());
    }
}
