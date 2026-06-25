"""PostgreSQL-backed persistent job queue for pipeline execution.

Uses SELECT FOR UPDATE SKIP LOCKED to guarantee atomic single-claim
and prevent double-execution of queued jobs.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.dao.postgresql.models import PipelineJob


@dataclass
class JobRow:
    """Lightweight representation of a claimed job."""

    job_id: str
    processing_run_id: str
    source_document_id: str
    request_data: dict  # noqa: dict-return


class JobQueueRepository:
    """Atomic operations on the pipeline_jobs table.

    All public methods create their own session (session-per-operation)
    to avoid stale-session issues in long-lived dispatcher loops.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def enqueue(
        self,
        *,
        job_id: uuid.UUID,
        processing_run_id: uuid.UUID,
        source_document_id: uuid.UUID,
        request_data: dict,  # noqa: dict-return — external deserialized payload
        priority: int = 0,
    ) -> None:
        """Insert a new job in queued status."""
        async with self._session_factory() as session:
            session.add(
                PipelineJob(
                    job_id=job_id,
                    processing_run_id=processing_run_id,
                    source_document_id=source_document_id,
                    status="queued",
                    priority=priority,
                    request_data=request_data,
                )
            )
            await session.commit()
        logger.info(
            "Job enqueued: job_id={}, processing_run_id={}",
            job_id,
            processing_run_id,
        )

    async def claim_next(self, worker_id: str) -> JobRow | None:
        """Atomically claim the highest-priority queued job.

        Uses SELECT FOR UPDATE SKIP LOCKED inside a CTE to prevent
        two workers from claiming the same job.  Returns None when
        no queued jobs are available.
        """
        async with self._session_factory() as session:
            # CTE: select the best candidate and lock it
            candidate = (
                select(PipelineJob)
                .where(PipelineJob.status == "queued")
                .order_by(PipelineJob.priority.desc(), PipelineJob.created_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
                .cte("candidate")
            )
            # Update: transition the locked row to running
            stmt = (
                update(PipelineJob)
                .where(
                    PipelineJob.job_id == select(candidate.c.job_id).scalar_subquery()
                )
                .where(PipelineJob.status == "queued")
                .values(
                    status="running",
                    started_at=datetime.now(timezone.utc),
                    worker_id=worker_id,
                )
                .returning(
                    PipelineJob.job_id,
                    PipelineJob.processing_run_id,
                    PipelineJob.source_document_id,
                    PipelineJob.request_data,
                )
            )
            result = await session.execute(stmt)
            row = result.first()
            await session.commit()

            if row is None:
                return None

            return JobRow(
                job_id=str(row[0]),
                processing_run_id=str(row[1]),
                source_document_id=str(row[2]),
                request_data=row[3] if row[3] else {},
            )

    async def complete(self, job_id: str) -> None:
        """Mark a job as successfully completed."""
        async with self._session_factory() as session:
            await session.execute(
                update(PipelineJob)
                .where(PipelineJob.job_id == uuid.UUID(job_id))
                .where(PipelineJob.status == "running")
                .values(
                    status="completed",
                    finished_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
        logger.info("Job completed: job_id={}", job_id)

    async def fail(self, job_id: str, error_message: str) -> None:
        """Mark a job as failed with an error message."""
        async with self._session_factory() as session:
            await session.execute(
                update(PipelineJob)
                .where(PipelineJob.job_id == uuid.UUID(job_id))
                .where(PipelineJob.status == "running")
                .values(
                    status="failed",
                    finished_at=datetime.now(timezone.utc),
                    error_message=error_message[:4000] if error_message else None,
                )
            )
            await session.commit()
        logger.warning("Job failed: job_id={}, error={}", job_id, error_message)

    async def get_status(self, processing_run_id: str) -> str | None:
        """Return the most recent job status for a processing_run_id."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(PipelineJob.status)
                .where(
                    PipelineJob.processing_run_id == uuid.UUID(processing_run_id)
                )
                .order_by(PipelineJob.created_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            return row

    async def get_running_count(self) -> int:
        """Return the number of currently running jobs (for diagnostics)."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count())
                .select_from(PipelineJob)
                .where(PipelineJob.status == "running")
            )
            return result.scalar() or 0
