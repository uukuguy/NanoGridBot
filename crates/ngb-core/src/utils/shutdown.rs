use tokio::sync::broadcast;
use tracing::info;

/// Graceful shutdown handler using tokio broadcast channel.
pub struct GracefulShutdown {
    shutdown_tx: broadcast::Sender<()>,
    is_shutting_down: std::sync::atomic::AtomicBool,
}

impl GracefulShutdown {
    pub fn new() -> Self {
        let (tx, _) = broadcast::channel(1);
        Self {
            shutdown_tx: tx,
            is_shutting_down: std::sync::atomic::AtomicBool::new(false),
        }
    }

    /// Check if shutdown has been requested.
    pub fn is_shutting_down(&self) -> bool {
        self.is_shutting_down
            .load(std::sync::atomic::Ordering::Relaxed)
    }

    /// Subscribe to shutdown signal. Returns a receiver that completes when shutdown is requested.
    pub fn subscribe(&self) -> broadcast::Receiver<()> {
        self.shutdown_tx.subscribe()
    }

    /// Request graceful shutdown.
    pub fn request_shutdown(&self) {
        if !self.is_shutting_down() {
            self.is_shutting_down
                .store(true, std::sync::atomic::Ordering::Relaxed);
            info!("Shutdown requested, initiating graceful shutdown...");
            let _ = self.shutdown_tx.send(());
        }
    }

    /// Install signal handlers (SIGINT / SIGTERM).
    /// Returns a future that resolves when a signal is received.
    pub async fn wait_for_signal(&self) {
        #[cfg(unix)]
        {
            use tokio::signal::unix::{signal, SignalKind};
            let mut sigint = signal(SignalKind::interrupt()).expect("SIGINT handler");
            let mut sigterm = signal(SignalKind::terminate()).expect("SIGTERM handler");
            tokio::select! {
                _ = sigint.recv() => info!("Received SIGINT"),
                _ = sigterm.recv() => info!("Received SIGTERM"),
            }
        }
        #[cfg(not(unix))]
        {
            tokio::signal::ctrl_c().await.expect("Ctrl+C handler");
            info!("Received Ctrl+C");
        }
        self.request_shutdown();
    }
}

impl Default for GracefulShutdown {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn shutdown_initially_not_shutting_down() {
        let gs = GracefulShutdown::new();
        assert!(!gs.is_shutting_down());
    }

    #[tokio::test]
    async fn shutdown_request_sets_flag() {
        let gs = GracefulShutdown::new();
        gs.request_shutdown();
        assert!(gs.is_shutting_down());
    }

    #[tokio::test]
    async fn shutdown_broadcast_to_subscribers() {
        let gs = GracefulShutdown::new();
        let mut rx = gs.subscribe();

        gs.request_shutdown();

        let result = rx.recv().await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn shutdown_multiple_requests_are_idempotent() {
        let gs = GracefulShutdown::new();
        gs.request_shutdown();
        gs.request_shutdown(); // should not panic
        assert!(gs.is_shutting_down());
    }
}
