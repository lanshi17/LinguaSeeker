"""Background pipeline runner with asyncio task management and DB fallback."""

from __future__ import annotations

import asyncio
import os
import socket
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from src.agents.concurrency import PipelineSemaphore
from src.agents.contracts import PipelineGraphState, PipelineMode, PipelineStatus
from src.agents.content_hash import compute_content_hash
from src.agents.processing_cache import DocumentProcessingCacheService
from src.agents.state_persistence import SessionBoundStatePersistence, PipelineRunSummaryRow, _derive_error_phase


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
        processing_cache: DocumentProcessingCacheService | None = None,
        processing_cache_enabled: bool = True,
        duplicate_run_prevention_enabled: bool = True,
        worker_id: str | None = None,
        heartbeat_interval_seconds: float = 15.0,
    ):
        self._orchestrator = orchestrator
        self._semaphore = semaphore
        self._persistence = state_persistence
        self._processing_cache = processing_cache
        self._processing_cache_enabled = processing_cache_enabled
        self._duplicate_run_prevention_enabled = duplicate_run_prevention_enabled
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._last_states: OrderedDict[str, PipelineGraphState] = OrderedDict()
        self._worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}:{id(self)}"
        self._heartbeat_interval = heartbeat_interval_seconds

    @property
    def processing_cache_enabled(self) -> bool:
        """Return whether completed pipeline result caching is enabled."""
        return self._processing_cache_enabled

    @property
    def duplicate_run_prevention_enabled(self) -> bool:
        """Return whether active source-key deduplication is enabled."""
        return self._duplicate_run_prevention_enabled

    def remember_state(self, run_id: str, state: PipelineGraphState) -> None:
        """Store a state in the cache, evicting the oldest if over limit."""
        self._last_states[run_id] = state
        self._last_states.move_to_end(run_id)
        while len(self._last_states) > self._MAX_CACHED_STATES:
            self._last_states.popitem(last=False)

    def _start_heartbeat(self, run_id: str) -> asyncio.Task | None:
        """Start the heartbeat background task for a pipeline run."""
        try:

            async def _heartbeat_loop():
                consecutive_failures = 0
                while True:
                    await asyncio.sleep(self._heartbeat_interval)
                    try:
                        await self._persistence.heartbeat(run_id, self._worker_id)
                        consecutive_failures = 0
                    except Exception:
                        consecutive_failures += 1
                        logger.warning(
                            "Heartbeat failed for run={} (consecutive failures: {})",
                            run_id,
                            consecutive_failures,
                        )

            return asyncio.create_task(_heartbeat_loop())
        except Exception:
            logger.warning("Heartbeat task creation failed for run={}", run_id)
            return None

    async def start(self, initial_state: PipelineGraphState) -> asyncio.Task:
        """Start a pipeline run as a background task.

        Performs initial durable claim (with ownership metadata) before scheduling
        the background task. IntegrityError from the first save propagates to the
        API route as the race-proof duplicate-source guard.
        """
        run_id = initial_state.processing_run_id
        now = datetime.now(timezone.utc)

        if initial_state.mode == PipelineMode.PHASE and initial_state.target_phase is not None:
            await self._persistence.reset_phase_rerun_artifacts(
                processing_run_id=initial_state.processing_run_id,
                source_document_id=initial_state.source_document_id,
                target_phase=initial_state.target_phase,
            )

        # Durable claim: persist initial state with ownership before background task
        await self._persistence.save(
            initial_state,
            owner_worker_id=self._worker_id,
            heartbeat_at=now,
        )
        # Overwrite cache for phase reruns (old terminal → new pending),
        # but preserve non-terminal cached states that may be newer
        # (e.g. set by on_state_change during a previous run).
        cached = self._last_states.get(run_id)
        if cached is None or cached.pipeline_status not in self._ACTIVE_STATUSES:
            self.remember_state(run_id, initial_state)

        async def _run_pipeline():
            heartbeat_task = self._start_heartbeat(run_id)

            logger.info("Pipeline execution started: run={}", run_id)
            try:
                async with self._semaphore:
                    result = await self._orchestrator.run(initial_state)
                self.remember_state(run_id, result)
                logger.info("Pipeline execution completed: run={}", run_id)
                # Cache completed result for dedup on identical future submissions
                if self._processing_cache_enabled and self._processing_cache is not None and initial_state.content_hash:
                    try:
                        await self._processing_cache.cache_result(initial_state.content_hash, result)
                    except Exception:
                        logger.exception("Failed to cache processing result for run={}", run_id)
                return result
            except (Exception, asyncio.CancelledError) as e:
                is_cancel = isinstance(e, asyncio.CancelledError)
                log_fn = logger.warning if is_cancel else logger.exception
                log_fn("Pipeline {}cancelled: run={}", "cancel " if is_cancel else "failed ", run_id)
                # Use latest cached state as base so error preserves phase outputs
                last_state = self._last_states.get(run_id)
                base_state = last_state if last_state is not None else initial_state
                current_phase = (
                    base_state.error_phase if base_state.error_phase is not None else _derive_error_phase(base_state)
                )
                error_state = base_state.model_copy(
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
                    logger.exception("Failed to persist error state for run={}", run_id)
                if is_cancel:
                    raise
                return error_state
            finally:
                if heartbeat_task is not None:
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except (asyncio.CancelledError, Exception):
                        pass

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
        PostgreSQL for crash recovery scenarios.  Read-only: never mutates
        a run loaded from DB — stale active rows are handled by heartbeat
        recovery, not by GET-triggered writes.
        """
        # Check in-memory first
        cached = self._last_states.get(processing_run_id)
        if cached is not None:
            return cached

        # Fall back to database (crash recovery) — read-only
        state = await self._persistence.load(processing_run_id)
        if state is not None and state.pipeline_status not in self._ACTIVE_STATUSES:
            # Only cache terminal states from DB; active states owned by
            # another worker would become stale if cached here.
            self.remember_state(processing_run_id, state)
        return state

    def is_running(self, processing_run_id: str) -> bool:
        """Check if a pipeline run is currently active."""
        task = self._active_tasks.get(processing_run_id)
        return task is not None and not task.done()

    async def recover_orphaned_runs(self, *, heartbeat_timeout_seconds: int = 300) -> int:
        """Mark runs stuck in non-terminal states as FAILED after server restart."""
        return await self._persistence.recover_orphaned_runs(heartbeat_timeout_seconds=heartbeat_timeout_seconds)

    async def list_runs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        search: str | None = None,
    ) -> tuple[list[PipelineRunSummaryRow], int]:
        """List pipeline run summaries (newest first)."""
        return await self._persistence.list_runs(
            limit=limit,
            offset=offset,
            status=status,
            search=search,
        )

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
                len(pending),
                pending_ids,
            )
            for task in pending:
                task.cancel()
            # Brief grace period for CancelledError handlers to persist FAILED state.
            await asyncio.wait(pending, timeout=5.0)
            for rid, task in active.items():
                if task in pending and not task.done():
                    logger.error("Pipeline run {} could not be cancelled before shutdown", rid)

    async def is_running_for_source(self, source_key: str) -> bool:
        """Check if any active run is processing this source key (N3 fix).

        Compares against state.source_key (filename or query), not
        source_document_id (UUID), so the API route can dedup by
        user-visible identifiers.  Falls back to persistence for
        cross-worker dedup when the in-memory cache misses.
        """
        if not self._duplicate_run_prevention_enabled:
            return False
        for run_id, state in self._last_states.items():
            if (
                state.source_key == source_key
                and state.pipeline_status in self._ACTIVE_STATUSES
                and self.is_running(run_id)
            ):
                return True
        # Cross-worker dedup: check persistence for active source keys
        return await self._persistence.has_active_source_key(source_key)

    async def check_processing_cache(self, content_hash: str) -> PipelineGraphState | None:
        """Check the L1/L2 processing cache for a previously completed result.

        Returns the cached PipelineGraphState if found, or None on miss.
        The caller (API route) uses this to short-circuit re-processing of
        identical document content.
        """
        if not self._processing_cache_enabled or self._processing_cache is None or not content_hash:
            return None
        result = await self._processing_cache.get_cached_result(content_hash)
        if result is None:
            return None
        return result.state

    async def compute_initial_content_hash(self, state: PipelineGraphState) -> str | None:
        """Compute the content hash for an initial pipeline state.

        Delegates to the content_hash module, which handles local uploads
        (file bytes), pre-parsed markdown, and online acquisition keys.
        """
        return await compute_content_hash(state)
