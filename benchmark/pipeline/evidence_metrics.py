"""PG evidence metrics collection for pipeline benchmark results.

Usage:
    from benchmark.pipeline.evidence_metrics import query_evidence_metrics

Queries run_evidence_items, canonical_evidence_items, and evidence_entity_bindings
to measure pipeline extraction quality after a successful run.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, case, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.dao.postgresql.models import (
    CanonicalEvidenceItem,
    EvidenceEntityBinding,
    RunEvidenceItem,
)


@dataclass
class TrackMetrics:
    """Evidence counts for a single track (original or translated)."""

    count: int
    avg_confidence: float | None
    distinct_fields: int


@dataclass
class CategoryCoverage:
    """Per-category (A-J) field coverage breakdown."""

    category: str
    total_fields: int
    found_fields: int
    found_count: int
    not_found_count: int


@dataclass
class SourceGroundingMetrics:
    """Source grounding quality distribution."""

    total_with_source: int
    exact_count: int
    corrected_count: int
    ambiguous_count: int
    no_source_count: int
    grounding_rate: float  # exact / total_found


@dataclass
class EvidenceMetrics:
    """Aggregated evidence metrics for one processing run in PG."""

    # Layer 1: quantity metrics
    run_evidence_count: int
    canonical_evidence_count: int
    entity_binding_count: int
    avg_confidence: float | None
    field_coverage: int
    track_breakdown: dict[str, TrackMetrics]
    status_breakdown: dict[str, int]

    # Layer 2: quality metrics
    found_rate: float  # found / total
    source_grounding: SourceGroundingMetrics
    category_coverage: list[CategoryCoverage]
    key_field_found: dict[str, bool]  # A.gene_symbol, B.disease_diagnosis, etc.


# ── Catalog category definitions ──────────────────────────────────────
# Maps category prefix to display name and expected field count
_CATALOG_CATEGORIES = {
    "A": ("Variant Information", 18),
    "B": ("Case/Phenotype", 22),
    "C": ("Segregation/Family", 18),
    "D": ("Population/Frequency", 9),
    "E": ("Computational/Prediction", 8),
    "F": ("Functional", 17),
    "G": ("Case-Control", 12),
    "H": ("Contradiction/Exclusion", 10),
    "I": ("Gene Function/Experimental", 18),
    "J": ("Authority/Time Validity", 6),
}

# Key fields that must be found for ACMG scoring
_KEY_FIELDS = [
    "A.gene_symbol",
    "A.variant_hgvs_c",
    "A.variant_hgvs_p",
    "B.disease_diagnosis",
    "B.diagnosis_sufficiency",
    "D.allele_frequency",
]


async def query_evidence_metrics(
    session_factory: async_sessionmaker[AsyncSession],
    processing_run_id: str | uuid.UUID,
) -> EvidenceMetrics:
    """Query PG for evidence metrics after a pipeline run.

    Args:
        session_factory: Async session factory (same pattern as Phase 3 adapter).
        processing_run_id: The run to measure.

    Returns:
        EvidenceMetrics with aggregated counts and breakdowns.
    """
    run_id = uuid.UUID(str(processing_run_id)) if isinstance(processing_run_id, str) else processing_run_id

    async with session_factory() as session:

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

        # ── found rate ──
        found_count = status_breakdown.get("found", 0)
        found_rate = found_count / run_count if run_count > 0 else 0.0

        # ── source grounding metrics ──
        # source_span is JSONB with source_precision field
        stmt = (
            select(
                func.count(RunEvidenceItem.run_evidence_item_id).label("total"),
                func.count(
                    case(
                        (RunEvidenceItem.source_span["source_precision"].astext == "exact", 1),
                    )
                ).label("exact"),
                func.count(
                    case(
                        (RunEvidenceItem.source_span["source_precision"].astext == "corrected", 1),
                    )
                ).label("corrected"),
                func.count(
                    case(
                        (RunEvidenceItem.source_span["source_precision"].astext == "ambiguous", 1),
                    )
                ).label("ambiguous"),
            )
            .where(
                RunEvidenceItem.processing_run_id == run_id,
                RunEvidenceItem.status == "found",
            )
        )
        sg_row = (await session.execute(stmt)).one()
        total_with_source = sg_row.total or 0
        exact = sg_row.exact or 0
        corrected = sg_row.corrected or 0
        ambiguous = sg_row.ambiguous or 0
        no_source = found_count - total_with_source
        grounding_rate = exact / found_count if found_count > 0 else 0.0

        source_grounding = SourceGroundingMetrics(
            total_with_source=total_with_source,
            exact_count=exact,
            corrected_count=corrected,
            ambiguous_count=ambiguous,
            no_source_count=max(0, no_source),
            grounding_rate=round(grounding_rate, 4),
        )

        # ── per-category coverage ──
        stmt = (
            select(
                RunEvidenceItem.field_id,
                RunEvidenceItem.status,
                func.count(RunEvidenceItem.run_evidence_item_id).label("cnt"),
            )
            .where(RunEvidenceItem.processing_run_id == run_id)
            .group_by(RunEvidenceItem.field_id, RunEvidenceItem.status)
        )
        rows = (await session.execute(stmt)).all()

        # Aggregate by category prefix
        cat_data: dict[str, dict[str, int]] = {}
        for r in rows:
            cat = r.field_id.split(".")[0] if "." in r.field_id else r.field_id[0]
            if cat not in cat_data:
                cat_data[cat] = {"found_fields": set(), "found_count": 0, "not_found_count": 0}
            if r.status == "found":
                cat_data[cat]["found_fields"].add(r.field_id)
                cat_data[cat]["found_count"] += r.cnt
            elif r.status == "not_found":
                cat_data[cat]["not_found_count"] += r.cnt

        category_coverage: list[CategoryCoverage] = []
        for cat_prefix, (cat_name, total_fields) in sorted(_CATALOG_CATEGORIES.items()):
            data = cat_data.get(cat_prefix, {"found_fields": set(), "found_count": 0, "not_found_count": 0})
            category_coverage.append(CategoryCoverage(
                category=f"{cat_prefix}. {cat_name}",
                total_fields=total_fields,
                found_fields=len(data["found_fields"]),
                found_count=data["found_count"],
                not_found_count=data["not_found_count"],
            ))

        # ── key field found ──
        stmt = (
            select(RunEvidenceItem.field_id)
            .where(
                RunEvidenceItem.processing_run_id == run_id,
                RunEvidenceItem.status == "found",
                RunEvidenceItem.field_id.in_(_KEY_FIELDS),
            )
            .distinct()
        )
        found_key_fields = {r.field_id for r in (await session.execute(stmt)).all()}
        key_field_found = {f: (f in found_key_fields) for f in _KEY_FIELDS}

        # ── canonical_evidence_items (distinct canonical items linked to this run) ──
        stmt = (
            select(func.count(func.distinct(CanonicalEvidenceItem.canonical_evidence_id)))
            .join(
                RunEvidenceItem,
                CanonicalEvidenceItem.current_best_run_evidence_id == RunEvidenceItem.run_evidence_item_id,
            )
            .where(
                RunEvidenceItem.processing_run_id == run_id,
                CanonicalEvidenceItem.current_best_run_evidence_id.isnot(None),
            )
        )
        canonical_count: int = (await session.execute(stmt)).scalar_one() or 0

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
        found_rate=round(found_rate, 4),
        source_grounding=source_grounding,
        category_coverage=category_coverage,
        key_field_found=key_field_found,
    )
