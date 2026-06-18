"""Tests for cross-lingual evidence alignment metrics."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.analysis.dataset_curation.alignment_metrics import (
    AlignmentMetricConfig,
    build_alignment_metric_report,
    alignment_report_to_payload,
)


def _write_alignment_case(
    root: Path,
    *,
    gold_label: str,
    predicted_label: str,
    gold_support: str = "supports",
    predicted_support: str = "supports",
) -> None:
    entry_dir = root / "clingen_000"
    artifact_dir = entry_dir / "preprocessed" / "phase_2"
    artifact_dir.mkdir(parents=True)
    (root / "selection.json").write_text(json.dumps([{"entry_id": "clingen_000"}]), encoding="utf-8")
    (entry_dir / "alignment_annotations.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "entry_id": "clingen_000",
                        "field_id": "A.gene_symbol",
                        "original_value": "GENE1",
                        "translated_value": "GENE1",
                        "normalized_value": "gene1",
                        "original_span_id": "original-p1",
                        "translated_span_id": "translated-p1",
                        "alignment_label": gold_label,
                        "support_label": gold_support,
                        "confidence": 1.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "extraction_result.json").write_text(
        json.dumps(
            {
                "alignment_records": [
                    {
                        "entry_id": "clingen_000",
                        "field_id": "A.gene_symbol",
                        "original_value": "GENE1",
                        "translated_value": "GENE1",
                        "normalized_value": "gene1",
                        "original_span_id": "original-p1",
                        "translated_span_id": "translated-p1",
                        "alignment_label": predicted_label,
                        "support_label": predicted_support,
                        "confidence": 0.9,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_alignment_metrics_reports_accuracy_and_binary_f1(tmp_path: Path) -> None:
    _write_alignment_case(tmp_path, gold_label="drifted", predicted_label="drifted", gold_support="insufficient")

    report = build_alignment_metric_report(AlignmentMetricConfig(ground_truth_root=tmp_path))

    assert report.overall.alignment_accuracy == 1.0
    assert report.overall.support_label_accuracy == 0.0
    assert report.overall.drift_detection_f1 == 1.0
    assert report.overall.conflict_detection_f1 == 0.0
    assert report.counts.total == 1


def test_alignment_metrics_derive_records_when_artifact_has_dual_tracks(tmp_path: Path) -> None:
    entry_dir = tmp_path / "clingen_000"
    artifact_dir = entry_dir / "preprocessed" / "phase_2"
    artifact_dir.mkdir(parents=True)
    (tmp_path / "selection.json").write_text(json.dumps([{"entry_id": "clingen_000"}]), encoding="utf-8")
    (entry_dir / "alignment_annotations.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "entry_id": "clingen_000",
                        "field_id": "A.gene_disease_relationship",
                        "original_value": "causative",
                        "translated_value": "refuted",
                        "normalized_value": "causative",
                        "original_span_id": "original-p1",
                        "translated_span_id": "translated-p1",
                        "alignment_label": "drifted",
                        "support_label": "insufficient",
                        "confidence": 1.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "extraction_result.json").write_text(
        json.dumps(
            {
                "document_id": "doc-1",
                "original_result": {
                    "status": "completed",
                    "document_id": "doc-1",
                    "track": "original",
                    "evidence_items": [
                        {
                            "field_id": "A.gene_disease_relationship",
                            "category": "A",
                            "field_name": "relationship",
                            "status": "found",
                            "value": "causative",
                            "confidence": 0.9,
                            "source": {
                                "span_id": "original-p1",
                                "page": 1,
                                "start_offset": 0,
                                "end_offset": 20,
                                "context_type": "text",
                                "context_ref": "Results",
                                "text_snippet": "GENE1 causes disease.",
                            },
                        }
                    ],
                },
                "translated_result": {
                    "status": "completed",
                    "document_id": "doc-1",
                    "track": "translated",
                    "evidence_items": [
                        {
                            "field_id": "A.gene_disease_relationship",
                            "category": "A",
                            "field_name": "relationship",
                            "status": "found",
                            "value": "refuted",
                            "confidence": 0.8,
                            "source": {
                                "span_id": "translated-p1",
                                "page": 1,
                                "start_offset": 0,
                                "end_offset": 24,
                                "context_type": "text",
                                "context_ref": "Results",
                                "text_snippet": "GENE1 refutes disease.",
                            },
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    report = build_alignment_metric_report(AlignmentMetricConfig(ground_truth_root=tmp_path))

    assert report.overall.alignment_accuracy == 1.0
    assert report.overall.drift_detection_f1 == 1.0
    assert report.by_field["A.gene_disease_relationship"].alignment_accuracy == 1.0


def test_alignment_metrics_ignore_expected_json_for_gold_labels(tmp_path: Path) -> None:
    _write_alignment_case(tmp_path, gold_label="aligned", predicted_label="aligned")
    (tmp_path / "clingen_000" / "expected.json").write_text(
        json.dumps({"alignment_label": "conflict"}),
        encoding="utf-8",
    )

    report = build_alignment_metric_report(AlignmentMetricConfig(ground_truth_root=tmp_path))

    assert report.overall.alignment_accuracy == 1.0
    assert report.counts.total == 1


def test_alignment_metrics_counts_absent_prediction_as_missing_when_gold_is_missing(tmp_path: Path) -> None:
    entry_dir = tmp_path / "clingen_000"
    artifact_dir = entry_dir / "preprocessed" / "phase_2"
    artifact_dir.mkdir(parents=True)
    (tmp_path / "selection.json").write_text(json.dumps([{"entry_id": "clingen_000"}]), encoding="utf-8")
    (entry_dir / "alignment_annotations.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "entry_id": "clingen_000",
                        "field_id": "A.disease_diagnosis",
                        "original_value": None,
                        "translated_value": None,
                        "normalized_value": "example disease",
                        "original_span_id": "",
                        "translated_span_id": "",
                        "alignment_label": "missing",
                        "support_label": "insufficient",
                        "confidence": 1.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "extraction_result.json").write_text(
        json.dumps({"alignment_records": []}),
        encoding="utf-8",
    )

    report = build_alignment_metric_report(AlignmentMetricConfig(ground_truth_root=tmp_path))

    assert report.overall.alignment_accuracy == 1.0
    assert report.overall.support_label_accuracy == 1.0


def test_alignment_report_payload_exposes_drift_and_conflict_gold_positive_counts(tmp_path: Path) -> None:
    _write_alignment_case(tmp_path, gold_label="aligned", predicted_label="drifted")

    report = build_alignment_metric_report(AlignmentMetricConfig(ground_truth_root=tmp_path))
    payload = alignment_report_to_payload(report)

    assert payload["counts"]["drift_gold_positive"] == 0
    assert payload["counts"]["conflict_gold_positive"] == 0
