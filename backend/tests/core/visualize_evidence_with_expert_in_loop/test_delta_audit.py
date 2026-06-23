"""Tests for delta audit service."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    DeltaEntry,
    EvidenceCardPayload,
    ReviewStatus,
    TargetType,
)
from src.core.visualize_evidence_with_expert_in_loop.delta_audit_service import (
    DeltaAuditService,
)
from src.dao.postgresql.models import CanonicalEvidenceItem, SourceDocument


class TestComputeDeltas:
    """DeltaAuditService.compute_deltas detects field-level changes."""

    def test_no_change_returns_empty(self) -> None:
        """Identical payloads produce no deltas."""
        old = EvidenceCardPayload(gene="GLA", phenotype="Fabry disease")
        new = EvidenceCardPayload(gene="GLA", phenotype="Fabry disease")
        deltas = DeltaAuditService.compute_deltas(old, new)
        assert deltas == []

    def test_single_field_change(self) -> None:
        """One field changed produces one delta."""
        old = EvidenceCardPayload(phenotype="Fabry disease")
        new = EvidenceCardPayload(phenotype="Fabry 病")
        deltas = DeltaAuditService.compute_deltas(old, new)
        assert len(deltas) == 1
        assert deltas[0].field == "phenotype"
        assert deltas[0].old_value == "Fabry disease"
        assert deltas[0].new_value == "Fabry 病"

    def test_multiple_field_changes(self) -> None:
        """Multiple fields changed produce multiple deltas."""
        old = EvidenceCardPayload(gene="GLA", classification="VUS")
        new = EvidenceCardPayload(gene="GAL", classification="Pathogenic")
        deltas = DeltaAuditService.compute_deltas(old, new)
        assert len(deltas) == 2
        fields = {d.field for d in deltas}
        assert fields == {"gene", "classification"}

    def test_references_list_replacement(self) -> None:
        """References are compared as whole lists (not element-wise diff)."""
        old = EvidenceCardPayload(references=["PMID:111"])
        new = EvidenceCardPayload(references=["PMID:222"])
        deltas = DeltaAuditService.compute_deltas(old, new)
        assert len(deltas) == 1
        assert deltas[0].field == "references"
        assert deltas[0].old_value == ["PMID:111"]
        assert deltas[0].new_value == ["PMID:222"]

    def test_null_to_value_is_change(self) -> None:
        """None → value is a change."""
        old = EvidenceCardPayload(gene=None)
        new = EvidenceCardPayload(gene="GLA")
        deltas = DeltaAuditService.compute_deltas(old, new)
        assert len(deltas) == 1
        assert deltas[0].old_value is None
        assert deltas[0].new_value == "GLA"

    def test_value_to_null_is_change(self) -> None:
        """value → None is a change."""
        old = EvidenceCardPayload(gene="GLA")
        new = EvidenceCardPayload(gene=None)
        deltas = DeltaAuditService.compute_deltas(old, new)
        assert len(deltas) == 1
        assert deltas[0].old_value == "GLA"
        assert deltas[0].new_value is None


@pytest.mark.asyncio
async def test_list_audit_events_filters_by_source_document(
    db_session: AsyncSession,
) -> None:
    """Source-document filtering returns only events for that literature record."""
    service = DeltaAuditService()
    first_doc_id, first_evidence_id = await _create_evidence(db_session, "A.gene_symbol")
    second_doc_id, second_evidence_id = await _create_evidence(
        db_session,
        "B.disease_diagnosis",
    )

    await service.record_audit_event(
        db_session,
        canonical_evidence_id=first_evidence_id,
        reviewer_id=None,
        target_type=TargetType.EVIDENCE_ITEM,
        old_status=ReviewStatus.PROVISIONAL,
        new_status=ReviewStatus.CORRECTED,
        field_deltas=[DeltaEntry(field="gene", old_value="GLA", new_value="PRKN")],
    )
    await service.record_audit_event(
        db_session,
        canonical_evidence_id=second_evidence_id,
        reviewer_id=None,
        target_type=TargetType.EVIDENCE_ITEM,
        old_status=ReviewStatus.PROVISIONAL,
        new_status=ReviewStatus.APPROVED,
        field_deltas=[],
    )

    events = await service.list_audit_events(
        db_session,
        source_document_id=first_doc_id,
    )

    assert [event.canonical_evidence_id for event in events] == [first_evidence_id]
    assert second_doc_id != first_doc_id


async def _create_evidence(session: AsyncSession, field_id: str) -> tuple[UUID, UUID]:
    """Create one source document with one canonical evidence item."""
    source_document_id = uuid4()
    canonical_evidence_id = uuid4()
    session.add(SourceDocument(source_document_id=source_document_id, raw_metadata={}))
    session.add(
        CanonicalEvidenceItem(
            canonical_evidence_id=canonical_evidence_id,
            source_document_id=source_document_id,
            field_id=field_id,
            position_hash=str(uuid4()),
            text_hash=str(uuid4()),
            entity_scope_hash=str(uuid4()),
            current_best_status="found",
            review_status="provisional",
            active_payload={"field_id": field_id, "value": "value"},
        )
    )
    await session.flush()
    return source_document_id, canonical_evidence_id
