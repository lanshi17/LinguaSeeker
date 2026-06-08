"""Tests for literature profile refresh after feedback patch."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.core.visualize_evidence_with_expert_in_loop.feedback_service import (
    FeedbackService,
)


@pytest.mark.asyncio
class TestFeedbackProfileRefresh:
    """FeedbackService refreshes literature profile after patching evidence."""

    async def test_feedback_service_has_refresh_method(self) -> None:
        """FeedbackService has _refresh_literature_profile method."""
        service = FeedbackService.__new__(FeedbackService)
        assert hasattr(service, "_refresh_literature_profile")

    async def test_patch_calls_refresh_literature_profile(self) -> None:
        """patch_evidence calls _refresh_literature_profile with source_document_id."""
        from src.core.visualize_evidence_with_expert_in_loop.contracts import (
            EvidencePatchRequest,
        )

        doc_id = uuid4()
        evidence_id = uuid4()

        # Build a mock evidence row.
        mock_evidence = MagicMock()
        mock_evidence.canonical_evidence_id = evidence_id
        mock_evidence.source_document_id = doc_id
        mock_evidence.active_payload = {
            "gene": "GLA",
            "phenotype": "Fabry disease",
            "classification": None,
            "variant": None,
            "disease": None,
            "evidence_strength": None,
            "evidence_type": None,
            "functional_impact": None,
            "inheritance_pattern": None,
            "zygosity": None,
            "references": [],
            "summary": None,
        }
        mock_evidence.review_status = "provisional"

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = mock_evidence

        session = MagicMock()
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        service = FeedbackService(session)

        with patch.object(
            service, "_refresh_literature_profile", new_callable=AsyncMock
        ) as mock_refresh:
            patch_req = EvidencePatchRequest(
                fields={"phenotype": "Updated"},
                change_reason="test",
            )
            await service.patch_evidence(
                canonical_evidence_id=evidence_id,
                patch=patch_req,
                reviewer_id=None,
            )
            mock_refresh.assert_awaited_once_with(doc_id)

    async def test_refresh_delegates_to_literature_profile_repo(self) -> None:
        """_refresh_literature_profile creates a LiteratureProfileRepository and
        calls refresh_for_document."""
        from src.core.visualize_evidence_with_expert_in_loop.feedback_service import (
            FeedbackService,
        )

        session = MagicMock()
        service = FeedbackService(session)
        doc_id = uuid4()

        # Patch at the source module since the import is lazy (inside the method).
        with patch(
            "src.dao.postgresql.literature_profile_repo.LiteratureProfileRepository"
        ) as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.refresh_for_document = AsyncMock()
            mock_repo_cls.return_value = mock_repo

            await service._refresh_literature_profile(doc_id)

            mock_repo_cls.assert_called_once_with(session)
            mock_repo.refresh_for_document.assert_awaited_once_with(doc_id)

    async def test_refresh_skipped_when_no_deltas_and_no_status_change(self) -> None:
        """_refresh_literature_profile is NOT called when patch produces no
        changes (no deltas and same status)."""
        from src.core.visualize_evidence_with_expert_in_loop.contracts import (
            EvidencePatchRequest,
        )

        evidence_id = uuid4()
        doc_id = uuid4()

        mock_evidence = MagicMock()
        mock_evidence.canonical_evidence_id = evidence_id
        mock_evidence.source_document_id = doc_id
        mock_evidence.active_payload = {
            "gene": "GLA",
            "phenotype": "Fabry disease",
            "classification": None,
            "variant": None,
            "disease": None,
            "evidence_strength": None,
            "evidence_type": None,
            "functional_impact": None,
            "inheritance_pattern": None,
            "zygosity": None,
            "references": [],
            "summary": None,
        }
        mock_evidence.review_status = "provisional"

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = mock_evidence

        session = MagicMock()
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        service = FeedbackService(session)

        with patch.object(
            service, "_refresh_literature_profile", new_callable=AsyncMock
        ) as mock_refresh:
            # Same value => no delta
            patch_req = EvidencePatchRequest(
                fields={"phenotype": "Fabry disease"},
                change_reason="no-op",
            )
            await service.patch_evidence(
                canonical_evidence_id=evidence_id,
                patch=patch_req,
                reviewer_id=None,
            )
            mock_refresh.assert_not_awaited()

    async def test_refresh_called_after_audit_event(self) -> None:
        """_refresh_literature_profile is called after the audit event is
        recorded (verifying call ordering)."""
        from src.core.visualize_evidence_with_expert_in_loop.contracts import (
            EvidencePatchRequest,
        )

        doc_id = uuid4()
        evidence_id = uuid4()

        mock_evidence = MagicMock()
        mock_evidence.canonical_evidence_id = evidence_id
        mock_evidence.source_document_id = doc_id
        mock_evidence.active_payload = {
            "gene": "GLA",
            "phenotype": "Fabry disease",
            "classification": None,
            "variant": None,
            "disease": None,
            "evidence_strength": None,
            "evidence_type": None,
            "functional_impact": None,
            "inheritance_pattern": None,
            "zygosity": None,
            "references": [],
            "summary": None,
        }
        mock_evidence.review_status = "provisional"

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = mock_evidence

        session = MagicMock()
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        service = FeedbackService(session)
        call_order: list[str] = []

        original_record = service._delta_service.record_audit_event

        async def tracking_record_audit(*args, **kwargs):
            call_order.append("audit_event")
            return await original_record(*args, **kwargs)

        with patch.object(
            service._delta_service,
            "record_audit_event",
            side_effect=tracking_record_audit,
        ):
            with patch.object(
                service, "_refresh_literature_profile", new_callable=AsyncMock
            ) as mock_refresh:
                mock_refresh.side_effect = lambda _: call_order.append("refresh")

                patch_req = EvidencePatchRequest(
                    fields={"phenotype": "Updated phenotype"},
                    change_reason="ordering test",
                )
                await service.patch_evidence(
                    canonical_evidence_id=evidence_id,
                    patch=patch_req,
                    reviewer_id=None,
                )

                assert "refresh" in call_order
                assert call_order.index("audit_event") < call_order.index("refresh")
