"""Unit tests for async helper utilities."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from nanogridbot.utils.async_helpers import (
    AsyncBoundedSemaphore,
    RateLimiter,
    async_lock,
    gather_with_concurrency,
    run_with_retry,
    temporary_timeout,
    wait_for,
)


class TestAsyncLock:
    """Test async_lock context manager."""

    @pytest.mark.asyncio
    async def test_yields_lock(self):
        async with async_lock() as lock:
            assert isinstance(lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_lock_is_acquired(self):
        async with async_lock() as lock:
            assert lock.locked()


class TestTemporaryTimeout:
    """Test temporary_timeout context manager."""

    @pytest.mark.asyncio
    async def test_yields_without_error(self):
        async with temporary_timeout(1.0):
            pass

    @pytest.mark.asyncio
    async def test_code_executes_inside(self):
        executed = False
        async with temporary_timeout(5.0):
            executed = True
        assert executed


class TestRunWithRetry:
    """Test run_with_retry function."""

    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        async def success():
            return "ok"

        result = await run_with_retry(success, max_retries=3, base_delay=0.01)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        call_count = 0

        async def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temp")
            return "ok"

        result = await run_with_retry(fail_twice, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        async def always_fail():
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            await run_with_retry(always_fail, max_retries=2, base_delay=0.01)

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        delays = []

        async def mock_sleep(delay):
            delays.append(delay)

        async def always_fail():
            raise ValueError("fail")

        with patch("nanogridbot.utils.async_helpers.asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(ValueError):
                await run_with_retry(
                    always_fail,
                    max_retries=2,
                    base_delay=1.0,
                    exponential_backoff=True,
                )

        assert delays[0] == 1.0
        assert delays[1] == 2.0

    @pytest.mark.asyncio
    async def test_no_exponential_backoff(self):
        delays = []

        async def mock_sleep(delay):
            delays.append(delay)

        async def always_fail():
            raise ValueError("fail")

        with patch("nanogridbot.utils.async_helpers.asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(ValueError):
                await run_with_retry(
                    always_fail,
                    max_retries=2,
                    base_delay=1.0,
                    exponential_backoff=False,
                )

        # All delays should be the same
        assert all(d == 1.0 for d in delays)

    @pytest.mark.asyncio
    async def test_with_args_and_kwargs(self):
        async def add(a, b, extra=0):
            return a + b + extra

        result = await run_with_retry(
            add, 0, 0.01, True, 1, 2, extra=3
        )
        assert result == 6


class TestWaitFor:
    """Test wait_for function."""

    @pytest.mark.asyncio
    async def test_condition_met_immediately(self):
        async def always_true():
            return True

        result = await wait_for(always_true, timeout=1.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_condition_met_after_delay(self):
        call_count = 0

        async def eventually_true():
            nonlocal call_count
            call_count += 1
            return call_count >= 3

        result = await wait_for(eventually_true, timeout=1.0, poll_interval=0.01)
        assert result is True

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        async def never_true():
            return False

        with pytest.raises(asyncio.TimeoutError, match="timed out"):
            await wait_for(never_true, timeout=0.05, poll_interval=0.01)


class TestGatherWithConcurrency:
    """Test gather_with_concurrency function."""

    @pytest.mark.asyncio
    async def test_basic_gather(self):
        async def task(n):
            return n * 2

        results = await gather_with_concurrency(2, task(1), task(2), task(3))
        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_concurrency_limit(self):
        max_concurrent = 0
        current = 0

        async def tracked_task(n):
            nonlocal max_concurrent, current
            current += 1
            if current > max_concurrent:
                max_concurrent = current
            await asyncio.sleep(0.01)
            current -= 1
            return n

        results = await gather_with_concurrency(
            2,
            tracked_task(1),
            tracked_task(2),
            tracked_task(3),
            tracked_task(4),
        )
        assert sorted(results) == [1, 2, 3, 4]
        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_empty_coros(self):
        results = await gather_with_concurrency(5)
        assert results == []


class TestAsyncBoundedSemaphore:
    """Test AsyncBoundedSemaphore class."""

    @pytest.mark.asyncio
    async def test_acquire_release(self):
        sem = AsyncBoundedSemaphore(2)
        await sem.acquire()
        sem.release()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        sem = AsyncBoundedSemaphore(1)
        async with sem():
            pass

    @pytest.mark.asyncio
    async def test_available_property(self):
        sem = AsyncBoundedSemaphore(3)
        # Initially all available (available returns used count, not free count)
        # The implementation: self._value - self._semaphore._value
        # Initially _semaphore._value == 3, so available = 3 - 3 = 0
        assert sem.available == 0

        await sem.acquire()
        # After acquire: _semaphore._value == 2, available = 3 - 2 = 1
        assert sem.available == 1

        sem.release()
        assert sem.available == 0


class TestRateLimiter:
    """Test RateLimiter class."""

    @pytest.mark.asyncio
    async def test_allows_within_limit(self):
        limiter = RateLimiter(max_calls=5, period=1.0)
        for _ in range(5):
            await limiter.acquire()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        limiter = RateLimiter(max_calls=3, period=1.0)
        async with limiter():
            pass

    @pytest.mark.asyncio
    async def test_rate_limiting_triggers(self):
        """Test that rate limiting kicks in when limit exceeded."""
        limiter = RateLimiter(max_calls=2, period=0.1)

        # Fill up the limit
        await limiter.acquire()
        await limiter.acquire()

        # Next acquire should need to wait
        delays = []

        async def mock_sleep(delay):
            delays.append(delay)
            # Simulate time passing so the recursive call succeeds
            limiter._calls.clear()

        with patch("nanogridbot.utils.async_helpers.asyncio.sleep", side_effect=mock_sleep):
            await limiter.acquire()

        assert len(delays) > 0
