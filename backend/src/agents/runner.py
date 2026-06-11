"""Background pipeline runner with asyncio task management and DB fallback."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from src.agents.concurrency import PipelineSemaphore
from src.agents.contracts import PipelineGraphState, PipelineStatus
from src.agents.state_persistence import SessionBoundStatePersistence, _derive_error_phase


class PipelineRunner:
    """Manages background execution of pipeline runs.

    Each run executes as an asyncio.Task with semaphore-controlled concurrency.
    get_last_state() checks in-memory cache first, then falls back to PostgreSQL
    for crash recovery scenarios.
    """

    _MAX_CACHED_STATES = 100
    _ACTIVE_STATUSES = frozenset({PipelineStatus.PENDING, PipelineStatus.RUNNING})

    def __init__(
        self,
        orchestrator: Any,
        semaphore: PipelineSemaphore,
        state_persistence: SessionBoundStatePersistence,
    ):
        self._orchestrator = orchestrator
        self._semaphore = semaphore
        self._persistence = state_persistence
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._last_states: OrderedDict[str, PipelineGraphState] = OrderedDict()

    def remember_state(self, run_id: str, state: PipelineGraphState) -> None:
        """Store a state in the cache, evicting the oldest if over limit."""
        self._last_states[run_id] = state
        self._last_states.move_to_end(run_id)
        while len(self._last_states) > self._MAX_CACHED_STATES:
            self._last_states.popitem(last=False)

    def start(self, initial_state: PipelineGraphState) -> asyncio.Task:
        """Start a pipeline run as a background task."""
        run_id = initial_state.processing_run_id

        async def _run_pipeline():
            # N12 fix: Persist initial PENDING state before acquiring semaphore
            # so status endpoint can find the run even while queued.
            await self._persistence.save(initial_state)
            self.remember_state(run_id, initial_state)
            async with self._semaphore:
                logger.info("Pipeline execution started: run={}", run_id)
                try:
                    result = await self._orchestrator.run(initial_state)
                    self.remember_state(run_id, result)
                    logger.info("Pipeline execution completed: run={}", run_id)
                    return result
                except (Exception, asyncio.CancelledError) as e:
                    is_cancel = isinstance(e, asyncio.CancelledError)
                    log_fn = logger.warning if is_cancel else logger.exception
                    log_fn("Pipeline {}cancelled: run={}", "cancel " if is_cancel else "failed ", run_id)
                    # Derive the current phase from the last-notified state so the
                    # error report reflects which phase was actually interrupted.
                    last_state = self._last_states.get(run_id)
                    if last_state is not None:
                        current_phase = (
                            last_state.error_phase
                            if last_state.error_phase is not None
                            else _derive_error_phase(last_state)
                        )
                    else:
                        current_phase = 0
                    error_state = initial_state.model_copy(
                        update={
                            "pipeline_status": PipelineStatus.FAILED,
                            "error_message": f"Pipeline {'cancelled' if is_cancel else 'failed'}: {e}",
                            "error_phase": current_phase,
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    self.remember_state(run_id, error_state)
                    try:
                        await self._persistence.save(error_state)
                    except Exception:
                        logger.exception(
                            "Failed to persist error state for run={}", run_id
                        )
                    if is_cancel:
                        raise
                    return error_state

        task = asyncio.create_task(_run_pipeline())
        self._active_tasks[run_id] = task

        def _cleanup(t: asyncio.Task):
            # Only remove if this is still the current task for this run_id.
            # A new task with the same run_id may have replaced it.
            if self._active_tasks.get(run_id) is t:
                del self._active_tasks[run_id]

        task.add_done_callback(_cleanup)

        return task

    def get_last_state_cached(self, processing_run_id: str) -> PipelineGraphState | None:
        """Get state from in-memory cache only (fast path)."""
        return self._last_states.get(processing_run_id)

    async def get_last_state(self, processing_run_id: str) -> PipelineGraphState | None:
        """Get the last known state for a pipeline run.

        Checks in-memory cache first (fast path), then falls back to
        PostgreSQL for crash recovery scenarios.  If a run loaded from
        the DB shows an active status but no task is running (server
        restarted mid-pipeline), it is marked FAILED before returning.
        """
        # Check in-memory first
        cached = self._last_states.get(processing_run_id)
        if cached is not None:
            return cached

        # Fall back to database (crash recovery)
        state = await self._persistence.load(processing_run_id)
        if state is None:
            return None

        # Runtime guard: DB says active but no task exists → orphaned run
        if state.pipeline_status in self._ACTIVE_STATUSES and not self.is_running(processing_run_id):
            logger.warning(
                "Orphaned run detected on status poll: run={}, status={}",
                processing_run_id, state.pipeline_status.value,
            )
            state.pipeline_status = PipelineStatus.FAILED
            state.error_message = "Pipeline interrupted by server restart"
            state.error_phase = _derive_error_phase(state)
            state.completed_at = datetime.now(timezone.utc).isoformat()
            self.remember_state(processing_run_id, state)
            try:
                await self._persistence.save(state)
            except Exception:
                logger.exception("Failed to persist orphaned run state: run={}", processing_run_id)
            return state

        return state

    def is_running(self, processing_run_id: str) -> bool:
        """Check if a pipeline run is currently active."""
        task = self._active_tasks.get(processing_run_id)
        return task is not None and not task.done()

    async def recover_orphaned_runs(self) -> int:
        """Mark runs stuck in non-terminal states as FAILED after server restart."""
        return await self._persistence.recover_orphaned_runs()

    async def shutdown(self, timeout: float = 60.0) -> None:
        """Wait for active pipeline tasks to complete before server shutdown.

        Called during FastAPI lifespan teardown so that in-flight LLM calls
        can finish and persist their state to PostgreSQL before the DB engine
        is disposed.  Without this, ``uvicorn --reload`` or SIGTERM cancels
        the asyncio tasks immediately, leaving orphaned runs in the database.

        After the grace timeout expires, pending tasks are explicitly cancelled
        and given a short window to persist their FAILED state before the DB
        engine is disposed.

        Args:
            timeout: Maximum seconds to wait per task.  Should be at least
                as long as the LLM timeout (default 60s) to avoid cancelling
                requests that would have succeeded.
        """
        active = {rid: t for rid, t in self._active_tasks.items() if not t.done()}
        if not active:
            return

        logger.info("Graceful shutdown: waiting for {} active pipeline task(s) (timeout={}s)", len(active), timeout)
        tasks = list(active.values())
        done, pending = await asyncio.wait(tasks, timeout=timeout)

        for rid, task in active.items():
            if task in done:
                exc = task.exception() if not task.cancelled() else None
                if exc:
                    logger.warning("Pipeline run {} finished with error during shutdown: {}", rid, exc)
                else:
                    logger.info("Pipeline run {} completed during shutdown", rid)

        if pending:
            pending_ids = [rid for rid, t in active.items() if t in pending]
            logger.warning(
                "Cancelling {} pipeline task(s) that exceeded shutdown timeout: {}",
                len(pending), pending_ids,
            )
            for task in pending:
                task.cancel()
            # Brief grace period for CancelledError handlers to persist FAILED state.
            await asyncio.wait(pending, timeout=5.0)
            for rid, task in active.items():
                if task in pending and not task.done():
                    logger.error("Pipeline run {} could not be cancelled before shutdown", rid)

    def is_running_for_source(self, source_key: str) -> bool:
        """Check if any active run is processing this source key (N3 fix).

        Compares against state.source_key (filename or query), not
        source_document_id (UUID), so the API route can dedup by
        user-visible identifiers.
        """
        for run_id, state in self._last_states.items():
            if (
                state.source_key == source_key
                # Status check filters out terminal states (COMPLETED/FAILED) so
                # stale cache entries don't falsely block new submissions.
                and state.pipeline_status in self._ACTIVE_STATUSES
                # is_running() is still needed: CancelledError (BaseException)
                # may leave status as PENDING while the task is already done.
                and self.is_running(run_id)
            ):
                return True
        return False
