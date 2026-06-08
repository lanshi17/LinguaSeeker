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
    EvidenceGroupDetailResponse,
    EvidencePatchRequest,
    EvidenceSearchResponse,
    PatchResultResponse,
    LiteratureProfileDetailResponse,
    LiteratureProfileSummary,
    LiteratureSearchResponse,
    EvidenceGroupSummary,
)
from src.core.visualize_evidence_with_expert_in_loop.search_service import SearchService

router = APIRouter()


@router.get("/groups/detail", response_model=EvidenceGroupDetailResponse)
async def get_evidence_group_detail(
    group_id: str = Query(..., description="Evidence group identifier"),
    session: AsyncSession = Depends(get_db_session),
) -> EvidenceGroupDetailResponse:
    """Return grouped evidence detail with distribution and traceability."""
    service = SearchService(session)
    try:
        return await service.get_group_detail(group_id=group_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Evidence group not found")


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


@router.get("/literature/search", response_model=LiteratureSearchResponse)
async def search_literature(
    session: AsyncSession = Depends(get_db_session),
    gene: str | None = Query(None, description="Filter by gene name"),
    variant: str | None = Query(None, description="Filter by variant"),
    disease: str | None = Query(None, description="Filter by disease"),
    pmid: str | None = Query(None, description="Filter by PMID (exact)"),
    doi: str | None = Query(None, description="Filter by DOI (partial)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> LiteratureSearchResponse:
    """Search literature profiles with per-article aggregation."""
    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    repo = LiteratureProfileRepository(session)
    items, total = await repo.search(
        gene=gene, variant=variant, disease=disease,
        pmid=pmid, doi=doi, page=page, page_size=page_size,
    )
    return LiteratureSearchResponse(
        items=[LiteratureProfileSummary(**item) for item in items],
        total=total, page=page, page_size=page_size,
    )


@router.get(
    "/literature/{source_document_id}/detail",
    response_model=LiteratureProfileDetailResponse,
)
async def get_literature_detail(
    source_document_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> LiteratureProfileDetailResponse:
    """Return full literature profile with all evidence groups."""
    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository

    repo = LiteratureProfileRepository(session)
    profile = await repo.get_by_document(source_document_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Literature profile not found")

    return LiteratureProfileDetailResponse(
        literature_profile_id=UUID(profile["literature_profile_id"]),
        source_document_id=UUID(profile["source_document_id"]),
        pmid=profile.get("pmid"),
        doi=profile.get("doi"),
        title=profile.get("title"),
        authors=profile.get("authors", []),
        journal=profile.get("journal"),
        publication_year=profile.get("publication_year"),
        evidence_groups=[
            EvidenceGroupSummary(**eg) for eg in profile.get("evidence_groups", [])
        ],
        review_status=profile.get("review_status", "provisional"),
        overall_confidence=profile.get("overall_confidence"),
        total_evidence_fields=profile.get("total_evidence_fields", 0),
        found_count=profile.get("found_count", 0),
        not_found_count=profile.get("not_found_count", 0),
    )


@router.post("/literature/refresh")
@limiter.limit("5/minute")
async def refresh_literature_profiles(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> dict:  # noqa: dict-return — simple admin status response
    """Refresh all literature profiles from canonical evidence. Admin endpoint."""
    from sqlalchemy import select

    from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository
    from src.dao.postgresql.models import SourceDocument

    stmt = select(SourceDocument.source_document_id)
    result = await session.execute(stmt)
    doc_ids = [row[0] for row in result.all()]

    repo = LiteratureProfileRepository(session)
    refreshed = 0
    for doc_id in doc_ids:
        await repo.refresh_for_document(doc_id)
        refreshed += 1

    return {"refreshed": refreshed, "total_documents": len(doc_ids)}
