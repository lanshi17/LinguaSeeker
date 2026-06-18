"""Tests for fused benchmark evaluation logic."""
from __future__ import annotations

import pytest

from benchmark.datasets.clinvar_fused.evaluate_fused import (
    compare_gene_disease,
    compare_variant_precision,
    compute_aggregate_metrics,
    evaluate_entry_from_preprocessed,
    fuzzy_match,
    normalize_text,
)


class TestNormalizeText:
    def test_basic(self) -> None:
        assert normalize_text("BRCA1") == "BRCA1"

    def test_punctuation(self) -> None:
        assert normalize_text("Charcot–Marie–Tooth") == "Charcot-Marie-Tooth"

    def test_fullwidth(self) -> None:
        assert normalize_text("ＡＴＧＣ") == "ATGC"  # NFKC

    def test_whitespace(self) -> None:
        assert normalize_text("  hello   world  ") == "hello world"


class TestFuzzyMatch:
    def test_exact(self) -> None:
        assert fuzzy_match("BRCA1", "BRCA1") is True

    def test_case_insensitive(self) -> None:
        assert fuzzy_match("brca1", "BRCA1") is True

    def test_substring(self) -> None:
        assert fuzzy_match("breast cancer", "Hereditary breast and ovarian cancer syndrome") is True

    def test_disease_word_overlap(self) -> None:
        assert fuzzy_match(
            "Charcot-Marie-Tooth disease",
            "Charcot-Marie-Tooth disease axonal type 2N",
        ) is True

    def test_no_match(self) -> None:
        assert fuzzy_match("BRCA1", "TP53") is False

    def test_empty(self) -> None:
        assert fuzzy_match("", "BRCA1") is False
        assert fuzzy_match("BRCA1", "") is False


class TestCompareGeneDisease:
    """Tests for Layer 1 gene-disease comparison."""

    def test_exact_match(self) -> None:
        expected = [
            {"field_id": "A.gene_symbol", "value": "BRCA1", "evaluation_type": "precision_recall"},
            {"field_id": "B.disease_diagnosis", "value": "breast cancer", "evaluation_type": "precision_recall"},
        ]
        extracted = [
            {"field_id": "A.gene_symbol", "status": "found", "value": "BRCA1"},
            {"field_id": "B.disease_diagnosis", "status": "found", "value": "breast cancer"},
        ]
        results = compare_gene_disease(expected, extracted)
        assert len(results) == 2
        assert all(r.matched for r in results)
        assert results[0].match_type == "exact"

    def test_missing_field(self) -> None:
        expected = [
            {"field_id": "A.gene_symbol", "value": "BRCA1", "evaluation_type": "precision_recall"},
        ]
        extracted: list[dict] = []
        results = compare_gene_disease(expected, extracted)
        assert len(results) == 1
        assert not results[0].matched

    def test_wrong_value(self) -> None:
        expected = [
            {"field_id": "A.gene_symbol", "value": "BRCA1", "evaluation_type": "precision_recall"},
        ]
        extracted = [
            {"field_id": "A.gene_symbol", "status": "found", "value": "TP53"},
        ]
        results = compare_gene_disease(expected, extracted)
        assert len(results) == 1
        assert not results[0].matched
        assert results[0].match_type == "wrong_value"

    def test_skips_precision_only(self) -> None:
        expected = [
            {"field_id": "A.variant_hgvs_c", "value": "c.123A>G", "evaluation_type": "precision_only"},
        ]
        results = compare_gene_disease(expected, [])
        assert len(results) == 0


class TestCompareVariantPrecision:
    """Tests for Layer 2 variant precision comparison."""

    def test_match_in_candidates(self) -> None:
        expected = [
            {
                "field_id": "A.variant_hgvs_c",
                "value": "c.5266dupC",
                "candidates": ["c.5266dupC", "c.5266dupC"],
                "evaluation_type": "precision_only",
            },
        ]
        extracted = [
            {"field_id": "A.variant_hgvs_c", "status": "found", "value": "c.5266dupC"},
        ]
        results = compare_variant_precision(expected, extracted)
        assert len(results) == 1
        assert results[0].matched
        assert not results[0].is_false_positive

    def test_not_in_candidates(self) -> None:
        expected = [
            {
                "field_id": "A.variant_hgvs_c",
                "value": "c.5266dupC",
                "candidates": ["c.5266dupC"],
                "evaluation_type": "precision_only",
            },
        ]
        extracted = [
            {"field_id": "A.variant_hgvs_c", "status": "found", "value": "c.9999A>T"},
        ]
        results = compare_variant_precision(expected, extracted)
        assert len(results) == 1
        assert not results[0].matched
        assert results[0].is_false_positive

    def test_no_extraction(self) -> None:
        expected = [
            {
                "field_id": "A.variant_hgvs_c",
                "value": "c.5266dupC",
                "candidates": ["c.5266dupC"],
                "evaluation_type": "precision_only",
            },
        ]
        results = compare_variant_precision(expected, [])
        assert len(results) == 1
        assert not results[0].matched
        assert not results[0].is_false_positive  # Not counted as FP

    def test_skips_precision_recall(self) -> None:
        expected = [
            {"field_id": "A.gene_symbol", "value": "BRCA1", "evaluation_type": "precision_recall"},
        ]
        results = compare_variant_precision(expected, [])
        assert len(results) == 0

    def test_multiple_extractions(self) -> None:
        expected = [
            {
                "field_id": "A.variant_hgvs_c",
                "value": "c.5266dupC",
                "candidates": ["c.5266dupC"],
                "evaluation_type": "precision_only",
            },
        ]
        extracted = [
            {"field_id": "A.variant_hgvs_c", "status": "found", "value": "c.5266dupC"},
            {"field_id": "A.variant_hgvs_c", "status": "found", "value": "c.9999A>T"},
        ]
        results = compare_variant_precision(expected, extracted)
        assert len(results) == 2
        assert results[0].matched
        assert not results[1].matched


class TestComputeAggregateMetrics:
    """Tests for aggregate metric computation."""

    def test_empty(self) -> None:
        result = compute_aggregate_metrics([])
        assert result["total_entries"] == 0
        assert result["layer1_gene_disease"]["overall"]["f1"] == 0

    def test_basic_aggregation(self) -> None:
        from benchmark.datasets.clinvar_fused.evaluate_fused import FieldResult, EntryResult

        entry = EntryResult(
            entry_id="test_001",
            gene_symbol="BRCA1",
            classification="Definitive",
            pipeline_status="preprocessed",
            field_results=[
                FieldResult(
                    field_id="A.gene_symbol", expected_value="BRCA1",
                    evaluation_type="precision_recall", matched=True,
                    extracted_value="BRCA1", match_type="exact",
                ),
                FieldResult(
                    field_id="A.variant_hgvs_c", expected_value="c.5266dupC",
                    evaluation_type="precision_only", matched=True,
                    extracted_value="c.5266dupC", match_type="candidate_match",
                ),
            ],
        )

        result = compute_aggregate_metrics([entry])
        gd = result["layer1_gene_disease"]["overall"]
        assert gd["tp"] == 1
        assert gd["f1"] == 1.0
        vp = result["layer2_variant"]
        assert vp["overall_precision"] == 1.0
