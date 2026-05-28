"""Evidence review and feedback routes."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidencePatchRequest,
)
from src.core.visualize_evidence_with_expert_in_loop.feedback_service import (
    FeedbackService,
    PatchResult,
)

router = APIRouter()


@router.patch("/{canonical_evidence_id}")
async def patch_evidence(
    canonical_evidence_id: UUID,
    patch: EvidencePatchRequest,
    session: AsyncSession = Depends(get_db_session),
) -> PatchResult:
    """Apply a patch to an evidence card and record audit event."""
    service = FeedbackService(session)
    try:
        return await service.patch_evidence(
            canonical_evidence_id=canonical_evidence_id,
            patch=patch,
            reviewer_id=None,
        )
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Evidence not found")
