use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use notify::{Event, EventKind, RecommendedWatcher, RecursiveMode, Watcher};
use tracing::{error, info, warn};

use crate::config::reload_config;

type ChangeCallbacks = Arc<Mutex<Vec<Box<dyn Fn() + Send + 'static>>>>;

/// Watch configuration files for changes and trigger reloads.
pub struct ConfigWatcher {
    watcher: Option<RecommendedWatcher>,
    callbacks: ChangeCallbacks,
    running: bool,
}

impl ConfigWatcher {
    pub fn new() -> Self {
        Self {
            watcher: None,
            callbacks: Arc::new(Mutex::new(Vec::new())),
            running: false,
        }
    }

    /// Start watching configuration files.
    ///
    /// Watches `.env` file and `groups/*/config.json` by default.
    /// Additional paths can be provided.
    pub fn start(&mut self, paths: Vec<PathBuf>) -> ngb_types::Result<()> {
        if self.running {
            return Ok(());
        }

        let mut watch_paths = Vec::new();

        // Watch .env file's parent directory
        let env_file = PathBuf::from(".env");
        if env_file.exists() {
            if let Some(parent) = env_file.parent() {
                let parent = if parent.as_os_str().is_empty() {
                    PathBuf::from(".")
                } else {
                    parent.to_path_buf()
                };
                watch_paths.push(parent);
            }
        }

        // Add custom paths
        watch_paths.extend(paths);

        if watch_paths.is_empty() {
            info!("No paths to watch for config changes");
            return Ok(());
        }

        // Deduplicate
        watch_paths.sort();
        watch_paths.dedup();

        let callbacks = Arc::clone(&self.callbacks);

        let mut watcher = notify::recommended_watcher(move |res: notify::Result<Event>| {
            match res {
                Ok(event) => {
                    // Skip directory events and temp files
                    if matches!(event.kind, EventKind::Access(_)) {
                        return;
                    }

                    let dominated_by_temp = event.paths.iter().all(|p| {
                        p.extension()
                            .map(|e| e == "tmp" || e == "swp")
                            .unwrap_or(false)
                    });
                    if dominated_by_temp {
                        return;
                    }

                    info!("Configuration change detected: {:?}", event.paths);

                    if let Err(e) = reload_config() {
                        error!("Failed to reload config: {e}");
                        return;
                    }

                    if let Ok(cbs) = callbacks.lock() {
                        for cb in cbs.iter() {
                            cb();
                        }
                    }
                }
                Err(e) => {
                    warn!("File watch error: {e}");
                }
            }
        })
        .map_err(|e| {
            ngb_types::NanoGridBotError::Config(format!("Failed to create watcher: {e}"))
        })?;

        for path in &watch_paths {
            watcher.watch(path, RecursiveMode::Recursive).map_err(|e| {
                ngb_types::NanoGridBotError::Config(format!(
                    "Failed to watch {}: {e}",
                    path.display()
                ))
            })?;
        }

        info!(
            "Config watcher started, watching {} paths",
            watch_paths.len()
        );
        self.watcher = Some(watcher);
        self.running = true;
        Ok(())
    }

    /// Stop watching.
    pub fn stop(&mut self) {
        self.watcher = None;
        self.running = false;
    }

    /// Register a callback for config changes.
    pub fn on_change<F>(&self, callback: F)
    where
        F: Fn() + Send + 'static,
    {
        if let Ok(mut cbs) = self.callbacks.lock() {
            cbs.push(Box::new(callback));
        }
    }

    /// Whether the watcher is running.
    pub fn is_running(&self) -> bool {
        self.running
    }
}

impl Default for ConfigWatcher {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn watcher_new_is_not_running() {
        let w = ConfigWatcher::new();
        assert!(!w.is_running());
    }

    #[test]
    fn watcher_stop_when_not_started() {
        let mut w = ConfigWatcher::new();
        w.stop(); // should not panic
        assert!(!w.is_running());
    }

    #[test]
    fn watcher_start_with_valid_path() {
        let tmp = tempfile::tempdir().unwrap();
        let mut w = ConfigWatcher::new();
        let result = w.start(vec![tmp.path().to_path_buf()]);
        assert!(result.is_ok());
        assert!(w.is_running());
        w.stop();
        assert!(!w.is_running());
    }

    #[test]
    fn watcher_on_change_registers_callback() {
        let w = ConfigWatcher::new();
        let called = Arc::new(Mutex::new(false));
        let called_clone = Arc::clone(&called);
        w.on_change(move || {
            *called_clone.lock().unwrap() = true;
        });
        // Verify callback was registered
        assert_eq!(w.callbacks.lock().unwrap().len(), 1);
    }
}
