"""Source linker routes for evidence traceability."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    BilingualSpan,
    TrackSpan,
)
from src.core.visualize_evidence_with_expert_in_loop.source_linker import (
    SourceLinker,
)

router = APIRouter()


@router.get("/{canonical_evidence_id}/bilingual")
async def get_bilingual_span(
    canonical_evidence_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> BilingualSpan:
    """Retrieve bilingual traceability span for an evidence card."""
    linker = SourceLinker(session)
    return await linker.get_bilingual_span(
        canonical_evidence_id=canonical_evidence_id
    )


@router.get("/{canonical_evidence_id}/{track}")
async def get_track_span(
    canonical_evidence_id: UUID,
    track: str,
    session: AsyncSession = Depends(get_db_session),
) -> TrackSpan | None:
    """Retrieve source span for one track (original or translated).

    Returns 404-style null if no span exists for the specified track.
    """
    linker = SourceLinker(session)
    return await linker.get_track_span(
        canonical_evidence_id=canonical_evidence_id,
        track=track,
    )
