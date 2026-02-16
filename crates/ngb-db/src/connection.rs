use std::path::Path;

use sqlx::sqlite::{SqliteConnectOptions, SqlitePool, SqlitePoolOptions};
use tracing::info;

use ngb_types::{NanoGridBotError, Result};

/// Async SQLite database connection manager.
pub struct Database {
    pool: SqlitePool,
}

impl Database {
    /// Create a new database connection from file path.
    pub async fn new(path: &Path) -> Result<Self> {
        let opts = SqliteConnectOptions::new()
            .filename(path)
            .create_if_missing(true)
            .journal_mode(sqlx::sqlite::SqliteJournalMode::Wal)
            .busy_timeout(std::time::Duration::from_millis(5000))
            .foreign_keys(true);

        let pool = SqlitePoolOptions::new()
            .max_connections(5)
            .connect_with(opts)
            .await
            .map_err(|e| NanoGridBotError::Database(format!("Failed to connect: {e}")))?;

        Ok(Self { pool })
    }

    /// Create a new in-memory database (for testing).
    pub async fn in_memory() -> Result<Self> {
        let opts = SqliteConnectOptions::new()
            .filename(":memory:")
            .journal_mode(sqlx::sqlite::SqliteJournalMode::Wal)
            .foreign_keys(true);

        let pool = SqlitePoolOptions::new()
            .max_connections(1)
            .connect_with(opts)
            .await
            .map_err(|e| NanoGridBotError::Database(format!("Failed to connect: {e}")))?;

        Ok(Self { pool })
    }

    /// Initialize all database tables and indexes.
    pub async fn initialize(&self) -> Result<()> {
        // Messages table
        sqlx::query(
            "CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_jid TEXT NOT NULL,
                sender TEXT NOT NULL,
                sender_name TEXT,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                is_from_me INTEGER DEFAULT 0,
                role TEXT DEFAULT 'user'
            )",
        )
        .execute(&self.pool)
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Create messages table: {e}")))?;

        sqlx::query(
            "CREATE INDEX IF NOT EXISTS idx_messages_chat_time
             ON messages(chat_jid, timestamp)",
        )
        .execute(&self.pool)
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Create messages index: {e}")))?;

        // Groups table
        sqlx::query(
            "CREATE TABLE IF NOT EXISTS groups (
                jid TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                folder TEXT NOT NULL,
                trigger_pattern TEXT,
                container_config TEXT,
                requires_trigger INTEGER DEFAULT 1
            )",
        )
        .execute(&self.pool)
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Create groups table: {e}")))?;

        // Tasks table
        sqlx::query(
            "CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_folder TEXT NOT NULL,
                prompt TEXT NOT NULL,
                schedule_type TEXT NOT NULL,
                schedule_value TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                next_run TEXT,
                context_mode TEXT DEFAULT 'group',
                target_chat_jid TEXT
            )",
        )
        .execute(&self.pool)
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Create tasks table: {e}")))?;

        // Container metrics table
        sqlx::query(
            "CREATE TABLE IF NOT EXISTS container_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_folder TEXT NOT NULL,
                channel TEXT NOT NULL,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                duration_seconds REAL,
                status TEXT DEFAULT 'running',
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                error TEXT
            )",
        )
        .execute(&self.pool)
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Create container_metrics table: {e}")))?;

        sqlx::query(
            "CREATE INDEX IF NOT EXISTS idx_container_metrics_group
             ON container_metrics(group_folder)",
        )
        .execute(&self.pool)
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Create container_metrics index: {e}")))?;

        sqlx::query(
            "CREATE INDEX IF NOT EXISTS idx_container_metrics_time
             ON container_metrics(start_time)",
        )
        .execute(&self.pool)
        .await
        .map_err(|e| {
            NanoGridBotError::Database(format!("Create container_metrics time index: {e}"))
        })?;

        // Request metrics table
        sqlx::query(
            "CREATE TABLE IF NOT EXISTS request_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                group_folder TEXT,
                timestamp TIMESTAMP NOT NULL,
                request_type TEXT NOT NULL,
                success INTEGER NOT NULL,
                error TEXT
            )",
        )
        .execute(&self.pool)
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Create request_metrics table: {e}")))?;

        sqlx::query(
            "CREATE INDEX IF NOT EXISTS idx_request_metrics_channel
             ON request_metrics(channel)",
        )
        .execute(&self.pool)
        .await
        .map_err(|e| {
            NanoGridBotError::Database(format!("Create request_metrics channel index: {e}"))
        })?;

        sqlx::query(
            "CREATE INDEX IF NOT EXISTS idx_request_metrics_time
             ON request_metrics(timestamp)",
        )
        .execute(&self.pool)
        .await
        .map_err(|e| {
            NanoGridBotError::Database(format!("Create request_metrics time index: {e}"))
        })?;

        info!("Database schema initialized (5 tables, 5 indexes)");
        Ok(())
    }

    /// Get a reference to the connection pool.
    pub fn pool(&self) -> &SqlitePool {
        &self.pool
    }

    /// Close the database.
    pub async fn close(&self) {
        self.pool.close().await;
        info!("Database connection closed");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn database_initialize() {
        let db = Database::in_memory().await.unwrap();
        db.initialize().await.unwrap();

        // Verify tables exist by querying them
        let row: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM messages")
            .fetch_one(db.pool())
            .await
            .unwrap();
        assert_eq!(row.0, 0);

        let row: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM groups")
            .fetch_one(db.pool())
            .await
            .unwrap();
        assert_eq!(row.0, 0);

        let row: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM tasks")
            .fetch_one(db.pool())
            .await
            .unwrap();
        assert_eq!(row.0, 0);

        let row: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM container_metrics")
            .fetch_one(db.pool())
            .await
            .unwrap();
        assert_eq!(row.0, 0);

        let row: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM request_metrics")
            .fetch_one(db.pool())
            .await
            .unwrap();
        assert_eq!(row.0, 0);
    }
}
