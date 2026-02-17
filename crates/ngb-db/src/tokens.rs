use ngb_types::{AccessToken, NanoGridBotError, Result};
use uuid::Uuid;

use crate::connection::Database;

/// Repository for access token management.
pub struct TokenRepository<'a> {
    db: &'a Database,
}

impl<'a> TokenRepository<'a> {
    pub fn new(db: &'a Database) -> Self {
        Self { db }
    }

    /// Create a new access token for a workspace. Returns the generated token string.
    pub async fn create_token(&self, workspace_id: &str) -> Result<String> {
        let token = format!("ngb-{}", Uuid::new_v4().simple().to_string().get(..12).unwrap());

        sqlx::query(
            "INSERT INTO access_tokens (token, workspace_id) VALUES (?, ?)",
        )
        .bind(&token)
        .bind(workspace_id)
        .execute(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Create token: {e}")))?;

        Ok(token)
    }

    /// Validate a token and mark it as used. Returns the workspace_id if valid.
    pub async fn validate_and_consume(&self, token: &str) -> Result<Option<String>> {
        let row: Option<TokenRow> = sqlx::query_as(
            "SELECT token, workspace_id, used FROM access_tokens WHERE token = ?",
        )
        .bind(token)
        .fetch_optional(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Validate token: {e}")))?;

        match row {
            Some(r) if r.used == 0 => {
                sqlx::query("UPDATE access_tokens SET used = 1 WHERE token = ?")
                    .bind(token)
                    .execute(self.db.pool())
                    .await
                    .map_err(|e| NanoGridBotError::Database(format!("Consume token: {e}")))?;

                Ok(Some(r.workspace_id))
            }
            _ => Ok(None),
        }
    }

    /// Get all tokens for a workspace.
    pub async fn get_by_workspace(&self, workspace_id: &str) -> Result<Vec<AccessToken>> {
        let rows: Vec<TokenRow> = sqlx::query_as(
            "SELECT token, workspace_id, used FROM access_tokens WHERE workspace_id = ?",
        )
        .bind(workspace_id)
        .fetch_all(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Get tokens by workspace: {e}")))?;

        Ok(rows
            .into_iter()
            .map(|r| AccessToken {
                token: r.token,
                workspace_id: r.workspace_id,
                used: r.used != 0,
            })
            .collect())
    }
}

#[derive(sqlx::FromRow)]
struct TokenRow {
    token: String,
    workspace_id: String,
    used: i32,
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
    async fn create_token_format() {
        let db = setup().await;
        let repo = TokenRepository::new(&db);

        let token = repo.create_token("ws-1").await.unwrap();
        assert!(token.starts_with("ngb-"));
        assert_eq!(token.len(), 16); // "ngb-" (4) + 12 hex chars
    }

    #[tokio::test]
    async fn validate_and_consume() {
        let db = setup().await;
        let repo = TokenRepository::new(&db);

        let token = repo.create_token("ws-abc").await.unwrap();

        // First use succeeds
        let ws_id = repo.validate_and_consume(&token).await.unwrap();
        assert_eq!(ws_id, Some("ws-abc".to_string()));

        // Second use fails (already consumed)
        let ws_id = repo.validate_and_consume(&token).await.unwrap();
        assert_eq!(ws_id, None);
    }

    #[tokio::test]
    async fn validate_nonexistent() {
        let db = setup().await;
        let repo = TokenRepository::new(&db);

        let ws_id = repo.validate_and_consume("ngb-doesnotexist").await.unwrap();
        assert_eq!(ws_id, None);
    }

    #[tokio::test]
    async fn get_by_workspace() {
        let db = setup().await;
        let repo = TokenRepository::new(&db);

        repo.create_token("ws-1").await.unwrap();
        repo.create_token("ws-1").await.unwrap();
        repo.create_token("ws-2").await.unwrap();

        let tokens = repo.get_by_workspace("ws-1").await.unwrap();
        assert_eq!(tokens.len(), 2);
        assert!(tokens.iter().all(|t| t.workspace_id == "ws-1"));
    }

    #[tokio::test]
    async fn token_marks_used() {
        let db = setup().await;
        let repo = TokenRepository::new(&db);

        let token_str = repo.create_token("ws-1").await.unwrap();

        let tokens = repo.get_by_workspace("ws-1").await.unwrap();
        assert!(!tokens[0].used);

        repo.validate_and_consume(&token_str).await.unwrap();

        let tokens = repo.get_by_workspace("ws-1").await.unwrap();
        assert!(tokens[0].used);
    }
}
