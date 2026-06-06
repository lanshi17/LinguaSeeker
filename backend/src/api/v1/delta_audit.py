"""Delta audit query routes."""
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session, get_phase4_factory
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    DeltaEntry,
    ReviewAuditEventResponse,
    ReviewStatus,
    TargetType,
)

if TYPE_CHECKING:
    from src.dao.postgresql.models import ReviewAuditEvent

router = APIRouter()


@router.get("", response_model=list[ReviewAuditEventResponse])
async def list_audit_events(
    canonical_evidence_id: UUID | None = None,
    reviewer_id: UUID | None = None,
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_db_session),
) -> list[ReviewAuditEventResponse]:
    """List review audit events with optional filters."""
    service = get_phase4_factory().delta_audit
    events = await service.list_audit_events(
        session,
        canonical_evidence_id=canonical_evidence_id,
        reviewer_id=reviewer_id,
        limit=limit,
    )
    return [_to_response(e) for e in events]


def _to_response(event: ReviewAuditEvent) -> ReviewAuditEventResponse:
    """Convert ORM model to API response."""
    return ReviewAuditEventResponse(
        review_event_id=event.review_event_id,
        canonical_evidence_id=event.canonical_evidence_id,
        reviewer_id=event.reviewer_id,
        target_type=TargetType(event.target_type),
        old_status=ReviewStatus(event.old_status) if event.old_status else None,
        new_status=ReviewStatus(event.new_status) if event.new_status else None,
        field_deltas=[DeltaEntry(**d) for d in event.field_deltas],
        change_reason=event.change_reason,
        created_at=event.created_at,
    )
