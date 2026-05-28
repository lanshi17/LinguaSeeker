"""Tests for Phase 4 contracts."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    DeltaEntry,
    EvidenceCardPayload,
    ReviewStatus,
    TargetType,
)


class TestEvidenceCardPayload:
    """EvidenceCardPayload has a fixed schema for diff operations."""

    def test_minimal_payload(self) -> None:
        """All fields are optional."""
        payload = EvidenceCardPayload()
        assert payload.gene is None
        assert payload.references == []

    def test_full_payload(self) -> None:
        """All fields can be populated."""
        payload = EvidenceCardPayload(
            gene="GLA",
            variant="p.R227X",
            phenotype="Fabry disease",
            disease="Fabry disease",
            classification="Pathogenic",
            evidence_strength="PS3",
            evidence_type="Functional",
            functional_impact="Loss of function",
            inheritance_pattern="X-linked",
            zygosity="Hemizygous",
            references=["PMID:12345678"],
            summary="Test summary",
        )
        assert payload.gene == "GLA"
        assert payload.references == ["PMID:12345678"]

    def test_diff_fields_constant(self) -> None:
        """DIFF_FIELDS contains exactly the expected field names."""
        expected = {
            "gene", "variant", "phenotype", "disease", "classification",
            "evidence_strength", "evidence_type", "functional_impact",
            "inheritance_pattern", "zygosity", "references", "summary",
        }
        assert set(EvidenceCardPayload.DIFF_FIELDS) == expected


class TestReviewStatus:
    """ReviewStatus defines the state machine for evidence review."""

    def test_provisional_is_initial(self) -> None:
        assert ReviewStatus.PROVISIONAL.value == "provisional"

    def test_all_states(self) -> None:
        assert set(ReviewStatus) == {
            ReviewStatus.PROVISIONAL,
            ReviewStatus.APPROVED,
            ReviewStatus.CORRECTED,
            ReviewStatus.REJECTED,
        }


class TestTargetType:
    """TargetType enumerates review feedback targets."""

    def test_implemented_types(self) -> None:
        """Three target types are implemented in P0."""
        implemented = {
            TargetType.EVIDENCE_ITEM,
            TargetType.ENTITY,
            TargetType.MISSED_EVIDENCE,
        }
        assert implemented <= set(TargetType)

    def test_declared_but_not_implemented(self) -> None:
        """Other target types are declared but not implemented."""
        assert TargetType.TASK in set(TargetType)
        assert TargetType.NATIVE_EXTRACTION in set(TargetType)


class TestDeltaEntry:
    """DeltaEntry represents a single field change."""

    def test_valid_delta(self) -> None:
        delta = DeltaEntry(
            field="phenotype",
            old_value="Fabry disease",
            new_value="Fabry 病",
        )
        assert delta.field == "phenotype"
        assert delta.field in EvidenceCardPayload.DIFF_FIELDS

    def test_invalid_field_rejected(self) -> None:
        """Arbitrary field paths are rejected to prevent injection."""
        with pytest.raises(ValidationError):
            DeltaEntry(
                field="__class__.__dict__",
                old_value="x",
                new_value="y",
            )
