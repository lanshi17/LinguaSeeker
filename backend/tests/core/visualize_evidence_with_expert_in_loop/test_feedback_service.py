"""Tests for feedback service."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidenceCardPayload,
    EvidencePatchRequest,
    ReviewStatus,
)
from src.core.visualize_evidence_with_expert_in_loop.feedback_service import (
    FeedbackService,
)


@pytest.mark.asyncio
class TestFeedbackService:
    """FeedbackService handles evidence card patch operations."""

    async def test_patch_single_field(self, db_session: AsyncSession) -> None:
        """Patching one field updates payload and records delta."""
        evidence_id = await self._create_test_evidence(db_session)

        patch = EvidencePatchRequest(
            fields={"phenotype": "Fabry 病"},
            change_reason="Bilingual correction",
        )
        service = FeedbackService(db_session)
        result = await service.patch_evidence(
            canonical_evidence_id=evidence_id,
            patch=patch,
            reviewer_id=None,
        )

        assert result.new_status == ReviewStatus.CORRECTED
        assert result.deltas == 1
        assert result.field_deltas[0].field == "phenotype"
        assert result.field_deltas[0].old_value == "Fabry disease"
        assert result.field_deltas[0].new_value == "Fabry 病"

    async def test_patch_no_change_skips_delta(self, db_session: AsyncSession) -> None:
        """Patching with identical values produces no delta (zero-noise)."""
        evidence_id = await self._create_test_evidence(db_session)
        patch = EvidencePatchRequest(fields={"phenotype": "Fabry disease"})
        service = FeedbackService(db_session)
        result = await service.patch_evidence(
            canonical_evidence_id=evidence_id,
            patch=patch,
            reviewer_id=None,
        )

        assert result.deltas == 0
        assert result.field_deltas == []

    async def test_patch_multiple_fields(self, db_session: AsyncSession) -> None:
        """Patching multiple fields records all deltas."""
        evidence_id = await self._create_test_evidence(db_session)
        patch = EvidencePatchRequest(
            fields={
                "gene": "GAL",
                "classification": "Pathogenic",
            }
        )
        service = FeedbackService(db_session)
        result = await service.patch_evidence(
            canonical_evidence_id=evidence_id,
            patch=patch,
            reviewer_id=None,
        )

        assert result.deltas == 2
        fields = {d.field for d in result.field_deltas}
        assert fields == {"gene", "classification"}

    async def test_patch_with_explicit_status(self, db_session: AsyncSession) -> None:
        """Explicit new_status overrides auto-CORRECTED."""
        evidence_id = await self._create_test_evidence(db_session)
        patch = EvidencePatchRequest(
            fields={"phenotype": "Fabry 病"},
            new_status=ReviewStatus.APPROVED,
        )
        service = FeedbackService(db_session)
        result = await service.patch_evidence(
            canonical_evidence_id=evidence_id,
            patch=patch,
            reviewer_id=None,
        )

        assert result.new_status == ReviewStatus.APPROVED

    async def test_patch_rejects_invalid_field(self, db_session: AsyncSession) -> None:
        """Arbitrary field paths are rejected."""
        evidence_id = await self._create_test_evidence(db_session)
        with pytest.raises(ValueError, match="Invalid fields"):
            patch = EvidencePatchRequest(fields={"__class__": "exploit"})
            service = FeedbackService(db_session)
            await service.patch_evidence(
                canonical_evidence_id=evidence_id,
                patch=patch,
                reviewer_id=None,
            )

    async def test_patch_empty_fields_rejected(self, db_session: AsyncSession) -> None:
        """Empty fields dict with no status change is rejected by contract validation."""
        with pytest.raises(ValueError, match="at least one"):
            EvidencePatchRequest(fields={})

    async def test_patch_status_only_accepted(self, db_session: AsyncSession) -> None:
        """Empty fields with new_status is a valid status-only patch."""
        req = EvidencePatchRequest(fields={}, new_status=ReviewStatus.APPROVED)
        assert req.new_status == ReviewStatus.APPROVED
        assert req.fields == {}

    async def test_status_only_change_records_audit_event(self, db_session: AsyncSession) -> None:
        """Status-only change (no field deltas) still records an audit event."""
        from sqlalchemy import select

        from src.dao.postgresql.models import ReviewAuditEvent

        evidence_id = await self._create_test_evidence(db_session)
        service = FeedbackService(db_session)

        # Status-only patch: provisional -> approved, no field changes
        patch = EvidencePatchRequest(
            fields={},
            new_status=ReviewStatus.APPROVED,
            change_reason="status-only approval",
        )
        result = await service.patch_evidence(
            canonical_evidence_id=evidence_id,
            patch=patch,
            reviewer_id=None,
        )
        assert result.deltas == 0
        assert result.new_status == ReviewStatus.APPROVED

        # Verify audit event was recorded
        stmt = select(ReviewAuditEvent).where(
            ReviewAuditEvent.canonical_evidence_id == evidence_id
        )
        events = (await db_session.execute(stmt)).scalars().all()
        assert len(events) == 1
        assert events[0].old_status == "provisional"
        assert events[0].new_status == "approved"
        assert events[0].field_deltas == []
        assert events[0].change_reason == "status-only approval"

    async def test_patch_nonexistent_evidence_raises(self, db_session: AsyncSession) -> None:
        """Patching nonexistent evidence raises NoResultFound."""
        from uuid import uuid4

        from sqlalchemy.exc import NoResultFound

        patch = EvidencePatchRequest(fields={"phenotype": "test"})
        service = FeedbackService(db_session)
        with pytest.raises(NoResultFound):
            await service.patch_evidence(
                canonical_evidence_id=uuid4(),
                patch=patch,
                reviewer_id=None,
            )

    async def _create_test_evidence(self, session: AsyncSession) -> uuid.UUID:
        """Helper: create test evidence card with provisional status."""
        from uuid import uuid4

        from src.dao.postgresql.models import CanonicalEvidenceItem, SourceDocument

        doc = SourceDocument(source_document_id=uuid4(), raw_metadata={})
        session.add(doc)
        await session.flush()

        evidence = CanonicalEvidenceItem(
            canonical_evidence_id=uuid4(),
            source_document_id=doc.source_document_id,
            field_id="A.test.1",
            position_hash="abc123",
            text_hash="def456",
            entity_scope_hash="ghi789",
            current_best_status="found",
            review_status="provisional",
            active_payload=EvidenceCardPayload(
                gene="GLA",
                phenotype="Fabry disease",
            ).model_dump(),
        )
        session.add(evidence)
        await session.flush()
        return evidence.canonical_evidence_id
