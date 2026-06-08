"""Tests for background pipeline runner."""
import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.contracts import (
    PipelineGraphState,
    PipelineMode,
    SourceType,
    PipelineStatus,
)
from src.agents.runner import PipelineRunner


def test_runner_evicts_oldest_states_beyond_limit():
    """Runner should evict oldest cached states when exceeding max size.

    Tests through remember_state() helper which is called by start(),
    not by directly manipulating _last_states (which bypasses eviction).
    """
    runner = PipelineRunner(
        orchestrator=MagicMock(),
        semaphore=MagicMock(),
        state_persistence=MagicMock(),
    )

    # Use remember_state helper to go through eviction path
    for i in range(105):
        state = PipelineGraphState(
            processing_run_id=f"run-{i}",
            source_document_id=f"doc-{i}",
            mode=PipelineMode.FULL,
            source_type=SourceType.LOCAL,
            pipeline_status=PipelineStatus.COMPLETED,
        )
        runner.remember_state(f"run-{i}", state)

    assert len(runner._last_states) <= 100
    assert "run-104" in runner._last_states  # newest kept
    assert "run-0" not in runner._last_states  # oldest evicted


@pytest.fixture
def mock_orchestrator():
    return MagicMock(run=AsyncMock())


@pytest.fixture
def mock_semaphore():
    return MagicMock()


@pytest.fixture
def mock_persistence():
    return MagicMock(load=AsyncMock(), save=AsyncMock())


@pytest.fixture
def sample_state() -> PipelineGraphState:
    return PipelineGraphState(
        processing_run_id="run-123",
        source_document_id="doc-456",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
    )


@pytest.mark.asyncio
async def test_runner_executes_in_background(
    sample_state, mock_orchestrator, mock_semaphore, mock_persistence
):
    """PipelineRunner executes pipeline in background task."""
    completed_state = sample_state.model_copy(deep=True)
    completed_state.pipeline_status = PipelineStatus.AWAITING_REVIEW
    mock_orchestrator.run.return_value = completed_state

    runner = PipelineRunner(
        orchestrator=mock_orchestrator,
        semaphore=mock_semaphore,
        state_persistence=mock_persistence,
    )

    task = runner.start(sample_state)
    await task

    assert mock_orchestrator.run.called
    assert task.done()


@pytest.mark.asyncio
async def test_runner_captures_errors(
    sample_state, mock_orchestrator, mock_semaphore, mock_persistence
):
    """PipelineRunner captures and logs errors without crashing."""
    mock_orchestrator.run.side_effect = RuntimeError("Unexpected error")

    runner = PipelineRunner(
        orchestrator=mock_orchestrator,
        semaphore=mock_semaphore,
        state_persistence=mock_persistence,
    )

    task = runner.start(sample_state)
    await task

    assert task.done()
    final_state = runner.get_last_state_cached("run-123")
    assert final_state is not None
    assert final_state.error_message is not None
    assert "Unexpected error" in final_state.error_message


@pytest.mark.asyncio
async def test_runner_get_last_state_falls_back_to_db(
    sample_state, mock_orchestrator, mock_semaphore, mock_persistence
):
    """get_last_state falls back to PostgreSQL when in-memory cache misses."""
    db_state = sample_state.model_copy(deep=True)
    db_state.pipeline_status = PipelineStatus.AWAITING_REVIEW
    mock_persistence.load.return_value = db_state

    runner = PipelineRunner(
        orchestrator=mock_orchestrator,
        semaphore=mock_semaphore,
        state_persistence=mock_persistence,
    )

    # Not in memory cache
    result = await runner.get_last_state("unknown-run")

    assert result is not None
    assert result.pipeline_status == PipelineStatus.AWAITING_REVIEW
    mock_persistence.load.assert_called_once_with("unknown-run")


@pytest.mark.asyncio
async def test_runner_get_last_state_returns_none(
    sample_state, mock_orchestrator, mock_semaphore, mock_persistence
):
    """get_last_state returns None when neither memory nor DB has the run."""
    mock_persistence.load.return_value = None

    runner = PipelineRunner(
        orchestrator=mock_orchestrator,
        semaphore=mock_semaphore,
        state_persistence=mock_persistence,
    )

    result = await runner.get_last_state("nonexistent-run")

    assert result is None


@pytest.mark.asyncio
async def test_cleanup_identity_check_prevents_stale_task_removal(
    sample_state, mock_orchestrator, mock_semaphore, mock_persistence
):
    """Old task cleanup must not remove a new task started with the same run_id."""
    # First run: completes immediately
    completed = sample_state.model_copy(deep=True)
    completed.pipeline_status = PipelineStatus.COMPLETED
    mock_orchestrator.run.return_value = completed

    runner = PipelineRunner(
        orchestrator=mock_orchestrator,
        semaphore=mock_semaphore,
        state_persistence=mock_persistence,
    )

    task1 = runner.start(sample_state)
    await task1
    assert task1.done()

    # Second run with same run_id: still active
    running_state = sample_state.model_copy(deep=True)
    running_state.pipeline_status = PipelineStatus.RUNNING
    mock_orchestrator.run.return_value = running_state

    task2 = runner.start(sample_state)
    # task1's cleanup already ran; task2 must still be tracked
    assert runner._active_tasks.get("run-123") is task2
    task2.cancel()
    try:
        await task2
    except asyncio.CancelledError:
        pass


def test_is_running_for_source_ignores_terminal_states(sample_state):
    """is_running_for_source must not match COMPLETED or FAILED states.

    Validates the _ACTIVE_STATUSES filter by registering a fake task that
    appears active (is_running=True) but whose cached state is terminal.
    Without the status filter this would incorrectly block resubmission.
    """
    runner = PipelineRunner(
        orchestrator=MagicMock(),
        semaphore=MagicMock(),
        state_persistence=MagicMock(),
    )

    # Insert a COMPLETED state and register a fake "active" task for the
    # same run_id so is_running() would return True if not for the filter.
    completed = sample_state.model_copy(deep=True)
    completed.pipeline_status = PipelineStatus.COMPLETED
    completed.source_key = "test-query"
    runner.remember_state("run-done", completed)

    fake_task = MagicMock()
    fake_task.done.return_value = False
    runner._active_tasks["run-done"] = fake_task

    # The status filter should reject COMPLETED even though is_running is True.
    assert runner.is_running_for_source("test-query") is False

    # FAILED state should also be rejected with an active task.
    failed = sample_state.model_copy(deep=True)
    failed.pipeline_status = PipelineStatus.FAILED
    failed.source_key = "test-query"
    runner.remember_state("run-failed", failed)

    fake_task2 = MagicMock()
    fake_task2.done.return_value = False
    runner._active_tasks["run-failed"] = fake_task2

    assert runner.is_running_for_source("test-query") is False


@pytest.mark.asyncio
async def test_cancelled_task_persists_failed_state(
    sample_state, mock_semaphore, mock_persistence
):
    """Cancelled pipeline must record FAILED state and persist it."""
    orch = MagicMock()
    reached_orchestrator = asyncio.Event()
    hang_forever: asyncio.Future[None] = asyncio.get_running_loop().create_future()

    async def _hang(_state: object) -> None:
        reached_orchestrator.set()
        await hang_forever

    orch.run = AsyncMock(side_effect=_hang)

    runner = PipelineRunner(
        orchestrator=orch,
        semaphore=mock_semaphore,
        state_persistence=mock_persistence,
    )

    task = runner.start(sample_state)
    await reached_orchestrator.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    final_state = runner.get_last_state_cached("run-123")
    assert final_state is not None
    assert final_state.pipeline_status == PipelineStatus.FAILED
    assert "cancelled" in (final_state.error_message or "").lower()


@pytest.mark.asyncio
async def test_cancelled_task_preserves_current_phase(
    sample_state, mock_semaphore, mock_persistence
):
    """Cancelled pipeline must report the phase that was actually running, not phase 0."""
    orch = MagicMock()
    reached_orchestrator = asyncio.Event()
    hang_forever: asyncio.Future[None] = asyncio.get_running_loop().create_future()

    async def _hang(state: object) -> None:
        # Simulate the orchestrator having progressed to phase 2 by
        # updating the cached state before hanging.
        from src.agents.contracts import PipelineGraphState
        if isinstance(state, PipelineGraphState):
            state.error_phase = 2
        reached_orchestrator.set()
        await hang_forever

    orch.run = AsyncMock(side_effect=_hang)

    runner = PipelineRunner(
        orchestrator=orch,
        semaphore=mock_semaphore,
        state_persistence=mock_persistence,
    )

    task = runner.start(sample_state)
    await reached_orchestrator.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    final_state = runner.get_last_state_cached("run-123")
    assert final_state is not None
    assert final_state.error_phase == 2  # not 0


@pytest.mark.asyncio
async def test_get_last_state_marks_orphaned_run_as_failed(
    sample_state, mock_orchestrator, mock_semaphore, mock_persistence
):
    """get_last_state marks DB-loaded RUNNING runs as FAILED when no task exists."""
    # DB returns a RUNNING state (server restarted mid-pipeline)
    db_state = sample_state.model_copy(deep=True)
    db_state.pipeline_status = PipelineStatus.RUNNING
    mock_persistence.load.return_value = db_state

    runner = PipelineRunner(
        orchestrator=mock_orchestrator,
        semaphore=mock_semaphore,
        state_persistence=mock_persistence,
    )

    result = await runner.get_last_state("run-123")

    assert result is not None
    assert result.pipeline_status == PipelineStatus.FAILED
    assert "server restart" in (result.error_message or "").lower()
    # Should be persisted and cached
    mock_persistence.save.assert_called_once()
    assert runner.get_last_state_cached("run-123") is result


@pytest.mark.asyncio
async def test_get_last_state_does_not_mark_active_run_as_failed(
    sample_state, mock_semaphore, mock_persistence
):
    """get_last_state must NOT mark a run as FAILED if an active task exists."""
    db_state = sample_state.model_copy(deep=True)
    db_state.pipeline_status = PipelineStatus.RUNNING
    mock_persistence.load.return_value = db_state

    orch = MagicMock()
    hang: asyncio.Future[None] = asyncio.get_running_loop().create_future()

    async def _hang(_state: object) -> None:
        await hang

    orch.run = AsyncMock(side_effect=_hang)

    runner = PipelineRunner(
        orchestrator=orch,
        semaphore=mock_semaphore,
        state_persistence=mock_persistence,
    )

    # Start a real task so is_running returns True
    task = runner.start(sample_state)
    # Give the task a moment to start
    await asyncio.sleep(0.01)

    # Clear cache so get_last_state falls back to DB
    runner._last_states.clear()

    result = await runner.get_last_state("run-123")
    assert result is not None
    assert result.pipeline_status == PipelineStatus.RUNNING

    # Cleanup
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_recover_orphaned_runs(sample_state, mock_orchestrator, mock_semaphore, mock_persistence):
    """recover_orphaned_runs delegates to persistence layer."""
    mock_persistence.recover_orphaned_runs = AsyncMock(return_value=2)

    runner = PipelineRunner(
        orchestrator=mock_orchestrator,
        semaphore=mock_semaphore,
        state_persistence=mock_persistence,
    )

    count = await runner.recover_orphaned_runs()
    assert count == 2
    mock_persistence.recover_orphaned_runs.assert_called_once()
