"""Unit tests for error handling utilities."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanogridbot.utils.error_handling import (
    CircuitBreaker,
    GracefulShutdown,
    run_with_timeout,
    with_retry,
)


class TestWithRetryDecorator:
    """Test with_retry decorator."""

    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        """Test successful call doesn't retry."""
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.01)
        async def success():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await success()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_then_success(self):
        """Test retries then succeeds."""
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.01)
        async def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary")
            return "ok"

        result = await fail_twice()
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        """Test raises after all retries exhausted."""
        call_count = 0

        @with_retry(max_retries=2, base_delay=0.01)
        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            await always_fail()
        assert call_count == 3  # initial + 2 retries

    @pytest.mark.asyncio
    async def test_specific_exception_type(self):
        """Test only catches specified exception types."""
        call_count = 0

        @with_retry(max_retries=3, base_delay=0.01, exceptions=(ValueError,))
        async def raise_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("wrong type")

        with pytest.raises(TypeError):
            await raise_type_error()
        assert call_count == 1  # No retry for TypeError

    @pytest.mark.asyncio
    async def test_exponential_backoff_delay(self):
        """Test that delay increases exponentially."""
        delays = []

        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            delays.append(delay)

        @with_retry(max_retries=3, base_delay=1.0, exponential_base=2.0, max_delay=60.0)
        async def always_fail():
            raise ValueError("fail")

        with patch("nanogridbot.utils.error_handling.asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(ValueError):
                await always_fail()

        # Delays: 1.0 * 2^0 = 1.0, 1.0 * 2^1 = 2.0, 1.0 * 2^2 = 4.0
        assert delays == [1.0, 2.0, 4.0]

    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Test delay is capped at max_delay."""
        delays = []

        async def mock_sleep(delay):
            delays.append(delay)

        @with_retry(max_retries=3, base_delay=10.0, exponential_base=10.0, max_delay=50.0)
        async def always_fail():
            raise ValueError("fail")

        with patch("nanogridbot.utils.error_handling.asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(ValueError):
                await always_fail()

        # 10*10^0=10, 10*10^1=100→capped to 50, 10*10^2=1000→capped to 50
        assert delays == [10.0, 50.0, 50.0]

    @pytest.mark.asyncio
    async def test_zero_retries(self):
        """Test with zero retries just runs once."""
        call_count = 0

        @with_retry(max_retries=0, base_delay=0.01)
        async def fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await fail()
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        """Test decorator preserves function metadata."""

        @with_retry(max_retries=1, base_delay=0.01)
        async def my_function():
            return "ok"

        assert my_function.__name__ == "my_function"


class TestCircuitBreaker:
    """Test CircuitBreaker class."""

    def test_initial_state_closed(self):
        """Test circuit starts in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == CircuitBreaker.CLOSED

    @pytest.mark.asyncio
    async def test_success_stays_closed(self):
        """Test successful calls keep circuit closed."""
        cb = CircuitBreaker(failure_threshold=3)

        async def success():
            return "ok"

        result = await cb.call(success)
        assert result == "ok"
        assert cb.state == CircuitBreaker.CLOSED

    @pytest.mark.asyncio
    async def test_failures_open_circuit(self):
        """Test enough failures open the circuit."""
        cb = CircuitBreaker(failure_threshold=3)

        async def fail():
            raise Exception("fail")

        for _ in range(3):
            with pytest.raises(Exception):
                await cb.call(fail)

        assert cb.state == CircuitBreaker.OPEN

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self):
        """Test open circuit rejects calls immediately."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=100.0)

        async def fail():
            raise Exception("fail")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await cb.call(fail)

        assert cb.state == CircuitBreaker.OPEN

        # Next call should fail fast
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            await cb.call(fail)

    @pytest.mark.asyncio
    async def test_half_open_after_recovery_timeout(self):
        """Test circuit transitions to HALF_OPEN after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.0)

        async def fail():
            raise Exception("fail")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await cb.call(fail)

        assert cb.state == CircuitBreaker.OPEN

        # With recovery_timeout=0, next call should try half-open
        # But the call itself will fail, so it stays open
        with pytest.raises(Exception, match="fail"):
            await cb.call(fail)

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self):
        """Test successful call in HALF_OPEN closes circuit."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.0)

        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("fail")
            return "ok"

        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await cb.call(fail_then_succeed)

        assert cb.state == CircuitBreaker.OPEN

        # Recovery timeout is 0, so next call goes to HALF_OPEN and succeeds
        result = await cb.call(fail_then_succeed)
        assert result == "ok"
        assert cb.state == CircuitBreaker.CLOSED

    @pytest.mark.asyncio
    async def test_failure_count_resets_on_success(self):
        """Test failure count resets after successful call."""
        cb = CircuitBreaker(failure_threshold=3)

        async def fail():
            raise Exception("fail")

        async def success():
            return "ok"

        # Two failures
        for _ in range(2):
            with pytest.raises(Exception):
                await cb.call(fail)

        assert cb._failure_count == 2

        # One success resets
        await cb.call(success)
        assert cb._failure_count == 0
        assert cb.state == CircuitBreaker.CLOSED

    @pytest.mark.asyncio
    async def test_specific_exception_type(self):
        """Test circuit only tracks specified exception type."""
        cb = CircuitBreaker(failure_threshold=2, expected_exception=ValueError)

        async def raise_type_error():
            raise TypeError("wrong type")

        # TypeError should not be tracked by circuit breaker
        # but it will still propagate
        with pytest.raises(TypeError):
            await cb.call(raise_type_error)

        assert cb._failure_count == 0


class TestGracefulShutdown:
    """Test GracefulShutdown class."""

    def test_initial_state(self):
        """Test initial state is not shutting down."""
        gs = GracefulShutdown()
        assert gs.is_shutting_down is False

    def test_request_shutdown(self):
        """Test requesting shutdown."""
        gs = GracefulShutdown()
        gs.request_shutdown()
        assert gs.is_shutting_down is True

    def test_request_shutdown_idempotent(self):
        """Test requesting shutdown multiple times is safe."""
        gs = GracefulShutdown()
        gs.request_shutdown()
        gs.request_shutdown()
        assert gs.is_shutting_down is True

    def test_track_task(self):
        """Test tracking tasks."""
        gs = GracefulShutdown()

        task = MagicMock(spec=asyncio.Task)
        task.done.return_value = False

        gs.track_task(task)
        assert len(gs._tasks) == 1

    def test_request_shutdown_cancels_tasks(self):
        """Test shutdown cancels tracked tasks."""
        gs = GracefulShutdown()

        task1 = MagicMock(spec=asyncio.Task)
        task1.done.return_value = False
        task2 = MagicMock(spec=asyncio.Task)
        task2.done.return_value = True  # Already done

        gs.track_task(task1)
        gs.track_task(task2)
        gs.request_shutdown()

        task1.cancel.assert_called_once()
        task2.cancel.assert_not_called()

    @pytest.mark.asyncio
    async def test_shutdown_complete(self):
        """Test shutdown complete signals event."""
        gs = GracefulShutdown()

        await gs.shutdown_complete()
        assert gs._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_wait_for_shutdown(self):
        """Test waiting for shutdown signal."""
        gs = GracefulShutdown()

        async def signal_later():
            await asyncio.sleep(0.01)
            gs._shutdown_event.set()

        task = asyncio.create_task(signal_later())
        await gs.wait_for_shutdown()
        assert gs._shutdown_event.is_set()
        await task


class TestRetryAsync:
    """Test retry_async function."""

    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        """Test successful coroutine doesn't retry."""
        from nanogridbot.utils.error_handling import retry_async

        async def success():
            return "ok"

        result = await retry_async(success(), max_retries=3, base_delay=0.01)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_failure_raises(self):
        """Test failed coroutine raises after retries."""
        from nanogridbot.utils.error_handling import retry_async

        async def fail():
            raise ValueError("fail")

        with pytest.raises(ValueError, match="fail"):
            await retry_async(fail(), max_retries=0, base_delay=0.01)

    @pytest.mark.asyncio
    async def test_retry_with_delay(self):
        """Test retry_async exercises the retry-with-delay path.

        Note: retry_async takes a coroutine object (not callable), so the
        coroutine can only be awaited once. Subsequent retries get RuntimeError.
        This test verifies the retry delay path is exercised.
        """
        from nanogridbot.utils.error_handling import retry_async

        async def fail_coro():
            raise ValueError("retry me")

        delays = []
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            delays.append(delay)

        with patch("nanogridbot.utils.error_handling.asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(RuntimeError):
                await retry_async(fail_coro(), max_retries=2, base_delay=1.0)

        # Verify delays were calculated (retry path was exercised)
        assert len(delays) == 2

    @pytest.mark.asyncio
    async def test_specific_exception(self):
        """Test only catches specified exceptions."""
        from nanogridbot.utils.error_handling import retry_async

        async def raise_type_error():
            raise TypeError("wrong")

        with pytest.raises(TypeError):
            await retry_async(
                raise_type_error(), max_retries=3, base_delay=0.01, exceptions=(ValueError,)
            )


class TestRunWithTimeout:
    """Test run_with_timeout function."""

    @pytest.mark.asyncio
    async def test_completes_within_timeout(self):
        """Test coroutine completes within timeout."""

        async def quick():
            return "done"

        result = await run_with_timeout(quick(), timeout=1.0)
        assert result == "done"

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        """Test timeout raises TimeoutError."""

        async def slow():
            await asyncio.sleep(10)
            return "done"

        with pytest.raises(asyncio.TimeoutError):
            await run_with_timeout(slow(), timeout=0.01)
