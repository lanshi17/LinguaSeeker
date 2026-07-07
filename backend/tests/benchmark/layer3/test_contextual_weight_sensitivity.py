"""Tests for contextual reconcile weight-sensitivity replay."""

from __future__ import annotations

from benchmark.analysis.reconcile.contextual_weight_sensitivity import (
    DEFAULT_WEIGHTS,
    _build_weight_grid,
    _weighted_score,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    Track,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.contracts import (
    CandidateScore,
)


def test_default_grid_uses_current_contextual_seven_term_weights() -> None:
    """Default W2 grid must track contextual.py, not the old 4-term scorer."""
    default = _build_weight_grid()[0]

    assert default.name == "default"
    assert default.source == DEFAULT_WEIGHTS["source"]
    assert default.agreement == DEFAULT_WEIGHTS["agreement"]
    assert default.verifier_support == DEFAULT_WEIGHTS["verifier_support"]
    assert default.target_specificity == DEFAULT_WEIGHTS["target_specificity"]
    assert default.confidence == DEFAULT_WEIGHTS["confidence"]
    assert default.status == DEFAULT_WEIGHTS["status"]
    assert default.contradiction_penalty == DEFAULT_WEIGHTS["contradiction_penalty"]
    assert round(default.positive_total(), 6) == 1.0


def test_weighted_score_includes_verifier_target_and_contradiction_terms() -> None:
    """The replay formula must include the three contextual-only terms."""
    score = CandidateScore(
        field_id="A.gene_disease_relationship",
        track=Track.ORIGINAL,
        normalized_value="causative",
        score=0.0,
        source_score=1.0,
        confidence_score=0.5,
        agreement_score=0.25,
        status_score=1.0,
        verifier_support_score=0.75,
        target_specificity_score=0.5,
        contradiction_penalty=0.4,
    )
    default = _build_weight_grid()[0]

    assert _weighted_score(score, default) == 0.575
