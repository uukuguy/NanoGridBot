use std::collections::HashMap;

use ngb_types::{NanoGridBotError, Result, Workspace};

use crate::connection::Database;

/// Repository for workspace storage and retrieval.
pub struct WorkspaceRepository<'a> {
    db: &'a Database,
}

impl<'a> WorkspaceRepository<'a> {
    pub fn new(db: &'a Database) -> Self {
        Self { db }
    }

    /// Save or update a workspace (upsert).
    pub async fn save(&self, ws: &Workspace) -> Result<()> {
        let container_config = ws
            .container_config
            .as_ref()
            .map(|c| serde_json::to_string(c).unwrap_or_default());

        sqlx::query(
            "INSERT OR REPLACE INTO workspaces
             (id, name, owner, folder, shared, container_config)
             VALUES (?, ?, ?, ?, ?, ?)",
        )
        .bind(&ws.id)
        .bind(&ws.name)
        .bind(&ws.owner)
        .bind(&ws.folder)
        .bind(ws.shared as i32)
        .bind(&container_config)
        .execute(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Save workspace: {e}")))?;

        Ok(())
    }

    /// Get a workspace by ID.
    pub async fn get(&self, id: &str) -> Result<Option<Workspace>> {
        let row: Option<WorkspaceRow> = sqlx::query_as(
            "SELECT id, name, owner, folder, shared, container_config
             FROM workspaces WHERE id = ?",
        )
        .bind(id)
        .fetch_optional(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Get workspace: {e}")))?;

        Ok(row.map(row_to_workspace))
    }

    /// Get all workspaces.
    pub async fn get_all(&self) -> Result<Vec<Workspace>> {
        let rows: Vec<WorkspaceRow> = sqlx::query_as(
            "SELECT id, name, owner, folder, shared, container_config
             FROM workspaces ORDER BY name ASC",
        )
        .fetch_all(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Get all workspaces: {e}")))?;

        Ok(rows.into_iter().map(row_to_workspace).collect())
    }

    /// Delete a workspace by ID.
    pub async fn delete(&self, id: &str) -> Result<bool> {
        let result = sqlx::query("DELETE FROM workspaces WHERE id = ?")
            .bind(id)
            .execute(self.db.pool())
            .await
            .map_err(|e| NanoGridBotError::Database(format!("Delete workspace: {e}")))?;

        Ok(result.rows_affected() > 0)
    }

    /// Check if a workspace exists.
    pub async fn exists(&self, id: &str) -> Result<bool> {
        let row: Option<(i32,)> = sqlx::query_as("SELECT 1 FROM workspaces WHERE id = ?")
            .bind(id)
            .fetch_optional(self.db.pool())
            .await
            .map_err(|e| NanoGridBotError::Database(format!("Check workspace exists: {e}")))?;

        Ok(row.is_some())
    }
}

#[derive(sqlx::FromRow)]
struct WorkspaceRow {
    id: String,
    name: String,
    owner: String,
    folder: String,
    shared: i32,
    container_config: Option<String>,
}

fn row_to_workspace(row: WorkspaceRow) -> Workspace {
    let container_config: Option<HashMap<String, serde_json::Value>> = row
        .container_config
        .as_deref()
        .and_then(|s| serde_json::from_str(s).ok());

    Workspace {
        id: row.id,
        name: row.name,
        owner: row.owner,
        folder: row.folder,
        shared: row.shared != 0,
        container_config,
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
    async fn save_and_get() {
        let db = setup().await;
        let repo = WorkspaceRepository::new(&db);

        let ws = make_workspace("ws-1", "my-agent");
        repo.save(&ws).await.unwrap();

        let found = repo.get("ws-1").await.unwrap().unwrap();
        assert_eq!(found.id, "ws-1");
        assert_eq!(found.name, "my-agent");
        assert_eq!(found.owner, "test-user");
        assert!(!found.shared);
    }

    #[tokio::test]
    async fn save_upsert() {
        let db = setup().await;
        let repo = WorkspaceRepository::new(&db);

        let mut ws = make_workspace("ws-1", "old-name");
        repo.save(&ws).await.unwrap();

        ws.name = "new-name".to_string();
        repo.save(&ws).await.unwrap();

        let found = repo.get("ws-1").await.unwrap().unwrap();
        assert_eq!(found.name, "new-name");
    }

    #[tokio::test]
    async fn get_all() {
        let db = setup().await;
        let repo = WorkspaceRepository::new(&db);

        repo.save(&make_workspace("ws-a", "alpha")).await.unwrap();
        repo.save(&make_workspace("ws-b", "beta")).await.unwrap();

        let all = repo.get_all().await.unwrap();
        assert_eq!(all.len(), 2);
        assert_eq!(all[0].name, "alpha");
        assert_eq!(all[1].name, "beta");
    }

    #[tokio::test]
    async fn delete() {
        let db = setup().await;
        let repo = WorkspaceRepository::new(&db);

        repo.save(&make_workspace("ws-1", "test")).await.unwrap();
        assert!(repo.exists("ws-1").await.unwrap());

        let deleted = repo.delete("ws-1").await.unwrap();
        assert!(deleted);
        assert!(!repo.exists("ws-1").await.unwrap());

        let deleted_again = repo.delete("ws-1").await.unwrap();
        assert!(!deleted_again);
    }

    #[tokio::test]
    async fn not_found() {
        let db = setup().await;
        let repo = WorkspaceRepository::new(&db);

        let found = repo.get("nonexistent").await.unwrap();
        assert!(found.is_none());
    }

    #[tokio::test]
    async fn with_container_config() {
        let db = setup().await;
        let repo = WorkspaceRepository::new(&db);

        let mut ws = make_workspace("ws-1", "custom");
        let mut config = HashMap::new();
        config.insert(
            "memory".to_string(),
            serde_json::Value::String("512m".to_string()),
        );
        ws.container_config = Some(config);
        ws.shared = true;

        repo.save(&ws).await.unwrap();

        let found = repo.get("ws-1").await.unwrap().unwrap();
        assert!(found.shared);
        let cc = found.container_config.unwrap();
        assert_eq!(cc["memory"], "512m");
    }
}
