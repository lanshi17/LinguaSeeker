"""Tests for concurrency control and retry logic."""

import pytest
import asyncio
from unittest.mock import MagicMock
from src.agents.concurrency import PipelineSemaphore, RetryablePhaseExecutor
from src.agents.contracts import RetryablePhaseError, PermanentPhaseError, PhaseError


@pytest.mark.asyncio
async def test_semaphore_limits_concurrency():
    """Semaphore limits concurrent pipeline executions."""
    sem = PipelineSemaphore(max_concurrent=2)

    max_observed = 0
    current = 0

    async def slow_task():
        nonlocal current, max_observed
        async with sem:
            current += 1
            max_observed = max(max_observed, current)
            await asyncio.sleep(0.05)
            current -= 1
            return "done"

    tasks = [asyncio.create_task(slow_task()) for _ in range(4)]
    results = await asyncio.gather(*tasks)

    assert all(r == "done" for r in results)
    assert max_observed <= 2


@pytest.mark.asyncio
async def test_retry_executor_retries_on_retryable_error():
    """RetryablePhaseExecutor retries when operation raises RetryablePhaseError."""
    call_count = 0

    async def flaky_operation(state):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RetryablePhaseError("API timeout", phase=1, attempt=call_count - 1)
        return state

    executor = RetryablePhaseExecutor(max_retries=2, backoff_base=0.01)
    result = await executor.execute_with_retry(
        operation=flaky_operation,
        state=MagicMock(),
        phase_name="phase_1",
    )

    assert call_count == 2
    assert result is not None


@pytest.mark.asyncio
async def test_retry_executor_passes_through_permanent_errors():
    """RetryablePhaseExecutor does NOT retry PermanentPhaseError."""

    async def permanent_failure(state):
        raise PermanentPhaseError("Configuration error", phase=2)

    executor = RetryablePhaseExecutor(max_retries=2, backoff_base=0.01)

    with pytest.raises(PermanentPhaseError, match="Configuration error"):
        await executor.execute_with_retry(
            operation=permanent_failure,
            state=MagicMock(),
            phase_name="phase_2",
        )


@pytest.mark.asyncio
async def test_retry_executor_exhausts_retries():
    """RetryablePhaseExecutor raises after exhausting all retries."""
    call_count = 0

    async def always_fails(state):
        nonlocal call_count
        call_count += 1
        raise RetryablePhaseError("Always fails", phase=1, attempt=call_count - 1)

    executor = RetryablePhaseExecutor(max_retries=2, backoff_base=0.01)

    with pytest.raises(RetryablePhaseError):
        await executor.execute_with_retry(
            operation=always_fails,
            state=MagicMock(),
            phase_name="phase_1",
        )

    assert call_count == 3  # initial + 2 retries


def test_retryable_phase_error_is_phase_error():
    """RetryablePhaseError inherits from PhaseError."""
    err = RetryablePhaseError("timeout", phase=1, attempt=0)
    assert isinstance(err, PhaseError)


def test_permanent_phase_error_is_phase_error():
    """PermanentPhaseError inherits from PhaseError."""
    err = PermanentPhaseError("config error", phase=2)
    assert isinstance(err, PhaseError)
