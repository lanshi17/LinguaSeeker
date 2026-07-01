"""Evidence review, feedback, and search routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from src.api.auth import require_api_key
from src.api.deps import get_db_session, get_phase4_factory
from src.api.rate_limit import limiter
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidenceGroupDetailResponse,
    EvidenceGroupSummary,
    EvidencePatchRequest,
    EvidenceSearchResponse,
    LiteratureProfileDetailResponse,
    LiteratureProfileSummary,
    LiteratureSearchResponse,
    PatchResultResponse,
)
from src.core.visualize_evidence_with_expert_in_loop.search_service import SearchService
from src.dao.postgresql.literature_profile_repo import LiteratureProfileRepository
from src.dao.postgresql.models import SourceDocument

router = APIRouter()


@router.get("/groups/detail", response_model=EvidenceGroupDetailResponse)
async def get_evidence_group_detail(
    group_id: str | None = Query(None, description="Evidence group identifier"),
    source_document_id: UUID | None = Query(None, description="Source document UUID to scope results"),
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> EvidenceGroupDetailResponse:
    """Return grouped evidence detail with distribution and traceability.

    At least one of *group_id* or *source_document_id* must be provided.
    When only *source_document_id* is given, the service picks the first
    group found for that document.
    """
    if not group_id and not source_document_id:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one of group_id or source_document_id",
        )
    service = SearchService(session)
    try:
        return await service.get_group_detail(
            group_id=group_id,
            source_document_id=str(source_document_id) if source_document_id else None,
        )
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
    _api_key: str | None = Depends(require_api_key),
    gene: str | None = Query(None, description="Filter by gene (partial match on A.gene_symbol)"),
    variant: str | None = Query(None, description="Filter by variant (partial match on HGVS fields)"),
    disease: str | None = Query(None, description="Filter by disease (partial match on diagnosis fields)"),
    pmid: str | None = Query(None, description="Filter by PMID (exact match)"),
    doi: str | None = Query(None, description="Filter by DOI (partial match)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
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
    _api_key: str | None = Depends(require_api_key),
    gene: str | None = Query(None, description="Filter by gene name"),
    variant: str | None = Query(None, description="Filter by variant"),
    disease: str | None = Query(None, description="Filter by disease"),
    pmid: str | None = Query(None, description="Filter by PMID (exact)"),
    doi: str | None = Query(None, description="Filter by DOI (partial)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> LiteratureSearchResponse:
    """Search literature profiles with per-article aggregation."""
    repo = LiteratureProfileRepository(session)
    items, total = await repo.search(
        gene=gene,
        variant=variant,
        disease=disease,
        pmid=pmid,
        doi=doi,
        page=page,
        page_size=page_size,
    )
    return LiteratureSearchResponse(
        items=[LiteratureProfileSummary(**vars(item)) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/literature/{source_document_id}/detail",
    response_model=LiteratureProfileDetailResponse,
)
async def get_literature_detail(
    source_document_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> LiteratureProfileDetailResponse:
    """Return full literature profile with all evidence groups."""
    repo = LiteratureProfileRepository(session)
    profile = await repo.get_by_document(source_document_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Literature profile not found")

    return LiteratureProfileDetailResponse(
        literature_profile_id=UUID(profile.literature_profile_id),
        source_document_id=UUID(profile.source_document_id),
        pmid=profile.pmid,
        doi=profile.doi,
        title=profile.title,
        authors=profile.authors,
        journal=profile.journal,
        publication_year=profile.publication_year,
        evidence_groups=[EvidenceGroupSummary(**eg) for eg in profile.evidence_groups],
        review_status=profile.review_status,
        review_notes=profile.review_notes,
        overall_confidence=profile.overall_confidence,
        total_evidence_fields=profile.total_evidence_fields,
        found_count=profile.found_count,
        not_found_count=profile.not_found_count,
    )


@router.post("/literature/refresh")
@limiter.limit("5/minute")
async def refresh_literature_profiles(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> dict:  # noqa: dict-return — simple admin status response
    """Refresh all literature profiles from canonical evidence. Admin endpoint."""
    stmt = select(SourceDocument.source_document_id)
    result = await session.execute(stmt)
    doc_ids = [row[0] for row in result.all()]

    repo = LiteratureProfileRepository(session)
    refreshed = 0
    for doc_id in doc_ids:
        await repo.refresh_for_document(doc_id)
        refreshed += 1

    return {"refreshed": refreshed, "total_documents": len(doc_ids)}
