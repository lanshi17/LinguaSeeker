"""Evidence search service with field-level pivoting."""
from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidenceSearchResponse,
    EvidenceSearchResult,
)
from src.dao.postgresql.models import (
    CanonicalEvidenceItem,
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
        if doc_ids:
            ident_stmt = select(SourceDocumentIdentifier).where(
                SourceDocumentIdentifier.source_document_id.in_(doc_ids)
            )
            ident_result = await self._session.execute(ident_stmt)
            for ident in ident_result.scalars():
                ident_map.setdefault(str(ident.source_document_id), {})
                ident_map[str(ident.source_document_id)][ident.identifier_type] = ident.identifier_value

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
