use std::path::Path;

use tracing_appender::rolling;
use tracing_subscriber::fmt::format::FmtSpan;
use tracing_subscriber::prelude::*;
use tracing_subscriber::EnvFilter;

/// Initialize the tracing/logging system.
///
/// Sets up console (ANSI) and optional file (rolling) layers.
pub fn init_logging(log_level: &str, log_file: Option<&Path>, structured: bool) {
    let env_filter =
        EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new(log_level));

    if structured {
        // JSON structured logging to stderr
        let fmt_layer = tracing_subscriber::fmt::layer()
            .json()
            .with_target(true)
            .with_span_events(FmtSpan::CLOSE);

        let subscriber = tracing_subscriber::registry()
            .with(env_filter)
            .with(fmt_layer);

        if let Some(log_path) = log_file {
            let dir = log_path.parent().unwrap_or(Path::new("."));
            let filename = log_path
                .file_name()
                .map(|n| n.to_string_lossy().to_string())
                .unwrap_or_else(|| "nanogridbot.log".to_string());

            let file_appender = rolling::daily(dir, &filename);
            let file_layer = tracing_subscriber::fmt::layer()
                .json()
                .with_writer(file_appender)
                .with_target(true)
                .with_ansi(false);

            subscriber.with(file_layer).init();
        } else {
            subscriber.init();
        }
    } else {
        // Human-readable console logging
        let fmt_layer = tracing_subscriber::fmt::layer()
            .with_target(true)
            .with_ansi(true);

        let subscriber = tracing_subscriber::registry()
            .with(env_filter)
            .with(fmt_layer);

        if let Some(log_path) = log_file {
            let dir = log_path.parent().unwrap_or(Path::new("."));
            let filename = log_path
                .file_name()
                .map(|n| n.to_string_lossy().to_string())
                .unwrap_or_else(|| "nanogridbot.log".to_string());

            let file_appender = rolling::daily(dir, &filename);
            let file_layer = tracing_subscriber::fmt::layer()
                .with_writer(file_appender)
                .with_target(true)
                .with_ansi(false);

            subscriber.with(file_layer).init();
        } else {
            subscriber.init();
        }
    }
}

#[cfg(test)]
mod tests {
    // Logging initialization is global state (tracing subscriber),
    // so we only test that the function signature and parameters compile.
    // Actual logging is verified via integration tests.

    use super::*;

    #[test]
    fn init_logging_compiles() {
        // Just ensure the function exists with the right signature.
        // We can't call init_logging multiple times (global subscriber),
        // so we only verify it compiles.
        let _ = init_logging as fn(&str, Option<&Path>, bool);
    }
}
