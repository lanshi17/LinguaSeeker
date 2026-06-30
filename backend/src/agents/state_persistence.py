"""State persistence layer for pipeline orchestrator.

Two implementations:
- DirectStatePersistence: binds a single session (unit tests).
- SessionBoundStatePersistence: session-per-operation (production).
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.agents.contracts import (
    PipelineMode,
    PhaseStatus,
    PipelineGraphState,
    PipelineStatus,
    validate_all_phase_transitions,
    validate_pipeline_status_transition,
)
from src.dao.postgresql.models import (
    CanonicalEvidenceItem,
    EvidenceEntityBinding,
    LiteratureProfile,
    PipelineRunState,
    RunEvidenceItem,
    SourceDocument,
)
from src.utils.text_normalize import concat_document_text


@dataclass
class PipelineRunSummaryRow:
    """Lightweight summary for listing pipeline runs (avoids full state deserialization)."""

    processing_run_id: str
    pipeline_status: str
    source_key: str | None
    started_at: str | None
    completed_at: str | None
    title: str | None
    current_phase: str | None
    completed_phases: int
    total_phases: int


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


async def _build_raw_metadata(state: PipelineGraphState) -> dict[str, object]:
    """Extract title/authors from Phase 1 metadata.json for SourceDocument.raw_metadata."""
    meta: dict[str, object] = {}
    if not state.phase_1_output or not state.phase_1_output.metadata_path:
        return meta
    try:
        def _read() -> dict:
            with open(state.phase_1_output.metadata_path, encoding="utf-8") as f:
                return json.load(f)
        phase1_meta = await asyncio.to_thread(_read)
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
async def _read_doc_json(path: str) -> str | None:
    """Read a Phase 2 JSON file and return concatenated document text."""
    try:
        def _read() -> dict:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        data = await asyncio.to_thread(_read)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return concat_document_text(data)


async def load_phase2_text_from_paths(
    original_json_path: str,
    translated_json_path: str,
) -> tuple[str | None, str | None]:
    """Load document text from explicit file paths.

    Use this variant when you have the paths directly (e.g. in Phase 2 adapter
    right after files are written and guaranteed to exist).
    """
    return await _read_doc_json(original_json_path), await _read_doc_json(translated_json_path)


async def _load_phase2_document_text(state: PipelineGraphState) -> tuple[str | None, str | None]:
    """Read Phase 2 JSON files from state and return (original_text, translated_text).

    Returns (None, None) when Phase 2 output is missing or files are unreadable.
    """
    p2 = state.phase_2_output
    if p2 is None:
        return None, None
    return await load_phase2_text_from_paths(p2.original_json_path, p2.translated_json_path)


def _is_phase2_rerun(state: PipelineGraphState) -> bool:
    """Return True when a save belongs to a Phase 2-or-earlier rerun."""
    return (
        state.mode == PipelineMode.PHASE
        and state.target_phase is not None
        and state.target_phase <= 2
    )


async def _persist_phase2_document_text(
    session: AsyncSession,
    state: PipelineGraphState,
    sd_id: UUID,
) -> None:
    """Write Phase 2 document text and structured blocks to SourceDocument.

    Shared by both DirectStatePersistence and SessionBoundStatePersistence.
    Only writes when Phase 2 is COMPLETED and the DB doesn't already have text.
    """
    if not (state.phase_2_output and state.phase_2_status.status == PhaseStatus.COMPLETED):
        return
    sd = await session.get(SourceDocument, sd_id)
    if sd is None:
        return
    replace_existing = _is_phase2_rerun(state)
    needs_original = replace_existing or not sd.original_text
    needs_translated = replace_existing or not sd.translated_text
    if needs_original or needs_translated:
        p2 = state.phase_2_output
        original_text = p2.original_text
        translated_text = p2.translated_text
        if original_text is None and translated_text is None:
            original_text, translated_text = await _load_phase2_document_text(state)
        if needs_original and original_text:
            sd.original_text = original_text
        if needs_translated and translated_text:
            sd.translated_text = translated_text
    # Persist structured blocks for document rendering
    p2 = state.phase_2_output
    if p2.original_blocks and (replace_existing or not sd.original_blocks):
        sd.original_blocks = p2.original_blocks
    if p2.translated_blocks and (replace_existing or not sd.translated_blocks):
        sd.translated_blocks = p2.translated_blocks


def _state_json_without_inline_phase2_data(state: PipelineGraphState) -> dict[str, object]:  # noqa: dict-return
    """Serialize state for JSONB without mutating the live pipeline state."""
    persisted_state = state.model_copy(deep=True)
    if persisted_state.phase_2_output is not None:
        persisted_state.phase_2_output.original_text = None
        persisted_state.phase_2_output.translated_text = None
        persisted_state.phase_2_output.original_blocks = None
        persisted_state.phase_2_output.translated_blocks = None
    return persisted_state.model_dump(mode="json")


async def _reset_phase_rerun_artifacts(
    session: AsyncSession,
    *,
    processing_run_id: str,
    source_document_id: str,
    target_phase: int,
) -> None:
    """Clear stale DB artifacts before re-running a phase in-place."""
    run_id = UUID(processing_run_id)
    doc_id = UUID(source_document_id)

    if target_phase <= 2:
        source_document = await session.get(SourceDocument, doc_id)
        if source_document is not None:
            source_document.original_text = None
            source_document.translated_text = None
            source_document.original_blocks = None
            source_document.translated_blocks = None

    if target_phase <= 3:
        try:
            from src.dao.postgresql.search_index_repo import frontend_search_index

            canonical_ids = select(CanonicalEvidenceItem.canonical_evidence_id).where(
                CanonicalEvidenceItem.source_document_id == doc_id
            )
            await session.execute(
                delete(frontend_search_index).where(
                    frontend_search_index.c.canonical_evidence_id.in_(canonical_ids)
                )
            )
        except Exception:
            logger.debug(
                "Skipping frontend_search_index cleanup during phase rerun reset",
                exc_info=True,
            )

        run_item_ids = select(RunEvidenceItem.run_evidence_item_id).where(
            RunEvidenceItem.processing_run_id == run_id
        )
        await session.execute(
            update(CanonicalEvidenceItem)
            .where(CanonicalEvidenceItem.current_best_run_evidence_id.in_(run_item_ids))
            .values(current_best_run_evidence_id=None)
        )
        await session.execute(
            delete(EvidenceEntityBinding).where(
                EvidenceEntityBinding.run_evidence_item_id.in_(run_item_ids)
            )
        )
        await session.execute(
            delete(RunEvidenceItem).where(RunEvidenceItem.processing_run_id == run_id)
        )
        await session.execute(
            delete(CanonicalEvidenceItem).where(
                CanonicalEvidenceItem.source_document_id == doc_id,
                CanonicalEvidenceItem.review_status == "provisional",
            )
        )
        await session.execute(
            delete(LiteratureProfile).where(LiteratureProfile.source_document_id == doc_id)
        )


_TERMINAL_PHASE_STATUSES = frozenset({"completed", "skipped"})
_PHASE_KEYS = ("phase_1", "phase_2", "phase_3")


def _derive_run_title(sj: dict) -> str | None:
    """Derive a human-readable title from state_json fields."""
    query = sj.get("query")
    if query and isinstance(query, str):
        return query[:120]
    identifiers = sj.get("identifiers")
    if identifiers and isinstance(identifiers, list) and identifiers:
        return ", ".join(str(i) for i in identifiers[:5])
    source_key = sj.get("source_key")
    if source_key and isinstance(source_key, str):
        return source_key[:120]
    upload_path = sj.get("upload_file_path")
    if upload_path and isinstance(upload_path, str):
        from pathlib import PurePosixPath

        return PurePosixPath(upload_path.replace("\\", "/")).name
    return None


def _derive_current_phase(sj: dict) -> str | None:
    """Return the phase key that is currently 'running', or None."""
    for pk in _PHASE_KEYS:
        phase_detail = sj.get(pk + "_status")
        if isinstance(phase_detail, dict) and phase_detail.get("status") == "running":
            return pk
    return None


def _count_completed_phases(sj: dict) -> tuple[int, int]:
    """Count completed/skipped phases and return (completed, total)."""
    total = len(_PHASE_KEYS)
    completed = 0
    for pk in _PHASE_KEYS:
        detail = sj.get(pk + "_status")
        if isinstance(detail, dict) and detail.get("status") in _TERMINAL_PHASE_STATUSES:
            completed += 1
    return completed, total


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
            raw_meta = await _build_raw_metadata(state)
            self._session.add(SourceDocument(source_document_id=sd_id, raw_metadata=raw_meta))
            await self._session.flush()
        elif state.phase_1_output:
            # Update metadata if Phase 1 just completed
            new_meta = await _build_raw_metadata(state)
            if new_meta.get("title"):
                existing_sd.raw_metadata = {**existing_sd.raw_metadata, **new_meta}

        await _persist_phase2_document_text(self._session, state, sd_id)

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

        state_json = _state_json_without_inline_phase2_data(state)
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

    async def reset_phase_rerun_artifacts(
        self,
        *,
        processing_run_id: str,
        source_document_id: str,
        target_phase: int,
    ) -> None:
        """Clear stale downstream artifacts before an in-place phase rerun."""
        await _reset_phase_rerun_artifacts(
            self._session,
            processing_run_id=processing_run_id,
            source_document_id=source_document_id,
            target_phase=target_phase,
        )
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
            # Ensure source_document exists (FK requirement for pipeline_run_states).
            # Use ON CONFLICT DO_UPDATE to merge metadata in a single round-trip
            # instead of upsert-nothing + conditional get + update (#7 fix).
            sd_id = UUID(state.source_document_id)
            raw_meta = await _build_raw_metadata(state)
            sd_upsert = (
                pg_insert(SourceDocument)
                .values(source_document_id=sd_id, raw_metadata=raw_meta)
                .on_conflict_do_update(
                    index_elements=["source_document_id"],
                    set_={
                        "raw_metadata": SourceDocument.raw_metadata.op("||")(raw_meta),
                    },
                )
            )
            await session.execute(sd_upsert)

            await _persist_phase2_document_text(session, state, sd_id)

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

            state_json = _state_json_without_inline_phase2_data(state)
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

    async def reset_phase_rerun_artifacts(
        self,
        *,
        processing_run_id: str,
        source_document_id: str,
        target_phase: int,
    ) -> None:
        """Clear stale downstream artifacts before an in-place phase rerun."""
        async with self._session_factory() as session:
            await _reset_phase_rerun_artifacts(
                session,
                processing_run_id=processing_run_id,
                source_document_id=source_document_id,
                target_phase=target_phase,
            )
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

    async def list_runs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        search: str | None = None,
    ) -> tuple[list[PipelineRunSummaryRow], int]:
        """List pipeline run summaries ordered by creation time (newest first).

        Returns a (items, total) tuple. Extracts summary fields from the
        JSONB state_json column to avoid full state deserialization.

        Args:
            status: Filter by pipeline_status value.
            search: Case-insensitive substring match on title (state_json).
        """
        from sqlalchemy import String, cast

        async with self._session_factory() as session:
            base = select(PipelineRunState)
            if status:
                base = base.where(PipelineRunState.pipeline_status == status)
            if search:
                pattern = f"%{search}%"
                base = base.where(
                    cast(PipelineRunState.state_json["query"], String).ilike(pattern)
                    | cast(PipelineRunState.state_json["identifiers"], String).ilike(pattern)
                    | cast(PipelineRunState.source_key, String).ilike(pattern)
                )

            count_result = await session.execute(
                select(func.count()).select_from(base.subquery())
            )
            total = count_result.scalar() or 0

            stmt = (
                base
                .order_by(PipelineRunState.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(stmt)
            records = result.scalars().all()

            items: list[PipelineRunSummaryRow] = []
            for record in records:
                sj = record.state_json

                title = _derive_run_title(sj)
                current_phase = _derive_current_phase(sj)
                completed, total_phases = _count_completed_phases(sj)

                items.append(
                    PipelineRunSummaryRow(
                        processing_run_id=str(record.processing_run_id),
                        pipeline_status=record.pipeline_status,
                        source_key=record.source_key,
                        started_at=sj.get("started_at"),
                        completed_at=sj.get("completed_at"),
                        title=title,
                        current_phase=current_phase,
                        completed_phases=completed,
                        total_phases=total_phases,
                    )
                )

            return items, total
