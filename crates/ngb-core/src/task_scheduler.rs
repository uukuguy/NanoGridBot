use std::str::FromStr;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use chrono::{Duration, Utc};
use ngb_db::{Database, TaskRepository};
use ngb_types::{NanoGridBotError, Result, ScheduleType, ScheduledTask, TaskStatus};
use regex::Regex;
use tokio::task::JoinHandle;
use tracing::{debug, error, info, warn};

use crate::group_queue::GroupQueue;

/// Poll interval for the scheduler loop (seconds).
const SCHEDULER_POLL_SECS: u64 = 60;

/// CRON/INTERVAL/ONCE task scheduler.
///
/// Periodically checks for due tasks and enqueues them into the GroupQueue.
pub struct TaskScheduler {
    db: Arc<Database>,
    queue: Arc<GroupQueue>,
    running: Arc<AtomicBool>,
    task_handle: Option<JoinHandle<()>>,
}

impl TaskScheduler {
    /// Create a new scheduler.
    pub fn new(db: Arc<Database>, queue: Arc<GroupQueue>) -> Self {
        Self {
            db,
            queue,
            running: Arc::new(AtomicBool::new(false)),
            task_handle: None,
        }
    }

    /// Start the scheduler background loop.
    pub fn start(&mut self) {
        if self.running.load(Ordering::SeqCst) {
            warn!("Scheduler is already running");
            return;
        }

        self.running.store(true, Ordering::SeqCst);
        let running = self.running.clone();
        let db = self.db.clone();
        let queue = self.queue.clone();

        let handle = tokio::spawn(async move {
            info!("Task scheduler started");
            while running.load(Ordering::SeqCst) {
                if let Err(e) = check_and_enqueue_due_tasks(&db, &queue).await {
                    error!(error = %e, "Scheduler tick failed");
                }
                tokio::time::sleep(std::time::Duration::from_secs(SCHEDULER_POLL_SECS)).await;
            }
            info!("Task scheduler stopped");
        });

        self.task_handle = Some(handle);
    }

    /// Stop the scheduler.
    pub fn stop(&mut self) {
        self.running.store(false, Ordering::SeqCst);
        if let Some(handle) = self.task_handle.take() {
            handle.abort();
        }
        info!("Task scheduler stop requested");
    }

    /// Check if the scheduler is running.
    pub fn is_running(&self) -> bool {
        self.running.load(Ordering::SeqCst)
    }

    /// Schedule a new task: calculate its next_run and save to DB.
    pub async fn schedule_task(&self, mut task: ScheduledTask) -> Result<i64> {
        let next_run = calculate_next_run(&task)?;
        task.next_run = next_run;
        task.status = TaskStatus::Active;

        let repo = TaskRepository::new(&self.db);
        let id = repo.save_task(&task).await?;
        info!(
            task_id = id,
            next_run = ?task.next_run,
            "Task scheduled"
        );
        Ok(id)
    }

    /// Cancel (delete) a task.
    pub async fn cancel_task(&self, task_id: i64) -> Result<bool> {
        let repo = TaskRepository::new(&self.db);
        let deleted = repo.delete_task(task_id).await?;
        if deleted {
            info!(task_id, "Task cancelled");
        }
        Ok(deleted)
    }

    /// Pause a task.
    pub async fn pause_task(&self, task_id: i64) -> Result<bool> {
        let repo = TaskRepository::new(&self.db);
        let updated = repo.update_status(task_id, TaskStatus::Paused).await?;
        if updated {
            info!(task_id, "Task paused");
        }
        Ok(updated)
    }

    /// Resume a paused task (re-calculate next_run).
    pub async fn resume_task(&self, task_id: i64) -> Result<bool> {
        let repo = TaskRepository::new(&self.db);
        if let Some(mut task) = repo.get_task(task_id).await? {
            task.status = TaskStatus::Active;
            let next_run = calculate_next_run(&task)?;
            task.next_run = next_run;
            repo.save_task(&task).await?;
            info!(task_id, next_run = ?task.next_run, "Task resumed");
            Ok(true)
        } else {
            Ok(false)
        }
    }
}

/// Check for due tasks and enqueue them into the GroupQueue.
async fn check_and_enqueue_due_tasks(db: &Database, queue: &GroupQueue) -> Result<()> {
    let repo = TaskRepository::new(db);
    let due_tasks = repo.get_due().await?;

    if due_tasks.is_empty() {
        return Ok(());
    }

    debug!(count = due_tasks.len(), "Found due tasks");

    for task in due_tasks {
        let task_id = task.id.unwrap_or(0);
        let jid = task
            .target_chat_jid
            .clone()
            .unwrap_or_else(|| format!("task:{}", task.group_folder));

        // Enqueue the task
        if let Err(e) = queue
            .enqueue_task(&jid, &task.group_folder, task.clone(), "scheduler")
            .await
        {
            error!(task_id, error = %e, "Failed to enqueue due task");
            continue;
        }

        // Update next_run based on schedule type
        match task.schedule_type {
            ScheduleType::Once => {
                // One-shot: mark as completed
                repo.update_status(task_id, TaskStatus::Completed).await?;
            }
            _ => {
                // Recurring: calculate next run
                if let Some(next) = calculate_next_run(&task)? {
                    repo.update_next_run(task_id, next).await?;
                }
            }
        }
    }

    Ok(())
}

/// Calculate the next run time for a task based on its schedule type.
pub fn calculate_next_run(task: &ScheduledTask) -> Result<Option<chrono::DateTime<chrono::Utc>>> {
    match task.schedule_type {
        ScheduleType::Cron => calculate_cron_next(&task.schedule_value),
        ScheduleType::Interval => calculate_interval_next(&task.schedule_value),
        ScheduleType::Once => {
            if let Some(next) = task.next_run {
                if next > Utc::now() {
                    Ok(Some(next))
                } else {
                    Ok(None)
                }
            } else {
                // Schedule for immediate execution
                Ok(Some(Utc::now()))
            }
        }
    }
}

/// Convert 5-field cron to 7-field and calculate next occurrence.
///
/// Rust `cron` crate uses 7-field format: sec min hour dom month dow year.
/// Standard user input is 5-field: min hour dom month dow.
/// We prepend "0" (second) and append "*" (year).
fn calculate_cron_next(expr: &str) -> Result<Option<chrono::DateTime<chrono::Utc>>> {
    let fields: Vec<&str> = expr.split_whitespace().collect();
    let normalized = fields.join(" ");
    let cron_expr = match fields.len() {
        5 => format!("0 {normalized} *"), // 5→7: prepend sec, append year
        6 => format!("{normalized} *"),   // 6→7: append year
        7 => normalized,                  // Already 7-field
        _ => {
            return Err(NanoGridBotError::Config(format!(
                "Invalid cron expression (expected 5-7 fields): {expr}"
            )));
        }
    };

    let schedule = cron::Schedule::from_str(&cron_expr).map_err(|e| {
        NanoGridBotError::Config(format!("Invalid cron expression '{cron_expr}': {e}"))
    })?;

    Ok(schedule.upcoming(Utc).next())
}

/// Parse interval expressions like "60s", "5m", "2h", "1d".
fn calculate_interval_next(value: &str) -> Result<Option<chrono::DateTime<chrono::Utc>>> {
    let re = Regex::new(r"^(\d+)([smhd])$").unwrap();
    if let Some(caps) = re.captures(value.trim()) {
        let amount: i64 = caps[1]
            .parse()
            .map_err(|_| NanoGridBotError::Config(format!("Invalid interval amount: {value}")))?;

        let duration = match &caps[2] {
            "s" => Duration::seconds(amount),
            "m" => Duration::minutes(amount),
            "h" => Duration::hours(amount),
            "d" => Duration::days(amount),
            _ => unreachable!(),
        };

        Ok(Some(Utc::now() + duration))
    } else {
        // Try plain number as seconds
        if let Ok(secs) = value.trim().parse::<i64>() {
            Ok(Some(Utc::now() + Duration::seconds(secs)))
        } else {
            Err(NanoGridBotError::Config(format!(
                "Invalid interval expression: {value}. Expected format: 60s, 5m, 2h, 1d"
            )))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ngb_config::Config;
    use ngb_db::Database;

    #[test]
    fn cron_next_5_field() {
        let result = calculate_cron_next("0 9 * * *").unwrap();
        assert!(result.is_some());
        let next = result.unwrap();
        assert!(next > Utc::now());
    }

    #[test]
    fn cron_next_6_field() {
        let result = calculate_cron_next("0 0 9 * * *").unwrap();
        assert!(result.is_some());
    }

    #[test]
    fn cron_next_7_field() {
        let result = calculate_cron_next("0 0 9 * * * *").unwrap();
        assert!(result.is_some());
    }

    #[test]
    fn cron_invalid_expression() {
        let result = calculate_cron_next("not a cron");
        assert!(result.is_err());
    }

    #[test]
    fn interval_seconds() {
        let result = calculate_interval_next("60s").unwrap().unwrap();
        let diff = result - Utc::now();
        assert!(diff.num_seconds() >= 59 && diff.num_seconds() <= 61);
    }

    #[test]
    fn interval_minutes() {
        let result = calculate_interval_next("5m").unwrap().unwrap();
        let diff = result - Utc::now();
        assert!(diff.num_minutes() >= 4 && diff.num_minutes() <= 6);
    }

    #[test]
    fn interval_hours() {
        let result = calculate_interval_next("2h").unwrap().unwrap();
        let diff = result - Utc::now();
        assert!(diff.num_hours() >= 1 && diff.num_hours() <= 3);
    }

    #[test]
    fn interval_days() {
        let result = calculate_interval_next("1d").unwrap().unwrap();
        let diff = result - Utc::now();
        assert!(diff.num_hours() >= 23 && diff.num_hours() <= 25);
    }

    #[test]
    fn interval_plain_number_as_seconds() {
        let result = calculate_interval_next("120").unwrap().unwrap();
        let diff = result - Utc::now();
        assert!(diff.num_seconds() >= 119 && diff.num_seconds() <= 121);
    }

    #[test]
    fn interval_invalid() {
        let result = calculate_interval_next("abc");
        assert!(result.is_err());
    }

    #[test]
    fn once_future_time() {
        let future = Utc::now() + Duration::hours(1);
        let task = ScheduledTask {
            id: Some(1),
            group_folder: "g1".to_string(),
            prompt: "test".to_string(),
            schedule_type: ScheduleType::Once,
            schedule_value: "".to_string(),
            status: TaskStatus::Active,
            next_run: Some(future),
            context_mode: "group".to_string(),
            target_chat_jid: None,
        };
        let result = calculate_next_run(&task).unwrap();
        assert!(result.is_some());
    }

    #[test]
    fn once_past_time() {
        let past = Utc::now() - Duration::hours(1);
        let task = ScheduledTask {
            id: Some(1),
            group_folder: "g1".to_string(),
            prompt: "test".to_string(),
            schedule_type: ScheduleType::Once,
            schedule_value: "".to_string(),
            status: TaskStatus::Active,
            next_run: Some(past),
            context_mode: "group".to_string(),
            target_chat_jid: None,
        };
        let result = calculate_next_run(&task).unwrap();
        assert!(result.is_none());
    }

    #[tokio::test]
    async fn scheduler_start_stop() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let cfg = test_config();
        let queue = Arc::new(GroupQueue::new(cfg, db.clone()));
        let mut scheduler = TaskScheduler::new(db, queue);

        assert!(!scheduler.is_running());
        scheduler.start();
        assert!(scheduler.is_running());
        scheduler.stop();
        assert!(!scheduler.is_running());
    }

    #[tokio::test]
    async fn schedule_and_cancel_task() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let cfg = test_config();
        let queue = Arc::new(GroupQueue::new(cfg, db.clone()));
        let scheduler = TaskScheduler::new(db.clone(), queue);

        let task = ScheduledTask {
            id: None,
            group_folder: "g1".to_string(),
            prompt: "daily check".to_string(),
            schedule_type: ScheduleType::Interval,
            schedule_value: "60s".to_string(),
            status: TaskStatus::Active,
            next_run: None,
            context_mode: "group".to_string(),
            target_chat_jid: None,
        };

        let id = scheduler.schedule_task(task).await.unwrap();
        assert!(id > 0);

        // Verify it was saved
        let repo = TaskRepository::new(&db);
        let saved = repo.get_task(id).await.unwrap().unwrap();
        assert!(saved.next_run.is_some());
        assert_eq!(saved.status, TaskStatus::Active);

        // Cancel it
        let cancelled = scheduler.cancel_task(id).await.unwrap();
        assert!(cancelled);
        assert!(repo.get_task(id).await.unwrap().is_none());
    }

    #[tokio::test]
    async fn pause_and_resume_task() {
        let db = Arc::new(Database::in_memory().await.unwrap());
        db.initialize().await.unwrap();

        let cfg = test_config();
        let queue = Arc::new(GroupQueue::new(cfg, db.clone()));
        let scheduler = TaskScheduler::new(db.clone(), queue);

        let task = ScheduledTask {
            id: None,
            group_folder: "g1".to_string(),
            prompt: "check".to_string(),
            schedule_type: ScheduleType::Cron,
            schedule_value: "0 9 * * *".to_string(),
            status: TaskStatus::Active,
            next_run: None,
            context_mode: "group".to_string(),
            target_chat_jid: None,
        };

        let id = scheduler.schedule_task(task).await.unwrap();

        // Pause
        scheduler.pause_task(id).await.unwrap();
        let repo = TaskRepository::new(&db);
        let paused = repo.get_task(id).await.unwrap().unwrap();
        assert_eq!(paused.status, TaskStatus::Paused);

        // Resume
        scheduler.resume_task(id).await.unwrap();
        let resumed = repo.get_task(id).await.unwrap().unwrap();
        assert_eq!(resumed.status, TaskStatus::Active);
        assert!(resumed.next_run.is_some());
    }

    fn test_config() -> Config {
        let base = std::path::PathBuf::from("/tmp/ngb-sched-test");
        Config {
            project_name: "test".to_string(),
            version: "0.0.1".to_string(),
            debug: false,
            base_dir: base.clone(),
            data_dir: base.join("data"),
            store_dir: base.join("store"),
            groups_dir: base.join("groups"),
            workspaces_dir: base.join("workspaces"),
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
}
