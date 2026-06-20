"""State persistence layer for pipeline orchestrator.

Two implementations:
- DirectStatePersistence: binds a single session (unit tests).
- SessionBoundStatePersistence: session-per-operation (production).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.agents.contracts import (
    PhaseStatus,
    PipelineGraphState,
    PipelineStatus,
    validate_all_phase_transitions,
    validate_pipeline_status_transition,
)
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


def _build_raw_metadata(state: PipelineGraphState) -> dict[str, object]:
    """Extract title/authors from Phase 1 metadata.json for SourceDocument.raw_metadata."""
    meta: dict[str, object] = {}
    if not state.phase_1_output or not state.phase_1_output.metadata_path:
        return meta
    try:
        with open(state.phase_1_output.metadata_path, encoding="utf-8") as f:
            phase1_meta = json.load(f)
        if isinstance(phase1_meta, dict):
            title = phase1_meta.get("title")
            if title and isinstance(title, str):
                meta["title"] = title
            authors = phase1_meta.get("authors")
            if authors and isinstance(authors, list):
                meta["authors"] = authors
            journal = phase1_meta.get("journal")
            if journal and isinstance(journal, str):
                meta["journal"] = journal
    except (OSError, json.JSONDecodeError):
        pass
    return meta


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
            raw_meta = _build_raw_metadata(state)
            self._session.add(SourceDocument(source_document_id=sd_id, raw_metadata=raw_meta))
            await self._session.flush()
        elif state.phase_1_output:
            # Update metadata if Phase 1 just completed
            new_meta = _build_raw_metadata(state)
            if new_meta.get("title"):
                existing_sd.raw_metadata = {**existing_sd.raw_metadata, **new_meta}

        existing = await self._session.get(
            PipelineRunState, UUID(state.processing_run_id)
        )
        # ── State transition guard ──
        if existing is not None:
            old_state = PipelineGraphState.model_validate(existing.state_json)
            ctx = f"run={state.processing_run_id}"
            validate_pipeline_status_transition(
                old_state.pipeline_status,
                state.pipeline_status,
                context=ctx,
            )
            validate_all_phase_transitions(old_state, state, context=ctx)
        # ── End state transition guard ──

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

    async def recover_orphaned_runs(self, *, heartbeat_timeout_seconds: int = 300) -> int:
        """Not supported in unit-test persistence — raises on misuse."""
        raise NotImplementedError(
            "recover_orphaned_runs is not available in DirectStatePersistence; "
            "use SessionBoundStatePersistence for crash recovery."
        )

    async def heartbeat(self, processing_run_id: str, owner_worker_id: str) -> bool:
        """Not supported in unit-test persistence — raises on misuse."""
        raise NotImplementedError(
            "heartbeat is not available in DirectStatePersistence; "
            "use SessionBoundStatePersistence for heartbeat refresh."
        )

    async def has_active_source_key(self, source_key: str) -> bool:
        """Not supported in unit-test persistence — raises on misuse."""
        raise NotImplementedError(
            "has_active_source_key is not available in DirectStatePersistence; "
            "use SessionBoundStatePersistence for source dedup."
        )

    async def finalize_review(self, processing_run_id: str) -> PipelineGraphState | None:
        """Not supported in unit-test persistence — raises on misuse."""
        raise NotImplementedError(
            "finalize_review is not available in DirectStatePersistence; "
            "use SessionBoundStatePersistence for review finalization."
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
            raw_meta = _build_raw_metadata(state)
            sd_upsert = (
                pg_insert(SourceDocument)
                .values(source_document_id=sd_id, raw_metadata=raw_meta)
                .on_conflict_do_nothing(index_elements=["source_document_id"])
            )
            await session.execute(sd_upsert)
            # Update metadata if Phase 1 just completed. The upsert above only
            # sets raw_metadata on first insert; existing rows need an update.
            if state.phase_1_output and raw_meta.get("title"):
                existing_sd = await session.get(SourceDocument, sd_id)
                if existing_sd is not None and existing_sd.raw_metadata.get("title") != raw_meta["title"]:
                    existing_sd.raw_metadata = {**existing_sd.raw_metadata, **raw_meta}

            # ── State transition guard ──
            # Load existing state (if any) to validate the transition is legal.
            # This is an extra read per save, but correctness in a medical
            # pipeline is worth the cost.
            existing = await session.get(
                PipelineRunState, UUID(state.processing_run_id)
            )
            if existing is not None:
                old_state = PipelineGraphState.model_validate(existing.state_json)
                ctx = f"run={state.processing_run_id}"
                validate_pipeline_status_transition(
                    old_state.pipeline_status,
                    state.pipeline_status,
                    context=ctx,
                )
                validate_all_phase_transitions(old_state, state, context=ctx)
            # ── End state transition guard ──

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

    async def recover_orphaned_runs(self, *, heartbeat_timeout_seconds: int = 300) -> int:
        """Mark pipeline runs stuck in non-terminal states as FAILED.

        Only fails runs whose heartbeat is older than the timeout (default 5 minutes).
        Legacy rows without a heartbeat use updated_at as fallback.
        """
        async with self._session_factory() as session:
            now = datetime.now(timezone.utc)
            timeout_cutoff = now - timedelta(seconds=heartbeat_timeout_seconds)

            # Select active runs where heartbeat is stale or missing
            result = await session.execute(
                select(PipelineRunState).where(
                    PipelineRunState.pipeline_status.in_(("pending", "running")),
                    (
                        (PipelineRunState.heartbeat_at < timeout_cutoff)
                        | (
                            (PipelineRunState.heartbeat_at.is_(None))
                            & (PipelineRunState.updated_at < timeout_cutoff)
                        )
                    ),
                )
            )
            records = result.scalars().all()

            count = 0
            for record in records:
                state = PipelineGraphState.model_validate(record.state_json)
                state.pipeline_status = PipelineStatus.FAILED
                state.error_message = "Pipeline heartbeat expired"
                state.error_phase = _derive_error_phase(state)
                state.completed_at = now.isoformat()
                record.state_json = state.model_dump(mode="json")
                record.pipeline_status = "failed"
                count += 1

            if count:
                await session.commit()
                logger.warning("Recovered {} orphaned pipeline run(s) with stale heartbeat", count)

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

    async def finalize_review(self, processing_run_id: str) -> PipelineGraphState | None:
        """Transition a run from AWAITING_REVIEW to COMPLETED.

        Returns the finalized state, or None if the run was not found.
        Returns the current state unchanged if not in AWAITING_REVIEW status.
        """
        async with self._session_factory() as session:
            record = await session.get(
                PipelineRunState, UUID(processing_run_id)
            )
            if record is None:
                return None

            state = PipelineGraphState.model_validate(record.state_json)
            if state.pipeline_status != PipelineStatus.AWAITING_REVIEW:
                return state

            state.pipeline_status = PipelineStatus.COMPLETED
            state.completed_at = datetime.now(timezone.utc).isoformat()

            record.state_json = state.model_dump(mode="json")
            record.pipeline_status = "completed"
            await session.commit()
            return state
