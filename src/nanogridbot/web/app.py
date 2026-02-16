"""FastAPI application for NanoGridBot web monitoring panel."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from loguru import logger
from pydantic import BaseModel


# ============================================================================
# Response Models
# ============================================================================


class GroupResponse(BaseModel):
    """Response model for a registered group."""

    jid: str
    name: str
    folder: str
    active: bool
    trigger_pattern: str | None
    requires_trigger: bool


class TaskResponse(BaseModel):
    """Response model for a scheduled task."""

    id: int | None
    group_folder: str
    prompt: str
    schedule_type: str
    schedule_value: str
    status: str
    next_run: str | None
    context_mode: str


class MessageResponse(BaseModel):
    """Response model for a chat message."""

    id: str
    chat_jid: str
    sender: str
    sender_name: str | None
    content: str
    timestamp: str | None
    is_from_me: bool


class HealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    timestamp: str
    version: str


class ChannelStatus(BaseModel):
    """Response model for a single channel's connection status."""

    name: str
    connected: bool


class MetricsResponse(BaseModel):
    """Response model for system metrics."""

    active_containers: int
    registered_groups: int
    active_tasks: int
    connected_channels: int
    total_channels: int
    channels: list[ChannelStatus]


class WebState:
    """Web application state container."""

    def __init__(self):
        self.orchestrator = None
        self.db = None


web_state = WebState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("NanoGridBot Web Dashboard starting...")

    # Initialize metrics database
    try:
        from nanogridbot.database import metrics

        await metrics.init_metrics_db()
        logger.info("Metrics database initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize metrics database: {e}")

    yield
    logger.info("NanoGridBot Web Dashboard shutting down...")


app = FastAPI(
    title="NanoGridBot Dashboard",
    description="Web monitoring panel for NanoGridBot",
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "groups", "description": "Registered group management"},
        {"name": "tasks", "description": "Scheduled task management"},
        {"name": "messages", "description": "Chat message retrieval"},
        {"name": "health", "description": "Health checks and system metrics"},
        {"name": "metrics", "description": "Extended metrics and analytics"},
    ],
)


def set_orchestrator(orchestrator: Any) -> None:
    """Set the orchestrator instance for the web app."""
    web_state.orchestrator = orchestrator
    web_state.db = orchestrator.db if orchestrator else None


def create_app(orchestrator: Any = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if orchestrator:
        set_orchestrator(orchestrator)
    return app


def get_app() -> FastAPI:
    """Get the FastAPI application instance."""
    return app


# ============================================================================
# Dashboard Pages
# ============================================================================


@app.get("/")
async def root() -> HTMLResponse:
    """Serve the main dashboard page."""
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NanoGridBot Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.prod.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js"></script>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background-color: #f5f5f5; }
            .navbar { box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .card { box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; }
            .status-indicator {
                display: inline-block;
                width: 10px;
                height: 10px;
                border-radius: 50%;
                margin-right: 5px;
            }
            .status-active { background-color: #28a745; }
            .status-inactive { background-color: #6c757d; }
            .status-error { background-color: #dc3545; }
            .metric-value { font-size: 2rem; font-weight: bold; }
            .metric-label { color: #6c757d; font-size: 0.875rem; }
            .log-output {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Monaco', 'Menlo', monospace;
                font-size: 0.75rem;
                padding: 10px;
                border-radius: 4px;
                max-height: 300px;
                overflow-y: auto;
            }
            [v-cloak] { display: none; }
        </style>
    </head>
    <body>
        <div id="app" v-cloak>
            <!-- Navigation -->
            <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
                <div class="container-fluid">
                    <a class="navbar-brand" href="/">🤖 NanoGridBot</a>
                    <span class="navbar-text text-muted">v{{ version }}</span>
                </div>
            </nav>

            <div class="container-fluid mt-4">
                <!-- Status Overview -->
                <div class="row">
                    <div class="col-md-3">
                        <div class="card">
                            <div class="card-body">
                                <div class="metric-label">Active Containers</div>
                                <div class="metric-value text-primary">{{ metrics.active_containers }}</div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card">
                            <div class="card-body">
                                <div class="metric-label">Registered Groups</div>
                                <div class="metric-value text-info">{{ metrics.registered_groups }}</div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card">
                            <div class="card-body">
                                <div class="metric-label">Active Tasks</div>
                                <div class="metric-value text-warning">{{ metrics.active_tasks }}</div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card">
                            <div class="card-body">
                                <div class="metric-label">Channels</div>
                                <div class="metric-value text-success">{{ metrics.connected_channels }}/{{ metrics.total_channels }}</div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row mt-4">
                    <!-- Groups Panel -->
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h5 class="mb-0">📂 Groups</h5>
                                <button class="btn btn-sm btn-outline-primary" @click="refreshGroups">Refresh</button>
                            </div>
                            <div class="card-body">
                                <div v-if="groups.length === 0" class="text-muted text-center py-4">
                                    No registered groups
                                </div>
                                <div v-else class="list-group">
                                    <div v-for="group in groups" :key="group.jid" class="list-group-item">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <div>
                                                <strong>{{ group.name }}</strong>
                                                <br><small class="text-muted">{{ group.jid }}</small>
                                            </div>
                                            <span :class="'status-indicator status-' + (group.active ? 'active' : 'inactive')"></span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Tasks Panel -->
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h5 class="mb-0">📅 Scheduled Tasks</h5>
                                <button class="btn btn-sm btn-outline-primary" @click="refreshTasks">Refresh</button>
                            </div>
                            <div class="card-body">
                                <div v-if="tasks.length === 0" class="text-muted text-center py-4">
                                    No scheduled tasks
                                </div>
                                <div v-else class="list-group">
                                    <div v-for="task in tasks" :key="task.id" class="list-group-item">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <div>
                                                <strong>{{ task.prompt.substring(0, 50) }}...</strong>
                                                <br><small class="text-muted">{{ task.schedule_type }}: {{ task.schedule_value }}</small>
                                            </div>
                                            <span :class="'badge bg-' + (task.status === 'active' ? 'success' : 'secondary')">
                                                {{ task.status }}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Channel Status -->
                <div class="row mt-4">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header">
                                <h5 class="mb-0">🔌 Channel Status</h5>
                            </div>
                            <div class="card-body">
                                <div class="row">
                                    <div v-for="channel in channels" :key="channel.name" class="col-md-2 col-sm-4 text-center">
                                        <div :class="'status-indicator status-' + (channel.connected ? 'active' : 'inactive') + ' mb-2'" style="width: 20px; height: 20px;"></div>
                                        <div><strong>{{ channel.name }}</strong></div>
                                        <small class="text-muted">{{ channel.connected ? 'Connected' : 'Disconnected' }}</small>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- System Logs -->
                <div class="row mt-4">
                    <div class="col-12">
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h5 class="mb-0">📋 System Logs</h5>
                                <span class="text-muted">Last updated: {{ lastUpdate }}</span>
                            </div>
                            <div class="card-body">
                                <div class="log-output">{{ systemLogs }}</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            const { createApp } = Vue;

            createApp({
                data() {
                    return {
                        version: '0.1.0-alpha',
                        groups: [],
                        tasks: [],
                        channels: [],
                        metrics: {
                            active_containers: 0,
                            registered_groups: 0,
                            active_tasks: 0,
                            connected_channels: 0,
                            total_channels: 0,
                        },
                        systemLogs: 'Connecting to WebSocket...',
                        lastUpdate: '-',
                        ws: null,
                    };
                },
                mounted() {
                    this.connectWebSocket();
                    this.refreshAll();
                },
                beforeUnmount() {
                    if (this.ws) {
                        this.ws.close();
                    }
                },
                methods: {
                    connectWebSocket() {
                        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                        this.ws = new WebSocket(protocol + '//' + window.location.host + '/ws');

                        this.ws.onmessage = (event) => {
                            const data = JSON.parse(event.data);
                            this.groups = data.groups || [];
                            this.tasks = data.tasks || [];
                            this.channels = data.channels || [];
                            this.metrics = data.metrics || this.metrics;
                            this.lastUpdate = new Date().toLocaleTimeString();
                        };

                        this.ws.onerror = (error) => {
                            console.error('WebSocket error:', error);
                            this.systemLogs = 'WebSocket connection error. Reconnecting...';
                        };

                        this.ws.onclose = () => {
                            this.systemLogs = 'WebSocket disconnected. Reconnecting...';
                            setTimeout(() => this.connectWebSocket(), 3000);
                        };
                    },
                    async refreshAll() {
                        await Promise.all([
                            this.refreshGroups(),
                            this.refreshTasks(),
                            this.refreshMetrics(),
                        ]);
                    },
                    async refreshGroups() {
                        try {
                            const response = await axios.get('/api/groups');
                            this.groups = response.data;
                        } catch (error) {
                            console.error('Failed to fetch groups:', error);
                        }
                    },
                    async refreshTasks() {
                        try {
                            const response = await axios.get('/api/tasks');
                            this.tasks = response.data;
                        } catch (error) {
                            console.error('Failed to fetch tasks:', error);
                        }
                    },
                    async refreshMetrics() {
                        try {
                            const response = await axios.get('/api/health/metrics');
                            this.metrics = response.data;
                            this.channels = response.data.channels || [];
                        } catch (error) {
                            console.error('Failed to fetch metrics:', error);
                        }
                    },
                },
            }).mount('#app');
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)


# ============================================================================
# API Endpoints
# ============================================================================


@app.get(
    "/api/groups",
    response_model=list[GroupResponse],
    tags=["groups"],
    summary="List registered groups",
    description="Returns all registered groups with their current active status.",
)
async def get_groups():
    """Get list of registered groups."""
    if not web_state.orchestrator:
        return []

    registered_groups = web_state.orchestrator.registered_groups
    queue_states = (
        web_state.orchestrator.queue.states if hasattr(web_state.orchestrator, "queue") else {}
    )

    return [
        {
            "jid": jid,
            "name": group.name,
            "folder": group.folder,
            "active": (
                queue_states.get(jid, {}).get("active", False)
                if isinstance(queue_states.get(jid), dict)
                else False
            ),
            "trigger_pattern": group.trigger_pattern,
            "requires_trigger": group.requires_trigger,
        }
        for jid, group in registered_groups.items()
    ]


@app.get(
    "/api/tasks",
    response_model=list[TaskResponse],
    tags=["tasks"],
    summary="List scheduled tasks",
    description="Returns all active scheduled tasks with their configuration and next run time.",
)
async def get_tasks():
    """Get list of scheduled tasks."""
    if not web_state.db:
        return []

    try:
        task_repo = web_state.db.get_task_repository()
        tasks = await task_repo.get_active_tasks()
        return [
            {
                "id": task.id,
                "group_folder": task.group_folder,
                "prompt": task.prompt,
                "schedule_type": task.schedule_type,
                "schedule_value": task.schedule_value,
                "status": task.status,
                "next_run": task.next_run.isoformat() if task.next_run else None,
                "context_mode": task.context_mode,
            }
            for task in tasks
        ]
    except Exception:
        return []


@app.get(
    "/api/messages",
    response_model=list[MessageResponse],
    tags=["messages"],
    summary="List recent messages",
    description="Returns recent chat messages, optionally filtered by chat JID.",
)
async def get_messages(
    limit: int = Query(default=50, description="Maximum number of messages to return"),
    chat_jid: str | None = Query(default=None, description="Filter messages by chat JID"),
):
    """Get recent messages."""
    if not web_state.db:
        return []

    try:
        message_repo = web_state.db.get_message_repository()
        if chat_jid:
            messages = await message_repo.get_recent_messages(chat_jid, limit)
        else:
            messages = await message_repo.get_new_messages(None)

        return [
            {
                "id": msg.id,
                "chat_jid": msg.chat_jid,
                "sender": msg.sender,
                "sender_name": msg.sender_name,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                "is_from_me": msg.is_from_me,
            }
            for msg in messages[:limit]
        ]
    except Exception:
        return []


# ============================================================================
# Health & Metrics
# ============================================================================


@app.get(
    "/api/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health check",
    description="Returns the current health status, timestamp, and version of the service.",
)
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "0.1.0",
    }


@app.get(
    "/api/health/metrics",
    response_model=MetricsResponse,
    tags=["health"],
    summary="System metrics",
    description="Returns system metrics including container, group, task, and channel counts.",
)
async def get_metrics():
    """Get system metrics."""
    orchestrator = web_state.orchestrator

    if not orchestrator:
        return {
            "active_containers": 0,
            "registered_groups": 0,
            "active_tasks": 0,
            "connected_channels": 0,
            "total_channels": 0,
            "channels": [],
        }

    # Get channel status
    channels = []
    connected_count = 0
    if hasattr(orchestrator, "channels"):
        for ch in orchestrator.channels:
            connected = ch.is_connected() if hasattr(ch, "is_connected") else False
            if connected:
                connected_count += 1
            channels.append(
                {
                    "name": ch.name if hasattr(ch, "name") else "unknown",
                    "connected": connected,
                }
            )

    # Get active tasks count
    active_tasks = 0
    if web_state.db:
        try:
            task_repo = web_state.db.get_task_repository()
            tasks = await task_repo.get_active_tasks()
            active_tasks = len(tasks)
        except Exception:
            pass

    # Get queue stats
    active_containers = 0
    if hasattr(orchestrator, "queue"):
        active_containers = orchestrator.queue.active_count

    return {
        "active_containers": active_containers,
        "registered_groups": (
            len(orchestrator.registered_groups) if hasattr(orchestrator, "registered_groups") else 0
        ),
        "active_tasks": active_tasks,
        "connected_channels": connected_count,
        "total_channels": len(channels),
        "channels": channels,
    }


# ============================================================================
# Extended Metrics API
# ============================================================================


@app.get(
    "/api/metrics/containers",
    tags=["metrics"],
    summary="Container execution metrics",
    description="Returns detailed container execution statistics including token usage and duration.",
)
async def get_container_metrics(
    group: str | None = Query(None, description="Filter by group folder"),
    days: int = Query(7, description="Number of days to look back", ge=1, le=90),
):
    """Get container execution metrics."""
    try:
        from nanogridbot.database import metrics

        stats = await metrics.get_container_stats(group_folder=group, days=days)
        return stats
    except Exception as e:
        logger.error(f"Error getting container metrics: {e}")
        return {"error": str(e)}


@app.get(
    "/api/metrics/requests",
    tags=["metrics"],
    summary="Request metrics",
    description="Returns request statistics grouped by channel.",
)
async def get_request_metrics(
    channel: str | None = Query(None, description="Filter by channel"),
    days: int = Query(7, description="Number of days to look back", ge=1, le=90),
):
    """Get request statistics."""
    try:
        from nanogridbot.database import metrics

        stats = await metrics.get_request_stats(channel=channel, days=days)
        return stats
    except Exception as e:
        logger.error(f"Error getting request metrics: {e}")
        return {"error": str(e)}


# ============================================================================
# WebSocket
# ============================================================================


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()

    try:
        while True:
            # Gather all data
            groups_data = await get_groups()
            tasks_data = await get_tasks()
            metrics_data = await get_metrics()

            # Send update
            await websocket.send_json(
                {
                    "groups": groups_data,
                    "tasks": tasks_data,
                    "channels": metrics_data.get("channels", []),
                    "metrics": metrics_data,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Wait before next update
            await asyncio.sleep(2)

    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await websocket.close()
