"""Tests for evidence verification contracts."""

from __future__ import annotations

import dataclasses

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.verify.contracts import (
    EvidenceVerificationInput,
    EvidenceVerificationResult,
    RelationshipLabel,
)


def test_relationship_label_rejects_unknown_values() -> None:
    with pytest.raises(ValueError):
        RelationshipLabel("maybe_causal")


def test_verification_result_scores_must_be_probabilities() -> None:
    with pytest.raises(ValueError, match="support_score"):
        EvidenceVerificationResult(
            field_id="A.gene_disease_relationship",
            recommended_value="causative",
            support_score=1.2,
            contradiction_score=0.0,
            target_specificity_score=1.0,
            rationale="out of range",
            requires_review=False,
        )


def test_verification_contracts_are_immutable() -> None:
    verification_input = EvidenceVerificationInput(
        entry_id="clingen_024",
        field_id="A.gene_disease_relationship",
        candidate_value="causative",
        source_snippet="TLR5 causes systemic lupus erythematosus.",
        source_precision="exact",
        track="original",
        target_gene="TLR5",
        target_disease="systemic lupus erythematosus",
        disease_aliases=("systemic lupus erythematosus", "SLE"),
        moi="AD",
    )

    assert dataclasses.is_dataclass(verification_input)
    assert verification_input.__dataclass_params__.frozen is True
