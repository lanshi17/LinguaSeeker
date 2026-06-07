"""Evidence search service."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidenceSearchResponse,
    EvidenceSearchResult,
)
from src.dao.postgresql.models import (
    CanonicalEvidenceItem,
    SourceDocumentIdentifier,
)


class SearchService:
    """Search evidence cards with filtering."""

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
        """Search evidence with optional filters."""
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

        stmt = (
            select(CanonicalEvidenceItem)
            .order_by(CanonicalEvidenceItem.field_id)
            .limit(limit)
        )
        if conditions:
            from sqlalchemy import and_
            stmt = stmt.where(and_(*conditions))

        result = await self._session.execute(stmt)
        items = result.scalars().all()

        # Batch-load identifiers for all matched documents
        doc_ids = {item.source_document_id for item in items}
        ident_map: dict[str, dict[str, str]] = {}
        if doc_ids:
            ident_stmt = select(SourceDocumentIdentifier).where(
                SourceDocumentIdentifier.source_document_id.in_(doc_ids)
            )
            ident_result = await self._session.execute(ident_stmt)
            for ident in ident_result.scalars():
                ident_map.setdefault(str(ident.source_document_id), {})
                ident_map[str(ident.source_document_id)][ident.identifier_type] = ident.identifier_value

        # Filter by PMID/DOI if specified
        filtered = []
        for item in items:
            doc_ident = ident_map.get(str(item.source_document_id), {})
            if pmid and pmid not in doc_ident.get("pmid", ""):
                continue
            if doi and doi.lower() not in doc_ident.get("doi", "").lower():
                continue
            filtered.append((item, doc_ident))

        results = []
        for item, doc_ident in filtered:
            payload = item.active_payload or {}
            results.append(
                EvidenceSearchResult(
                    canonical_evidence_id=item.canonical_evidence_id,
                    pmid=doc_ident.get("pmid"),
                    doi=doc_ident.get("doi"),
                    gene_ids=[payload["gene"]] if payload.get("gene") else [],
                    variant_ids=[payload["variant"]] if payload.get("variant") else [],
                    field_id=item.field_id,
                    review_status=item.review_status,
                    current_best_confidence=float(item.current_best_confidence) if item.current_best_confidence else None,
                    active_payload=payload,
                )
            )

        return EvidenceSearchResponse(items=results, total=len(results))
