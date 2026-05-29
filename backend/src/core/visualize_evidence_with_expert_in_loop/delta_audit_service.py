"""Delta audit service for evidence review tracking."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    DeltaEntry,
    EvidenceCardPayload,
    ReviewStatus,
    TargetType,
)
from src.dao.postgresql.models import ReviewAuditEvent


class DeltaAuditService:
    """Compute and persist field-level deltas for evidence review."""

    @staticmethod
    def compute_deltas(
        old: EvidenceCardPayload,
        new: EvidenceCardPayload,
    ) -> list[DeltaEntry]:
        """Compute field-level differences between two payloads.

        Returns empty list if payloads are identical.
        """
        deltas: list[DeltaEntry] = []
        for field in EvidenceCardPayload.DIFF_FIELDS:
            old_value = getattr(old, field)
            new_value = getattr(new, field)
            if old_value != new_value:
                deltas.append(
                    DeltaEntry(
                        field=field,
                        old_value=old_value,
                        new_value=new_value,
                    )
                )
        return deltas

    async def record_audit_event(
        self,
        session: AsyncSession,
        *,
        canonical_evidence_id: UUID,
        reviewer_id: UUID | None,
        target_type: TargetType,
        old_status: ReviewStatus | None,
        new_status: ReviewStatus | None,
        field_deltas: list[DeltaEntry],
        change_reason: str | None = None,
    ) -> ReviewAuditEvent:
        """Persist a review audit event with field deltas."""
        event = ReviewAuditEvent(
            canonical_evidence_id=canonical_evidence_id,
            reviewer_id=reviewer_id,
            target_type=target_type.value,
            old_status=old_status.value if old_status else None,
            new_status=new_status.value if new_status else None,
            field_deltas=[d.model_dump() for d in field_deltas],
            change_reason=change_reason,
        )
        session.add(event)
        await session.flush()
        return event

    async def list_audit_events(
        self,
        session: AsyncSession,
        *,
        canonical_evidence_id: UUID | None = None,
        reviewer_id: UUID | None = None,
        limit: int = 100,
    ) -> list[ReviewAuditEvent]:
        """Query review audit events with optional filters."""
        stmt = select(ReviewAuditEvent)
        if canonical_evidence_id:
            stmt = stmt.where(
                ReviewAuditEvent.canonical_evidence_id == canonical_evidence_id
            )
        if reviewer_id:
            stmt = stmt.where(ReviewAuditEvent.reviewer_id == reviewer_id)
        stmt = stmt.order_by(ReviewAuditEvent.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())
