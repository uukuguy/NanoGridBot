use std::future::Future;
use std::time::Duration;

use tracing::{error, warn};

/// Configuration for retry behavior.
#[derive(Debug, Clone)]
pub struct RetryConfig {
    pub max_retries: u32,
    pub base_delay: Duration,
    pub max_delay: Duration,
    pub exponential_base: f64,
}

impl Default for RetryConfig {
    fn default() -> Self {
        Self {
            max_retries: 3,
            base_delay: Duration::from_secs(1),
            max_delay: Duration::from_secs(60),
            exponential_base: 2.0,
        }
    }
}

/// Execute an async function with exponential backoff retry.
pub async fn with_retry<F, Fut, T, E>(config: &RetryConfig, name: &str, mut f: F) -> Result<T, E>
where
    F: FnMut() -> Fut,
    Fut: Future<Output = Result<T, E>>,
    E: std::fmt::Display,
{
    let mut last_err: Option<E> = None;

    for attempt in 0..=config.max_retries {
        match f().await {
            Ok(result) => return Ok(result),
            Err(e) => {
                if attempt >= config.max_retries {
                    error!(
                        "Function {name} failed after {} retries: {e}",
                        config.max_retries
                    );
                    return Err(e);
                }

                let delay_secs =
                    config.base_delay.as_secs_f64() * config.exponential_base.powi(attempt as i32);
                let delay_secs = delay_secs.min(config.max_delay.as_secs_f64());
                let delay = Duration::from_secs_f64(delay_secs);

                warn!(
                    "Function {name} failed (attempt {}/{}) retrying in {:.1}s: {e}",
                    attempt + 1,
                    config.max_retries + 1,
                    delay.as_secs_f64()
                );

                tokio::time::sleep(delay).await;
                last_err = Some(e);
            }
        }
    }

    Err(last_err.unwrap())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU32, Ordering};
    use std::sync::Arc;

    #[tokio::test]
    async fn retry_success_first_attempt() {
        let config = RetryConfig {
            max_retries: 3,
            base_delay: Duration::from_millis(10),
            ..Default::default()
        };

        let result: Result<i32, String> = with_retry(&config, "test", || async { Ok(42) }).await;
        assert_eq!(result.unwrap(), 42);
    }

    #[tokio::test]
    async fn retry_success_after_failures() {
        let config = RetryConfig {
            max_retries: 3,
            base_delay: Duration::from_millis(10),
            max_delay: Duration::from_millis(50),
            exponential_base: 2.0,
        };

        let attempts = Arc::new(AtomicU32::new(0));
        let attempts_clone = Arc::clone(&attempts);

        let result: Result<i32, String> = with_retry(&config, "test", move || {
            let a = Arc::clone(&attempts_clone);
            async move {
                let n = a.fetch_add(1, Ordering::SeqCst);
                if n < 2 {
                    Err("transient error".to_string())
                } else {
                    Ok(42)
                }
            }
        })
        .await;

        assert_eq!(result.unwrap(), 42);
        assert_eq!(attempts.load(Ordering::SeqCst), 3);
    }

    #[tokio::test]
    async fn retry_exhausted() {
        let config = RetryConfig {
            max_retries: 2,
            base_delay: Duration::from_millis(10),
            max_delay: Duration::from_millis(50),
            exponential_base: 2.0,
        };

        let attempts = Arc::new(AtomicU32::new(0));
        let attempts_clone = Arc::clone(&attempts);

        let result: Result<i32, String> = with_retry(&config, "test", move || {
            let a = Arc::clone(&attempts_clone);
            async move {
                a.fetch_add(1, Ordering::SeqCst);
                Err("persistent error".to_string())
            }
        })
        .await;

        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "persistent error");
        // 1 initial + 2 retries = 3 total
        assert_eq!(attempts.load(Ordering::SeqCst), 3);
    }
}
