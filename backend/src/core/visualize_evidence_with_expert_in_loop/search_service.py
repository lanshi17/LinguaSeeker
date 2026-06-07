"""Evidence search service."""
from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidenceSearchResponse,
    EvidenceSearchResult,
)
from src.dao.postgresql.models import (
    CanonicalEvidenceItem,
    ProcessingRun,
    SourceDocument,
    SourceDocumentIdentifier,
)


class SearchService:
    """Search evidence cards with filtering using multi-table JOINs."""

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
        limit: int = 100,
    ) -> EvidenceSearchResponse:
        """Search evidence with optional filters using JOIN queries."""
        # Build base query with JOINs
        # canonical_evidence_items -> source_documents -> source_document_identifiers
        #                          -> processing_runs (for run metadata)
        stmt = (
            select(
                CanonicalEvidenceItem.canonical_evidence_id,
                CanonicalEvidenceItem.source_document_id,
                CanonicalEvidenceItem.field_id,
                CanonicalEvidenceItem.review_status,
                CanonicalEvidenceItem.current_best_confidence,
                CanonicalEvidenceItem.active_payload,
                SourceDocumentIdentifier.identifier_type,
                SourceDocumentIdentifier.identifier_value,
                ProcessingRun.run_status,
                ProcessingRun.created_at,
            )
            .join(
                SourceDocument,
                CanonicalEvidenceItem.source_document_id == SourceDocument.source_document_id,
            )
            .outerjoin(
                SourceDocumentIdentifier,
                CanonicalEvidenceItem.source_document_id == SourceDocumentIdentifier.source_document_id,
            )
            .outerjoin(
                ProcessingRun,
                SourceDocument.latest_processing_run_id == ProcessingRun.processing_run_id,
            )
        )

        # Build WHERE conditions
        conditions = []
        
        if gene:
            conditions.append(
                CanonicalEvidenceItem.active_payload["gene"].astext.ilike(f"%{gene}%")
            )
        if variant:
            conditions.append(
                CanonicalEvidenceItem.active_payload["variant"].astext.ilike(f"%{variant}%")
            )
        if disease:
            conditions.append(
                CanonicalEvidenceItem.active_payload["disease"].astext.ilike(f"%{disease}%")
            )
        if pmid:
            conditions.append(
                and_(
                    SourceDocumentIdentifier.identifier_type == "pmid",
                    SourceDocumentIdentifier.identifier_value.ilike(f"%{pmid}%"),
                )
            )
        if doi:
            conditions.append(
                and_(
                    SourceDocumentIdentifier.identifier_type == "doi",
                    SourceDocumentIdentifier.identifier_value.ilike(f"%{doi}%"),
                )
            )

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(CanonicalEvidenceItem.field_id).limit(limit)

        # Execute query
        result = await self._session.execute(stmt)
        rows = result.all()

        # Group rows by canonical_evidence_id (one evidence can have multiple identifiers)
        evidence_map: dict[str, dict] = {}
        for row in rows:
            evidence_id = str(row.canonical_evidence_id)
            if evidence_id not in evidence_map:
                evidence_map[evidence_id] = {
                    "canonical_evidence_id": row.canonical_evidence_id,
                    "source_document_id": row.source_document_id,
                    "field_id": row.field_id,
                    "review_status": row.review_status,
                    "current_best_confidence": row.current_best_confidence,
                    "active_payload": row.active_payload or {},
                    "identifiers": {},
                    "run_status": row.run_status,
                    "created_at": row.created_at,
                }
            
            # Collect identifiers
            if row.identifier_type and row.identifier_value:
                evidence_map[evidence_id]["identifiers"][row.identifier_type] = row.identifier_value

        # Build results
        results = []
        for data in evidence_map.values():
            payload = data["active_payload"]
            results.append(
                EvidenceSearchResult(
                    canonical_evidence_id=data["canonical_evidence_id"],
                    pmid=data["identifiers"].get("pmid"),
                    doi=data["identifiers"].get("doi"),
                    gene_ids=[payload["gene"]] if payload.get("gene") else [],
                    variant_ids=[payload["variant"]] if payload.get("variant") else [],
                    field_id=data["field_id"],
                    review_status=data["review_status"],
                    current_best_confidence=float(data["current_best_confidence"]) if data["current_best_confidence"] else None,
                    active_payload=payload,
                )
            )

        return EvidenceSearchResponse(items=results, total=len(results))
