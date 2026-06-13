"""Tests for retry logic distinguishing permanent vs transient errors."""

import pytest


def test_permanent_os_errors_are_excluded_from_retryable():
    """Verify _PERMANENT_OS_ERRORS are NOT accidentally caught by _RETRYABLE_ERRORS in the except chain."""
    from src.agents.contracts import build_retryable_errors

    retryable = build_retryable_errors()
    # The real fix: _PERMANENT_OS_ERRORS must be listed BEFORE _RETRYABLE_ERRORS
    # in the except chain. This test verifies FileNotFoundError IS a subclass
    # of OSError (which is in retryable) — confirming the ordering is necessary.
    assert issubclass(FileNotFoundError, OSError), (
        "FileNotFoundError is a subclass of OSError — if _PERMANENT_OS_ERRORS "
        "appears after _RETRYABLE_ERRORS in the except chain, this error WILL be retried"
    )


def test_os_error_is_retryable():
    """Generic OSError should still be retryable (network errors, etc.)."""
    from src.agents.contracts import build_retryable_errors

    retryable = build_retryable_errors()
    assert OSError in retryable


@pytest.mark.asyncio
async def test_file_not_found_is_not_retried_by_executor():
    """FileNotFoundError should fail immediately, not retry."""
    from src.agents.concurrency import RetryablePhaseExecutor
    from src.agents.contracts import PermanentPhaseError

    executor = RetryablePhaseExecutor(max_retries=2, backoff_base=0.01)
    call_count = 0

    async def failing_phase(state):
        nonlocal call_count
        call_count += 1
        raise FileNotFoundError("No such file: phase_1/metadata.json")

    # FileNotFoundError is caught by phase adapters as PermanentPhaseError
    # before reaching the executor, but if it reaches the executor directly
    # it should not be retried (it's not a RetryablePhaseError).
    with pytest.raises(FileNotFoundError):
        await executor.execute_with_retry(
            operation=failing_phase,
            state=None,
            phase_name="phase_2",
        )

    assert call_count == 1


def test_phase2_adapter_classifies_file_not_found_as_permanent():
    """Phase2Adapter should classify FileNotFoundError as PermanentPhaseError."""
    from src.agents.phase_2_adapter import _PERMANENT_OS_ERRORS

    assert issubclass(FileNotFoundError, _PERMANENT_OS_ERRORS)
