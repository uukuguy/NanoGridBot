"""Error handling and recovery utilities for NanoGridBot."""

import asyncio
import functools
import logging
from typing import Any, Callable, Coroutine, TypeVar

from loguru import logger

T = TypeVar("T")


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator for async functions with exponential backoff retry.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        exceptions: Tuple of exception types to catch

    Returns:
        Decorated function with retry logic
    """

    def decorator(
        func: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt >= max_retries:
                        logger.error(
                            f"Function {func.__name__} failed after {max_retries} retries: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base**attempt), max_delay)
                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)

            # This should never be reached, but satisfies type checking
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected error in retry wrapper")

        return wrapper

    return decorator


async def retry_async(
    coro: Coroutine[Any, Any, T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """Retry an async coroutine with exponential backoff.

    Args:
        coro: Coroutine to execute
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        exceptions: Tuple of exception types to catch

    Returns:
        Result of the coroutine

    Raises:
        Last exception if all retries fail
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await coro
        except exceptions as e:
            last_exception = e

            if attempt >= max_retries:
                logger.error(f"Operation failed after {max_retries} retries: {e}")
                raise

            delay = min(base_delay * (exponential_base**attempt), max_delay)
            logger.warning(
                f"Operation failed (attempt {attempt + 1}/{max_retries + 1}), "
                f"retrying in {delay:.1f}s: {e}"
            )
            await asyncio.sleep(delay)

    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected error in retry")


class CircuitBreaker:
    """Circuit breaker pattern implementation for fault tolerance.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit is open, requests fail fast
    - HALF_OPEN: Testing if service is recovered
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exception: type[Exception] = Exception,
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying again
            expected_exception: Exception type to track
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        """Get current circuit state."""
        return self._state

    async def call(
        self, func: Callable[..., Coroutine[Any, Any, T]], *args: Any, **kwargs: Any
    ) -> T:
        """Execute function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of function execution

        Raises:
            Exception: If circuit is open or function fails
        """
        async with self._lock:
            if self._state == self.OPEN:
                # Check if we should try half-open
                if self._last_failure_time and (
                    asyncio.get_event_loop().time() - self._last_failure_time
                    >= self.recovery_timeout
                ):
                    self._state = self.HALF_OPEN
                    logger.info("Circuit breaker entering HALF_OPEN state")
                else:
                    raise Exception("Circuit breaker is OPEN")

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except self.expected_exception as e:
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            if self._state == self.HALF_OPEN:
                logger.info("Circuit breaker closing after successful call")
            self._failure_count = 0
            self._state = self.CLOSED

    async def _on_failure(self) -> None:
        """Handle failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = asyncio.get_event_loop().time()

            if self._failure_count >= self.failure_threshold:
                if self._state != self.OPEN:
                    logger.warning(f"Circuit breaker opening after {self._failure_count} failures")
                self._state = self.OPEN


class GracefulShutdown:
    """Graceful shutdown handler for managing shutdown sequence."""

    def __init__(self):
        """Initialize graceful shutdown handler."""
        self._shutdown_event = asyncio.Event()
        self._tasks: list[asyncio.Task[Any]] = []
        self._is_shutting_down = False

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self._is_shutting_down

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()

    def request_shutdown(self) -> None:
        """Request graceful shutdown."""
        if not self._is_shutting_down:
            self._is_shutting_down = True
            logger.info("Shutdown requested, initiating graceful shutdown...")

            # Cancel all tracked tasks
            for task in self._tasks:
                if not task.done():
                    task.cancel()

    async def shutdown_complete(self) -> None:
        """Signal shutdown is complete."""
        self._shutdown_event.set()
        logger.info("Graceful shutdown complete")

    def track_task(self, task: asyncio.Task[Any]) -> None:
        """Track a task for graceful shutdown.

        Args:
            task: Task to track
        """
        self._tasks.append(task)


async def run_with_timeout(
    coro: Coroutine[Any, Any, T],
    timeout: float,
    timeout_message: str = "Operation timed out",
) -> T:
    """Run coroutine with timeout.

    Args:
        coro: Coroutine to execute
        timeout: Timeout in seconds
        timeout_message: Error message on timeout

    Returns:
        Result of coroutine

    Raises:
        asyncio.TimeoutError: If operation times out
    """
    return await asyncio.wait_for(coro, timeout=timeout)
