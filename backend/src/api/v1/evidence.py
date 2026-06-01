"""Evidence review and feedback routes."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import require_api_key
from src.api.deps import get_db_session, get_phase4_factory
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidencePatchRequest,
    PatchResultResponse,
)

router = APIRouter()


@router.patch("/{canonical_evidence_id}", response_model=PatchResultResponse)
async def patch_evidence(
    canonical_evidence_id: UUID,
    patch: EvidencePatchRequest,
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
            patch=patch,
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
