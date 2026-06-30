"""Tests for prepare_extracted_items() — alias remapping, malformed filtering, dedup."""
from __future__ import annotations

from benchmark.core.matching import prepare_extracted_items


def test_remaps_legacy_disease_name_to_b_disease_diagnosis() -> None:
    items = [
        {"field_id": "A.disease_name", "status": "found", "value": "CMT2N", "confidence": 0.9},
    ]
    result = prepare_extracted_items(items)
    assert len(result) == 1
    assert result[0]["field_id"] == "B.disease_diagnosis"
    assert result[0]["value"] == "CMT2N"


def test_filters_malformed_bare_category_field_id() -> None:
    items = [
        {"field_id": "A", "status": "found", "value": "something", "confidence": 0.5},
        {"field_id": "A.gene_symbol", "status": "found", "value": "AARS2", "confidence": 0.9},
    ]
    result = prepare_extracted_items(items)
    assert len(result) == 1
    assert result[0]["field_id"] == "A.gene_symbol"


def test_filters_empty_field_id() -> None:
    items = [
        {"field_id": "", "status": "found", "value": "x", "confidence": 0.5},
        {"field_id": "B.disease_diagnosis", "status": "found", "value": "CMT", "confidence": 0.8},
    ]
    result = prepare_extracted_items(items)
    assert len(result) == 1
    assert result[0]["field_id"] == "B.disease_diagnosis"


def test_deduplicates_same_field_id_and_value_across_tracks() -> None:
    items = [
        {"field_id": "A.gene_symbol", "status": "found", "value": "AARS2", "confidence": 0.95},
        {"field_id": "A.gene_symbol", "status": "found", "value": "AARS2", "confidence": 0.85},
    ]
    result = prepare_extracted_items(items)
    assert len(result) == 1
    assert result[0]["confidence"] == 0.95


def test_keeps_distinct_values_for_same_field_id() -> None:
    items = [
        {"field_id": "A.gene_symbol", "status": "found", "value": "AARS2", "confidence": 0.9},
        {"field_id": "A.gene_symbol", "status": "found", "value": "BRCA1", "confidence": 0.6},
    ]
    result = prepare_extracted_items(items)
    assert len(result) == 2
    values = {r["value"] for r in result}
    assert values == {"AARS2", "BRCA1"}


def test_deduplicates_normalized_equivalent_values() -> None:
    items = [
        {
            "field_id": "B.disease_diagnosis",
            "status": "found",
            "value": "Charcot-Marie-Tooth disease",
            "confidence": 0.9,
        },
        {
            "field_id": "B.disease_diagnosis",
            "status": "found",
            "value": "Charcot–Marie–Tooth disease",
            "confidence": 0.8,
        },
    ]
    result = prepare_extracted_items(items)
    assert len(result) == 1
    assert result[0]["confidence"] == 0.9


def test_filters_items_without_status_found() -> None:
    items = [
        {"field_id": "A.gene_symbol", "status": "not_found", "value": "", "confidence": 0.0},
        {"field_id": "A.gene_symbol", "status": "source_invalid", "value": "AARS2", "confidence": 1.0},
        {"field_id": "A.gene_symbol", "status": "found", "value": "AARS2", "confidence": 0.9},
    ]
    result = prepare_extracted_items(items)
    assert len(result) == 1
    assert result[0]["status"] == "found"
    assert result[0]["value"] == "AARS2"


def test_keeps_low_confidence_found_items_for_smoke_experiment() -> None:
    items = [
        {"field_id": "B.disease_diagnosis", "status": "found", "value": "MERRF syndrome", "confidence": 0.35},
    ]

    result = prepare_extracted_items(items)

    assert len(result) == 1
    assert result[0]["value"] == "MERRF syndrome"
    assert result[0]["confidence"] == 0.35


def test_handles_missing_confidence_gracefully() -> None:
    items = [
        {"field_id": "A.gene_symbol", "status": "found", "value": "AARS2"},
    ]
    result = prepare_extracted_items(items)
    assert len(result) == 1
    assert result[0]["value"] == "AARS2"


def test_legacy_alias_combined_with_dedup_across_tracks() -> None:
    items = [
        {"field_id": "A.disease_name", "status": "found", "value": "CMT2N", "confidence": 0.9},
        {"field_id": "B.disease_diagnosis", "status": "found", "value": "CMT2N", "confidence": 0.8},
    ]
    result = prepare_extracted_items(items)
    assert len(result) == 1
    assert result[0]["field_id"] == "B.disease_diagnosis"
    assert result[0]["confidence"] == 0.9
