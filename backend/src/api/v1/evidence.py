"""Evidence review and feedback routes."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.requests import Request

from src.api.rate_limit import limiter
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import require_api_key
from src.api.deps import get_db_session, get_phase4_factory
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidencePatchRequest,
    EvidenceSearchResponse,
    EvidenceSearchResult,
    PatchResultResponse,
)
from src.dao.postgresql.search_index_repo import SearchIndexRepository

router = APIRouter()


@router.get("/search", response_model=EvidenceSearchResponse)
@limiter.limit("60/minute")
async def search_evidence(
    request: Request,
    gene: str | None = Query(None, description="Gene name (case-insensitive partial match)"),
    variant: str | None = Query(None, description="Variant description (case-insensitive partial match)"),
    disease: str | None = Query(None, description="Disease name (case-insensitive partial match)"),
    pmid: str | None = Query(None, description="PubMed ID (exact match)"),
    limit: int = Query(50, ge=1, le=500, description="Max results to return"),
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> EvidenceSearchResponse:
    """Search evidence cards from the frontend search index.

    When no filters are supplied, returns all evidence (default list view),
    ordered by PMID.
    """
    repo = SearchIndexRepository(session)
    rows = await repo.search(
        gene=gene,
        variant=variant,
        disease=disease,
        pmid=pmid,
        limit=limit,
    )

    items = [
        EvidenceSearchResult(
            canonical_evidence_id=row["canonical_evidence_id"],
            pmid=row.get("pmid"),
            doi=row.get("doi"),
            gene_ids=row.get("gene_ids", []),
            variant_ids=row.get("variant_ids", []),
            field_id=row["field_id"],
            review_status=row["review_status"],
            current_best_confidence=(
                float(row["current_best_confidence"])
                if row.get("current_best_confidence") is not None
                else None
            ),
            active_payload=row.get("active_payload", {}),
        )
        for row in rows
    ]

    return EvidenceSearchResponse(items=items, total=len(items))


@router.patch("/{canonical_evidence_id}", response_model=PatchResultResponse)
@limiter.limit("30/minute")
async def patch_evidence(
    request: Request,
    canonical_evidence_id: UUID,
    body: EvidencePatchRequest,
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> PatchResultResponse:
    """Apply a patch to an evidence card and record audit event."""
    factory = get_phase4_factory()
    service = factory.create_feedback_service(session)
    try:
        result = await service.patch_evidence(
            canonical_evidence_id=canonical_evidence_id,
            patch=body,
            reviewer_id=None,
        )
        return PatchResultResponse(
            canonical_evidence_id=result.canonical_evidence_id,
            old_status=result.old_status,
            new_status=result.new_status,
            deltas=result.deltas,
            field_deltas=result.field_deltas,
        )
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Evidence not found")
