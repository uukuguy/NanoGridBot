use std::future::Future;
use std::time::Instant;

use tokio::sync::Mutex;
use tracing::{info, warn};

use ngb_types::NanoGridBotError;

/// Circuit breaker states.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CircuitState {
    Closed,
    Open,
    HalfOpen,
}

/// Circuit breaker pattern for fault tolerance.
pub struct CircuitBreaker {
    failure_threshold: u32,
    recovery_timeout: std::time::Duration,
    inner: Mutex<CircuitInner>,
}

struct CircuitInner {
    state: CircuitState,
    failure_count: u32,
    last_failure_time: Option<Instant>,
}

impl CircuitBreaker {
    pub fn new(failure_threshold: u32, recovery_timeout_secs: f64) -> Self {
        Self {
            failure_threshold,
            recovery_timeout: std::time::Duration::from_secs_f64(recovery_timeout_secs),
            inner: Mutex::new(CircuitInner {
                state: CircuitState::Closed,
                failure_count: 0,
                last_failure_time: None,
            }),
        }
    }

    /// Get the current circuit state.
    pub async fn state(&self) -> CircuitState {
        self.inner.lock().await.state
    }

    /// Execute a function with circuit breaker protection.
    pub async fn call<F, Fut, T, E>(&self, f: F) -> Result<T, NanoGridBotError>
    where
        F: FnOnce() -> Fut,
        Fut: Future<Output = Result<T, E>>,
        E: std::fmt::Display,
    {
        // Check if circuit allows the call
        {
            let mut inner = self.inner.lock().await;
            if inner.state == CircuitState::Open {
                if let Some(last_failure) = inner.last_failure_time {
                    if last_failure.elapsed() >= self.recovery_timeout {
                        inner.state = CircuitState::HalfOpen;
                        info!("Circuit breaker entering HALF_OPEN state");
                    } else {
                        return Err(NanoGridBotError::CircuitBreakerOpen);
                    }
                } else {
                    return Err(NanoGridBotError::CircuitBreakerOpen);
                }
            }
        }

        match f().await {
            Ok(result) => {
                self.on_success().await;
                Ok(result)
            }
            Err(e) => {
                self.on_failure().await;
                Err(NanoGridBotError::Other(e.to_string()))
            }
        }
    }

    async fn on_success(&self) {
        let mut inner = self.inner.lock().await;
        if inner.state == CircuitState::HalfOpen {
            info!("Circuit breaker closing after successful call");
        }
        inner.failure_count = 0;
        inner.state = CircuitState::Closed;
    }

    async fn on_failure(&self) {
        let mut inner = self.inner.lock().await;
        inner.failure_count += 1;
        inner.last_failure_time = Some(Instant::now());

        if inner.failure_count >= self.failure_threshold && inner.state != CircuitState::Open {
            warn!(
                "Circuit breaker opening after {} failures",
                inner.failure_count
            );
            inner.state = CircuitState::Open;
        }
    }
}

impl Default for CircuitBreaker {
    fn default() -> Self {
        Self::new(5, 30.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn circuit_starts_closed() {
        let cb = CircuitBreaker::default();
        assert_eq!(cb.state().await, CircuitState::Closed);
    }

    #[tokio::test]
    async fn circuit_stays_closed_on_success() {
        let cb = CircuitBreaker::new(3, 1.0);
        let result: Result<i32, NanoGridBotError> = cb.call(|| async { Ok::<_, String>(42) }).await;
        assert_eq!(result.unwrap(), 42);
        assert_eq!(cb.state().await, CircuitState::Closed);
    }

    #[tokio::test]
    async fn circuit_opens_after_threshold() {
        let cb = CircuitBreaker::new(3, 1.0);

        for _ in 0..3 {
            let _ = cb.call(|| async { Err::<i32, _>("fail") }).await;
        }

        assert_eq!(cb.state().await, CircuitState::Open);
    }

    #[tokio::test]
    async fn circuit_rejects_when_open() {
        let cb = CircuitBreaker::new(2, 100.0); // long recovery

        for _ in 0..2 {
            let _ = cb.call(|| async { Err::<i32, _>("fail") }).await;
        }

        let result = cb.call(|| async { Ok::<_, String>(42) }).await;
        assert!(matches!(result, Err(NanoGridBotError::CircuitBreakerOpen)));
    }

    #[tokio::test]
    async fn circuit_half_open_after_recovery() {
        let cb = CircuitBreaker::new(2, 0.05); // 50ms recovery

        for _ in 0..2 {
            let _ = cb.call(|| async { Err::<i32, _>("fail") }).await;
        }
        assert_eq!(cb.state().await, CircuitState::Open);

        // Wait for recovery
        tokio::time::sleep(std::time::Duration::from_millis(60)).await;

        // Next call should succeed and close the circuit
        let result = cb.call(|| async { Ok::<_, String>(42) }).await;
        assert_eq!(result.unwrap(), 42);
        assert_eq!(cb.state().await, CircuitState::Closed);
    }

    #[tokio::test]
    async fn circuit_resets_on_success() {
        let cb = CircuitBreaker::new(3, 1.0);

        // 2 failures (below threshold)
        let _ = cb.call(|| async { Err::<i32, _>("fail") }).await;
        let _ = cb.call(|| async { Err::<i32, _>("fail") }).await;

        // Success resets count
        let _ = cb.call(|| async { Ok::<_, String>(42) }).await;

        // 2 more failures should not open (reset happened)
        let _ = cb.call(|| async { Err::<i32, _>("fail") }).await;
        let _ = cb.call(|| async { Err::<i32, _>("fail") }).await;

        assert_eq!(cb.state().await, CircuitState::Closed);
    }
}
