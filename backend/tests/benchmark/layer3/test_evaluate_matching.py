"""Tests for ClinGen layer-3 value matching."""
from __future__ import annotations

from benchmark.layer3.evaluate import compare_evidence, fuzzy_match_value


def test_fuzzy_match_value_treats_dash_variants_as_equivalent() -> None:
    assert fuzzy_match_value(
        "Charcot-Marie-Tooth disease axonal type 2N",
        "Charcot–Marie–Tooth disease axonal type 2N",
    )


def test_fuzzy_match_value_normalizes_curly_quotes_and_spacing() -> None:
    assert fuzzy_match_value("AARS2-related disease", "AARS2‑related  disease")


def test_fuzzy_match_value_normalizes_cjk_fullwidth_hyphen() -> None:
    assert fuzzy_match_value("AARS2-related disease", "AARS2－related disease")


def test_compare_evidence_counts_extra_found_candidate_as_over_extraction() -> None:
    expected = [{"field_id": "A.gene_symbol", "value": "AARS2"}]
    extracted = [
        {"field_id": "A.gene_symbol", "status": "found", "value": "AARS2", "confidence": 0.9},
        {"field_id": "A.gene_symbol", "status": "found", "value": "BRCA1", "confidence": 0.6},
    ]

    matches = compare_evidence(expected, extracted)

    assert matches[0].matched
    assert matches[0].match_type == "exact"
    assert matches[0].extra_found_values == ["BRCA1"]


def test_compare_evidence_deduplicates_extra_found_values() -> None:
    expected = [{"field_id": "A.gene_symbol", "value": "AARS2"}]
    extracted = [
        {"field_id": "A.gene_symbol", "status": "found", "value": "AARS2", "confidence": 0.9},
        {"field_id": "A.gene_symbol", "status": "found", "value": "BRCA1", "confidence": 0.6},
        {"field_id": "A.gene_symbol", "status": "found", "value": "BRCA1", "confidence": 0.5},
    ]

    matches = compare_evidence(expected, extracted)

    assert matches[0].extra_found_values == ["BRCA1"]
