use std::collections::VecDeque;
use std::time::{Duration, Instant};

use tokio::sync::Mutex;

/// Sliding-window rate limiter for async operations.
pub struct RateLimiter {
    max_calls: usize,
    period: Duration,
    calls: Mutex<VecDeque<Instant>>,
}

impl RateLimiter {
    pub fn new(max_calls: usize, period_secs: f64) -> Self {
        Self {
            max_calls,
            period: Duration::from_secs_f64(period_secs),
            calls: Mutex::new(VecDeque::new()),
        }
    }

    /// Acquire permission to proceed.
    /// Blocks if the rate limit is exceeded.
    pub async fn acquire(&self) {
        loop {
            let now = Instant::now();
            let mut calls = self.calls.lock().await;

            // Remove expired entries
            while let Some(&front) = calls.front() {
                if now.duration_since(front) >= self.period {
                    calls.pop_front();
                } else {
                    break;
                }
            }

            if calls.len() < self.max_calls {
                calls.push_back(now);
                return;
            }

            // Calculate wait time
            let oldest = calls.front().copied().unwrap();
            let wait_time = self.period - now.duration_since(oldest) + Duration::from_millis(10);
            drop(calls); // Release lock before sleeping

            tokio::time::sleep(wait_time).await;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn rate_limiter_allows_under_limit() {
        let rl = RateLimiter::new(5, 1.0);

        for _ in 0..5 {
            rl.acquire().await; // should not block
        }
    }

    #[tokio::test]
    async fn rate_limiter_blocks_over_limit() {
        let rl = RateLimiter::new(2, 0.1); // 2 per 100ms

        let start = Instant::now();

        rl.acquire().await;
        rl.acquire().await;
        // Third call should block until the window slides
        rl.acquire().await;

        let elapsed = start.elapsed();
        // Should have waited at least ~100ms
        assert!(elapsed >= Duration::from_millis(90));
    }
}
