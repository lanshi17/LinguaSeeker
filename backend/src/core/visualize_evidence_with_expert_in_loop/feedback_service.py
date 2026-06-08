"""Feedback service for evidence review and correction."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    DeltaEntry,
    EvidenceCardPayload,
    EvidencePatchRequest,
    ReviewStatus,
    TargetType,
)
from src.core.visualize_evidence_with_expert_in_loop.delta_audit_service import (
    DeltaAuditService,
)
from src.dao.postgresql.models import CanonicalEvidenceItem


@dataclass
class PatchResult:
    """Result of an evidence patch operation."""

    canonical_evidence_id: UUID
    old_status: ReviewStatus
    new_status: ReviewStatus
    deltas: int
    field_deltas: list[DeltaEntry]


class FeedbackService:
    """Handle evidence review and correction with audit trail."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._delta_service = DeltaAuditService()

    async def patch_evidence(
        self,
        *,
        canonical_evidence_id: UUID,
        patch: EvidencePatchRequest,
        reviewer_id: UUID | None = None,
    ) -> PatchResult:
        """Apply a patch to an evidence card and record audit event.

        Caller must commit the session after this returns. All changes
        (payload update + audit event) are flushed but not committed.

        Steps:
        1. SELECT current active_payload (old)
        2. Merge patch → new payload
        3. UPDATE active_payload + review_status
        4. Compute deltas (old vs new)
        5. If deltas > 0: INSERT review_audit_event
        6. Return PatchResult
        """
        stmt = select(CanonicalEvidenceItem).where(
            CanonicalEvidenceItem.canonical_evidence_id == canonical_evidence_id
        )
        result = await self._session.execute(stmt)
        evidence = result.scalar_one()

        old_payload = EvidenceCardPayload(**evidence.active_payload)

        new_data = old_payload.model_dump()
        new_data.update(patch.fields)
        new_payload = EvidenceCardPayload(**new_data)

        field_deltas = DeltaAuditService.compute_deltas(old_payload, new_payload)

        old_status = ReviewStatus(evidence.review_status)
        new_status = patch.new_status or (
            ReviewStatus.CORRECTED if field_deltas else old_status
        )

        evidence.active_payload = new_payload.model_dump()
        evidence.review_status = new_status.value
        await self._session.flush()

        if field_deltas or new_status != old_status:
            await self._delta_service.record_audit_event(
                self._session,
                canonical_evidence_id=canonical_evidence_id,
                reviewer_id=reviewer_id,
                target_type=TargetType.EVIDENCE_ITEM,
                old_status=old_status,
                new_status=new_status,
                field_deltas=field_deltas,
                change_reason=patch.change_reason,
            )
            await self._refresh_literature_profile(evidence.source_document_id)

        return PatchResult(
            canonical_evidence_id=canonical_evidence_id,
            old_status=old_status,
            new_status=new_status,
            deltas=len(field_deltas),
            field_deltas=field_deltas,
        )

    async def _refresh_literature_profile(self, source_document_id: UUID) -> None:
        """Rebuild the literature profile for the given source document.

        Lazy-imports LiteratureProfileRepository to avoid circular imports.
        """
        from src.dao.postgresql.literature_profile_repo import (
            LiteratureProfileRepository,
        )

        repo = LiteratureProfileRepository(self._session)
        await repo.refresh_for_document(source_document_id)
