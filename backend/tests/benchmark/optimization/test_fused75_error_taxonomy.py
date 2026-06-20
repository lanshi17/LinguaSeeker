"""Tests for fused-75 adjudicated error taxonomy."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.optimization.fused75.adjudication_contracts import Fused75EntryAdjudication, Fused75FieldAdjudication
from benchmark.optimization.fused75.error_taxonomy import (
    build_detailed_error_taxonomy,
    build_error_taxonomy,
    write_detailed_error_taxonomy_report,
)
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


def test_detailed_error_taxonomy_preserves_field_level_errors() -> None:
    report = build_detailed_error_taxonomy(
        (
            _entry(
                "fused_004",
                (
                    AdjudicatedFieldResult(
                        field_id="A.variant_hgvs_p",
                        expected_value="p.Arg81*",
                        extracted_value=None,
                        outcome="fn",
                    ),
                    AdjudicatedFieldResult(
                        field_id="A.variant_hgvs_p",
                        expected_value="",
                        extracted_value="Arg81Ter",
                        outcome="fp",
                    ),
                    AdjudicatedFieldResult(
                        field_id="B.disease_diagnosis",
                        expected_value="SCID",
                        extracted_value=None,
                        outcome="fn",
                    ),
                ),
            ),
        )
    )

    assert report.counts["normalization_error"] == 1
    assert report.counts["candidate_absent"] == 1
    assert [error.category for error in report.errors] == [
        "normalization_error",
        "normalization_error",
        "candidate_absent",
    ]
    assert report.errors[0].entry_id == "fused_004"
    assert report.errors[0].field_id == "A.variant_hgvs_p"
    assert report.errors[0].expected_value == "p.Arg81*"
    assert report.errors[1].extracted_value == "Arg81Ter"


def test_detailed_error_taxonomy_can_attach_source_visible_label_context() -> None:
    adjudication = Fused75EntryAdjudication(
        entry_id="fused_005",
        split="adjudication_dev",
        source_path=Path("source.md"),
        expected_path=Path("expected.json"),
        is_complete=True,
        labels=(
            Fused75FieldAdjudication(
                field_id="A.gene_symbol",
                expected_value="DICER1",
                visibility="source_visible",
                source_quote="Germline pathogenic variants in DICER1",
                source_location="Abstract",
                adjudicator="human",
            ),
        ),
    )

    report = build_detailed_error_taxonomy(
        (
            _entry(
                "fused_005",
                (
                    AdjudicatedFieldResult(
                        field_id="A.gene_symbol",
                        expected_value="DICER1",
                        extracted_value=None,
                        outcome="fn",
                    ),
                ),
            ),
        ),
        adjudications=(adjudication,),
    )

    assert report.errors[0].source_quote == "Germline pathogenic variants in DICER1"
    assert report.errors[0].source_location == "Abstract"


def test_write_detailed_error_taxonomy_report_writes_stable_json(tmp_path: Path) -> None:
    report = build_detailed_error_taxonomy(
        (
            _entry(
                "fused_006",
                (
                    AdjudicatedFieldResult(
                        field_id="B.disease_diagnosis",
                        expected_value="retinopathy",
                        extracted_value=None,
                        outcome="fn",
                    ),
                ),
            ),
        )
    )
    output_path = tmp_path / "taxonomy.json"

    write_detailed_error_taxonomy_report(report, output_path)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload == {
        "counts": {
            "candidate_absent": 1,
            "normalization_error": 0,
            "not_source_visible_label": 0,
            "unsupported_prediction": 0,
            "wrong_boundary": 0,
            "wrong_relationship": 0,
        },
        "errors": [
            {
                "category": "candidate_absent",
                "entry_id": "fused_006",
                "expected_value": "retinopathy",
                "extracted_value": None,
                "field_id": "B.disease_diagnosis",
                "outcome": "fn",
                "source_location": None,
                "source_quote": None,
            }
        ],
    }
