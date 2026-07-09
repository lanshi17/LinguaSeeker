"""Source linker routes for evidence traceability."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_account
from src.api.deps import get_db_session, get_phase4_factory
from src.core.auth.contracts import AuthContext
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    BilingualSpan,
    TrackSpan,
)

router = APIRouter()


@router.get("/{canonical_evidence_id}/bilingual", response_model=BilingualSpan)
async def get_bilingual_span(
    canonical_evidence_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    account: AuthContext = Depends(get_current_account),
) -> BilingualSpan:
    """Retrieve bilingual traceability span for an evidence card."""
    factory = get_phase4_factory()
    linker = factory.create_source_linker(session)
    return await linker.get_bilingual_span(
        canonical_evidence_id=canonical_evidence_id,
        owner_user_id=account.owner_user_id,
    )


@router.get("/{canonical_evidence_id}/{track}", response_model=TrackSpan | None)
async def get_track_span(
    canonical_evidence_id: UUID,
    track: str,
    session: AsyncSession = Depends(get_db_session),
    account: AuthContext = Depends(get_current_account),
) -> TrackSpan | None:
    """Retrieve source span for one track (original or translated).

    Returns 404-style null if no span exists for the specified track.
    """
    factory = get_phase4_factory()
    linker = factory.create_source_linker(session)
    return await linker.get_track_span(
        canonical_evidence_id=canonical_evidence_id,
        track=track,
        owner_user_id=account.owner_user_id,
    )
