use std::collections::HashMap;

use ngb_types::{NanoGridBotError, RegisteredGroup, Result};

use crate::connection::Database;

/// Repository for group storage and retrieval.
pub struct GroupRepository<'a> {
    db: &'a Database,
}

impl<'a> GroupRepository<'a> {
    pub fn new(db: &'a Database) -> Self {
        Self { db }
    }

    /// Save or update a group (upsert).
    pub async fn save_group(&self, group: &RegisteredGroup) -> Result<()> {
        let container_config = group
            .container_config
            .as_ref()
            .map(|c| serde_json::to_string(c).unwrap_or_default());

        sqlx::query(
            "INSERT OR REPLACE INTO groups
             (jid, name, folder, trigger_pattern, container_config, requires_trigger)
             VALUES (?, ?, ?, ?, ?, ?)",
        )
        .bind(&group.jid)
        .bind(&group.name)
        .bind(&group.folder)
        .bind(&group.trigger_pattern)
        .bind(&container_config)
        .bind(group.requires_trigger as i32)
        .execute(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Save group: {e}")))?;

        Ok(())
    }

    /// Get a group by JID.
    pub async fn get_group(&self, jid: &str) -> Result<Option<RegisteredGroup>> {
        let row: Option<GroupRow> = sqlx::query_as(
            "SELECT jid, name, folder, trigger_pattern, container_config, requires_trigger
             FROM groups WHERE jid = ?",
        )
        .bind(jid)
        .fetch_optional(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Get group: {e}")))?;

        Ok(row.map(row_to_group))
    }

    /// Get all registered groups.
    pub async fn get_all(&self) -> Result<Vec<RegisteredGroup>> {
        let rows: Vec<GroupRow> = sqlx::query_as(
            "SELECT jid, name, folder, trigger_pattern, container_config, requires_trigger
             FROM groups ORDER BY name ASC",
        )
        .fetch_all(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Get all groups: {e}")))?;

        Ok(rows.into_iter().map(row_to_group).collect())
    }

    /// Get groups by folder.
    pub async fn get_by_folder(&self, folder: &str) -> Result<Vec<RegisteredGroup>> {
        let rows: Vec<GroupRow> = sqlx::query_as(
            "SELECT jid, name, folder, trigger_pattern, container_config, requires_trigger
             FROM groups WHERE folder = ? ORDER BY name ASC",
        )
        .bind(folder)
        .fetch_all(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Get groups by folder: {e}")))?;

        Ok(rows.into_iter().map(row_to_group).collect())
    }

    /// Delete a group by JID.
    pub async fn delete_group(&self, jid: &str) -> Result<bool> {
        let result = sqlx::query("DELETE FROM groups WHERE jid = ?")
            .bind(jid)
            .execute(self.db.pool())
            .await
            .map_err(|e| NanoGridBotError::Database(format!("Delete group: {e}")))?;

        Ok(result.rows_affected() > 0)
    }

    /// Check if a group exists.
    pub async fn exists(&self, jid: &str) -> Result<bool> {
        let row: Option<(i32,)> = sqlx::query_as("SELECT 1 FROM groups WHERE jid = ?")
            .bind(jid)
            .fetch_optional(self.db.pool())
            .await
            .map_err(|e| NanoGridBotError::Database(format!("Check group exists: {e}")))?;

        Ok(row.is_some())
    }
}

#[derive(sqlx::FromRow)]
struct GroupRow {
    jid: String,
    name: String,
    folder: String,
    trigger_pattern: Option<String>,
    container_config: Option<String>,
    requires_trigger: i32,
}

fn row_to_group(row: GroupRow) -> RegisteredGroup {
    let container_config: Option<HashMap<String, serde_json::Value>> = row
        .container_config
        .as_deref()
        .and_then(|s| serde_json::from_str(s).ok());

    RegisteredGroup {
        jid: row.jid,
        name: row.name,
        folder: row.folder,
        trigger_pattern: row.trigger_pattern,
        container_config,
        requires_trigger: row.requires_trigger != 0,
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

    fn make_group(jid: &str, name: &str, folder: &str) -> RegisteredGroup {
        RegisteredGroup {
            jid: jid.to_string(),
            name: name.to_string(),
            folder: folder.to_string(),
            trigger_pattern: None,
            container_config: None,
            requires_trigger: true,
        }
    }

    #[tokio::test]
    async fn save_and_get_group() {
        let db = setup().await;
        let repo = GroupRepository::new(&db);

        let group = make_group("tg:123", "Test Group", "test");
        repo.save_group(&group).await.unwrap();

        let found = repo.get_group("tg:123").await.unwrap().unwrap();
        assert_eq!(found.jid, "tg:123");
        assert_eq!(found.name, "Test Group");
        assert!(found.requires_trigger);
    }

    #[tokio::test]
    async fn save_group_upsert() {
        let db = setup().await;
        let repo = GroupRepository::new(&db);

        let mut group = make_group("tg:123", "Old Name", "test");
        repo.save_group(&group).await.unwrap();

        group.name = "New Name".to_string();
        repo.save_group(&group).await.unwrap();

        let found = repo.get_group("tg:123").await.unwrap().unwrap();
        assert_eq!(found.name, "New Name");
    }

    #[tokio::test]
    async fn get_all_groups() {
        let db = setup().await;
        let repo = GroupRepository::new(&db);

        repo.save_group(&make_group("a:1", "Alpha", "alpha"))
            .await
            .unwrap();
        repo.save_group(&make_group("b:2", "Beta", "beta"))
            .await
            .unwrap();

        let all = repo.get_all().await.unwrap();
        assert_eq!(all.len(), 2);
        // Sorted by name
        assert_eq!(all[0].name, "Alpha");
        assert_eq!(all[1].name, "Beta");
    }

    #[tokio::test]
    async fn get_by_folder() {
        let db = setup().await;
        let repo = GroupRepository::new(&db);

        repo.save_group(&make_group("a:1", "A", "shared"))
            .await
            .unwrap();
        repo.save_group(&make_group("b:2", "B", "shared"))
            .await
            .unwrap();
        repo.save_group(&make_group("c:3", "C", "other"))
            .await
            .unwrap();

        let shared = repo.get_by_folder("shared").await.unwrap();
        assert_eq!(shared.len(), 2);
    }

    #[tokio::test]
    async fn delete_group() {
        let db = setup().await;
        let repo = GroupRepository::new(&db);

        repo.save_group(&make_group("tg:1", "G1", "f1"))
            .await
            .unwrap();
        assert!(repo.exists("tg:1").await.unwrap());

        let deleted = repo.delete_group("tg:1").await.unwrap();
        assert!(deleted);
        assert!(!repo.exists("tg:1").await.unwrap());

        let deleted_again = repo.delete_group("tg:1").await.unwrap();
        assert!(!deleted_again);
    }

    #[tokio::test]
    async fn group_not_found() {
        let db = setup().await;
        let repo = GroupRepository::new(&db);

        let found = repo.get_group("nonexistent").await.unwrap();
        assert!(found.is_none());
    }

    #[tokio::test]
    async fn group_with_container_config() {
        let db = setup().await;
        let repo = GroupRepository::new(&db);

        let mut config = HashMap::new();
        config.insert(
            "timeout".to_string(),
            serde_json::Value::Number(serde_json::Number::from(60)),
        );

        let mut group = make_group("tg:1", "G1", "f1");
        group.container_config = Some(config);
        repo.save_group(&group).await.unwrap();

        let found = repo.get_group("tg:1").await.unwrap().unwrap();
        let cc = found.container_config.unwrap();
        assert_eq!(cc.get("timeout").unwrap(), &serde_json::json!(60));
    }
}
