"""Task execution logging and history tracking."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class TaskExecutionStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskExecution(BaseModel):
    """Record of a task execution."""
    id: int | None = None
    task_id: int
    group_folder: str
    status: TaskExecutionStatus
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    result: str | None = None
    error_message: str | None = None
    session_id: str | None = None
    container_id: str | None = None


class TaskLog(BaseModel):
    """Task log entry for detailed tracking."""
    id: int | None = None
    execution_id: int
    timestamp: datetime
    level: str  # info, warning, error
    message: str
    metadata: dict[str, Any] = {}


class TaskStatistics(BaseModel):
    """Task execution statistics."""
    total_executions: int = 0
    success_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    timeout_count: int = 0
    avg_duration_seconds: float = 0
    min_duration_seconds: float | None = None
    max_duration_seconds: float | None = None
    last_execution: datetime | None = None


class TaskLogService:
    """Service for task execution logging and history."""

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def get_execution_log_path(self, execution_id: int) -> Path:
        """Get the log file path for an execution."""
        return self.log_dir / f"execution_{execution_id}.log"

    def get_execution_summary_path(self, group_folder: str) -> Path:
        """Get the summary JSON path for a group."""
        return self.log_dir / f"{group_folder}_summary.json"

    def log_execution_start(
        self,
        task_id: int,
        group_folder: str,
        session_id: str | None = None,
    ) -> int:
        """Log the start of a task execution."""
        import json

        summary_path = self.get_execution_summary_path(group_folder)
        summary = self._load_summary(summary_path)

        execution_id = summary["next_execution_id"]
        execution: dict[str, Any] = {
            "id": execution_id,
            "task_id": task_id,
            "group_folder": group_folder,
            "status": TaskExecutionStatus.PENDING.value,
            "started_at": datetime.now().isoformat(),
            "session_id": session_id,
        }
        summary["executions"].append(execution)
        summary["next_execution_id"] += 1
        summary["total_runs"] += 1

        self._save_summary(summary_path, summary)
        return execution_id

    def log_execution_end(
        self,
        execution_id: int,
        group_folder: str,
        status: TaskExecutionStatus,
        result: str | None = None,
        error_message: str | None = None,
        container_id: str | None = None,
    ) -> None:
        """Log the end of a task execution."""
        import json
        from pathlib import Path

        summary_path = self.get_execution_summary_path(group_folder)
        summary = self._load_summary(summary_path)

        finished_at = datetime.now()

        for exec_data in summary["executions"]:
            if exec_data["id"] == execution_id:
                exec_data["status"] = status.value
                exec_data["finished_at"] = finished_at.isoformat()

                if exec_data.get("started_at"):
                    started = datetime.fromisoformat(exec_data["started_at"])
                    duration = (finished_at - started).total_seconds()
                    exec_data["duration_seconds"] = duration

                if result:
                    exec_data["result"] = result
                if error_message:
                    exec_data["error_message"] = error_message
                if container_id:
                    exec_data["container_id"] = container_id
                break

        # Update statistics
        summary["stats"]["total_executions"] += 1
        if status == TaskExecutionStatus.SUCCESS:
            summary["stats"]["success_count"] += 1
        elif status == TaskExecutionStatus.FAILED:
            summary["stats"]["failed_count"] += 1
        elif status == TaskExecutionStatus.CANCELLED:
            summary["stats"]["cancelled_count"] += 1
        elif status == TaskExecutionStatus.TIMEOUT:
            summary["stats"]["timeout_count"] += 1

        summary["stats"]["last_execution"] = finished_at.isoformat()

        # Recalculate average duration
        durations = [
            e.get("duration_seconds")
            for e in summary["executions"]
            if e.get("duration_seconds") is not None
        ]
        if durations:
            summary["stats"]["avg_duration_seconds"] = sum(durations) / len(durations)
            summary["stats"]["min_duration_seconds"] = min(durations)
            summary["stats"]["max_duration_seconds"] = max(durations)

        self._save_summary(summary_path, summary)

        # Write detailed log file
        log_path = self.get_execution_log_path(execution_id)
        with open(log_path, "a") as f:
            f.write(f"[{finished_at.isoformat()}] Execution {status.value}\n")
            if result:
                f.write(f"Result: {result[:500]}\n")
            if error_message:
                f.write(f"Error: {error_message}\n")

    def get_executions(
        self,
        group_folder: str | None = None,
        limit: int = 50,
        status: TaskExecutionStatus | None = None,
    ) -> list[dict[str, Any]]:
        """Get task execution history."""
        if group_folder:
            summary_path = self.get_execution_summary_path(group_folder)
            if not summary_path.exists():
                return []
            summary = self._load_summary(summary_path)
            executions = summary.get("executions", [])

            if status:
                executions = [e for e in executions if e.get("status") == status.value]

            return sorted(executions, key=lambda x: x.get("started_at", ""), reverse=True)[:limit]

        # Aggregate from all groups
        all_executions = []
        for path in self.log_dir.glob("*_summary.json"):
            try:
                summary = self._load_summary(path)
                all_executions.extend(summary.get("executions", []))
            except Exception:
                continue

        all_executions.sort(key=lambda x: x.get("started_at", ""), reverse=True)

        if status:
            all_executions = [e for e in all_executions if e.get("status") == status.value]

        return all_executions[:limit]

    def get_statistics(self, group_folder: str) -> TaskStatistics:
        """Get task execution statistics for a group."""
        summary_path = self.get_execution_summary_path(group_folder)
        if not summary_path.exists():
            return TaskStatistics()

        summary = self._load_summary(summary_path)
        stats = summary.get("stats", {})

        last_execution = None
        if stats.get("last_execution"):
            last_execution = datetime.fromisoformat(stats["last_execution"])

        return TaskStatistics(
            total_executions=stats.get("total_executions", 0),
            success_count=stats.get("success_count", 0),
            failed_count=stats.get("failed_count", 0),
            cancelled_count=stats.get("cancelled_count", 0),
            timeout_count=stats.get("timeout_count", 0),
            avg_duration_seconds=stats.get("avg_duration_seconds", 0),
            min_duration_seconds=stats.get("min_duration_seconds"),
            max_duration_seconds=stats.get("max_duration_seconds"),
            last_execution=last_execution,
        )

    def get_execution_detail(self, execution_id: int) -> dict[str, Any] | None:
        """Get detailed information about a specific execution."""
        # Search all summary files
        for path in self.log_dir.glob("*_summary.json"):
            try:
                summary = self._load_summary(path)
                for exec_data in summary.get("executions", []):
                    if exec_data.get("id") == execution_id:
                        return exec_data
            except Exception:
                continue
        return None

    def clear_old_executions(self, group_folder: str, keep_last: int = 100) -> int:
        """Clear old execution records, keeping only the most recent."""
        summary_path = self.get_execution_summary_path(group_folder)
        if not summary_path.exists():
            return 0

        summary = self._load_summary(summary_path)
        executions = summary.get("executions", [])

        if len(executions) <= keep_last:
            return 0

        # Keep only the most recent executions
        sorted_executions = sorted(executions, key=lambda x: x.get("started_at", ""), reverse=True)
        summary["executions"] = sorted_executions[:keep_last]

        self._save_summary(summary_path, summary)
        return len(executions) - keep_last

    def _load_summary(self, path: Path) -> dict[str, Any]:
        """Load summary JSON from file."""
        import json

        if path.exists():
            with open(path) as f:
                return json.load(f)

        return {
            "next_execution_id": 1,
            "total_runs": 0,
            "executions": [],
            "stats": {
                "total_executions": 0,
                "success_count": 0,
                "failed_count": 0,
                "cancelled_count": 0,
                "timeout_count": 0,
            },
        }

    def _save_summary(self, path: Path, summary: dict[str, Any]) -> None:
        """Save summary JSON to file."""
        import json

        with open(path, "w") as f:
            json.dump(summary, f, indent=2)


def create_task_log_service() -> TaskLogService:
    """Create a task log service instance."""
    from nanogridbot.config import get_config

    config = get_config()
    log_dir = config.store_dir / "task_logs"
    return TaskLogService(log_dir)
