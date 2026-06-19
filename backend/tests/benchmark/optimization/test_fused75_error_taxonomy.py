"""Tests for fused-75 adjudicated error taxonomy."""
from __future__ import annotations

from benchmark.optimization.fused75.error_taxonomy import build_error_taxonomy
from benchmark.optimization.fused75.evaluate_adjudicated import AdjudicatedEntryResult, AdjudicatedFieldResult, AdjudicatedMetric


def _entry(entry_id: str, fields: tuple[AdjudicatedFieldResult, ...]) -> AdjudicatedEntryResult:
    return AdjudicatedEntryResult(
        entry_id=entry_id,
        metric=AdjudicatedMetric(precision=0.0, recall=0.0, f1=0.0, tp=0, fp=0, fn=0),
        field_results=fields,
    )


def test_error_taxonomy_classifies_candidate_absent_false_negative() -> None:
    report = build_error_taxonomy(
        (
            _entry(
                "fused_000",
                (
                    AdjudicatedFieldResult(
                        field_id="A.gene_symbol",
                        expected_value="CFTR",
                        extracted_value=None,
                        outcome="fn",
                    ),
                ),
            ),
        )
    )

    assert report.counts["candidate_absent"] == 1
    assert report.examples["candidate_absent"] == ("fused_000",)


def test_error_taxonomy_classifies_unsupported_prediction_false_positive() -> None:
    report = build_error_taxonomy(
        (
            _entry(
                "fused_001",
                (
                    AdjudicatedFieldResult(
                        field_id="B.disease_diagnosis",
                        expected_value="",
                        extracted_value="unreviewed disease",
                        outcome="fp",
                    ),
                ),
            ),
        )
    )

    assert report.counts["unsupported_prediction"] == 1
    assert report.examples["unsupported_prediction"] == ("fused_001",)


def test_error_taxonomy_classifies_wrong_boundary_for_same_field_fn_fp_pair() -> None:
    report = build_error_taxonomy(
        (
            _entry(
                "fused_002",
                (
                    AdjudicatedFieldResult(
                        field_id="B.disease_diagnosis",
                        expected_value="cystic fibrosis",
                        extracted_value=None,
                        outcome="fn",
                    ),
                    AdjudicatedFieldResult(
                        field_id="B.disease_diagnosis",
                        expected_value="",
                        extracted_value="CFTR-related disorder",
                        outcome="fp",
                    ),
                ),
            ),
        )
    )

    assert report.counts["wrong_boundary"] == 1
    assert report.counts["candidate_absent"] == 0
    assert report.counts["unsupported_prediction"] == 0


def test_error_taxonomy_classifies_normalization_error_for_variant_field() -> None:
    report = build_error_taxonomy(
        (
            _entry(
                "fused_003",
                (
                    AdjudicatedFieldResult(
                        field_id="A.variant_hgvs_c",
                        expected_value="c.1521_1523del",
                        extracted_value=None,
                        outcome="fn",
                    ),
                    AdjudicatedFieldResult(
                        field_id="A.variant_hgvs_c",
                        expected_value="",
                        extracted_value="1521_1523del",
                        outcome="fp",
                    ),
                ),
            ),
        )
    )

    assert report.counts["normalization_error"] == 1
    assert report.examples["normalization_error"] == ("fused_003",)
