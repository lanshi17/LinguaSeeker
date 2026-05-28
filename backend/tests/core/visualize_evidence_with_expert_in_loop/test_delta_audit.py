"""Tests for delta audit service."""
from __future__ import annotations

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    EvidenceCardPayload,
)
from src.core.visualize_evidence_with_expert_in_loop.delta_audit_service import (
    DeltaAuditService,
)


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
