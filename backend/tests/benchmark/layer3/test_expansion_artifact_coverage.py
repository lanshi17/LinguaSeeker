"""Tests for Benchmark C expansion artifact coverage reporting."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.layer3.analysis.expansion_artifact_coverage import (
    build_expansion_artifact_coverage,
    expansion_artifact_coverage_to_payload,
    format_expansion_artifact_coverage,
    write_expansion_artifact_coverage,
)


def _write_expansion_selection(ground_truth_root: Path, entry_ids: list[str]) -> Path:
    ground_truth_root.mkdir(parents=True, exist_ok=True)
    selection_path = ground_truth_root / "expansion_selection_20260615.json"
    selection_path.write_text(
        json.dumps(
            {
                "selected_entries": [{"entry_id": entry_id} for entry_id in entry_ids],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return selection_path


def _write_preprocessed_artifact(ground_truth_root: Path, entry_id: str) -> Path:
    artifact_path = ground_truth_root / entry_id / "preprocessed" / "phase_2" / "extraction_result.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps({"entry_id": entry_id}), encoding="utf-8")
    return artifact_path


def test_expansion_artifact_coverage_reports_missing_and_present_artifacts(tmp_path: Path) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    _write_expansion_selection(ground_truth_root, ["clingen_030", "clingen_031"])
    _write_preprocessed_artifact(ground_truth_root, "clingen_030")

    report = build_expansion_artifact_coverage(
        ground_truth_root=ground_truth_root,
        selection_path=ground_truth_root / "expansion_selection_20260615.json",
    )

    assert report.total_entries == 2
    assert report.covered_count == 1
    assert report.needs_pipeline_count == 1
    assert [row.status for row in report.rows] == ["preprocessed", "needs_pipeline_run"]


def test_expansion_artifact_coverage_payload_and_writer(tmp_path: Path) -> None:
    ground_truth_root = tmp_path / "ground_truth"
    reports_dir = tmp_path / "reports"
    _write_expansion_selection(ground_truth_root, ["clingen_030"])
    _write_preprocessed_artifact(ground_truth_root, "clingen_030")

    report = build_expansion_artifact_coverage(
        ground_truth_root=ground_truth_root,
        selection_path=ground_truth_root / "expansion_selection_20260615.json",
    )
    payload = expansion_artifact_coverage_to_payload(report)
    report_path = write_expansion_artifact_coverage(report, reports_dir=reports_dir)

    assert payload["covered_count"] == 1
    assert payload["rows"][0]["entry_id"] == "clingen_030"
    assert report_path.exists()
    assert report_path.name.startswith("expansion_artifact_coverage_")
    assert "Covered=1/1" in format_expansion_artifact_coverage(report)
