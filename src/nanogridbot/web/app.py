"""FastAPI application for NanoGridBot web monitoring panel."""

import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse, JSONResponse
from loguru import logger
from pydantic import BaseModel, Field

from nanogridbot.auth import (
    InviteCodeManager,
    LoginLockManager,
    PasswordManager,
    SessionManager,
    get_current_user,
    require_permission,
    require_role,
)
from nanogridbot.auth.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    InviteCodeError,
    LoginLockedError,
    UserExistsError,
)
from nanogridbot.types import (
    AuditEventType,
    ChannelType,
    InviteCodeCreate,
    Permission,
    User,
    UserChannelConfig,
    UserChannelConfigUpdate,
    UserCreate,
    UserLogin,
    UserResponse,
    UserRole,
)


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


class GroupCreateRequest(BaseModel):
    """Request model for creating a group."""

    name: str
    folder: str | None = None
    trigger_pattern: str | None = None
    requires_trigger: bool = True
    execution_mode: str = "container"
    custom_cwd: str | None = None


class GroupUpdateRequest(BaseModel):
    """Request model for updating a group."""

    name: str | None = None
    trigger_pattern: str | None = None
    requires_trigger: bool | None = None


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

    # Set up auth dependencies if database is available
    if web_state.db:
        from nanogridbot.auth.dependencies import set_database
        from nanogridbot.auth.session import SessionManager

        set_database(web_state.db)
        session_mgr_instance = SessionManager(web_state.db)
        set_session_manager(session_mgr_instance)
        logger.info("Authentication system initialized")

        # Create default admin user if configured and no users exist
        from nanogridbot.config import Config
        from nanogridbot.database.users import UserRepository

        config = Config()
        if config.default_admin_username and config.default_admin_password:
            user_repo = UserRepository(web_state.db)
            users = await user_repo.list_users(limit=1)
            if not users:
                from nanogridbot.auth.password import PasswordManager

                pw_mgr = PasswordManager()
                password_hash = pw_mgr.hash_password(config.default_admin_password)
                user_id = await user_repo.create_user(
                    username=config.default_admin_username,
                    email=None,
                    password_hash=password_hash,
                )
                # Assign owner role
                await user_repo.update_user(user_id, role="owner")
                logger.info(f"Default admin user '{config.default_admin_username}' created")

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
        {"name": "auth", "description": "Authentication and user management"},
        {"name": "audit", "description": "Audit log and security events"},
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
    "/api/user/groups",
    response_model=list[GroupResponse],
    tags=["user"],
    summary="List user's groups",
    description="Returns groups owned by the current user.",
)
async def get_user_groups(
    user: User = Depends(get_current_user),
):
    """Get list of groups owned by the current user."""
    if not web_state.db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    group_repo = web_state.db.get_group_repository()
    user_groups = await group_repo.get_groups_by_user(user.id)

    # Get queue states from orchestrator
    queue_states = (
        web_state.orchestrator.queue.states if hasattr(web_state.orchestrator, "queue") else {}
    )

    return [
        {
            "jid": group.jid,
            "name": group.name,
            "folder": group.folder,
            "active": (
                queue_states.get(group.jid, {}).get("active", False)
                if isinstance(queue_states.get(group.jid), dict)
                else False
            ),
            "trigger_pattern": group.trigger_pattern,
            "requires_trigger": group.requires_trigger,
        }
        for group in user_groups
    ]


@app.post(
    "/api/groups",
    response_model=GroupResponse,
    tags=["groups"],
    summary="Create a new group",
    description="Register a new group/chat with the system.",
)
async def create_group(
    request: GroupCreateRequest,
    user: User = Depends(get_current_user),
):
    """Create a new group."""
    if not web_state.orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not available",
        )

    # Generate jid if not provided, use folder as identifier
    folder = request.folder or request.name.lower().replace(" ", "-")
    jid = f"group:{folder}"

    # Check if group already exists
    if jid in web_state.orchestrator.registered_groups:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Group with folder '{folder}' already exists",
        )

    # Create group directory if needed
    import os
    group_dir = Path("groups") / folder
    try:
        group_dir.mkdir(parents=True, exist_ok=True)
        config_file = group_dir / "config.json"
        if not config_file.exists():
            config_file.write_text("{}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create group directory: {str(e)}",
        )

    # Register group in orchestrator
    from nanogridbot.types import RegisteredGroup, ContainerConfig

    container_config = ContainerConfig()
    if request.execution_mode == "host":
        container_config = ContainerConfig(
            additional_mounts=[],
            timeout=request.timeout if hasattr(request, "timeout") else None,
        )

    group = RegisteredGroup(
        jid=jid,
        name=request.name,
        folder=folder,
        user_id=user.id,
        trigger_pattern=request.trigger_pattern,
        container_config=container_config.model_dump() if container_config else None,
        requires_trigger=request.requires_trigger,
    )

    # Save to database and register in orchestrator
    if web_state.db:
        group_repo = web_state.db.get_group_repository()
        await group_repo.save_group(group)

    web_state.orchestrator.registered_groups[jid] = group

    return {
        "success": True,
        "jid": group.jid,
        "group": {
            "jid": group.jid,
            "name": group.name,
            "folder": group.folder,
            "active": False,
            "trigger_pattern": group.trigger_pattern,
            "requires_trigger": group.requires_trigger,
        },
    }


@app.patch(
    "/api/groups/{jid}",
    response_model=GroupResponse,
    tags=["groups"],
    summary="Update a group",
    description="Update group configuration.",
)
async def update_group(
    jid: str,
    request: GroupUpdateRequest,
    user: User = Depends(get_current_user),
):
    """Update a group."""
    if not web_state.orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not available",
        )

    # URL decode jid
    import urllib.parse
    jid = urllib.parse.unquote(jid)

    # Check if group exists
    if jid not in web_state.orchestrator.registered_groups:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group '{jid}' not found",
        )

    group = web_state.orchestrator.registered_groups[jid]

    # Update fields
    if request.name is not None:
        group.name = request.name
    if request.trigger_pattern is not None:
        group.trigger_pattern = request.trigger_pattern
    if request.requires_trigger is not None:
        group.requires_trigger = request.requires_trigger

    # Save to database
    if web_state.db:
        group_repo = web_state.db.get_group_repository()
        await group_repo.save_group(group)

    # Get active status
    queue_states = (
        web_state.orchestrator.queue.states if hasattr(web_state.orchestrator, "queue") else {}
    )
    active = (
        queue_states.get(jid, {}).get("active", False)
        if isinstance(queue_states.get(jid), dict)
        else False
    )

    return {
        "jid": group.jid,
        "name": group.name,
        "folder": group.folder,
        "active": active,
        "trigger_pattern": group.trigger_pattern,
        "requires_trigger": group.requires_trigger,
    }


@app.delete(
    "/api/groups/{jid}",
    tags=["groups"],
    summary="Delete a group",
    description="Unregister and delete a group.",
)
async def delete_group(
    jid: str,
    user: User = Depends(get_current_user),
):
    """Delete a group."""
    if not web_state.orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not available",
        )

    # URL decode jid
    import urllib.parse
    jid = urllib.parse.unquote(jid)

    # Check if group exists
    if jid not in web_state.orchestrator.registered_groups:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group '{jid}' not found",
        )

    # Remove from orchestrator
    del web_state.orchestrator.registered_groups[jid]

    # Remove from database
    if web_state.db:
        group_repo = web_state.db.get_group_repository()
        await group_repo.delete_group(jid)

    return {"success": True}


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


class TaskCreateRequest(BaseModel):
    """Request model for creating a task."""

    group_folder: str
    chat_jid: str
    prompt: str
    schedule_type: str
    schedule_value: str
    context_mode: str = "group"


class TaskUpdateRequest(BaseModel):
    """Request model for updating a task."""

    status: str | None = None
    schedule_type: str | None = None
    schedule_value: str | None = None


@app.post(
    "/api/tasks",
    response_model=TaskResponse,
    tags=["tasks"],
    summary="Create a new task",
    description="Create a new scheduled task.",
)
async def create_task(
    request: TaskCreateRequest,
    user: User = Depends(get_current_user),
):
    """Create a new scheduled task."""
    if not web_state.db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    from nanogridbot.types import ScheduledTask, TaskStatus
    from nanogridbot.database.tasks import TaskRepository

    # Parse schedule value
    schedule_value = request.schedule_value
    next_run = None
    if request.schedule_type == "once":
        try:
            next_run = datetime.fromisoformat(schedule_value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid schedule_value for 'once' type. Use ISO format.",
            )
    elif request.schedule_type in ("cron", "interval"):
        # Validate cron/interval format
        pass

    task = ScheduledTask(
        id=None,
        group_folder=request.group_folder,
        chat_jid=request.chat_jid,
        prompt=request.prompt,
        schedule_type=request.schedule_type,
        schedule_value=request.schedule_value,
        status=TaskStatus.PENDING,
        next_run=next_run,
        context_mode=request.context_mode,
    )

    task_repo = web_state.db.get_task_repository()
    task_id = await task_repo.save_task(task)

    return {
        "id": task_id,
        "group_folder": task.group_folder,
        "prompt": task.prompt,
        "schedule_type": task.schedule_type,
        "schedule_value": task.schedule_value,
        "status": task.status.value,
        "next_run": next_run.isoformat() if next_run else None,
        "context_mode": task.context_mode,
    }


@app.patch(
    "/api/tasks/{task_id}",
    response_model=TaskResponse,
    tags=["tasks"],
    summary="Update a task",
    description="Update task configuration.",
)
async def update_task(
    task_id: int,
    request: TaskUpdateRequest,
    user: User = Depends(get_current_user),
):
    """Update a task."""
    if not web_state.db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    task_repo = web_state.db.get_task_repository()
    task = await task_repo.get_task(task_id)

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    # Update fields
    if request.status:
        from nanogridbot.types import TaskStatus
        task.status = TaskStatus(request.status)
    if request.schedule_type:
        task.schedule_type = request.schedule_type
    if request.schedule_value:
        task.schedule_value = request.schedule_value

    await task_repo.save_task(task)

    return {
        "id": task.id,
        "group_folder": task.group_folder,
        "prompt": task.prompt,
        "schedule_type": task.schedule_type,
        "schedule_value": task.schedule_value,
        "status": task.status.value,
        "next_run": task.next_run.isoformat() if task.next_run else None,
        "context_mode": task.context_mode,
    }


@app.delete(
    "/api/tasks/{task_id}",
    tags=["tasks"],
    summary="Delete a task",
    description="Delete a scheduled task.",
)
async def delete_task(
    task_id: int,
    user: User = Depends(get_current_user),
):
    """Delete a task."""
    if not web_state.db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    task_repo = web_state.db.get_task_repository()
    success = await task_repo.delete_task(task_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    return {"success": True}


@app.get(
    "/api/tasks/{task_id}/logs",
    tags=["tasks"],
    summary="Get task execution logs",
    description="Get execution logs for a task.",
)
async def get_task_logs(
    task_id: int,
    user: User = Depends(get_current_user),
):
    """Get task execution logs."""
    # Get task to find group_folder
    if not web_state.db:
        return {"logs": []}

    task_repo = web_state.db.get_task_repository()
    task = await task_repo.get_task(task_id)

    if not task:
        return {"logs": []}

    # Use task_logging to get execution logs
    if hasattr(web_state, "task_log_service") and web_state.task_log_service:
        try:
            executions = web_state.task_log_service.get_executions(task.group_folder)
            logs = [
                {
                    "id": exec.get("execution_id"),
                    "task_id": task_id,
                    "run_at": exec.get("start_time"),
                    "duration_ms": exec.get("duration_ms", 0),
                    "status": exec.get("status", "unknown"),
                    "result": exec.get("result"),
                    "error": exec.get("error"),
                }
                for exec in executions
            ]
            return {"logs": logs}
        except Exception:
            pass

    return {"logs": []}


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


@app.get(
    "/api/groups/{jid}/messages",
    tags=["messages"],
    summary="Get messages for a group",
    description="Returns messages for a specific group, with pagination support.",
)
async def get_group_messages(
    jid: str,
    limit: int = Query(default=50, description="Maximum number of messages"),
    before: str | None = Query(default=None, description="Return messages before this timestamp"),
    after: str | None = Query(default=None, description="Return messages after this timestamp"),
):
    """Get messages for a specific group."""
    if not web_state.db:
        return {"messages": [], "hasMore": False}

    import urllib.parse
    jid = urllib.parse.unquote(jid)

    try:
        message_repo = web_state.db.get_message_repository()
        messages = await message_repo.get_recent_messages(jid, limit + 1)

        # Filter by timestamp if provided
        if before:
            before_ts = datetime.fromisoformat(before)
            messages = [m for m in messages if m.timestamp and m.timestamp < before_ts]
        if after:
            after_ts = datetime.fromisoformat(after)
            messages = [m for m in messages if m.timestamp and m.timestamp > after_ts]

        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]

        return {
            "messages": [
                {
                    "id": msg.id,
                    "chat_jid": msg.chat_jid,
                    "sender": msg.sender,
                    "sender_name": msg.sender_name,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                    "is_from_me": msg.is_from_me,
                }
                for msg in messages
            ],
            "hasMore": has_more,
        }
    except Exception:
        return {"messages": [], "hasMore": False}


class MessageSendRequest(BaseModel):
    """Request model for sending a message."""

    chatJid: str
    content: str
    attachments: list[dict[str, str]] | None = None


@app.post(
    "/api/messages",
    tags=["messages"],
    summary="Send a message",
    description="Send a message to a group.",
)
async def send_message(
    request: MessageSendRequest,
    user: User = Depends(get_current_user),
):
    """Send a message to a group."""
    if not web_state.orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not available",
        )

    # Store message in database
    if web_state.db:
        message_repo = web_state.db.get_message_repository()
        from nanogridbot.types import Message
        msg = Message(
            id=f"msg_{datetime.now().timestamp()}",
            chat_jid=request.chatJid,
            sender=str(user.id),
            sender_name=user.username,
            content=request.content,
            timestamp=datetime.now(),
            is_from_me=False,
        )
        await message_repo.store_message(msg)

    # Queue the message for processing
    from nanogridbot.types import Message as QueueMessage
    queue_msg = QueueMessage(
        id=msg.id,
        chat_jid=request.chatJid,
        sender=str(user.id),
        sender_name=user.username,
        content=request.content,
        timestamp=datetime.now(),
        is_from_me=False,
    )

    if hasattr(web_state.orchestrator, "queue"):
        await web_state.orchestrator.queue.enqueue(request.chatJid, queue_msg)

    return {
        "success": True,
        "messageId": msg.id,
        "timestamp": msg.timestamp.isoformat(),
    }


@app.post(
    "/api/groups/{jid}/stop",
    tags=["groups"],
    summary="Stop group processing",
    description="Stop any running agent for this group.",
)
async def stop_group(jid: str):
    """Stop group processing."""
    if not web_state.orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not available",
        )

    import urllib.parse
    jid = urllib.parse.unquote(jid)

    # Try to stop via queue
    if hasattr(web_state.orchestrator, "queue"):
        await web_state.orchestrator.queue.stop(jid)

    return {"success": True}


@app.post(
    "/api/groups/{jid}/interrupt",
    tags=["groups"],
    summary="Interrupt group processing",
    description="Interrupt any running agent for this group.",
)
async def interrupt_group(jid: str):
    """Interrupt group processing."""
    if not web_state.orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not available",
        )

    import urllib.parse
    jid = urllib.parse.unquote(jid)

    interrupted = False
    # Try to interrupt via queue
    if hasattr(web_state.orchestrator, "queue"):
        interrupted = await web_state.orchestrator.queue.interrupt(jid)

    return {"success": True, "interrupted": interrupted}


@app.post(
    "/api/groups/{jid}/reset-session",
    tags=["groups"],
    summary="Reset group session",
    description="Reset the conversation session for this group.",
)
async def reset_group_session(jid: str):
    """Reset group session."""
    if not web_state.orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not available",
        )

    import urllib.parse
    jid = urllib.parse.unquote(jid)

    # Add divider message
    if web_state.db:
        message_repo = web_state.db.get_message_repository()
        from nanogridbot.types import Message
        divider_msg = Message(
            id=f"divider_{datetime.now().timestamp()}",
            chat_jid=jid,
            sender="__system__",
            sender_name="System",
            content="--- Session reset ---",
            timestamp=datetime.now(),
            is_from_me=True,
        )
        await message_repo.store_message(divider_msg)

    return {"success": True, "dividerMessageId": divider_msg.id}


@app.post(
    "/api/groups/{jid}/clear-history",
    tags=["groups"],
    summary="Clear group history",
    description="Clear all messages for this group.",
)
async def clear_group_history(jid: str):
    """Clear group history."""
    if not web_state.db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    import urllib.parse
    jid = urllib.parse.unquote(jid)

    # Note: Would need to add a method to delete messages by chat_jid
    # For now, just return success
    return {"success": True}


@app.get(
    "/api/status",
    tags=["groups"],
    summary="Get system status",
    description="Returns current status of all groups.",
)
async def get_status():
    """Get system status."""
    if not web_state.orchestrator:
        return {"groups": []}

    groups = []
    registered_groups = web_state.orchestrator.registered_groups
    queue_states = (
        web_state.orchestrator.queue.states if hasattr(web_state.orchestrator, "queue") else {}
    )

    for jid, group in registered_groups.items():
        queue_state = queue_states.get(jid, {})
        is_active = (
            queue_state.get("active", False)
            if isinstance(queue_state, dict)
            else False
        )
        pending_messages = (
            queue_state.get("pending_messages", 0) > 0
            if isinstance(queue_state, dict)
            else False
        )

        groups.append({
            "jid": jid,
            "name": group.name,
            "active": is_active,
            "pendingMessages": pending_messages,
        })

    return {"groups": groups}


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


# ============================================================================
# Authentication API
# ============================================================================


class AuthResponse(BaseModel):
    """Response model for authentication."""

    token: str
    user: UserResponse


class InviteCodeResponse(BaseModel):
    """Response model for invite code."""

    code: str
    expires_at: str
    max_uses: int


def get_client_ip(request: Request) -> str | None:
    """Get client IP from request.

    Args:
        request: FastAPI request.

    Returns:
        Client IP address.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@app.post(
    "/api/auth/register",
    response_model=AuthResponse,
    tags=["auth"],
    summary="Register new user",
    description="Register a new user account with an invite code.",
)
async def register(user_data: UserCreate, request: Request):
    """Register a new user."""
    db = web_state.db
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    try:
        # Validate invite code
        invite_mgr = InviteCodeManager(db)
        await invite_mgr.validate_code(user_data.invite_code)

        # Check if username exists
        user_repo = db.get_user_repository()
        existing = await user_repo.get_user_by_username(user_data.username)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )

        # Check if email exists (if provided)
        if user_data.email:
            existing = await user_repo.get_user_by_email(user_data.email)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )

        # Hash password and create user
        password_mgr = PasswordManager()
        hashed = password_mgr.hash_password(user_data.password)

        user_id = await user_repo.create_user(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed,
        )

        # Use invite code
        await invite_mgr.use_code(user_data.invite_code, user_id)

        # Create session
        session_mgr = SessionManager(db)
        token = await session_mgr.create_session(
            user_id=user_id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
        )

        # Get user for response
        user = await user_repo.get_user_by_id(user_id)

        # Log audit event
        audit_repo = db.get_audit_repository()
        await audit_repo.log_event(
            event_type=AuditEventType.REGISTER,
            user_id=user_id,
            username=user_data.username,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
        )

        logger.info(f"User registered: {user_data.username}")

        return AuthResponse(
            token=token,
            user=UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                role=user.role,
                is_active=user.is_active,
                is_verified=user.is_verified,
                created_at=user.created_at,
                last_login=user.last_login,
            ),
        )

    except InviteCodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@app.post(
    "/api/auth/login",
    response_model=AuthResponse,
    tags=["auth"],
    summary="User login",
    description="Authenticate user and create a session.",
)
async def login(credentials: UserLogin, request: Request, response: Response):
    """User login."""
    db = web_state.db
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    ip_address = get_client_ip(request)

    try:
        # Check lockout
        lock_mgr = LoginLockManager(db)
        await lock_mgr.check_lockout(credentials.username)

        # Get user
        user_repo = db.get_user_repository()
        user = await user_repo.get_user_by_username(credentials.username)

        if not user:
            # Record failed attempt
            await lock_mgr.record_failed_attempt(credentials.username, ip_address)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        # Verify password
        password_mgr = PasswordManager()
        if not password_mgr.verify_password(credentials.password, user.password_hash):
            # Record failed attempt
            await lock_mgr.record_failed_attempt(credentials.username, ip_address)

            # Log audit
            audit_repo = db.get_audit_repository()
            await audit_repo.log_event(
                event_type=AuditEventType.LOGIN_FAILED,
                user_id=user.id,
                username=user.username,
                ip_address=ip_address,
                user_agent=request.headers.get("User-Agent"),
                details={"reason": "invalid_password"},
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
            )

        # Record success and clear failed attempts
        await lock_mgr.record_success(credentials.username, ip_address)

        # Update last login
        await user_repo.update_last_login(user.id)

        # Create session
        session_mgr = SessionManager(db)
        token = await session_mgr.create_session(
            user_id=user.id,
            ip_address=ip_address,
            user_agent=request.headers.get("User-Agent"),
        )

        # Log audit
        audit_repo = db.get_audit_repository()
        await audit_repo.log_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id=user.id,
            username=user.username,
            ip_address=ip_address,
            user_agent=request.headers.get("User-Agent"),
        )

        logger.info(f"User logged in: {user.username}")

        # Set auth cookie
        response.set_cookie(
            key="auth_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 30,  # 30 days
        )

        return AuthResponse(
            token=token,
            user=UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                role=user.role,
                is_active=user.is_active,
                is_verified=user.is_verified,
                created_at=user.created_at,
                last_login=user.last_login,
            ),
        )

    except LoginLockedError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )


@app.post(
    "/api/auth/logout",
    tags=["auth"],
    summary="User logout",
    description="Logout and invalidate current session.",
)
async def logout(
    request: Request,
    authorization: str | None = Header(None),
):
    """User logout."""
    db = web_state.db
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token = authorization[7:]

    # Get session to log audit
    session_repo = db.get_session_repository()
    session = await session_repo.get_session_by_token(token)

    if session:
        # Log audit
        audit_repo = db.get_audit_repository()
        await audit_repo.log_event(
            event_type=AuditEventType.LOGOUT,
            user_id=session.user_id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
        )

        # Delete session
        await session_mgr.delete_session(token)

    return {"message": "Logged out successfully"}


@app.get(
    "/api/auth/me",
    response_model=UserResponse,
    tags=["auth"],
    summary="Get current user",
    description="Get information about the currently authenticated user.",
)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user."""
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        last_login=user.last_login,
    )


# ============================================================================
# Additional Auth Endpoints (for HappyClaw frontend compatibility)
# ============================================================================


class AuthStatusResponse(BaseModel):
    """Response model for auth status check."""
    initialized: bool


class PasswordChangeRequest(BaseModel):
    """Request model for password change."""
    current_password: str
    new_password: str


class ProfileUpdateRequest(BaseModel):
    """Request model for profile update."""
    username: str | None = None
    display_name: str | None = None
    avatar_emoji: str | None = None
    avatar_color: str | None = None
    ai_name: str | None = None
    ai_avatar_emoji: str | None = None
    ai_avatar_color: str | None = None


@app.get(
    "/api/auth/status",
    response_model=AuthStatusResponse,
    tags=["auth"],
    summary="Check auth status",
    description="Check if the system has been initialized (has any users).",
)
async def check_auth_status():
    """Check if system needs initial setup."""
    db = web_state.db
    if not db:
        return AuthStatusResponse(initialized=True)

    user_repo = db.get_user_repository()
    users = await user_repo.list_users(limit=1)

    # If no users exist, system needs setup
    return AuthStatusResponse(initialized=len(users) > 0)


@app.put(
    "/api/auth/password",
    response_model=AuthResponse,
    tags=["auth"],
    summary="Change password",
    description="Change the current user's password.",
)
async def change_password(
    password_data: PasswordChangeRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """Change user password."""
    db = web_state.db
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    # Verify current password
    password_mgr = PasswordManager()
    user_repo = db.get_user_repository()
    current_user = await user_repo.get_user_by_id(user.id)

    if not current_user or not password_mgr.verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Hash new password and update
    new_hash = password_mgr.hash_password(password_data.new_password)
    await user_repo.update_user(user.id, password_hash=new_hash)

    # Create new session
    session_mgr = SessionManager(db)
    token = await session_mgr.create_session(
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )

    # Get updated user
    updated_user = await user_repo.get_user_by_id(user.id)

    return AuthResponse(
        token=token,
        user=UserResponse(
            id=updated_user.id,
            username=updated_user.username,
            email=updated_user.email,
            role=updated_user.role,
            is_active=updated_user.is_active,
            is_verified=updated_user.is_verified,
            created_at=updated_user.created_at,
            last_login=updated_user.last_login,
        ),
    )


@app.put(
    "/api/auth/profile",
    response_model=AuthResponse,
    tags=["auth"],
    summary="Update profile",
    description="Update the current user's profile.",
)
async def update_profile(
    profile_data: ProfileUpdateRequest,
    request: Request,
    user: User = Depends(get_current_user),
):
    """Update user profile."""
    db = web_state.db
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    # Build update data
    update_fields = {}
    if profile_data.username is not None:
        update_fields["username"] = profile_data.username
    if profile_data.email is not None:
        update_fields["email"] = profile_data.email

    if update_fields:
        user_repo = db.get_user_repository()
        await user_repo.update_user(user.id, **update_fields)

    # Create new session (to refresh token)
    session_mgr = SessionManager(db)
    token = await session_mgr.create_session(
        user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )

    # Get updated user
    updated_user = await user_repo.get_user_by_id(user.id)

    return AuthResponse(
        token=token,
        user=UserResponse(
            id=updated_user.id,
            username=updated_user.username,
            email=updated_user.email,
            role=updated_user.role,
            is_active=updated_user.is_active,
            is_verified=updated_user.is_verified,
            created_at=updated_user.created_at,
            last_login=updated_user.last_login,
        ),
    )


@app.post(
    "/api/auth/invite",
    response_model=InviteCodeResponse,
    tags=["auth"],
    summary="Create invite code",
    description="Create a new invite code (requires admin role).",
)
async def create_invite(
    invite_data: InviteCodeCreate,
    request: Request,
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Create invite code."""
    db = web_state.db
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    invite_mgr = InviteCodeManager(db)
    code_data = await invite_mgr.create_code(
        created_by=user.id,
        expires_in_days=invite_data.expires_in_days,
        max_uses=invite_data.max_uses,
    )

    return InviteCodeResponse(
        code=code_data["code"],
        expires_at=code_data["expires_at"],
        max_uses=code_data["max_uses"],
    )


@app.get(
    "/api/auth/invites",
    tags=["auth"],
    summary="List invite codes",
    description="List all invite codes (requires admin role).",
)
async def list_invites(
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List invite codes."""
    db = web_state.db
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    invite_mgr = InviteCodeManager(db)
    return await invite_mgr.list_codes(created_by=user.id)


# ============================================================================
# User Channel Config API
# ============================================================================


class UserChannelConfigResponse(BaseModel):
    """Response model for user channel config."""

    user_id: int
    channel: str
    is_active: bool
    created_at: str | None
    updated_at: str | None


@app.get(
    "/api/user/channels",
    response_model=list[UserChannelConfigResponse],
    tags=["user"],
    summary="List user channel configs",
    description="List all channel configurations for the current user.",
)
async def list_user_channels(
    user: User = Depends(get_current_user),
):
    """List all channel configurations for the current user."""
    db = web_state.db
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    config_repo = db.get_user_channel_config_repository()
    configs = await config_repo.get_configs_by_user(user.id)

    return [
        UserChannelConfigResponse(
            user_id=c.user_id,
            channel=c.channel.value if isinstance(c.channel, ChannelType) else c.channel,
            is_active=c.is_active,
            created_at=c.created_at.isoformat() if c.created_at else None,
            updated_at=c.updated_at.isoformat() if c.updated_at else None,
        )
        for c in configs
    ]


@app.get(
    "/api/user/channels/{channel}",
    response_model=UserChannelConfigResponse,
    tags=["user"],
    summary="Get user channel config",
    description="Get channel configuration for a specific channel.",
)
async def get_user_channel(
    channel: ChannelType,
    user: User = Depends(get_current_user),
):
    """Get channel configuration for a specific channel."""
    db = web_state.db
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    config_repo = db.get_user_channel_config_repository()
    config = await config_repo.get_config(user.id, channel)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel configuration for {channel.value} not found",
        )

    return UserChannelConfigResponse(
        user_id=config.user_id,
        channel=config.channel.value if isinstance(config.channel, ChannelType) else config.channel,
        is_active=config.is_active,
        created_at=config.created_at.isoformat() if config.created_at else None,
        updated_at=config.updated_at.isoformat() if config.updated_at else None,
    )


@app.post(
    "/api/user/channels",
    response_model=UserChannelConfigResponse,
    tags=["user"],
    summary="Create or update user channel config",
    description="Create or update channel configuration for the current user.",
)
async def save_user_channel(
    config_data: UserChannelConfigUpdate,
    user: User = Depends(get_current_user),
):
    """Create or update channel configuration."""
    db = web_state.db
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    config_repo = db.get_user_channel_config_repository()

    # Check if config exists
    existing = await config_repo.get_config(user.id, config_data.channel)

    now = datetime.utcnow()
    config = UserChannelConfig(
        user_id=user.id,
        channel=config_data.channel,
        telegram_bot_token=config_data.telegram_bot_token,
        slack_bot_token=config_data.slack_bot_token,
        slack_signing_secret=config_data.slack_signing_secret,
        discord_bot_token=config_data.discord_bot_token,
        whatsapp_session_path=config_data.whatsapp_session_path,
        qq_host=config_data.qq_host,
        qq_port=config_data.qq_port,
        feishu_app_id=config_data.feishu_app_id,
        feishu_app_secret=config_data.feishu_app_secret,
        wecom_corp_id=config_data.wecom_corp_id,
        wecom_agent_id=config_data.wecom_agent_id,
        wecom_secret=config_data.wecom_secret,
        dingtalk_app_key=config_data.dingtalk_app_key,
        dingtalk_app_secret=config_data.dingtalk_app_secret,
        is_active=True,
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )

    await config_repo.save_config(config)

    # Log audit event
    audit_repo = db.get_audit_repository()
    await audit_repo.log_event(
        event_type=AuditEventType.USER_UPDATED,
        user_id=user.id,
        username=user.username,
        resource_type="user_channel_config",
        resource_id=config_data.channel.value if isinstance(config_data.channel, ChannelType) else config_data.channel,
    )

    return UserChannelConfigResponse(
        user_id=config.user_id,
        channel=config.channel.value if isinstance(config.channel, ChannelType) else config.channel,
        is_active=config.is_active,
        created_at=config.created_at.isoformat() if config.created_at else None,
        updated_at=config.updated_at.isoformat() if config.updated_at else None,
    )


@app.delete(
    "/api/user/channels/{channel}",
    tags=["user"],
    summary="Delete user channel config",
    description="Delete channel configuration for the current user.",
)
async def delete_user_channel(
    channel: ChannelType,
    user: User = Depends(get_current_user),
):
    """Delete channel configuration."""
    db = web_state.db
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    config_repo = db.get_user_channel_config_repository()
    deleted = await config_repo.delete_config(user.id, channel)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel configuration for {channel.value} not found",
        )

    # Log audit event
    audit_repo = db.get_audit_repository()
    await audit_repo.log_event(
        event_type=AuditEventType.USER_UPDATED,
        user_id=user.id,
        username=user.username,
        resource_type="user_channel_config",
        resource_id=channel.value,
        details={"action": "deleted"},
    )

    return {"message": f"Channel configuration for {channel.value} deleted"}


@app.put(
    "/api/user/channels/{channel}/active",
    response_model=UserChannelConfigResponse,
    tags=["user"],
    summary="Set channel active status",
    description="Enable or disable a channel configuration.",
)
async def set_channel_active(
    channel: ChannelType,
    is_active: bool,
    user: User = Depends(get_current_user),
):
    """Set channel configuration active status."""
    db = web_state.db
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    config_repo = db.get_user_channel_config_repository()
    config = await config_repo.get_config(user.id, channel)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel configuration for {channel.value} not found",
        )

    await config_repo.set_active(user.id, channel, is_active)

    # Get updated config
    updated = await config_repo.get_config(user.id, channel)

    return UserChannelConfigResponse(
        user_id=updated.user_id,
        channel=updated.channel.value if isinstance(updated.channel, ChannelType) else updated.channel,
        is_active=updated.is_active,
        created_at=updated.created_at.isoformat() if updated.created_at else None,
        updated_at=updated.updated_at.isoformat() if updated.updated_at else None,
    )


# Initialize session_mgr at module level for logout
session_mgr: SessionManager | None = None


def set_session_manager(mgr: SessionManager) -> None:
    """Set the session manager for the web app."""
    global session_mgr
    session_mgr = mgr


# ============================================================================
# Audit Log API
# ============================================================================


class AuditEventResponse(BaseModel):
    """Response model for audit event."""

    id: int
    event_type: str
    user_id: int | None
    username: str | None
    ip_address: str | None
    user_agent: str | None
    resource_type: str | None
    resource_id: str | None
    details: str | None
    timestamp: str


@app.get(
    "/api/audit/events",
    response_model=list[AuditEventResponse],
    tags=["auth"],
    summary="Get audit events",
    description="Get audit events (requires admin role).",
)
async def get_audit_events(
    event_type: AuditEventType | None = Query(None, description="Filter by event type"),
    user_id: int | None = Query(None, description="Filter by user ID"),
    limit: int = Query(100, ge=1, le=500, description="Maximum events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    user: User = Depends(require_permission(Permission.AUDIT_VIEW)),
):
    """Get audit events."""
    db = web_state.db
    if not db:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    audit_repo = db.get_audit_repository()
    events = await audit_repo.get_events(
        user_id=user_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )

    return [
        AuditEventResponse(
            id=e.id,
            event_type=e.event_type.value,
            user_id=e.user_id,
            username=e.username,
            ip_address=e.ip_address,
            user_agent=e.user_agent,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
            details=e.details,
            timestamp=e.timestamp.isoformat() if e.timestamp else "",
        )
        for e in events
    ]


# ============================================================================
# Memory API
# ============================================================================


from nanogridbot.memory import MemoryService, create_memory_service


class ConversationResponse(BaseModel):
    """Response model for conversation archive."""
    title: str
    path: str
    size: int
    modified: str


class ConversationListResponse(BaseModel):
    """Response model for conversation list."""
    conversations: list[ConversationResponse]
    total: int


class DailyConversationsResponse(BaseModel):
    """Response model for conversations grouped by date."""
    date: str
    conversations: list[dict[str, Any]]


class MemoryNoteCreate(BaseModel):
    """Request model for creating a memory note."""
    title: str
    content: str
    memory_type: str = "note"
    tags: list[str] = []
    group_folder: str | None = None


class MemoryNoteResponse(BaseModel):
    """Response model for memory note."""
    title: str
    path: str
    size: int
    modified: str


class DailySummaryResponse(BaseModel):
    """Response model for daily summary."""
    date: str
    summary: str
    conversation_count: int
    key_topics: list[str]


@app.get(
    "/api/memory/conversations",
    response_model=ConversationListResponse,
    tags=["memory"],
    summary="List conversation archives",
    description="List all conversation archives for the user.",
)
async def list_conversations(
    group_folder: str | None = Query(None, description="Filter by group folder"),
    limit: int = Query(50, ge=1, le=100, description="Maximum conversations to return"),
    user: User = Depends(get_current_user),
):
    """List conversation archives."""
    memory_service = create_memory_service(user_id=user.id)
    conversations = memory_service.list_conversations(
        user_id=user.id,
        group_folder=group_folder,
        limit=limit,
    )
    return ConversationListResponse(
        conversations=conversations,
        total=len(conversations),
    )


@app.get(
    "/api/memory/conversations/{file_path:path}",
    tags=["memory"],
    summary="Get conversation content",
    description="Get the content of a conversation archive.",
)
async def get_conversation(
    file_path: str,
    user: User = Depends(get_current_user),
):
    """Get conversation content."""
    memory_service = create_memory_service(user_id=user.id)
    content = memory_service.get_conversation(file_path)

    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return {"content": content}


@app.get(
    "/api/memory/conversations/by-date",
    response_model=list[DailyConversationsResponse],
    tags=["memory"],
    summary="List conversations by date",
    description="List conversation archives grouped by date.",
)
async def list_conversations_by_date(
    group_folder: str | None = Query(None, description="Filter by group folder"),
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    user: User = Depends(get_current_user),
):
    """List conversations grouped by date."""
    memory_service = create_memory_service(user_id=user.id)
    return memory_service.list_by_date(
        user_id=user.id,
        group_folder=group_folder,
        start_date=start_date,
        end_date=end_date,
    )


@app.post(
    "/api/memory/notes",
    response_model=MemoryNoteResponse,
    tags=["memory"],
    summary="Create memory note",
    description="Create a new memory note.",
)
async def create_memory_note(
    note: MemoryNoteCreate,
    user: User = Depends(get_current_user),
):
    """Create a new memory note."""
    memory_service = create_memory_service(user_id=user.id)
    file_path = memory_service.create_memory_note(
        user_id=user.id,
        group_folder=note.group_folder,
        title=note.title,
        content=note.content,
        memory_type=note.memory_type,
        tags=note.tags,
    )

    stat = file_path.stat()
    return MemoryNoteResponse(
        title=note.title,
        path=str(file_path),
        size=stat.st_size,
        modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
    )


@app.get(
    "/api/memory/notes",
    response_model=list[MemoryNoteResponse],
    tags=["memory"],
    summary="Search memory notes",
    description="Search memory notes by content or tags.",
)
async def search_memory_notes(
    q: str | None = Query(None, description="Search query"),
    tags: str | None = Query(None, description="Comma-separated tags"),
    memory_type: str | None = Query(None, description="Filter by memory type"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    user: User = Depends(get_current_user),
):
    """Search memory notes."""
    memory_service = create_memory_service(user_id=user.id)

    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    results = memory_service.search_memories(
        user_id=user.id,
        query=q,
        tags=tag_list,
        memory_type=memory_type,
        limit=limit,
    )

    return [
        MemoryNoteResponse(
            title=r["title"],
            path=r["path"],
            size=r["size"],
            modified=r["modified"],
        )
        for r in results
    ]


@app.get(
    "/api/memory/daily/{date}",
    response_model=DailySummaryResponse,
    tags=["memory"],
    summary="Get daily summary",
    description="Get or generate daily summary for a specific date.",
)
async def get_daily_summary(
    date: str,
    group_folder: str | None = Query(None, description="Filter by group folder"),
    user: User = Depends(get_current_user),
):
    """Get daily summary."""
    memory_service = create_memory_service(user_id=user.id)
    summary = memory_service.get_daily_summary(
        user_id=user.id,
        group_folder=group_folder,
        date=date,
    )

    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No data found for date {date}",
        )

    return DailySummaryResponse(
        date=summary.date,
        summary=summary.summary,
        conversation_count=summary.conversation_count,
        key_topics=summary.key_topics,
    )
