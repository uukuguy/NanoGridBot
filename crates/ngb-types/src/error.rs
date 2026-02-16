use thiserror::Error;

/// Top-level error type for NanoGridBot.
#[derive(Error, Debug)]
pub enum NanoGridBotError {
    #[error("Configuration error: {0}")]
    Config(String),

    #[error("Database error: {0}")]
    Database(String),

    #[error("Channel error: {0}")]
    Channel(String),

    #[error("Container error: {0}")]
    Container(String),

    #[error("Plugin error: {0}")]
    Plugin(String),

    #[error("Security error: {0}")]
    Security(String),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("Circuit breaker open")]
    CircuitBreakerOpen,

    #[error("Rate limit exceeded")]
    RateLimitExceeded,

    #[error("Timeout: {0}")]
    Timeout(String),

    #[error("{0}")]
    Other(String),
}

/// Convenience type alias.
pub type Result<T> = std::result::Result<T, NanoGridBotError>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn error_display() {
        let err = NanoGridBotError::Config("missing key".to_string());
        assert_eq!(err.to_string(), "Configuration error: missing key");
    }

    #[test]
    fn error_from_io() {
        let io_err = std::io::Error::new(std::io::ErrorKind::NotFound, "file not found");
        let err: NanoGridBotError = io_err.into();
        assert!(err.to_string().contains("file not found"));
    }

    #[test]
    fn result_alias_works() {
        fn ok_fn() -> Result<i32> {
            Ok(42)
        }
        fn err_fn() -> Result<i32> {
            Err(NanoGridBotError::Other("oops".to_string()))
        }
        assert_eq!(ok_fn().unwrap(), 42);
        assert!(err_fn().is_err());
    }
}
