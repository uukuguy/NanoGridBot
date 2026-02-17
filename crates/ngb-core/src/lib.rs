pub mod formatting;
pub mod logging;
pub mod security;
pub mod utils;

// Phase 2: Core runtime modules
pub mod container_prep;
pub mod container_runner;
pub mod container_session;
pub mod group_queue;
pub mod ipc_handler;
pub mod mount_security;
pub mod orchestrator;
pub mod router;
pub mod task_scheduler;
pub mod workspace_queue;

pub use formatting::{
    escape_xml, format_messages_xml, format_output_xml, parse_input_json, serialize_output,
    MessageData,
};
pub use logging::init_logging;
pub use security::{check_path_traversal, sanitize_filename, validate_container_path};
pub use utils::{
    with_retry, CircuitBreaker, CircuitState, GracefulShutdown, RateLimiter, RetryConfig,
};

// Phase 2 re-exports
pub use container_prep::prepare_container_launch;
pub use container_runner::{
    build_docker_args, check_docker_available, cleanup_container, get_container_status,
    parse_container_output, run_container_agent, OUTPUT_END_MARKER, OUTPUT_START_MARKER,
};
pub use container_session::ContainerSession;
pub use group_queue::GroupQueue;
pub use ipc_handler::{ChannelSender, IpcHandler};
pub use mount_security::{get_allowed_mount_paths, validate_workspace_mounts, MountMode, MountSpec};
pub use orchestrator::{HealthStatus, Orchestrator};
pub use router::{format_messages, MessageRouter, RouteAction, RouteResult};
pub use task_scheduler::{calculate_next_run, TaskScheduler};
pub use workspace_queue::WorkspaceQueue;
