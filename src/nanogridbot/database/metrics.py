"""Metrics database module for tracking usage statistics."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ContainerMetric(BaseModel):
    """Container execution metric."""

    id: int | None = None
    group_folder: str
    channel: str
    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: float | None = None
    status: str = "running"  # running, success, error, timeout
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    error: str | None = None


class RequestMetric(BaseModel):
    """Request statistics metric."""

    id: int | None = None
    channel: str
    group_folder: str | None
    timestamp: datetime
    request_type: str  # message, command, event
    success: bool
    error: str | None = None


async def init_metrics_db() -> None:
    """Initialize metrics tables."""
    from nanogridbot.database.connection import get_db_connection

    async with get_db_connection() as conn:
        # Container metrics table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS container_metrics (
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
            )
            """
        )

        # Request metrics table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS request_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                group_folder TEXT,
                timestamp TIMESTAMP NOT NULL,
                request_type TEXT NOT NULL,
                success INTEGER NOT NULL,
                error TEXT
            )
            """
        )

        # Create indexes
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_container_metrics_group ON container_metrics(group_folder)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_container_metrics_time ON container_metrics(start_time)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_request_metrics_channel ON request_metrics(channel)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_request_metrics_time ON request_metrics(timestamp)"
        )


async def record_container_start(
    group_folder: str,
    channel: str,
) -> int:
    """Record container execution start.

    Returns:
        Metric ID
    """
    from nanogridbot.database.connection import get_db_connection

    async with get_db_connection() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO container_metrics (group_folder, channel, start_time, status)
            VALUES (?, ?, ?, 'running')
            """,
            (group_folder, channel, datetime.now()),
        )
        await conn.commit()
        return cursor.lastrowid


async def record_container_end(
    metric_id: int,
    status: str,
    duration_seconds: float | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    error: str | None = None,
) -> None:
    """Record container execution end."""
    from nanogridbot.database.connection import get_db_connection

    total_tokens = None
    if prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens

    async with get_db_connection() as conn:
        await conn.execute(
            """
            UPDATE container_metrics
            SET end_time = ?, duration_seconds = ?, status = ?,
                prompt_tokens = ?, completion_tokens = ?, total_tokens = ?, error = ?
            WHERE id = ?
            """,
            (
                datetime.now(),
                duration_seconds,
                status,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                error,
                metric_id,
            ),
        )
        await conn.commit()


async def record_request(
    channel: str,
    request_type: str,
    success: bool,
    group_folder: str | None = None,
    error: str | None = None,
) -> None:
    """Record a request metric."""
    from nanogridbot.database.connection import get_db_connection

    async with get_db_connection() as conn:
        await conn.execute(
            """
            INSERT INTO request_metrics (channel, group_folder, timestamp, request_type, success, error)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (channel, group_folder, datetime.now(), request_type, 1 if success else 0, error),
        )
        await conn.commit()


async def get_container_stats(
    group_folder: str | None = None,
    days: int = 7,
) -> dict[str, Any]:
    """Get container execution statistics.

    Args:
        group_folder: Filter by group folder (optional)
        days: Number of days to look back

    Returns:
        Statistics dictionary
    """
    from nanogridbot.database.connection import get_db_connection

    since = datetime.now().timestamp() - (days * 24 * 60 * 60)

    query = """
        SELECT
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
    """

    params = [days]

    if group_folder:
        query += " AND group_folder = ?"
        params.append(group_folder)

    async with get_db_connection() as conn:
        async with conn.execute(query, params) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "total_runs": row[0] or 0,
                    "successful_runs": row[1] or 0,
                    "failed_runs": row[2] or 0,
                    "timeouts": row[3] or 0,
                    "avg_duration": round(row[4] or 0, 2),
                    "max_duration": row[5] or 0,
                    "min_duration": row[6] or 0,
                    "total_tokens": row[7] or 0,
                    "avg_tokens": round(row[8] or 0, 2),
                }
            return {
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "timeouts": 0,
                "avg_duration": 0,
                "max_duration": 0,
                "min_duration": 0,
                "total_tokens": 0,
                "avg_tokens": 0,
            }


async def get_request_stats(
    channel: str | None = None,
    days: int = 7,
) -> dict[str, Any]:
    """Get request statistics.

    Args:
        channel: Filter by channel (optional)
        days: Number of days to look back

    Returns:
        Statistics dictionary
    """
    from nanogridbot.database.connection import get_db_connection

    query = """
        SELECT
            COUNT(*) as total_requests,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_requests,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_requests,
            channel
        FROM request_metrics
        WHERE timestamp > datetime('now', '-' || ? || ' days')
    """

    params = [days]

    if channel:
        query += " AND channel = ?"
        params.append(channel)

    query += " GROUP BY channel"

    async with get_db_connection() as conn:
        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            result = {}
            for row in rows:
                result[row[3]] = {
                    "total_requests": row[0],
                    "successful_requests": row[1],
                    "failed_requests": row[2],
                }
            return result
