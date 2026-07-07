"""Single-worker job dispatcher for the pipeline job queue.

Polls the ``pipeline_jobs`` table for queued jobs, claims one atomically,
executes it via PipelineRunner, and updates the job status on completion
or failure.  Only one job runs at a time (the DB claim guarantees this
even across multiple backend processes).
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

from src.agents.contracts import (
    PipelineGraphState,
    PipelineStatus,
)
from src.dao.postgresql.job_queue import JobQueueRepository


class SingleJobDispatcher:
    """Background dispatcher that processes queued pipeline jobs one at a time.

    Lifecycle:
        dispatcher.start()   — call during app startup (after wire_dependencies)
        dispatcher.stop()    — call during app shutdown (before engine dispose)

    The dispatcher polls on a configurable interval and uses
    ``JobQueueRepository.claim_next()`` which is atomic (SELECT FOR UPDATE
    SKIP LOCKED) so only one worker process can claim a given job.
    """

    def __init__(
        self,
        runner: Any,
        job_queue: JobQueueRepository,
        poll_interval: float = 2.0,
        worker_id: str | None = None,
    ):
        self._runner = runner
        self._job_queue = job_queue
        self._poll_interval = poll_interval
        self._worker_id = worker_id or f"dispatcher:{uuid.uuid4().hex[:8]}"
        self._task: asyncio.Task | None = None
        self._stopping = False

    def start(self) -> None:
        """Start the background polling loop."""
        if self._task is not None and not self._task.done():
            return
        self._stopping = False
        self._task = asyncio.create_task(self._loop())
        logger.info("Job dispatcher started (worker_id={})", self._worker_id)

    async def stop(self, timeout: float = 120.0) -> None:
        """Stop the dispatcher and wait for the current job to finish.

        Args:
            timeout: Maximum seconds to wait for the current job.
        """
        self._stopping = True
        if self._task is None or self._task.done():
            return
        self._task.cancel()
        try:
            await asyncio.wait_for(self._task, timeout=timeout)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        self._task = None
        logger.info("Job dispatcher stopped")

    async def _loop(self) -> None:
        """Main polling loop: claim → execute → repeat."""
        while not self._stopping:
            try:
                job = await self._job_queue.claim_next(self._worker_id)
                if job is None:
                    await asyncio.sleep(self._poll_interval)
                    continue
                await self._execute(job)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Dispatcher loop error")
                await asyncio.sleep(self._poll_interval)

    async def _execute(self, job: Any) -> None:
        """Run a claimed job through the pipeline."""
        logger.info(
            "Executing job: job_id={}, processing_run_id={}",
            job.job_id,
            job.processing_run_id,
        )
        rd = job.request_data
        rd["processing_run_id"] = job.processing_run_id
        rd["source_document_id"] = job.source_document_id
        try:
            initial_state = PipelineGraphState.from_request_data(rd)
        except Exception as exc:
            logger.exception("Failed to build initial state for job_id={}", job.job_id)
            await self._job_queue.fail(job.job_id, f"Invalid request data: {exc}")
            return

        try:
            task = await self._runner.start(initial_state)
            result: PipelineGraphState = await task

            if result.pipeline_status == PipelineStatus.COMPLETED:
                await self._job_queue.complete(job.job_id)
                self._cleanup_upload_file(rd)
            else:
                error_msg = result.error_message or "Pipeline ended in non-completed state"
                await self._job_queue.fail(job.job_id, error_msg)
        except Exception as exc:
            logger.exception("Job execution failed: job_id={}", job.job_id)
            await self._job_queue.fail(job.job_id, str(exc))

    def _cleanup_upload_file(self, request_data: dict[str, Any]) -> None:
        """Remove local upload temp file after a successful job."""
        upload_path = request_data.get("upload_file_path")
        if upload_path:
            try:
                Path(upload_path).unlink(missing_ok=True)
            except OSError:
                pass
