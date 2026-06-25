"""Tests for the pipeline job queue and single-job dispatcher.

Unit tests use mocked persistence (SQLite doesn't support FOR UPDATE SKIP LOCKED).
Integration tests with PostgreSQL can be added separately.
"""
from __future__ import annotations

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.contracts import (
    PipelineGraphState,
    PipelineMode,
    PipelineStatus,
    SourceType,
)
from src.agents.dispatcher import SingleJobDispatcher
from src.dao.postgresql.job_queue import JobQueueRepository, JobRow


# ── Dispatcher tests ────────────────────────────────────────────────────────


@pytest.fixture
def mock_runner():
    runner = MagicMock()
    runner.start = AsyncMock()
    return runner


@pytest.fixture
def mock_job_queue():
    jq = MagicMock(spec=JobQueueRepository)
    jq.claim_next = AsyncMock()
    jq.complete = AsyncMock()
    jq.fail = AsyncMock()
    return jq


def _make_job(
    job_id: str = "job-1",
    processing_run_id: str = "run-1",
    source_document_id: str = "doc-1",
    request_data: dict | None = None,
) -> JobRow:
    return JobRow(
        job_id=job_id,
        processing_run_id=processing_run_id,
        source_document_id=source_document_id,
        request_data=request_data or {
            "mode": "full",
            "source_type": "local",
            "created_at": "2026-06-25T00:00:00",
        },
    )


def _completed_state(run_id: str = "run-1") -> PipelineGraphState:
    return PipelineGraphState(
        processing_run_id=run_id,
        source_document_id="doc-1",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.COMPLETED,
    )


def _failed_state(run_id: str = "run-1") -> PipelineGraphState:
    return PipelineGraphState(
        processing_run_id=run_id,
        source_document_id="doc-1",
        mode=PipelineMode.FULL,
        source_type=SourceType.LOCAL,
        pipeline_status=PipelineStatus.FAILED,
        error_message="Something went wrong",
    )


@pytest.mark.asyncio
async def test_dispatcher_single_running_job(mock_runner, mock_job_queue):
    """Only one job runs at a time; next is claimed only after current completes."""
    call_count = 0

    async def claim_sequence(*args):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_job("job-1", "run-1")
        if call_count == 2:
            return _make_job("job-2", "run-2")
        return None  # no more jobs

    mock_job_queue.claim_next = AsyncMock(side_effect=claim_sequence)
    completed = _completed_state()
    task = asyncio.get_running_loop().create_future()
    task.set_result(completed)
    mock_runner.start = AsyncMock(return_value=task)

    dispatcher = SingleJobDispatcher(
        runner=mock_runner,
        job_queue=mock_job_queue,
        poll_interval=0.01,
    )
    dispatcher._stopping = False

    # Run the loop for a short while, then stop
    loop_task = asyncio.create_task(dispatcher._loop())
    await asyncio.sleep(0.1)
    dispatcher._stopping = True
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    # Both jobs should have been completed
    assert mock_job_queue.complete.await_count == 2
    mock_job_queue.complete.assert_any_await("job-1")
    mock_job_queue.complete.assert_any_await("job-2")


@pytest.mark.asyncio
async def test_dispatcher_fifo_order(mock_runner, mock_job_queue):
    """Jobs are claimed in FIFO order (priority then created_at)."""
    claimed_order = []

    async def claim_sequence(*args):
        if len(claimed_order) == 0:
            job = _make_job("job-first", "run-1")
            claimed_order.append("job-first")
            return job
        if len(claimed_order) == 1:
            job = _make_job("job-second", "run-2")
            claimed_order.append("job-second")
            return job
        return None

    mock_job_queue.claim_next = AsyncMock(side_effect=claim_sequence)
    completed = _completed_state()
    task = asyncio.get_running_loop().create_future()
    task.set_result(completed)
    mock_runner.start = AsyncMock(return_value=task)

    dispatcher = SingleJobDispatcher(
        runner=mock_runner,
        job_queue=mock_job_queue,
        poll_interval=0.01,
    )
    dispatcher._stopping = False

    loop_task = asyncio.create_task(dispatcher._loop())
    await asyncio.sleep(0.1)
    dispatcher._stopping = True
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    assert claimed_order == ["job-first", "job-second"]


@pytest.mark.asyncio
async def test_dispatcher_failed_job_does_not_block_queue(mock_runner, mock_job_queue):
    """A failed job is marked as failed and the dispatcher moves to the next."""
    call_count = 0

    async def claim_sequence(*args):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_job("job-fail", "run-1")
        if call_count == 2:
            return _make_job("job-ok", "run-2")
        return None

    mock_job_queue.claim_next = AsyncMock(side_effect=claim_sequence)

    failed = _failed_state("run-1")
    failed_task = asyncio.get_running_loop().create_future()
    failed_task.set_result(failed)
    completed = _completed_state("run-2")
    completed_task = asyncio.get_running_loop().create_future()
    completed_task.set_result(completed)

    mock_runner.start = AsyncMock(side_effect=[failed_task, completed_task])

    dispatcher = SingleJobDispatcher(
        runner=mock_runner,
        job_queue=mock_job_queue,
        poll_interval=0.01,
    )
    dispatcher._stopping = False

    loop_task = asyncio.create_task(dispatcher._loop())
    await asyncio.sleep(0.1)
    dispatcher._stopping = True
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    # Failed job marked as failed, second job completed
    mock_job_queue.fail.assert_awaited_once_with("job-fail", "Something went wrong")
    mock_job_queue.complete.assert_awaited_once_with("job-ok")


@pytest.mark.asyncio
async def test_dispatcher_runner_exception_marks_job_failed(mock_runner, mock_job_queue):
    """Exception from runner.start() is caught and job is marked as failed."""
    mock_job_queue.claim_next = AsyncMock(
        side_effect=[_make_job("job-crash", "run-1"), None]
    )

    error_task = asyncio.get_running_loop().create_future()
    error_task.set_exception(RuntimeError("LLM timeout"))
    mock_runner.start = AsyncMock(return_value=error_task)

    dispatcher = SingleJobDispatcher(
        runner=mock_runner,
        job_queue=mock_job_queue,
        poll_interval=0.01,
    )
    dispatcher._stopping = False

    loop_task = asyncio.create_task(dispatcher._loop())
    await asyncio.sleep(0.1)
    dispatcher._stopping = True
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    mock_job_queue.fail.assert_awaited()
    call_args = mock_job_queue.fail.call_args
    assert call_args[0][0] == "job-crash"
    assert "LLM timeout" in call_args[0][1]


@pytest.mark.asyncio
async def test_dispatcher_only_one_running_at_a_time(mock_runner, mock_job_queue):
    """The dispatcher processes jobs sequentially, never concurrently."""
    running_timestamps: list[float] = []
    import time

    async def slow_claim(*args):
        if len(running_timestamps) >= 2:
            return None
        return _make_job(f"job-{len(running_timestamps)}", f"run-{len(running_timestamps)}")

    async def slow_start(state):
        running_timestamps.append(time.monotonic())
        await asyncio.sleep(0.05)
        return _completed_state(state.processing_run_id)

    mock_job_queue.claim_next = AsyncMock(side_effect=slow_claim)
    mock_runner.start = AsyncMock(side_effect=slow_start)

    dispatcher = SingleJobDispatcher(
        runner=mock_runner,
        job_queue=mock_job_queue,
        poll_interval=0.01,
    )
    dispatcher._stopping = False

    loop_task = asyncio.create_task(dispatcher._loop())
    await asyncio.sleep(0.2)
    dispatcher._stopping = True
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    # Jobs must not overlap: second starts after first finishes
    assert len(running_timestamps) == 2
    assert running_timestamps[1] - running_timestamps[0] >= 0.04


@pytest.mark.asyncio
async def test_dispatcher_cleans_up_temp_file(mock_runner, mock_job_queue):
    """Upload temp files are cleaned up after job execution."""
    mock_job_queue.claim_next = AsyncMock(
        side_effect=[
            _make_job("job-1", "run-1", request_data={
                "mode": "full",
                "source_type": "local",
                "upload_file_path": "/tmp/fake_upload.pdf",
                "created_at": "2026-06-25T00:00:00",
            }),
            None,
        ]
    )
    completed = _completed_state()
    task = asyncio.get_running_loop().create_future()
    task.set_result(completed)
    mock_runner.start = AsyncMock(return_value=task)

    dispatcher = SingleJobDispatcher(
        runner=mock_runner,
        job_queue=mock_job_queue,
        poll_interval=0.01,
    )
    dispatcher._stopping = False

    with patch("src.agents.dispatcher.Path") as mock_path_cls:
        mock_path = MagicMock()
        mock_path_cls.return_value = mock_path
        loop_task = asyncio.create_task(dispatcher._loop())
        await asyncio.sleep(0.1)
        dispatcher._stopping = True
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass

        # Temp file unlink was attempted
        mock_path.unlink.assert_called_once_with(missing_ok=True)


@pytest.mark.asyncio
async def test_dispatcher_invalid_request_data_marks_failed(mock_runner, mock_job_queue):
    """Invalid request data (e.g. bad enum) marks the job as failed."""
    mock_job_queue.claim_next = AsyncMock(
        side_effect=[
            _make_job("job-bad", "run-1", request_data={
                "mode": "INVALID_MODE",
                "source_type": "local",
                "created_at": "2026-06-25T00:00:00",
            }),
            None,
        ]
    )

    dispatcher = SingleJobDispatcher(
        runner=mock_runner,
        job_queue=mock_job_queue,
        poll_interval=0.01,
    )
    dispatcher._stopping = False

    loop_task = asyncio.create_task(dispatcher._loop())
    await asyncio.sleep(0.1)
    dispatcher._stopping = True
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    mock_job_queue.fail.assert_awaited_once()
    assert "Invalid request data" in mock_job_queue.fail.call_args[0][1]


@pytest.mark.asyncio
async def test_dispatcher_start_stop_lifecycle(mock_runner, mock_job_queue):
    """Dispatcher can be started and stopped cleanly."""
    mock_job_queue.claim_next = AsyncMock(return_value=None)

    dispatcher = SingleJobDispatcher(
        runner=mock_runner,
        job_queue=mock_job_queue,
        poll_interval=0.01,
    )

    dispatcher.start()
    assert dispatcher._task is not None
    assert not dispatcher._task.done()

    await dispatcher.stop(timeout=1.0)
    assert dispatcher._task is None


@pytest.mark.asyncio
async def test_dispatcher_recovery_after_restart(mock_runner, mock_job_queue):
    """After restart, dispatcher picks up queued jobs from DB.

    This simulates the scenario: a job was enqueued, server restarted,
    and the dispatcher starts fresh — it should still claim the queued job.
    """
    mock_job_queue.claim_next = AsyncMock(
        side_effect=[_make_job("job-old", "run-old"), None]
    )
    completed = _completed_state("run-old")
    task = asyncio.get_running_loop().create_future()
    task.set_result(completed)
    mock_runner.start = AsyncMock(return_value=task)

    dispatcher = SingleJobDispatcher(
        runner=mock_runner,
        job_queue=mock_job_queue,
        poll_interval=0.01,
    )
    dispatcher._stopping = False

    loop_task = asyncio.create_task(dispatcher._loop())
    await asyncio.sleep(0.1)
    dispatcher._stopping = True
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    mock_job_queue.complete.assert_awaited_once_with("job-old")
