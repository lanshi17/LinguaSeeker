"""Background pipeline runner with asyncio task management and DB fallback."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import datetime
from typing import Any

from loguru import logger

from src.agents.concurrency import PipelineSemaphore
from src.agents.contracts import PipelineGraphState, PipelineStatus
from src.agents.state_persistence import SessionBoundStatePersistence


class PipelineRunner:
    """Manages background execution of pipeline runs.

    Each run executes as an asyncio.Task with semaphore-controlled concurrency.
    get_last_state() checks in-memory cache first, then falls back to PostgreSQL
    for crash recovery scenarios.
    """

    _MAX_CACHED_STATES = 100

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

    def _remember_state(self, run_id: str, state: PipelineGraphState) -> None:
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
            await self._persistence.save(initial_state)
            self._remember_state(run_id, initial_state)
            async with self._semaphore:
                logger.info("Pipeline execution started: run={}", run_id)
                try:
                    result = await self._orchestrator.run(initial_state)
                    self._remember_state(run_id, result)
                    logger.info("Pipeline execution completed: run={}", run_id)
                    return result
                except Exception as e:
                    logger.exception("Pipeline execution failed: run={}", run_id)
                    error_state = initial_state.model_copy(
                        update={
                            "pipeline_status": PipelineStatus.FAILED,
                            "error_message": f"Pipeline failed: {str(e)}",
                            "error_phase": 0,
                            "completed_at": datetime.now().isoformat(),
                        }
                    )
                    self._remember_state(run_id, error_state)
                    await self._persistence.save(error_state)
                    return error_state

        task = asyncio.create_task(_run_pipeline())
        self._active_tasks[run_id] = task

        def _cleanup(t: asyncio.Task):
            self._active_tasks.pop(run_id, None)

        task.add_done_callback(_cleanup)

        return task

    def get_last_state_cached(self, processing_run_id: str) -> PipelineGraphState | None:
        """Get state from in-memory cache only (fast path)."""
        return self._last_states.get(processing_run_id)

    async def get_last_state(self, processing_run_id: str) -> PipelineGraphState | None:
        """Get the last known state for a pipeline run.

        Checks in-memory cache first (fast path), then falls back to
        PostgreSQL for crash recovery scenarios.
        """
        # Check in-memory first
        cached = self._last_states.get(processing_run_id)
        if cached is not None:
            return cached

        # Fall back to database (crash recovery)
        return await self._persistence.load(processing_run_id)

    def is_running(self, processing_run_id: str) -> bool:
        """Check if a pipeline run is currently active."""
        task = self._active_tasks.get(processing_run_id)
        return task is not None and not task.done()

    def is_running_for_source(self, source_key: str) -> bool:
        """Check if any active run is processing this source key (N3 fix).

        Compares against state.source_key (filename or query), not
        source_document_id (UUID), so the API route can dedup by
        user-visible identifiers.
        """
        for run_id, state in self._last_states.items():
            if state.source_key == source_key and self.is_running(run_id):
                return True
        return False
