use std::collections::HashMap;

use chrono::Utc;

use ngb_types::{NanoGridBotError, Result};

use crate::connection::Database;

/// Repository for metrics tracking.
pub struct MetricsRepository<'a> {
    db: &'a Database,
}

impl<'a> MetricsRepository<'a> {
    pub fn new(db: &'a Database) -> Self {
        Self { db }
    }

    /// Record container execution start. Returns metric ID.
    pub async fn record_container_start(&self, group_folder: &str, channel: &str) -> Result<i64> {
        let now = Utc::now().to_rfc3339();
        let result = sqlx::query(
            "INSERT INTO container_metrics (group_folder, channel, start_time, status)
             VALUES (?, ?, ?, 'running')",
        )
        .bind(group_folder)
        .bind(channel)
        .bind(&now)
        .execute(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Record container start: {e}")))?;

        Ok(result.last_insert_rowid())
    }

    /// Record container execution end.
    pub async fn record_container_end(
        &self,
        metric_id: i64,
        status: &str,
        duration_seconds: Option<f64>,
        prompt_tokens: Option<i64>,
        completion_tokens: Option<i64>,
        error: Option<&str>,
    ) -> Result<()> {
        let now = Utc::now().to_rfc3339();
        let total_tokens = match (prompt_tokens, completion_tokens) {
            (Some(p), Some(c)) => Some(p + c),
            _ => None,
        };

        sqlx::query(
            "UPDATE container_metrics
             SET end_time = ?, duration_seconds = ?, status = ?,
                 prompt_tokens = ?, completion_tokens = ?, total_tokens = ?, error = ?
             WHERE id = ?",
        )
        .bind(&now)
        .bind(duration_seconds)
        .bind(status)
        .bind(prompt_tokens)
        .bind(completion_tokens)
        .bind(total_tokens)
        .bind(error)
        .bind(metric_id)
        .execute(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Record container end: {e}")))?;

        Ok(())
    }

    /// Get container execution statistics.
    pub async fn get_container_stats(
        &self,
        group_folder: Option<&str>,
        days: i64,
    ) -> Result<ContainerStats> {
        let (query, has_group) = if group_folder.is_some() {
            (
                "SELECT
                    COUNT(*) as total_runs,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_runs,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as failed_runs,
                    SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END) as timeouts,
                    AVG(duration_seconds) as avg_duration,
                    MAX(duration_seconds) as max_duration,
                    MIN(duration_seconds) as min_duration,
                    SUM(total_tokens) as total_tokens,
                    AVG(total_tokens) as avg_tokens
                 FROM container_metrics
                 WHERE start_time > datetime('now', '-' || ? || ' days')
                   AND group_folder = ?",
                true,
            )
        } else {
            (
                "SELECT
                    COUNT(*) as total_runs,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_runs,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as failed_runs,
                    SUM(CASE WHEN status = 'timeout' THEN 1 ELSE 0 END) as timeouts,
                    AVG(duration_seconds) as avg_duration,
                    MAX(duration_seconds) as max_duration,
                    MIN(duration_seconds) as min_duration,
                    SUM(total_tokens) as total_tokens,
                    AVG(total_tokens) as avg_tokens
                 FROM container_metrics
                 WHERE start_time > datetime('now', '-' || ? || ' days')",
                false,
            )
        };

        let row: StatsRow = if has_group {
            sqlx::query_as(query)
                .bind(days)
                .bind(group_folder.unwrap())
                .fetch_one(self.db.pool())
                .await
        } else {
            sqlx::query_as(query)
                .bind(days)
                .fetch_one(self.db.pool())
                .await
        }
        .map_err(|e| NanoGridBotError::Database(format!("Get container stats: {e}")))?;

        Ok(ContainerStats {
            total_runs: row.total_runs.unwrap_or(0),
            successful_runs: row.successful_runs.unwrap_or(0),
            failed_runs: row.failed_runs.unwrap_or(0),
            timeouts: row.timeouts.unwrap_or(0),
            avg_duration: row.avg_duration.unwrap_or(0.0),
            max_duration: row.max_duration.unwrap_or(0.0),
            min_duration: row.min_duration.unwrap_or(0.0),
            total_tokens: row.total_tokens.unwrap_or(0),
            avg_tokens: row.avg_tokens.unwrap_or(0.0),
        })
    }

    /// Record a request metric.
    pub async fn record_request(
        &self,
        channel: &str,
        request_type: &str,
        success: bool,
        group_folder: Option<&str>,
        error: Option<&str>,
    ) -> Result<()> {
        let now = Utc::now().to_rfc3339();
        sqlx::query(
            "INSERT INTO request_metrics (channel, group_folder, timestamp, request_type, success, error)
             VALUES (?, ?, ?, ?, ?, ?)",
        )
        .bind(channel)
        .bind(group_folder)
        .bind(&now)
        .bind(request_type)
        .bind(success as i32)
        .bind(error)
        .execute(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Record request: {e}")))?;

        Ok(())
    }

    /// Get request statistics grouped by channel.
    pub async fn get_request_stats(
        &self,
        channel: Option<&str>,
        days: i64,
    ) -> Result<HashMap<String, RequestStats>> {
        let (query, has_channel) = if channel.is_some() {
            (
                "SELECT
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_requests,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_requests,
                    channel
                 FROM request_metrics
                 WHERE timestamp > datetime('now', '-' || ? || ' days')
                   AND channel = ?
                 GROUP BY channel",
                true,
            )
        } else {
            (
                "SELECT
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_requests,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_requests,
                    channel
                 FROM request_metrics
                 WHERE timestamp > datetime('now', '-' || ? || ' days')
                 GROUP BY channel",
                false,
            )
        };

        let rows: Vec<RequestStatsRow> = if has_channel {
            sqlx::query_as(query)
                .bind(days)
                .bind(channel.unwrap())
                .fetch_all(self.db.pool())
                .await
        } else {
            sqlx::query_as(query)
                .bind(days)
                .fetch_all(self.db.pool())
                .await
        }
        .map_err(|e| NanoGridBotError::Database(format!("Get request stats: {e}")))?;

        let mut result = HashMap::new();
        for row in rows {
            result.insert(
                row.channel,
                RequestStats {
                    total_requests: row.total_requests.unwrap_or(0),
                    successful_requests: row.successful_requests.unwrap_or(0),
                    failed_requests: row.failed_requests.unwrap_or(0),
                },
            );
        }

        Ok(result)
    }
}

/// Container execution statistics.
#[derive(Debug, Clone)]
pub struct ContainerStats {
    pub total_runs: i64,
    pub successful_runs: i64,
    pub failed_runs: i64,
    pub timeouts: i64,
    pub avg_duration: f64,
    pub max_duration: f64,
    pub min_duration: f64,
    pub total_tokens: i64,
    pub avg_tokens: f64,
}

/// Request statistics for a channel.
#[derive(Debug, Clone)]
pub struct RequestStats {
    pub total_requests: i64,
    pub successful_requests: i64,
    pub failed_requests: i64,
}

#[derive(sqlx::FromRow)]
struct StatsRow {
    total_runs: Option<i64>,
    successful_runs: Option<i64>,
    failed_runs: Option<i64>,
    timeouts: Option<i64>,
    avg_duration: Option<f64>,
    max_duration: Option<f64>,
    min_duration: Option<f64>,
    total_tokens: Option<i64>,
    avg_tokens: Option<f64>,
}

#[derive(sqlx::FromRow)]
struct RequestStatsRow {
    total_requests: Option<i64>,
    successful_requests: Option<i64>,
    failed_requests: Option<i64>,
    channel: String,
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
    async fn record_container_lifecycle() {
        let db = setup().await;
        let repo = MetricsRepository::new(&db);

        let id = repo.record_container_start("g1", "telegram").await.unwrap();
        assert!(id > 0);

        repo.record_container_end(id, "success", Some(2.5), Some(100), Some(200), None)
            .await
            .unwrap();

        let stats = repo.get_container_stats(None, 7).await.unwrap();
        assert_eq!(stats.total_runs, 1);
        assert_eq!(stats.successful_runs, 1);
        assert_eq!(stats.total_tokens, 300);
    }

    #[tokio::test]
    async fn record_container_error() {
        let db = setup().await;
        let repo = MetricsRepository::new(&db);

        let id = repo.record_container_start("g1", "slack").await.unwrap();
        repo.record_container_end(id, "error", Some(1.0), None, None, Some("timeout"))
            .await
            .unwrap();

        let stats = repo.get_container_stats(None, 7).await.unwrap();
        assert_eq!(stats.failed_runs, 1);
    }

    #[tokio::test]
    async fn container_stats_by_group() {
        let db = setup().await;
        let repo = MetricsRepository::new(&db);

        let id1 = repo.record_container_start("g1", "telegram").await.unwrap();
        repo.record_container_end(id1, "success", Some(1.0), None, None, None)
            .await
            .unwrap();

        let id2 = repo.record_container_start("g2", "slack").await.unwrap();
        repo.record_container_end(id2, "success", Some(2.0), None, None, None)
            .await
            .unwrap();

        let stats = repo.get_container_stats(Some("g1"), 7).await.unwrap();
        assert_eq!(stats.total_runs, 1);
    }

    #[tokio::test]
    async fn record_and_get_request_stats() {
        let db = setup().await;
        let repo = MetricsRepository::new(&db);

        repo.record_request("telegram", "message", true, Some("g1"), None)
            .await
            .unwrap();
        repo.record_request("telegram", "command", true, Some("g1"), None)
            .await
            .unwrap();
        repo.record_request("slack", "message", false, None, Some("timeout"))
            .await
            .unwrap();

        let stats = repo.get_request_stats(None, 7).await.unwrap();
        assert_eq!(stats.len(), 2);

        let tg = stats.get("telegram").unwrap();
        assert_eq!(tg.total_requests, 2);
        assert_eq!(tg.successful_requests, 2);

        let sl = stats.get("slack").unwrap();
        assert_eq!(sl.total_requests, 1);
        assert_eq!(sl.failed_requests, 1);
    }

    #[tokio::test]
    async fn request_stats_by_channel() {
        let db = setup().await;
        let repo = MetricsRepository::new(&db);

        repo.record_request("telegram", "message", true, None, None)
            .await
            .unwrap();
        repo.record_request("slack", "message", true, None, None)
            .await
            .unwrap();

        let stats = repo.get_request_stats(Some("telegram"), 7).await.unwrap();
        assert_eq!(stats.len(), 1);
        assert!(stats.contains_key("telegram"));
    }

    #[tokio::test]
    async fn empty_stats() {
        let db = setup().await;
        let repo = MetricsRepository::new(&db);

        let stats = repo.get_container_stats(None, 7).await.unwrap();
        assert_eq!(stats.total_runs, 0);

        let req_stats = repo.get_request_stats(None, 7).await.unwrap();
        assert!(req_stats.is_empty());
    }
}
