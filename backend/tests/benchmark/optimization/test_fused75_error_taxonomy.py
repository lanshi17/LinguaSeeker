"""Tests for fused-75 adjudicated error taxonomy."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.optimization.fused75.adjudication_contracts import Fused75EntryAdjudication, Fused75FieldAdjudication
from benchmark.optimization.fused75.error_taxonomy import (
    build_detailed_error_taxonomy,
    build_error_taxonomy,
    build_fn_root_cause_taxonomy,
    write_detailed_error_taxonomy_report,
    write_fn_root_cause_taxonomy_report,
)
from benchmark.optimization.fused75.evaluate_adjudicated import (
    AdjudicatedEntryResult,
    AdjudicatedFieldResult,
    AdjudicatedMetric,
)


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


def test_fn_root_cause_classifies_target_span_not_selected_when_quote_absent_from_artifact() -> None:
    detailed = build_detailed_error_taxonomy(
        (
            _entry(
                "fused_007",
                (
                    AdjudicatedFieldResult(
                        field_id="J.clinvar_assertion",
                        expected_value="Pathogenic",
                        extracted_value=None,
                        outcome="fn",
                    ),
                ),
            ),
        ),
        adjudications=(
            _adjudication_with_quote(
                entry_id="fused_007",
                field_id="J.clinvar_assertion",
                expected_value="Pathogenic",
                source_quote="ClinVar lists this variant as Pathogenic.",
            ),
        ),
    )

    report = build_fn_root_cause_taxonomy(detailed, artifact_payloads={"fused_007": {"items": []}})

    assert report.counts["target_span_not_selected"] == 1
    assert report.items[0].root_cause == "target_span_not_selected"


def test_fn_root_cause_classifies_span_selected_field_missing_when_quote_is_in_artifact() -> None:
    detailed = build_detailed_error_taxonomy(
        (
            _entry(
                "fused_008",
                (
                    AdjudicatedFieldResult(
                        field_id="B.mode_of_inheritance_reported",
                        expected_value="AR",
                        extracted_value=None,
                        outcome="fn",
                    ),
                ),
            ),
        ),
        adjudications=(
            _adjudication_with_quote(
                entry_id="fused_008",
                field_id="B.mode_of_inheritance_reported",
                expected_value="AR",
                source_quote="The disease follows an autosomal recessive inheritance pattern.",
            ),
        ),
    )
    artifact = {
        "reconciled_result": {
            "evidence_items": [
                {
                    "field_id": "A.gene_symbol",
                    "value": "CFTR",
                    "source": {
                        "text_snippet": "The disease follows an autosomal recessive inheritance pattern.",
                    },
                }
            ]
        }
    }

    report = build_fn_root_cause_taxonomy(detailed, artifact_payloads={"fused_008": artifact})

    assert report.counts["span_selected_field_missing"] == 1
    assert report.items[0].root_cause == "span_selected_field_missing"


def test_fn_root_cause_classifies_boundary_mismatch_for_paired_same_field_error() -> None:
    detailed = build_detailed_error_taxonomy(
        (
            _entry(
                "fused_009",
                (
                    AdjudicatedFieldResult(
                        field_id="B.disease_diagnosis",
                        expected_value="Stargardt disease",
                        extracted_value=None,
                        outcome="fn",
                    ),
                    AdjudicatedFieldResult(
                        field_id="B.disease_diagnosis",
                        expected_value="",
                        extracted_value="retinal dystrophy",
                        outcome="fp",
                    ),
                ),
            ),
        )
    )

    report = build_fn_root_cause_taxonomy(detailed, artifact_payloads={"fused_009": {"items": []}})

    assert report.counts["field_boundary_mismatch"] == 1
    assert report.items[0].root_cause == "field_boundary_mismatch"


def test_fn_root_cause_classifies_source_quote_invalid_for_unsupported_prediction_without_source_support() -> None:
    detailed = build_detailed_error_taxonomy(
        (
            _entry(
                "fused_010",
                (
                    AdjudicatedFieldResult(
                        field_id="B.disease_diagnosis",
                        expected_value="",
                        extracted_value="unsupported disease",
                        outcome="fp",
                    ),
                ),
            ),
        )
    )
    artifact = {
        "items": [
            {
                "field_id": "B.disease_diagnosis",
                "value": "unsupported disease",
                "source": {"text_snippet": "this sentence belongs to another document"},
            }
        ]
    }

    report = build_fn_root_cause_taxonomy(
        detailed,
        artifact_payloads={"fused_010": artifact},
        source_texts={"fused_010": "The document only discusses cystic fibrosis."},
    )

    assert report.counts["source_quote_invalid"] == 1
    assert report.items[0].root_cause == "source_quote_invalid"


def test_write_fn_root_cause_taxonomy_report_writes_stable_json(tmp_path: Path) -> None:
    detailed = build_detailed_error_taxonomy(
        (
            _entry(
                "fused_011",
                (
                    AdjudicatedFieldResult(
                        field_id="A.variant_type",
                        expected_value="missense",
                        extracted_value=None,
                        outcome="fn",
                    ),
                ),
            ),
        )
    )
    report = build_fn_root_cause_taxonomy(detailed, artifact_payloads={"fused_011": {"items": []}})
    output_path = tmp_path / "root-cause.json"

    write_fn_root_cause_taxonomy_report(report, output_path)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["counts"]["target_span_not_selected"] == 1
    assert payload["items"][0]["entry_id"] == "fused_011"
    assert payload["items"][0]["root_cause"] == "target_span_not_selected"


def _adjudication_with_quote(
    *,
    entry_id: str,
    field_id: str,
    expected_value: str,
    source_quote: str,
) -> Fused75EntryAdjudication:
    return Fused75EntryAdjudication(
        entry_id=entry_id,
        split="adjudication_dev",
        source_path=Path("source.md"),
        expected_path=Path("expected.json"),
        is_complete=True,
        labels=(
            Fused75FieldAdjudication(
                field_id=field_id,
                expected_value=expected_value,
                visibility="source_visible",
                source_quote=source_quote,
                source_location="source.md:1",
                adjudicator="human",
            ),
        ),
    )
