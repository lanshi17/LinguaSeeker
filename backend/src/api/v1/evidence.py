"""Evidence review, feedback, and search routes."""
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
    PatchResultResponse,
)
from src.core.visualize_evidence_with_expert_in_loop.search_service import SearchService

router = APIRouter()


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
        # TODO: resolve _api_key to a reviewer UUID via a token→user mapping.
        # Currently reviewer_id stays None because API key is a string,
        # not a UUID, and no identity table exists yet.
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


@router.get("/search", response_model=EvidenceSearchResponse)
async def search_evidence(
    session: AsyncSession = Depends(get_db_session),
    gene: str | None = Query(None, description="Filter by gene (partial match on A.gene_symbol)"),
    variant: str | None = Query(None, description="Filter by variant (partial match on HGVS fields)"),
    disease: str | None = Query(None, description="Filter by disease (partial match on diagnosis fields)"),
    pmid: str | None = Query(None, description="Filter by PMID (exact match)"),
    doi: str | None = Query(None, description="Filter by DOI (partial match)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
) -> EvidenceSearchResponse:
    """Search evidence cards with field-level pivoting and pagination.

    Groups field-level extractions by group_id and pivots them into summary
    rows with gene/variant/disease/classification columns.
    """
    service = SearchService(session)
    return await service.search_evidence(
        gene=gene,
        variant=variant,
        disease=disease,
        pmid=pmid,
        doi=doi,
        page=page,
        page_size=page_size,
    )
