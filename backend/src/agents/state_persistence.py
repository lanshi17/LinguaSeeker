"""State persistence layer for pipeline orchestrator.

Two implementations:
- DirectStatePersistence: binds a single session (unit tests).
- SessionBoundStatePersistence: session-per-operation (production).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.agents.contracts import PhaseStatus, PipelineGraphState, PipelineStatus
from src.dao.postgresql.models import PipelineRunState, SourceDocument


def _derive_error_phase(state: PipelineGraphState) -> int:
    """Derive the phase number that was running when the pipeline was interrupted.

    Inspects per-phase PhaseStatusDetail fields in order (phase 3 → 1).
    Returns 0 when no phase shows RUNNING status.
    """
    for phase_num in (3, 2, 1):
        detail = getattr(state, f"phase_{phase_num}_status", None)
        if detail is not None and detail.status == PhaseStatus.RUNNING:
            return phase_num
    return 0


class DirectStatePersistence:
    """Save/load PipelineGraphState with a fixed session.

    Intended for unit tests with short-lived sessions only.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(
        self,
        state: PipelineGraphState,
        *,
        owner_worker_id: str | None = None,
        heartbeat_at: datetime | None = None,
    ) -> None:
        # Ensure source_document exists (FK requirement for pipeline_run_states)
        sd_id = UUID(state.source_document_id)
        existing_sd = await self._session.get(SourceDocument, sd_id)
        if not existing_sd:
            self._session.add(SourceDocument(source_document_id=sd_id))
            await self._session.flush()

        existing = await self._session.get(
            PipelineRunState, UUID(state.processing_run_id)
        )
        state_json = state.model_dump(mode="json")
        if existing:
            existing.state_json = state_json
            existing.pipeline_status = state.pipeline_status.value
            if state.source_key is not None:
                existing.source_key = state.source_key
            if owner_worker_id is not None:
                existing.owner_worker_id = owner_worker_id
            if heartbeat_at is not None:
                existing.heartbeat_at = heartbeat_at
        else:
            new_record = PipelineRunState(
                processing_run_id=UUID(state.processing_run_id),
                source_document_id=UUID(state.source_document_id),
                state_json=state_json,
                pipeline_status=state.pipeline_status.value,
                source_key=state.source_key,
                owner_worker_id=owner_worker_id,
                heartbeat_at=heartbeat_at,
            )
            self._session.add(new_record)
        await self._session.commit()

    async def load(self, processing_run_id: str) -> Optional[PipelineGraphState]:
        record = await self._session.get(
            PipelineRunState, UUID(processing_run_id)
        )
        if record is None:
            return None
        return PipelineGraphState.model_validate(record.state_json)

    async def recover_orphaned_runs(self) -> int:
        """Not supported in unit-test persistence — raises on misuse."""
        raise NotImplementedError(
            "recover_orphaned_runs is not available in DirectStatePersistence; "
            "use SessionBoundStatePersistence for crash recovery."
        )


class SessionBoundStatePersistence:
    """Save/load PipelineGraphState with session-per-operation.

    Creates a fresh session for each save()/load() call, avoiding
    stale-session bugs in long-lived contexts (production lifespan).
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def save(
        self,
        state: PipelineGraphState,
        *,
        owner_worker_id: str | None = None,
        heartbeat_at: datetime | None = None,
    ) -> None:
        async with self._session_factory() as session:
            # Ensure source_document exists (FK requirement for pipeline_run_states)
            sd_id = UUID(state.source_document_id)
            sd_upsert = (
                pg_insert(SourceDocument)
                .values(source_document_id=sd_id)
                .on_conflict_do_nothing(index_elements=["source_document_id"])
            )
            await session.execute(sd_upsert)

            state_json = state.model_dump(mode="json")
            upsert_set: dict[str, object] = {
                "state_json": state_json,
                "pipeline_status": state.pipeline_status.value,
                "updated_at": func.now(),
            }
            if state.source_key is not None:
                upsert_set["source_key"] = state.source_key
            if owner_worker_id is not None:
                upsert_set["owner_worker_id"] = owner_worker_id
            if heartbeat_at is not None:
                upsert_set["heartbeat_at"] = heartbeat_at

            stmt = (
                pg_insert(PipelineRunState)
                .values(
                    processing_run_id=UUID(state.processing_run_id),
                    source_document_id=UUID(state.source_document_id),
                    state_json=state_json,
                    pipeline_status=state.pipeline_status.value,
                    source_key=state.source_key,
                    owner_worker_id=owner_worker_id,
                    heartbeat_at=heartbeat_at,
                )
                .on_conflict_do_update(
                    index_elements=["processing_run_id"],
                    set_=upsert_set,
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def load(self, processing_run_id: str) -> Optional[PipelineGraphState]:
        async with self._session_factory() as session:
            record = await session.get(
                PipelineRunState, UUID(processing_run_id)
            )
            if record is None:
                return None
            return PipelineGraphState.model_validate(record.state_json)

    async def recover_orphaned_runs(self) -> int:
        """Mark pipeline runs stuck in non-terminal states as FAILED after server restart."""
        async with self._session_factory() as session:
            # Only load runs in non-terminal states — uses dedicated column index.
            result = await session.execute(
                select(PipelineRunState).where(
                    PipelineRunState.pipeline_status.in_(("pending", "running"))
                )
            )
            records = result.scalars().all()

            count = 0
            for record in records:
                state = PipelineGraphState.model_validate(record.state_json)
                state.pipeline_status = PipelineStatus.FAILED
                state.error_message = "Pipeline interrupted by server restart"
                state.error_phase = _derive_error_phase(state)
                state.completed_at = datetime.now(timezone.utc).isoformat()
                record.state_json = state.model_dump(mode="json")
                record.pipeline_status = "failed"
                count += 1

            if count:
                await session.commit()
                logger.warning("Recovered {} orphaned pipeline run(s) from server restart", count)

            return count

    async def heartbeat(self, processing_run_id: str, owner_worker_id: str) -> bool:
        """Refresh heartbeat for an active run owned by this worker.

        Returns True if the heartbeat was updated (run exists and is owned by this worker).
        """
        async with self._session_factory() as session:
            result = await session.execute(
                update(PipelineRunState)
                .where(
                    PipelineRunState.processing_run_id == UUID(processing_run_id),
                    PipelineRunState.owner_worker_id == owner_worker_id,
                    PipelineRunState.pipeline_status.in_(("pending", "running")),
                )
                .values(heartbeat_at=func.now())
            )
            await session.commit()
            return result.rowcount > 0

    async def has_active_source_key(self, source_key: str) -> bool:
        """Return True when any pending/running run owns this source key."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(PipelineRunState.processing_run_id)
                .where(
                    PipelineRunState.source_key == source_key,
                    PipelineRunState.pipeline_status.in_(("pending", "running")),
                )
                .limit(1)
            )
            return result.scalar_one_or_none() is not None
