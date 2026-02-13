"""Async helper utilities."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable, TypeVar

T = TypeVar("T")


@asynccontextmanager
async def async_lock() -> AsyncGenerator[asyncio.Lock, None]:
    """Create an async context manager for locking.

    Usage:
        async with async_lock() as lock:
            # critical section

    Yields:
        asyncio.Lock instance
    """
    lock = asyncio.Lock()
    async with lock:
        yield lock


@asynccontextmanager
async def temporary_timeout(
    timeout: float,
) -> AsyncGenerator[None, None]:
    """Temporarily change the default timeout for an async operation.

    Note: This is a placeholder. Actual implementation depends on
    the specific async operations being performed.

    Args:
        timeout: Timeout in seconds

    Yields:
        None
    """
    # Store previous timeout if applicable
    # This is a no-op implementation that can be extended
    try:
        yield
    finally:
        pass


async def run_with_retry(
    coro: Callable[..., Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
    exponential_backoff: bool = True,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Run an async coroutine with retry logic.

    Args:
        coro: Coroutine function to run
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds between retries
        exponential_backoff: Whether to use exponential backoff
        *args: Positional arguments for coro
        **kwargs: Keyword arguments for coro

    Returns:
        Result of the coroutine

    Raises:
        Last exception if all retries fail
    """
    from loguru import logger

    last_exception = None
    delay = base_delay

    for attempt in range(max_retries + 1):
        try:
            return await coro(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
                if exponential_backoff:
                    delay *= 2
            else:
                logger.error(f"All {max_retries + 1} attempts failed")

    raise last_exception


async def wait_for(
    coro: Callable[[], Any],
    timeout: float,
    poll_interval: float = 0.1,
) -> Any:
    """Wait for a condition to become true.

    Args:
        coro: Coroutine that returns True when condition is met
        timeout: Maximum time to wait in seconds
        poll_interval: Time between checks in seconds

    Returns:
        Result of coro when it returns True

    Raises:
        asyncio.TimeoutError: If timeout is reached
    """
    start_time = asyncio.get_event_loop().time()

    while True:
        result = await coro()
        if result:
            return result

        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= timeout:
            raise asyncio.TimeoutError(f"Wait timed out after {timeout}s")

        await asyncio.sleep(poll_interval)


async def gather_with_concurrency(
    max_concurrent: int,
    *coros: Any,
) -> list[Any]:
    """Run coroutines with a concurrency limit.

    Args:
        max_concurrent: Maximum number of concurrent tasks
        *coros: Coroutines to run

    Returns:
        List of results in order
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def run_with_semaphore(coro: Any) -> Any:
        async with semaphore:
            return await coro

    return await asyncio.gather(*(run_with_semaphore(c) for c in coros))


class AsyncBoundedSemaphore:
    """Async semaphore with bounded queue for fairness."""

    def __init__(self, value: int) -> None:
        self._semaphore = asyncio.Semaphore(value)
        self._waiting: list[asyncio.Task] = []
        self._value = value

    async def acquire(self) -> None:
        """Acquire the semaphore."""
        await self._semaphore.acquire()

    def release(self) -> None:
        """Release the semaphore."""
        self._semaphore.release()

    @asynccontextmanager
    async def __call__(self) -> AsyncGenerator[None, None]:
        """Context manager for acquiring and releasing."""
        await self.acquire()
        try:
            yield
        finally:
            self.release()

    @property
    def available(self) -> int:
        """Number of available slots."""
        return self._value - self._semaphore._value


class RateLimiter:
    """Rate limiter for async operations."""

    def __init__(self, max_calls: int, period: float) -> None:
        """Initialize rate limiter.

        Args:
            max_calls: Maximum calls allowed in the period
            period: Time period in seconds
        """
        self._max_calls = max_calls
        self._period = period
        self._calls: list[float] = []

    async def acquire(self) -> None:
        """Acquire permission to make a call.

        Blocks if rate limit is exceeded.
        """
        import time

        now = time.monotonic()

        # Remove old calls outside the window
        self._calls = [t for t in self._calls if now - t < self._period]

        if len(self._calls) >= self._max_calls:
            # Calculate wait time
            oldest = self._calls[0]
            wait_time = self._period - (now - oldest) + 0.01
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                return await self.acquire()

        self._calls.append(now)

    @asynccontextmanager
    async def __call__(self) -> AsyncGenerator[None, None]:
        """Context manager for rate limiting."""
        await self.acquire()
        try:
            yield
        finally:
            pass
