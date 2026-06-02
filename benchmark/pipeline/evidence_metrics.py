"""PG evidence metrics collection for pipeline benchmark results.

Usage:
    from benchmark.pipeline.evidence_metrics import query_evidence_metrics

Queries run_evidence_items, canonical_evidence_items, and evidence_entity_bindings
to measure pipeline extraction quality after a successful run.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.dao.postgresql.models import (
    CanonicalEvidenceItem,
    EvidenceEntityBinding,
    ProcessingRun,
    RunEvidenceItem,
)


@dataclass
class TrackMetrics:
    """Evidence counts for a single track (original or translated)."""

    count: int
    avg_confidence: float | None
    distinct_fields: int


@dataclass
class EvidenceMetrics:
    """Aggregated evidence metrics for one processing run in PG."""

    run_evidence_count: int
    canonical_evidence_count: int
    entity_binding_count: int
    avg_confidence: float | None
    field_coverage: int
    track_breakdown: dict[str, TrackMetrics]
    status_breakdown: dict[str, int]


async def query_evidence_metrics(
    session_factory: async_sessionmaker[AsyncSession],
    processing_run_id: str | uuid.UUID,
    source_document_id: str | uuid.UUID | None = None,
) -> EvidenceMetrics:
    """Query PG for evidence metrics after a pipeline run.

    Args:
        session_factory: Async session factory (same pattern as Phase 3 adapter).
        processing_run_id: The run to measure.
        source_document_id: If known, used for canonical_evidence query. Falls back
            to looking it up from the processing_run record.

    Returns:
        EvidenceMetrics with aggregated counts and breakdowns.
    """
    run_id = uuid.UUID(str(processing_run_id)) if isinstance(processing_run_id, str) else processing_run_id

    async with session_factory() as session:
        # Resolve source_document_id if not provided
        doc_id = source_document_id
        if doc_id is None:
            stmt = select(ProcessingRun.source_document_id).where(
                ProcessingRun.processing_run_id == run_id
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            doc_id = uuid.UUID(str(row)) if row is not None else None

        # ── run_evidence_items ──
        stmt = (
            select(
                func.count(RunEvidenceItem.run_evidence_item_id).label("total"),
                func.avg(RunEvidenceItem.confidence).label("avg_conf"),
            )
            .where(RunEvidenceItem.processing_run_id == run_id)
        )
        row = (await session.execute(stmt)).one()
        run_count: int = row.total or 0
        avg_confidence: float | None = float(row.avg_conf) if row.avg_conf is not None else None

        # ── field coverage ──
        stmt = (
            select(func.count(func.distinct(RunEvidenceItem.field_id)))
            .where(RunEvidenceItem.processing_run_id == run_id)
        )
        field_coverage: int = (await session.execute(stmt)).scalar_one() or 0

        # ── track breakdown ──
        stmt = (
            select(
                RunEvidenceItem.track,
                func.count(RunEvidenceItem.run_evidence_item_id).label("cnt"),
                func.avg(RunEvidenceItem.confidence).label("avg_conf"),
                func.count(func.distinct(RunEvidenceItem.field_id)).label("fields"),
            )
            .where(RunEvidenceItem.processing_run_id == run_id)
            .group_by(RunEvidenceItem.track)
        )
        rows = (await session.execute(stmt)).all()
        track_breakdown: dict[str, TrackMetrics] = {}
        for r in rows:
            track_name = r.track or "unknown"
            track_breakdown[track_name] = TrackMetrics(
                count=r.cnt,
                avg_confidence=float(r.avg_conf) if r.avg_conf is not None else None,
                distinct_fields=r.fields,
            )

        # ── status breakdown ──
        stmt = (
            select(
                RunEvidenceItem.status,
                func.count(RunEvidenceItem.run_evidence_item_id).label("cnt"),
            )
            .where(RunEvidenceItem.processing_run_id == run_id)
            .group_by(RunEvidenceItem.status)
        )
        rows = (await session.execute(stmt)).all()
        status_breakdown: dict[str, int] = {r.status: r.cnt for r in rows}

        # ── canonical_evidence_items ──
        canonical_count = 0
        if doc_id is not None:
            stmt = (
                select(func.count(CanonicalEvidenceItem.canonical_evidence_id))
                .where(CanonicalEvidenceItem.source_document_id == doc_id)
            )
            canonical_count = (await session.execute(stmt)).scalar_one() or 0

        # ── evidence_entity_bindings (join through run_evidence_items) ──
        stmt = (
            select(func.count(EvidenceEntityBinding.evidence_entity_binding_id))
            .join(RunEvidenceItem, EvidenceEntityBinding.run_evidence_item_id == RunEvidenceItem.run_evidence_item_id)
            .where(RunEvidenceItem.processing_run_id == run_id)
        )
        entity_binding_count: int = (await session.execute(stmt)).scalar_one() or 0

    return EvidenceMetrics(
        run_evidence_count=run_count,
        canonical_evidence_count=canonical_count,
        entity_binding_count=entity_binding_count,
        avg_confidence=avg_confidence,
        field_coverage=field_coverage,
        track_breakdown=track_breakdown,
        status_breakdown=status_breakdown,
    )
