use chrono::{DateTime, Utc};

use ngb_types::{NanoGridBotError, Result, ScheduleType, ScheduledTask, TaskStatus};

use crate::connection::Database;

/// Repository for scheduled task storage and retrieval.
pub struct TaskRepository<'a> {
    db: &'a Database,
}

impl<'a> TaskRepository<'a> {
    pub fn new(db: &'a Database) -> Self {
        Self { db }
    }

    /// Save or update a task. Returns the task ID.
    pub async fn save_task(&self, task: &ScheduledTask) -> Result<i64> {
        let schedule_type = serde_json::to_value(task.schedule_type)
            .unwrap()
            .as_str()
            .unwrap_or("cron")
            .to_string();
        let status = serde_json::to_value(task.status)
            .unwrap()
            .as_str()
            .unwrap_or("active")
            .to_string();
        let next_run = task.next_run.map(|dt| dt.to_rfc3339());

        if task.id.is_none() {
            // Insert
            let result = sqlx::query(
                "INSERT INTO tasks
                 (group_folder, prompt, schedule_type, schedule_value, status, next_run, context_mode, target_chat_jid)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            )
            .bind(&task.group_folder)
            .bind(&task.prompt)
            .bind(&schedule_type)
            .bind(&task.schedule_value)
            .bind(&status)
            .bind(&next_run)
            .bind(&task.context_mode)
            .bind(&task.target_chat_jid)
            .execute(self.db.pool())
            .await
            .map_err(|e| NanoGridBotError::Database(format!("Insert task: {e}")))?;

            Ok(result.last_insert_rowid())
        } else {
            // Update
            sqlx::query(
                "UPDATE tasks
                 SET group_folder = ?, prompt = ?, schedule_type = ?, schedule_value = ?,
                     status = ?, next_run = ?, context_mode = ?, target_chat_jid = ?
                 WHERE id = ?",
            )
            .bind(&task.group_folder)
            .bind(&task.prompt)
            .bind(&schedule_type)
            .bind(&task.schedule_value)
            .bind(&status)
            .bind(&next_run)
            .bind(&task.context_mode)
            .bind(&task.target_chat_jid)
            .bind(task.id.unwrap())
            .execute(self.db.pool())
            .await
            .map_err(|e| NanoGridBotError::Database(format!("Update task: {e}")))?;

            Ok(task.id.unwrap())
        }
    }

    /// Get a task by ID.
    pub async fn get_task(&self, task_id: i64) -> Result<Option<ScheduledTask>> {
        let row: Option<TaskRow> = sqlx::query_as(
            "SELECT id, group_folder, prompt, schedule_type, schedule_value,
                    status, next_run, context_mode, target_chat_jid
             FROM tasks WHERE id = ?",
        )
        .bind(task_id)
        .fetch_optional(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Get task: {e}")))?;

        Ok(row.map(row_to_task))
    }

    /// Get all active tasks.
    pub async fn get_active(&self) -> Result<Vec<ScheduledTask>> {
        let rows: Vec<TaskRow> = sqlx::query_as(
            "SELECT id, group_folder, prompt, schedule_type, schedule_value,
                    status, next_run, context_mode, target_chat_jid
             FROM tasks WHERE status = 'active'
             ORDER BY next_run ASC",
        )
        .fetch_all(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Get active tasks: {e}")))?;

        Ok(rows.into_iter().map(row_to_task).collect())
    }

    /// Get all tasks.
    pub async fn get_all(&self) -> Result<Vec<ScheduledTask>> {
        let rows: Vec<TaskRow> = sqlx::query_as(
            "SELECT id, group_folder, prompt, schedule_type, schedule_value,
                    status, next_run, context_mode, target_chat_jid
             FROM tasks ORDER BY next_run ASC",
        )
        .fetch_all(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Get all tasks: {e}")))?;

        Ok(rows.into_iter().map(row_to_task).collect())
    }

    /// Get tasks by group folder.
    pub async fn get_by_group(&self, group_folder: &str) -> Result<Vec<ScheduledTask>> {
        let rows: Vec<TaskRow> = sqlx::query_as(
            "SELECT id, group_folder, prompt, schedule_type, schedule_value,
                    status, next_run, context_mode, target_chat_jid
             FROM tasks WHERE group_folder = ?
             ORDER BY next_run ASC",
        )
        .bind(group_folder)
        .fetch_all(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Get tasks by group: {e}")))?;

        Ok(rows.into_iter().map(row_to_task).collect())
    }

    /// Update task status.
    pub async fn update_status(&self, task_id: i64, status: TaskStatus) -> Result<bool> {
        let status_str = serde_json::to_value(status)
            .unwrap()
            .as_str()
            .unwrap_or("active")
            .to_string();

        let result = sqlx::query("UPDATE tasks SET status = ? WHERE id = ?")
            .bind(&status_str)
            .bind(task_id)
            .execute(self.db.pool())
            .await
            .map_err(|e| NanoGridBotError::Database(format!("Update task status: {e}")))?;

        Ok(result.rows_affected() > 0)
    }

    /// Update task next run time.
    pub async fn update_next_run(&self, task_id: i64, next_run: DateTime<Utc>) -> Result<bool> {
        let result = sqlx::query("UPDATE tasks SET next_run = ? WHERE id = ?")
            .bind(next_run.to_rfc3339())
            .bind(task_id)
            .execute(self.db.pool())
            .await
            .map_err(|e| NanoGridBotError::Database(format!("Update next run: {e}")))?;

        Ok(result.rows_affected() > 0)
    }

    /// Delete a task.
    pub async fn delete_task(&self, task_id: i64) -> Result<bool> {
        let result = sqlx::query("DELETE FROM tasks WHERE id = ?")
            .bind(task_id)
            .execute(self.db.pool())
            .await
            .map_err(|e| NanoGridBotError::Database(format!("Delete task: {e}")))?;

        Ok(result.rows_affected() > 0)
    }

    /// Get tasks that are due to run (active + next_run <= now).
    pub async fn get_due(&self) -> Result<Vec<ScheduledTask>> {
        let now = Utc::now().to_rfc3339();
        let rows: Vec<TaskRow> = sqlx::query_as(
            "SELECT id, group_folder, prompt, schedule_type, schedule_value,
                    status, next_run, context_mode, target_chat_jid
             FROM tasks
             WHERE status = 'active' AND next_run <= ?
             ORDER BY next_run ASC",
        )
        .bind(&now)
        .fetch_all(self.db.pool())
        .await
        .map_err(|e| NanoGridBotError::Database(format!("Get due tasks: {e}")))?;

        Ok(rows.into_iter().map(row_to_task).collect())
    }
}

#[derive(sqlx::FromRow)]
struct TaskRow {
    id: i64,
    group_folder: String,
    prompt: String,
    schedule_type: String,
    schedule_value: String,
    status: String,
    next_run: Option<String>,
    context_mode: String,
    target_chat_jid: Option<String>,
}

fn row_to_task(row: TaskRow) -> ScheduledTask {
    let schedule_type = match row.schedule_type.as_str() {
        "interval" => ScheduleType::Interval,
        "once" => ScheduleType::Once,
        _ => ScheduleType::Cron,
    };
    let status = match row.status.as_str() {
        "paused" => TaskStatus::Paused,
        "completed" => TaskStatus::Completed,
        _ => TaskStatus::Active,
    };
    let next_run = row
        .next_run
        .as_deref()
        .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
        .map(|dt| dt.with_timezone(&Utc));

    ScheduledTask {
        id: Some(row.id),
        group_folder: row.group_folder,
        prompt: row.prompt,
        schedule_type,
        schedule_value: row.schedule_value,
        status,
        next_run,
        context_mode: row.context_mode,
        target_chat_jid: row.target_chat_jid,
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

    fn make_task(folder: &str, prompt: &str) -> ScheduledTask {
        ScheduledTask {
            id: None,
            group_folder: folder.to_string(),
            prompt: prompt.to_string(),
            schedule_type: ScheduleType::Cron,
            schedule_value: "0 9 * * *".to_string(),
            status: TaskStatus::Active,
            next_run: Some(Utc::now()),
            context_mode: "group".to_string(),
            target_chat_jid: None,
        }
    }

    #[tokio::test]
    async fn save_and_get_task() {
        let db = setup().await;
        let repo = TaskRepository::new(&db);

        let task = make_task("test_group", "Run report");
        let id = repo.save_task(&task).await.unwrap();
        assert!(id > 0);

        let found = repo.get_task(id).await.unwrap().unwrap();
        assert_eq!(found.prompt, "Run report");
        assert_eq!(found.schedule_type, ScheduleType::Cron);
        assert_eq!(found.status, TaskStatus::Active);
    }

    #[tokio::test]
    async fn update_task() {
        let db = setup().await;
        let repo = TaskRepository::new(&db);

        let task = make_task("g1", "Old prompt");
        let id = repo.save_task(&task).await.unwrap();

        let mut updated = repo.get_task(id).await.unwrap().unwrap();
        updated.prompt = "New prompt".to_string();
        repo.save_task(&updated).await.unwrap();

        let found = repo.get_task(id).await.unwrap().unwrap();
        assert_eq!(found.prompt, "New prompt");
    }

    #[tokio::test]
    async fn get_active_tasks() {
        let db = setup().await;
        let repo = TaskRepository::new(&db);

        repo.save_task(&make_task("g1", "Task 1")).await.unwrap();

        let mut paused = make_task("g1", "Task 2");
        paused.status = TaskStatus::Paused;
        repo.save_task(&paused).await.unwrap();

        let active = repo.get_active().await.unwrap();
        assert_eq!(active.len(), 1);
        assert_eq!(active[0].prompt, "Task 1");
    }

    #[tokio::test]
    async fn update_status() {
        let db = setup().await;
        let repo = TaskRepository::new(&db);

        let id = repo.save_task(&make_task("g1", "T1")).await.unwrap();
        repo.update_status(id, TaskStatus::Paused).await.unwrap();

        let found = repo.get_task(id).await.unwrap().unwrap();
        assert_eq!(found.status, TaskStatus::Paused);
    }

    #[tokio::test]
    async fn update_next_run() {
        let db = setup().await;
        let repo = TaskRepository::new(&db);

        let id = repo.save_task(&make_task("g1", "T1")).await.unwrap();
        let new_time = Utc::now() + chrono::Duration::hours(1);
        repo.update_next_run(id, new_time).await.unwrap();

        let found = repo.get_task(id).await.unwrap().unwrap();
        assert!(found.next_run.is_some());
    }

    #[tokio::test]
    async fn delete_task() {
        let db = setup().await;
        let repo = TaskRepository::new(&db);

        let id = repo.save_task(&make_task("g1", "T1")).await.unwrap();
        assert!(repo.delete_task(id).await.unwrap());
        assert!(repo.get_task(id).await.unwrap().is_none());
    }

    #[tokio::test]
    async fn get_by_group() {
        let db = setup().await;
        let repo = TaskRepository::new(&db);

        repo.save_task(&make_task("g1", "T1")).await.unwrap();
        repo.save_task(&make_task("g1", "T2")).await.unwrap();
        repo.save_task(&make_task("g2", "T3")).await.unwrap();

        let g1_tasks = repo.get_by_group("g1").await.unwrap();
        assert_eq!(g1_tasks.len(), 2);
    }

    #[tokio::test]
    async fn get_due_tasks() {
        let db = setup().await;
        let repo = TaskRepository::new(&db);

        // Due task (past next_run)
        let mut due = make_task("g1", "Due");
        due.next_run = Some(Utc::now() - chrono::Duration::hours(1));
        repo.save_task(&due).await.unwrap();

        // Future task
        let mut future = make_task("g1", "Future");
        future.next_run = Some(Utc::now() + chrono::Duration::hours(1));
        repo.save_task(&future).await.unwrap();

        let due_tasks = repo.get_due().await.unwrap();
        assert_eq!(due_tasks.len(), 1);
        assert_eq!(due_tasks[0].prompt, "Due");
    }
}
