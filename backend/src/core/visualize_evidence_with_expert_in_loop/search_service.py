"""Evidence search service with field-level pivoting."""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any
from uuid import UUID

from loguru import logger

from sqlalchemy import and_, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

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


def _parse_source_offset(raw: object) -> int | None:
    """Parse a stored source offset, preserving missing/invalid as None."""
    if raw is None:
        return None
    return int(raw)


def _find_value_anchor(text: str, value: str | None) -> tuple[int, int] | None:
    """Find a safe value anchor in snippet text."""
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
        match = re.search(rf"(?<![A-Za-z0-9]){re.escape(candidate)}(?![A-Za-z0-9])", text)
        if not match:
            return None
        return match.start(), match.end()

    index = text.lower().find(candidate.lower())
    if index < 0:
        return None
    return index, index + len(candidate)


def _build_highlight(
    source_span: dict[str, object],
    value: str | None = None,
) -> EvidenceChainHighlight | None:
    """Build a clamped highlight payload from a stored source span.

    Source spans store document-global offsets, but text_snippet is a short
    excerpt. When offsets fall outside the snippet bounds, fall back to
    locating the evidence value within the snippet text.
    """
    if not source_span:
        return None

    text = str(source_span.get("text_snippet") or "")
    if not text:
        return None

    text_len = len(text)
    start = _parse_source_offset(source_span.get("start_offset"))
    end = _parse_source_offset(source_span.get("end_offset"))

    # Clamp offsets to snippet bounds. When start exceeds text length
    # the offsets are document-global; fall back to locating value in snippet.
    if start is None or end is None or start >= text_len:
        anchor = _find_value_anchor(text, value)
        if anchor:
            start, end = anchor
        else:
            start, end = 0, 0
    else:
        if end < start:
            end = text_len
        start = max(start, 0)
        end = min(max(end, start), text_len)

    page = source_span.get("page")
    clean_source_span = {k: v for k, v in source_span.items() if v is not None}
    return EvidenceChainHighlight(
        text=text,
        highlight_start=max(start, 0),
        highlight_end=min(max(end, 0), text_len),
        page=page if isinstance(page, int) else None,
        source_span=clean_source_span,
    )



def _load_full_document_text(
    source_document_id: str | UUID,
    track: str = "original",
) -> str | None:
    """Load full text content for a source document from phase 2 pipeline output.

    Looks for JSON files in the pipeline data directory structure.
    Returns concatenated text from all blocks, or None if not found.
    """
    # Base data directory
    data_root = Path(__file__).resolve().parents[4] / "data" / "pipeline"
    if not data_root.exists():
        return None

    # Convert UUID to string
    doc_id_str = str(source_document_id)

    # Search for the document across all pipeline runs
    for pipeline_dir in data_root.iterdir():
        if not pipeline_dir.is_dir():
            continue
        phase2_dir = pipeline_dir / "phase_2"
        if not phase2_dir.exists():
            continue
        doc_dir = phase2_dir / doc_id_str
        if not doc_dir.exists():
            continue
        
        # Load the requested track
        doc_file = doc_dir / f"{track}.json"
        if not doc_file.exists():
            continue

        try:
            with open(doc_file, "r", encoding="utf-8") as f:
                doc_data = json.load(f)
            # Concatenate all text blocks
            return "\n\n".join(block.get("text", "").strip() for block in doc_data.get("blocks", []) if block.get("text"))
        except Exception:
            logger.warning("Failed to load full {} text for document {}", track, doc_id_str)
            return None

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
        """Search evidence with optional filters and pagination.

        Groups field-level extractions by group_id and pivots them into
        summary rows with gene/variant/disease/classification columns.
        """
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

        # If filters are present, find matching group_ids first
        matching_group_ids = None
        if conditions:
            filter_stmt = (
                select(CanonicalEvidenceItem.active_payload["group_id"].astext)
                .where(and_(*conditions))
                .distinct()
            )
            result = await self._session.execute(filter_stmt)
            matching_group_ids = [row[0] for row in result.all()]
            if not matching_group_ids:
                return EvidenceSearchResponse(items=[], total=0, page=page, page_size=page_size)

        # Build main query: fetch all fields for matching groups
        stmt = (
            select(
                CanonicalEvidenceItem.canonical_evidence_id,
                CanonicalEvidenceItem.source_document_id,
                CanonicalEvidenceItem.field_id,
                CanonicalEvidenceItem.review_status,
                CanonicalEvidenceItem.current_best_confidence,
                CanonicalEvidenceItem.active_payload,
                CanonicalEvidenceItem.created_at,
            )
        )

        if matching_group_ids:
            stmt = stmt.where(
                CanonicalEvidenceItem.active_payload["group_id"].astext.in_(matching_group_ids)
            )

        stmt = stmt.order_by(
            CanonicalEvidenceItem.source_document_id,
            CanonicalEvidenceItem.active_payload["group_id"].astext,
            CanonicalEvidenceItem.field_id,
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        # Pivot: group by group_id and extract summary fields
        groups: dict[str, dict] = {}
        for row in rows:
            payload = row.active_payload or {}
            group_id = payload.get("group_id", "")
            if not group_id:
                continue

            if group_id not in groups:
                groups[group_id] = {
                    "group_id": group_id,
                    "source_document_id": row.source_document_id,
                    "canonical_evidence_id": row.canonical_evidence_id,
                    "created_at": row.created_at,
                    "review_status": row.review_status,
                    "field_count": 0,
                    "confidences": [],
                    "gene": None,
                    "variant": None,
                    "disease": None,
                    "classification": None,
                }

            g = groups[group_id]
            g["field_count"] += 1
            if row.current_best_confidence is not None:
                g["confidences"].append(float(row.current_best_confidence))

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

        # Batch-load identifiers for all source documents
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

        # Build results with pagination
        total = len(groups)
        offset = (page - 1) * page_size
        items = []

        for group_id, g in sorted(groups.items(), key=lambda x: x[0]):
            # Apply PMID/DOI filters
            doc_ident = ident_map.get(str(g["source_document_id"]), {})
            if pmid and pmid not in doc_ident.get("pmid", ""):
                total -= 1
                continue
            if doi and doi.lower() not in doc_ident.get("doi", "").lower():
                total -= 1
                continue

            confs = g["confidences"]
            avg_conf = sum(confs) / len(confs) if confs else None

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
                    avg_confidence=avg_conf,
                    review_status=g["review_status"],
                    canonical_evidence_id=g["canonical_evidence_id"],
                    created_at=g["created_at"],
                )
            )

        # Apply pagination
        paginated_items = items[offset:offset + page_size]

        return EvidenceSearchResponse(
            items=paginated_items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_group_detail(self, *, group_id: str) -> EvidenceGroupDetailResponse:
        """Return detail payload for one grouped evidence row."""
        stmt = (
            select(
                CanonicalEvidenceItem.canonical_evidence_id,
                CanonicalEvidenceItem.source_document_id,
                CanonicalEvidenceItem.field_id,
                CanonicalEvidenceItem.review_status,
                CanonicalEvidenceItem.current_best_confidence,
                CanonicalEvidenceItem.active_payload,
            )
            .where(CanonicalEvidenceItem.active_payload["group_id"].astext == group_id)
            .order_by(CanonicalEvidenceItem.field_id)
        )
        result = await self._session.execute(stmt)
        rows = result.all()
        if not rows:
            raise NoResultFound()

        source_document_id = rows[0].source_document_id

        ident_stmt = select(SourceDocumentIdentifier).where(
            SourceDocumentIdentifier.source_document_id == source_document_id
        )
        ident_result = await self._session.execute(ident_stmt)
        identifiers = {
            ident.identifier_type: ident.identifier_value
            for ident in ident_result.scalars().all()
        }
        metadata_stmt = select(SourceDocument.raw_metadata).where(
            SourceDocument.source_document_id == source_document_id
        )
        metadata_result = await self._session.execute(metadata_stmt)
        raw_metadata = metadata_result.scalar_one_or_none() or {}
        title = (
            _coerce_str(raw_metadata.get("title"))
            if isinstance(raw_metadata, dict)
            else None
        )

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


        # Build traces by matching original/translated pairs per field_id
        items_by_field: dict[str, list] = {}
        for row in rows:
            items_by_field.setdefault(row.field_id, []).append(row)

        traces: list[EvidenceTrackTrace] = []
        for field_id, field_rows in items_by_field.items():
            original_row = None
            translated_row = None
            for row in field_rows:
                payload = row.active_payload or {}
                track = payload.get("track")
                if track == "original":
                    if original_row is not None:
                        logger.warning(
                            "Duplicate original track for field_id={}: "
                            "overwriting with canonical_evidence_id={}",
                            field_id,
                            row.canonical_evidence_id,
                        )
                    original_row = row
                elif track == "translated":
                    if translated_row is not None:
                        logger.warning(
                            "Duplicate translated track for field_id={}: "
                            "overwriting with canonical_evidence_id={}",
                            field_id,
                            row.canonical_evidence_id,
                        )
                    translated_row = row
                else:
                    logger.warning(
                        "Non-standard track value {!r} for field_id={}, "
                        "canonical_evidence_id={} — skipping in trace pairing",
                        track,
                        field_id,
                        row.canonical_evidence_id,
                    )

            ref_row = original_row or translated_row
            if ref_row is None:
                logger.warning(
                    "No original/translated track found for field_id={} — skipping trace",
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
            original_document_text=_load_full_document_text(
                source_document_id, track="original"
            ),
            translated_document_text=_load_full_document_text(
                source_document_id, track="translated"
            ),
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
