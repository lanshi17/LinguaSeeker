"""Tests for primary-extraction plus review-track baseline."""

from __future__ import annotations

from benchmark.analysis.baselines.main_review_track import (
    ReviewDecision,
    _apply_review_decisions,
    _build_primary_prompt,
    _build_review_prompt,
    _raw_client_base_url,
)
from benchmark.analysis.baselines.runner import BaselineEntry, BaselineEvidenceItem


def test_review_decisions_cannot_add_new_fields() -> None:
    """Review track must not introduce candidates absent from primary extraction."""
    primary_items = [
        BaselineEvidenceItem(
            field_id="A.gene_symbol",
            status="found",
            value="MECP2",
            confidence=0.9,
        )
    ]
    decisions = [
        ReviewDecision(
            field_id="B.disease_diagnosis",
            action="correct",
            value="Rett syndrome",
            confidence=0.9,
            source_quote="Rett syndrome was diagnosed.",
        )
    ]

    reviewed = _apply_review_decisions(primary_items, decisions, "Rett syndrome was diagnosed.")

    assert [item.field_id for item in reviewed] == ["A.gene_symbol"]
    assert reviewed[0].value == "MECP2"


def test_review_decision_corrects_existing_candidate_and_maps_quote() -> None:
    """Correct decisions update an existing primary item and preserve traceability."""
    primary_items = [
        BaselineEvidenceItem(
            field_id="B.disease_diagnosis",
            status="found",
            value="neurodevelopmental disorder",
            confidence=0.4,
        )
    ]
    source_text = "The proband was diagnosed with Rett syndrome after regression."
    decisions = [
        ReviewDecision(
            field_id="B.disease_diagnosis",
            action="correct",
            value="Rett syndrome",
            confidence=0.85,
            source_quote="diagnosed with Rett syndrome",
        )
    ]

    reviewed = _apply_review_decisions(primary_items, decisions, source_text)

    assert reviewed[0].status == "found"
    assert reviewed[0].value == "Rett syndrome"
    assert reviewed[0].confidence == 0.85
    assert reviewed[0].source_span is not None
    assert reviewed[0].source_span["source_precision"] == "llm_quote_exact"


def test_review_decision_rejects_existing_candidate() -> None:
    """Reject decisions remove primary false positives from matching by status."""
    primary_items = [
        BaselineEvidenceItem(
            field_id="A.variant_hgvs_p",
            status="found",
            value="p.NotInArticle",
            confidence=0.5,
        )
    ]
    decisions = [ReviewDecision(field_id="A.variant_hgvs_p", action="reject", reason="not supported")]

    reviewed = _apply_review_decisions(primary_items, decisions, "No variant was reported.")

    assert reviewed[0].field_id == "A.variant_hgvs_p"
    assert reviewed[0].status == "not_found"
    assert reviewed[0].value == ""
    assert reviewed[0].confidence == 0.0


def test_primary_prompt_requests_broad_fields_and_source_quotes() -> None:
    entry = BaselineEntry(entry_id="gs_test", gene_symbol="LRRK2", disease_label="Parkinson disease")

    prompt = _build_primary_prompt(entry, "LRRK2 p.G2019S was observed.")

    assert "A.variant_hgvs_p" in prompt
    assert "B.mode_of_inheritance_reported" in prompt
    assert "source_quote" in prompt
    assert "single high-recall primary extraction pass" in prompt


def test_review_prompt_is_limited_to_primary_candidates() -> None:
    entry = BaselineEntry(entry_id="gs_test", gene_symbol="LRRK2", disease_label="Parkinson disease")
    primary_items = [
        BaselineEvidenceItem(
            field_id="A.variant_hgvs_p",
            status="found",
            value="p.G2019S",
            confidence=0.8,
        )
    ]

    prompt = _build_review_prompt(entry, "LRRK2 p.G2019S was observed.", primary_items)

    assert "Do not add new field IDs" in prompt
    assert "approve, reject, or correct" in prompt
    assert "A.variant_hgvs_p" in prompt
    assert "p.G2019S" in prompt


def test_raw_client_base_url_strips_existing_v1_suffix() -> None:
    assert _raw_client_base_url("https://provider.example/v1") == "https://provider.example"
    assert _raw_client_base_url("https://provider.example") == "https://provider.example"
