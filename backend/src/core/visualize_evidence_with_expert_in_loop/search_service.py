"""Evidence search service with field-level pivoting."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from loguru import logger

from sqlalchemy import and_, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.parsing import parse_gene_from_group_id, parse_variant_from_group_id
from src.utils.text_normalize import concat_document_text

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidenceChainHighlight,
    EvidenceFieldDistribution,
    EvidenceGroupDetailResponse,
    EvidenceGroupItem,
    EvidenceSearchResponse,
    EvidenceSearchResult,
    EvidenceTrackTrace,
)
from src.dao.postgresql.models import (
    CanonicalEvidenceItem,
    PipelineRunState,
    SourceDocument,
    SourceDocumentIdentifier,
)

# Field ID prefixes that map to summary columns
_GENE_FIELDS = ("A.gene_symbol", "A.gene_aliases")
_VARIANT_FIELDS = (
    "A.variant_hgvs_c",
    "A.variant_hgvs_p",
    "A.variant_hgvs_g",
    "A.variant_legacy_name",
)
_DISEASE_FIELDS = ("B.disease_diagnosis", "B.clinical_diagnosis", "B.hpo_terms")
_CLASSIFICATION_FIELDS = ("J.authority_classification", "J.clinvar_assertion")
_TOKEN_BOUNDARY_CHARS = r"A-Za-z0-9_"


def _coerce_str(value: Any) -> str | None:
    """Convert a payload value to a display string."""
    if value is None:
        return None
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)

def _category_from_field_id(field_id: str) -> str | None:
    """Infer the evidence category prefix from a field id."""
    if not field_id:
        return None
    if "." not in field_id:
        return field_id
    return field_id.split(".", 1)[0]


def _parse_source_offset(raw: object, *, default: int, name: str) -> tuple[int, bool]:
    """Parse a stored source offset, with default + validity flag for fallback.

    Returns (offset, valid). ``valid`` is False when the stored value was
    missing or malformed; callers use that to decide between clamping and
    value-anchor fallback.
    """
    if raw is None:
        return default, False
    try:
        return int(raw), True
    except (TypeError, ValueError):
        logger.warning(
            "Invalid source_span {}_offset={!r}; using value fallback",
            name,
            raw,
        )
        return default, False


def _find_value_anchor(text: str, value: str | None) -> tuple[int, int] | None:
    """Find a safe case-insensitive value anchor in snippet text.

    Single-letter values are too ambiguous in prose. Two-letter values are
    only matched when uppercase (typical for gene symbols like ``BR``).
    Three-or-more-letter values use a token-boundary regex with
    case-insensitive matching to avoid matching inside longer words.
    """
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if len(candidate) == 1:
        return None
    if len(candidate) == 2:
        if not candidate.isupper():
            return None
        match = re.search(
            rf"(?<![{_TOKEN_BOUNDARY_CHARS}]){re.escape(candidate)}(?![{_TOKEN_BOUNDARY_CHARS}])",
            text,
        )
        if not match:
            return None
        return match.start(), match.end()
    pattern = re.compile(
        rf"(?<![{_TOKEN_BOUNDARY_CHARS}]){re.escape(candidate)}(?![{_TOKEN_BOUNDARY_CHARS}])",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if match is None:
        return None
    return match.start(), match.end()


def _build_highlight(
    source_span: dict[str, object],
    value: str | None = None,
) -> EvidenceChainHighlight | None:
    """Build a clamped highlight payload from a stored source span.

    Source spans store document-global offsets while text_snippet is a short
    excerpt. When offsets are malformed or start beyond the snippet, locate
    value inside the snippet using a safe token-boundary search. When the value
    cannot be located, start and end collapse to 0 (no visible highlight).
    """
    if not source_span or not isinstance(source_span, dict):
        return None

    text = str(source_span.get("text_snippet") or "")
    if not text:
        return None

    text_len = len(text)
    start, start_valid = _parse_source_offset(
        source_span.get("start_offset"),
        default=0,
        name="start",
    )
    end, end_valid = _parse_source_offset(
        source_span.get("end_offset"),
        default=text_len,
        name="end",
    )
    if end < start:
        end = text_len

    # Valid starts inside the snippet should keep current behavior: clamp the
    # end to snippet bounds instead of falling through to value search.
    if start_valid and end_valid and start < text_len:
        start = max(start, 0)
        end = min(max(end, start), text_len)
    else:
        anchor = _find_value_anchor(text, value)
        if anchor is None:
            start = end = 0
        else:
            start, end = anchor

    page = source_span.get("page")
    clean_source_span = {k: v for k, v in source_span.items() if v is not None}
    return EvidenceChainHighlight(
        text=text,
        highlight_start=max(start, 0),
        highlight_end=min(max(end, 0), text_len),
        page=page if isinstance(page, int) else None,
        source_span=clean_source_span,
    )


def _load_from_dir(doc_dir: Path, track: str) -> str | None:
    """Try to load and concatenate text from a single document directory."""
    doc_file = doc_dir / f"{track}.json"
    if not doc_file.exists():
        return None
    try:
        with open(doc_file, "r", encoding="utf-8") as f:
            return concat_document_text(json.load(f))
    except Exception:
        logger.warning("Failed to load full {} text from {}", track, doc_file)
        return None

def _load_full_document_text(
    source_document_id: str | UUID,
    track: str = "original",
    identifiers: dict[str, str] | None = None,
    known_output_dir: str | None = None,
) -> str | None:
    """Load full text content for a source document from pipeline output.

    Searches in order:
    1. ``known_output_dir`` — exact path from pipeline_run_states.state_json.
    2. ``backend/data/pipeline/*/phase_2/{doc_id}/`` — scan current pipeline output.
    3. ``backend/output/cross_lingual/**/`` — legacy output (by UUID or identifiers).

    Returns concatenated text from all blocks, or None if not found.
    """
    # 1. Exact path from persisted pipeline state
    if known_output_dir:
        result = _load_from_dir(Path(known_output_dir), track)
        if result:
            return result

    backend_root = Path(__file__).resolve().parents[3]
    doc_id_str = str(source_document_id)

    # 2. Current pipeline output: backend/data/pipeline/{run_id}/phase_2/{doc_id}/
    pipeline_root = backend_root / "data" / "pipeline"
    if pipeline_root.exists():
        for pipeline_dir in pipeline_root.iterdir():
            if not pipeline_dir.is_dir():
                continue
            doc_dir = pipeline_dir / "phase_2" / doc_id_str
            result = _load_from_dir(doc_dir, track)
            if result:
                return result

    # 3. Legacy output: backend/output/cross_lingual/{lang}/{doc_id}/
    legacy_root = backend_root / "output" / "cross_lingual"
    if legacy_root.exists():
        for lang_dir in legacy_root.iterdir():
            if not lang_dir.is_dir():
                continue
            result = _load_from_dir(lang_dir / doc_id_str, track)
            if result:
                return result

        if identifiers:
            search_keys = [
                v.replace("/", "_")
                for v in identifiers.values()
                if v
            ]
            for lang_dir in legacy_root.iterdir():
                if not lang_dir.is_dir():
                    continue
                for child in lang_dir.iterdir():
                    if not child.is_dir():
                        continue
                    if child.name in search_keys or child.name.replace("/", "_") in search_keys:
                        result = _load_from_dir(child, track)
                        if result:
                            return result

    return None

class SearchService:
    """Search evidence cards grouped by group_id, pivoting field-level extractions."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def search_evidence(
        self,
        *,
        gene: str | None = None,
        variant: str | None = None,
        disease: str | None = None,
        pmid: str | None = None,
        doi: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> EvidenceSearchResponse:
        """Search evidence with optional filters and DB-level pagination.

        Groups field-level extractions by group_id and pivots them into
        summary rows with gene/variant/disease/classification columns.
        Uses a two-pass approach:
        1. DB-level GROUP BY + OFFSET/LIMIT to get current page group_ids
        2. Fetch details only for those groups (small bounded set)
        """
        from sqlalchemy import func as sa_func
        from sqlalchemy.dialects.postgresql.ext import aggregate_order_by

        group_id_expr = CanonicalEvidenceItem.active_payload["group_id"].astext

        # Build filter conditions on field-level rows
        conditions = []
        if gene:
            conditions.append(
                and_(
                    CanonicalEvidenceItem.field_id.in_(_GENE_FIELDS),
                    CanonicalEvidenceItem.active_payload["value"].astext.ilike(f"%{gene}%"),
                )
            )
        if variant:
            conditions.append(
                and_(
                    CanonicalEvidenceItem.field_id.in_(_VARIANT_FIELDS),
                    CanonicalEvidenceItem.active_payload["value"].astext.ilike(f"%{variant}%"),
                )
            )
        if disease:
            conditions.append(
                and_(
                    CanonicalEvidenceItem.field_id.in_(_DISEASE_FIELDS),
                    CanonicalEvidenceItem.active_payload["value"].astext.ilike(f"%{disease}%"),
                )
            )

        # If filters are present, narrow to matching group_ids
        if conditions:
            filter_stmt = (
                select(group_id_expr)
                .where(and_(*conditions))
                .group_by(group_id_expr)
            )
            result = await self._session.execute(filter_stmt)
            matching_group_ids = [row[0] for row in result.all() if row[0]]
            if not matching_group_ids:
                return EvidenceSearchResponse(items=[], total=0, page=page, page_size=page_size)
        else:
            matching_group_ids = None

        # ── Pass 1: DB-level GROUP BY + pagination ────────────────
        #
        # The inner query aggregates per-group rows. UUID-typed columns
        # (canonical_evidence_id) and status strings (review_status) cannot
        # be reduced with `min()` / `max()` (no PG ordering for UUID), so
        # we capture them as `array_agg(x ORDER BY created_at)` arrays.
        # The outer SELECT indexes those arrays at [1] to pick the oldest
        # row's value as the representative — a form PostgreSQL actually
        # accepts (unlike `CAST(... AS UUID[])[1]`, which is a syntax
        # error because the cast needs parentheses before indexing).
        inner = (
            select(
                group_id_expr.label("group_id"),
                sa_func.count().label("field_count"),
                sa_func.avg(CanonicalEvidenceItem.current_best_confidence).label("avg_confidence"),
                sa_func.array_agg(
                    aggregate_order_by(
                        CanonicalEvidenceItem.canonical_evidence_id,
                        CanonicalEvidenceItem.created_at.asc(),
                    )
                ).label("canonical_ids"),
                CanonicalEvidenceItem.source_document_id.label("source_document_id"),
                sa_func.array_agg(
                    aggregate_order_by(
                        CanonicalEvidenceItem.review_status,
                        CanonicalEvidenceItem.created_at.asc(),
                    )
                ).label("review_statuses"),
                sa_func.max(CanonicalEvidenceItem.created_at).label("created_at"),
            )
            .group_by(
                group_id_expr,
                CanonicalEvidenceItem.source_document_id,
            )
            .having(group_id_expr.isnot(None))
            .having(group_id_expr != "")
        )
        if matching_group_ids is not None:
            inner = inner.where(group_id_expr.in_(matching_group_ids))

        sub = inner.subquery()
        page_query = select(
            sub.c.group_id,
            sub.c.field_count,
            sub.c.avg_confidence,
            sub.c.canonical_ids[1].label("canonical_evidence_id"),
            sub.c.source_document_id,
            sub.c.review_statuses[1].label("review_status"),
            sub.c.created_at,
        )

        # Count total groups
        count_sub = page_query.subquery()
        count_stmt = select(sa_func.count()).select_from(count_sub)
        total = (await self._session.execute(count_stmt)).scalar_one()

        if total == 0:
            return EvidenceSearchResponse(items=[], total=0, page=page, page_size=page_size)

        # Apply pagination
        offset = (page - 1) * page_size
        page_query = page_query.order_by(sub.c.group_id).offset(offset).limit(page_size)
        page_result = await self._session.execute(page_query)
        page_rows = page_result.all()

        if not page_rows:
            return EvidenceSearchResponse(items=[], total=total, page=page, page_size=page_size)

        page_group_ids = [row.group_id for row in page_rows]
        # Build a lookup from the aggregated page data
        page_summary: dict[str, dict] = {}
        for row in page_rows:
            page_summary[row.group_id] = {
                "field_count": row.field_count,
                "avg_confidence": float(row.avg_confidence) if row.avg_confidence else None,
                "canonical_evidence_id": row.canonical_evidence_id,
                "source_document_id": row.source_document_id,
                "review_status": row.review_status,
                "created_at": row.created_at,
            }

        # ── Pass 2: Fetch detail rows for current page only ───────
        detail_stmt = (
            select(
                CanonicalEvidenceItem.canonical_evidence_id,
                CanonicalEvidenceItem.source_document_id,
                CanonicalEvidenceItem.field_id,
                CanonicalEvidenceItem.review_status,
                CanonicalEvidenceItem.current_best_confidence,
                CanonicalEvidenceItem.active_payload,
                CanonicalEvidenceItem.created_at,
            )
            .where(group_id_expr.in_(page_group_ids))
            .order_by(group_id_expr, CanonicalEvidenceItem.field_id)
        )
        detail_result = await self._session.execute(detail_stmt)
        detail_rows = detail_result.all()

        # Pivot: extract gene/variant/disease/classification per group
        groups: dict[str, dict] = {}
        for row in detail_rows:
            payload = row.active_payload or {}
            gid = payload.get("group_id", "")
            if not gid:
                continue

            if gid not in groups:
                summary = page_summary.get(gid, {})
                groups[gid] = {
                    "group_id": gid,
                    "source_document_id": summary.get("source_document_id", row.source_document_id),
                    "canonical_evidence_id": summary.get("canonical_evidence_id", row.canonical_evidence_id),
                    "created_at": summary.get("created_at", row.created_at),
                    "review_status": summary.get("review_status", row.review_status),
                    "field_count": summary.get("field_count", 0),
                    "avg_confidence": summary.get("avg_confidence"),
                    "gene": None,
                    "variant": None,
                    "disease": None,
                    "classification": None,
                }

            g = groups[gid]
            field_id = row.field_id
            value = payload.get("value")

            if field_id in _GENE_FIELDS and not g["gene"]:
                g["gene"] = _coerce_str(value)
            elif field_id in _VARIANT_FIELDS and not g["variant"]:
                g["variant"] = _coerce_str(value)
            elif field_id in _DISEASE_FIELDS and not g["disease"]:
                g["disease"] = _coerce_str(value)
            elif field_id in _CLASSIFICATION_FIELDS and not g["classification"]:
                g["classification"] = _coerce_str(value)

        # Fallback: parse gene/variant from group_id
        for g in groups.values():
            if not g["gene"]:
                g["gene"] = parse_gene_from_group_id(g["group_id"])
            if not g["variant"]:
                g["variant"] = parse_variant_from_group_id(g["group_id"])

        # Batch-load identifiers and titles for current page's documents
        doc_ids = {g["source_document_id"] for g in groups.values()}
        ident_map: dict[str, dict[str, str]] = {}
        title_map: dict[str, str] = {}
        if doc_ids:
            ident_stmt = select(SourceDocumentIdentifier).where(
                SourceDocumentIdentifier.source_document_id.in_(doc_ids)
            )
            ident_result = await self._session.execute(ident_stmt)
            for ident in ident_result.scalars():
                ident_map.setdefault(str(ident.source_document_id), {})
                ident_map[str(ident.source_document_id)][ident.identifier_type] = ident.identifier_value

            metadata_stmt = select(
                SourceDocument.source_document_id,
                SourceDocument.raw_metadata,
            ).where(SourceDocument.source_document_id.in_(doc_ids))
            metadata_result = await self._session.execute(metadata_stmt)
            for row in metadata_result.all():
                raw_metadata = row.raw_metadata or {}
                title = (
                    _coerce_str(raw_metadata.get("title"))
                    if isinstance(raw_metadata, dict)
                    else None
                )
                if title:
                    title_map[str(row.source_document_id)] = title

        # Build results (apply PMID/DOI post-filters)
        items: list[EvidenceSearchResult] = []
        filtered_total = total
        for gid in page_group_ids:
            g = groups.get(gid)
            if not g:
                continue

            doc_ident = ident_map.get(str(g["source_document_id"]), {})
            if pmid and pmid not in doc_ident.get("pmid", ""):
                filtered_total -= 1
                continue
            if doi and doi.lower() not in doc_ident.get("doi", "").lower():
                filtered_total -= 1
                continue

            items.append(
                EvidenceSearchResult(
                    group_id=g["group_id"],
                    source_document_id=g["source_document_id"],
                    title=title_map.get(str(g["source_document_id"])),
                    pmid=doc_ident.get("pmid"),
                    doi=doc_ident.get("doi"),
                    gene=g["gene"],
                    variant=g["variant"],
                    disease=g["disease"],
                    classification=g["classification"],
                    field_count=g["field_count"],
                    avg_confidence=g["avg_confidence"],
                    review_status=g["review_status"],
                    canonical_evidence_id=g["canonical_evidence_id"],
                    created_at=g["created_at"],
                )
            )

        return EvidenceSearchResponse(
            items=items,
            total=filtered_total if (pmid or doi) else total,
            page=page,
            page_size=page_size,
        )

    async def get_group_detail(
        self,
        *,
        group_id: str | None = None,
        source_document_id: str | None = None,
    ) -> EvidenceGroupDetailResponse:
        """Return detail payload for one grouped evidence row.

        At least one of *group_id* or *source_document_id* must be given.
        When only *source_document_id* is provided the method picks the
        first ``group_id`` found for that document.  This is required
        because ``group_id`` values are not unique per source document —
        the same ``gene=<G>|variant=<V>`` string can appear across many
        papers.
        """
        conditions: list = []
        if group_id:
            conditions.append(
                CanonicalEvidenceItem.active_payload["group_id"].astext == group_id,
            )
        if source_document_id:
            conditions.append(
                CanonicalEvidenceItem.source_document_id == source_document_id,
            )
        stmt = (
            select(
                CanonicalEvidenceItem.canonical_evidence_id,
                CanonicalEvidenceItem.source_document_id,
                CanonicalEvidenceItem.field_id,
                CanonicalEvidenceItem.review_status,
                CanonicalEvidenceItem.current_best_confidence,
                CanonicalEvidenceItem.active_payload,
                CanonicalEvidenceItem.updated_at,
            )
            .where(*conditions)
            .order_by(CanonicalEvidenceItem.field_id)
        )
        result = await self._session.execute(stmt)
        rows = result.all()
        if not rows:
            raise NoResultFound()

        # Deduplicate by (field_id, track): keep the most recently updated row
        # to avoid "Duplicate track" warnings from the trace-building loop.
        seen: dict[tuple[str, str], int] = {}
        deduped_rows = []
        for row in sorted(rows, key=lambda r: r.updated_at or "", reverse=True):
            track = (row.active_payload or {}).get("track", "original")
            key = (row.field_id, track)
            if key not in seen:
                seen[key] = 1
                deduped_rows.append(row)
        rows = deduped_rows

        # If group_id was not provided, extract it from the first row
        if not group_id:
            group_id = (rows[0].active_payload or {}).get("group_id", "")

        source_document_id = rows[0].source_document_id

        ident_stmt = select(SourceDocumentIdentifier).where(
            SourceDocumentIdentifier.source_document_id == source_document_id
        )
        ident_result = await self._session.execute(ident_stmt)
        identifiers = {
            ident.identifier_type: ident.identifier_value
            for ident in ident_result.scalars().all()
        }
        metadata_stmt = select(
            SourceDocument.raw_metadata,
            SourceDocument.original_text,
            SourceDocument.translated_text,
            SourceDocument.original_blocks,
            SourceDocument.translated_blocks,
        ).where(
            SourceDocument.source_document_id == source_document_id
        )
        metadata_result = await self._session.execute(metadata_stmt)
        metadata_row = metadata_result.one_or_none()
        raw_metadata = (metadata_row[0] if metadata_row else None) or {}
        db_original_text: str | None = metadata_row[1] if metadata_row else None
        db_translated_text: str | None = metadata_row[2] if metadata_row else None
        db_original_blocks: list[dict] | None = metadata_row[3] if metadata_row else None
        db_translated_blocks: list[dict] | None = metadata_row[4] if metadata_row else None
        title = (
            _coerce_str(raw_metadata.get("title"))
            if isinstance(raw_metadata, dict)
            else None
        )

        # Look up phase_2 output_dir from persisted pipeline state
        phase2_output_dir: str | None = None
        run_state_stmt = (
            select(PipelineRunState.state_json)
            .where(PipelineRunState.source_document_id == source_document_id)
            .order_by(PipelineRunState.created_at.desc())
            .limit(1)
        )
        run_state_result = await self._session.execute(run_state_stmt)
        state_json = run_state_result.scalar_one_or_none()
        if isinstance(state_json, dict):
            p2_output = state_json.get("phase_2_output")
            if isinstance(p2_output, dict):
                phase2_output_dir = p2_output.get("output_dir")

        distribution = EvidenceFieldDistribution()
        detail_items: list[EvidenceGroupItem] = []
        confidences: list[float] = []
        gene = variant = disease = classification = None

        for row in rows:
            payload = row.active_payload or {}
            value = _coerce_str(payload.get("value"))
            field_id = row.field_id
            field_name = payload.get("field_name")
            category = payload.get("category") or _category_from_field_id(field_id)
            track = payload.get("track")
            confidence = (
                float(row.current_best_confidence)
                if row.current_best_confidence is not None
                else None
            )
            if confidence is not None:
                confidences.append(confidence)

            if category:
                category_key = str(category)
                distribution.by_category[category_key] = distribution.by_category.get(category_key, 0) + 1
            distribution.by_field[field_id] = distribution.by_field.get(field_id, 0) + 1
            distribution.by_status[row.review_status] = distribution.by_status.get(row.review_status, 0) + 1
            if track:
                track_key = str(track)
                distribution.by_track[track_key] = distribution.by_track.get(track_key, 0) + 1

            if field_id in _GENE_FIELDS and not gene:
                gene = value
            elif field_id in _VARIANT_FIELDS and not variant:
                variant = value
            elif field_id in _DISEASE_FIELDS and not disease:
                disease = value
            elif field_id in _CLASSIFICATION_FIELDS and not classification:
                classification = value

            source_payload = payload.get("source")
            page = source_payload.get("page") if isinstance(source_payload, dict) else None
            detail_items.append(
                EvidenceGroupItem(
                    canonical_evidence_id=row.canonical_evidence_id,
                    field_id=field_id,
                    field_name=str(field_name) if field_name else None,
                    category=str(category) if category else None,
                    value=value,
                    review_status=row.review_status,
                    confidence=confidence,
                    track=str(track) if track else None,
                    page=page if isinstance(page, int) else None,
                )
            )


        # Fallback: parse gene/variant from group_id if field-level extraction missed them
        if not gene and group_id:
            gene = parse_gene_from_group_id(group_id)
        if not variant and group_id:
            variant = parse_variant_from_group_id(group_id)
        # Build traces by matching original/translated pairs per field_id
        items_by_field: dict[str, list] = {}
        for row in rows:
            items_by_field.setdefault(row.field_id, []).append(row)

        traces: list[EvidenceTrackTrace] = []
        for field_id, field_rows in items_by_field.items():
            original_row = None
            translated_row = None
            reconciled_row = None
            for row in field_rows:
                payload = row.active_payload or {}
                track = payload.get("track")
                if track == "original":
                    if original_row is not None:
                        logger.debug(
                            "Duplicate original track for field_id={}: "
                            "overwriting with canonical_evidence_id={}",
                            field_id,
                            row.canonical_evidence_id,
                        )
                    original_row = row
                elif track == "translated":
                    if translated_row is not None:
                        logger.debug(
                            "Duplicate translated track for field_id={}: "
                            "overwriting with canonical_evidence_id={}",
                            field_id,
                            row.canonical_evidence_id,
                        )
                    translated_row = row
                elif track == "reconciled":
                    if reconciled_row is None:
                        reconciled_row = row
                else:
                    logger.debug(
                        "Non-standard track value {!r} for field_id={}, "
                        "canonical_evidence_id={} — skipping in trace pairing",
                        track,
                        field_id,
                        row.canonical_evidence_id,
                    )

            # Fall back to reconciled row when no original/translated exist
            if original_row is None and translated_row is None and reconciled_row is not None:
                original_row = reconciled_row

            ref_row = original_row or translated_row or reconciled_row
            if ref_row is None:
                logger.debug(
                    "No usable track found for field_id={} — skipping trace",
                    field_id,
                )
                continue

            original_source = (
                original_row.active_payload.get("source")
                if original_row and original_row.active_payload else {}
            ) or {}
            translated_source = (
                translated_row.active_payload.get("source")
                if translated_row and translated_row.active_payload else {}
            ) or {}
            original_value = (
                _coerce_str(original_row.active_payload.get("value"))
                if original_row and original_row.active_payload else None
            )
            translated_value = (
                _coerce_str(translated_row.active_payload.get("value"))
                if translated_row and translated_row.active_payload else None
            )

            original = _build_highlight(original_source, original_value) if original_source is not None else None
            translated = _build_highlight(translated_source, translated_value) if translated_source is not None else None

            # Fall back to reconciled row's highlight when original/translated
            # sources are non-dict (e.g. "benchmark_ground_truth" strings)
            # and produce no usable highlight.
            if original is None and translated is None and reconciled_row is not None:
                rec_payload = reconciled_row.active_payload or {}
                rec_source = rec_payload.get("source")
                if isinstance(rec_source, dict):
                    rec_value = _coerce_str(rec_payload.get("value"))
                    original = _build_highlight(rec_source, rec_value)
                    original_value = original_value or rec_value

            canonical_id = ref_row.canonical_evidence_id
            field_name = ref_row.active_payload.get("field_name") if ref_row.active_payload else None

            traces.append(
                EvidenceTrackTrace(
                    canonical_evidence_id=canonical_id,
                    field_id=field_id,
                    field_name=str(field_name) if field_name else None,
                    original_value=original_value,
                    translated_value=translated_value,
                    original=original,
                    translated=translated,
                    alignment_confidence=1.0 if original and translated else None,
                )
            )

        return EvidenceGroupDetailResponse(
            group_id=group_id,
            source_document_id=source_document_id,
            title=title,
            pmid=identifiers.get("pmid"),
            doi=identifiers.get("doi"),
            original_document_text=(
                db_original_text
                or _load_full_document_text(
                    source_document_id,
                    track="original",
                    identifiers=identifiers,
                    known_output_dir=phase2_output_dir,
                )
            ),
            translated_document_text=(
                db_translated_text
                or _load_full_document_text(
                    source_document_id,
                    track="translated",
                    identifiers=identifiers,
                    known_output_dir=phase2_output_dir,
                )
            ),
            original_blocks=db_original_blocks,
            translated_blocks=db_translated_blocks,
            gene=gene,
            variant=variant,
            disease=disease,
            classification=classification,
            item_count=len(detail_items),
            avg_confidence=(sum(confidences) / len(confidences)) if confidences else None,
            distribution=distribution,
            items=detail_items,
            traces=traces,
        )
