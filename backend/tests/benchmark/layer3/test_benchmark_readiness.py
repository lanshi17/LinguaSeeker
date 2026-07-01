"""Tests for Benchmark A readiness reporting."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.analysis.dataset_curation.readiness import (
    BenchmarkReadinessConfig,
    build_benchmark_readiness_report,
    benchmark_readiness_report_to_payload,
    format_benchmark_readiness_report,
    write_benchmark_readiness_report,
)


def _write_selection(root: Path, entry_ids: list[str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "selection.json").write_text(
        json.dumps([{"entry_id": entry_id} for entry_id in entry_ids]),
        encoding="utf-8",
    )
    for entry_id in entry_ids:
        (root / entry_id).mkdir(parents=True, exist_ok=True)


def _write_alignment_annotations(root: Path, entry_id: str, *, alignment_label: str = "aligned") -> None:
    annotation_path = root / entry_id / "alignment_annotations.json"
    annotation_path.parent.mkdir(parents=True, exist_ok=True)
    annotation_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "entry_id": entry_id,
                        "field_id": "A.gene_symbol",
                        "original_value": "GENE1",
                        "translated_value": "GENE1",
                        "normalized_value": "gene1",
                        "original_span_id": "original-p1",
                        "translated_span_id": "translated-p1",
                        "alignment_label": alignment_label,
                        "support_label": "supports",
                        "confidence": 1.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _write_invalid_alignment_annotations(root: Path, entry_id: str) -> None:
    annotation_path = root / entry_id / "alignment_annotations.json"
    annotation_path.parent.mkdir(parents=True, exist_ok=True)
    annotation_path.write_text(
        json.dumps(
            {
                "entry_id": entry_id,
                "records": [
                    {
                        "field_id": "A.gene_symbol",
                        "value": "GENE1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_benchmark_readiness_reports_missing_alignment_annotations(tmp_path: Path) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    _write_selection(ground_truth_root, ["clingen_000", "clingen_001"])

    report = build_benchmark_readiness_report(BenchmarkReadinessConfig(ground_truth_root=ground_truth_root))

    assert report.overall.total_entries == 2
    assert report.overall.annotated_count == 0
    assert report.overall.missing_count == 2
    assert report.overall.alignment_annotation_coverage == 0.0
    assert report.overall.missing_entry_ids == ("clingen_000", "clingen_001")
    assert {row.status for row in report.rows} == {"missing_alignment_annotations"}
    assert report.warnings == (
        "clingen_000: missing alignment_annotations.json",
        "clingen_001: missing alignment_annotations.json",
    )


def test_benchmark_readiness_reports_partial_alignment_annotation_coverage(tmp_path: Path) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    _write_selection(ground_truth_root, ["clingen_000", "clingen_001", "clingen_002"])
    _write_alignment_annotations(ground_truth_root, "clingen_001")

    report = build_benchmark_readiness_report(BenchmarkReadinessConfig(ground_truth_root=ground_truth_root))

    assert report.overall.total_entries == 3
    assert report.overall.annotated_count == 1
    assert report.overall.invalid_count == 0
    assert report.overall.missing_count == 2
    assert report.overall.alignment_annotation_coverage == 0.3333
    assert report.overall.missing_entry_ids == ("clingen_000", "clingen_002")
    assert [row.status for row in report.rows] == [
        "missing_alignment_annotations",
        "annotated",
        "missing_alignment_annotations",
    ]


def test_benchmark_readiness_ignores_expected_json_for_alignment_gold(tmp_path: Path) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    _write_selection(ground_truth_root, ["clingen_000"])
    (ground_truth_root / "clingen_000" / "expected.json").write_text(
        json.dumps({"alignment_label": "conflict", "support_label": "contradicts"}),
        encoding="utf-8",
    )

    report = build_benchmark_readiness_report(BenchmarkReadinessConfig(ground_truth_root=ground_truth_root))

    assert report.overall.annotated_count == 0
    assert report.rows[0].status == "missing_alignment_annotations"


def test_benchmark_readiness_marks_invalid_alignment_annotations(tmp_path: Path) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    _write_selection(ground_truth_root, ["clingen_000"])
    _write_invalid_alignment_annotations(ground_truth_root, "clingen_000")

    report = build_benchmark_readiness_report(BenchmarkReadinessConfig(ground_truth_root=ground_truth_root))

    assert report.overall.annotated_count == 0
    assert report.overall.invalid_count == 1
    assert report.overall.missing_count == 1
    assert report.overall.invalid_entry_ids == ("clingen_000",)
    assert report.rows[0].status == "invalid_alignment_annotations"


def test_benchmark_readiness_payload_and_writer(tmp_path: Path) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    reports_dir = tmp_path / "reports"
    _write_selection(ground_truth_root, ["clingen_000"])
    _write_alignment_annotations(ground_truth_root, "clingen_000")

    report = build_benchmark_readiness_report(
        BenchmarkReadinessConfig(ground_truth_root=ground_truth_root, reports_dir=reports_dir)
    )
    payload = benchmark_readiness_report_to_payload(report)
    report_path = write_benchmark_readiness_report(report, reports_dir=reports_dir)

    assert payload["overall"]["alignment_annotation_coverage"] == 1.0
    assert payload["rows"][0]["status"] == "annotated"
    assert report_path.exists()
    assert report_path.name.startswith("benchmark_readiness_")
    assert "AlignmentAnnotationCoverage=1.0" in format_benchmark_readiness_report(report)
