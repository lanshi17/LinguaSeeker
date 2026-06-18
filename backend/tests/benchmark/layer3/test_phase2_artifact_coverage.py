"""Tests for Phase 2 artifact coverage planning."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.analysis.dataset_curation.inventory_system_runs import SystemRunInventory, SystemRunRow
from benchmark.analysis.dataset_curation.phase2_artifact_coverage import (
    Phase2ArtifactCoverageConfig,
    build_phase2_artifact_coverage,
    format_phase2_artifact_coverage,
    phase2_artifact_coverage_to_payload,
    write_phase2_artifact_coverage,
)
from backend.tests.benchmark.layer3.test_materialize_phase2_artifacts import _artifact


def _write_selection(ground_truth_dir: Path, entry_ids: list[str]) -> None:
    ground_truth_dir.mkdir(parents=True)
    (ground_truth_dir / "selection.json").write_text(
        json.dumps([{"entry_id": entry_id, "gene_symbol": "GENE"} for entry_id in entry_ids]),
        encoding="utf-8",
    )
    for entry_id in entry_ids:
        (ground_truth_dir / entry_id).mkdir()


def _write_preprocessed_artifact(ground_truth_dir: Path, entry_id: str) -> None:
    artifact_path = ground_truth_dir / entry_id / "preprocessed" / "phase_2" / "extraction_result.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(_artifact(entry_id).model_dump_json(), encoding="utf-8")


def _write_runtime_artifact(pipeline_root: Path, run_id: str, entry_id: str) -> None:
    artifact_path = pipeline_root / run_id / "phase_2" / "extraction_result.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(_artifact(entry_id).model_dump_json(), encoding="utf-8")


def _db_run(entry_id: str) -> SystemRunRow:
    return SystemRunRow(
        processing_run_id=f"run-{entry_id}",
        source_document_id=f"source-{entry_id}",
        pipeline_status="awaiting_review",
        source_key=f"{entry_id}.md|clingen={entry_id}",
        evidence_count=3,
        found_count=3,
        source_span_count=3,
        updated_at="2026-06-13 10:00:00+08",
    )


def _running_empty_db_run(entry_id: str) -> SystemRunRow:
    return SystemRunRow(
        processing_run_id=f"run-{entry_id}",
        source_document_id=f"source-{entry_id}",
        pipeline_status="running",
        source_key=f"{entry_id}.md|clingen={entry_id}",
        evidence_count=0,
        found_count=0,
        source_span_count=0,
        updated_at="2026-06-13 10:00:00+08",
    )


def test_build_phase2_artifact_coverage_prioritizes_existing_artifacts(tmp_path: Path) -> None:
    ground_truth_dir = tmp_path / "ground_truth"
    pipeline_root = tmp_path / "pipeline"
    entry_ids = ["clingen_000", "clingen_001", "clingen_002", "clingen_003"]
    _write_selection(ground_truth_dir, entry_ids)
    _write_preprocessed_artifact(ground_truth_dir, "clingen_000")
    _write_runtime_artifact(pipeline_root, "runtime-1", "clingen_001")
    inventory = SystemRunInventory(
        total_expected=4,
        best_by_entry={"clingen_002": _db_run("clingen_002")},
        missing_entry_ids=["clingen_000", "clingen_001", "clingen_003"],
        unmapped_count=0,
    )

    report = build_phase2_artifact_coverage(
        Phase2ArtifactCoverageConfig(
            ground_truth_dir=ground_truth_dir,
            pipeline_root=pipeline_root,
        ),
        inventory=inventory,
    )

    statuses = {row.entry_id: row.status for row in report.rows}
    assert statuses == {
        "clingen_000": "preprocessed",
        "clingen_001": "runtime_available",
        "clingen_002": "db_reconstructable",
        "clingen_003": "needs_pipeline_run",
    }
    assert report.covered_count == 3
    assert report.needs_pipeline_count == 1


def test_build_phase2_artifact_coverage_rejects_running_empty_db_runs(tmp_path: Path) -> None:
    ground_truth_dir = tmp_path / "ground_truth"
    pipeline_root = tmp_path / "pipeline"
    _write_selection(ground_truth_dir, ["clingen_019"])
    inventory = SystemRunInventory(
        total_expected=1,
        best_by_entry={"clingen_019": _running_empty_db_run("clingen_019")},
        missing_entry_ids=[],
        unmapped_count=0,
    )

    report = build_phase2_artifact_coverage(
        Phase2ArtifactCoverageConfig(
            ground_truth_dir=ground_truth_dir,
            pipeline_root=pipeline_root,
        ),
        inventory=inventory,
    )

    assert report.rows[0].status == "needs_pipeline_run"
    assert report.covered_count == 0
    assert report.needs_pipeline_count == 1


def test_phase2_artifact_coverage_respects_requested_entries(tmp_path: Path) -> None:
    ground_truth_dir = tmp_path / "ground_truth"
    pipeline_root = tmp_path / "pipeline"
    _write_selection(ground_truth_dir, ["clingen_000", "clingen_001"])
    _write_preprocessed_artifact(ground_truth_dir, "clingen_000")

    report = build_phase2_artifact_coverage(
        Phase2ArtifactCoverageConfig(
            ground_truth_dir=ground_truth_dir,
            pipeline_root=pipeline_root,
            entry_ids=("clingen_001",),
        )
    )

    assert [row.entry_id for row in report.rows] == ["clingen_001"]
    assert report.rows[0].status == "needs_pipeline_run"


def test_format_phase2_artifact_coverage_reports_missing_entries(tmp_path: Path) -> None:
    ground_truth_dir = tmp_path / "ground_truth"
    pipeline_root = tmp_path / "pipeline"
    _write_selection(ground_truth_dir, ["clingen_000"])

    output = format_phase2_artifact_coverage(
        build_phase2_artifact_coverage(
            Phase2ArtifactCoverageConfig(
                ground_truth_dir=ground_truth_dir,
                pipeline_root=pipeline_root,
            )
        )
    )

    assert "covered=0/1" in output
    assert "needs_pipeline=1" in output
    assert "clingen_000 needs_pipeline_run" in output


def test_write_phase2_artifact_coverage_persists_machine_readable_report(tmp_path: Path) -> None:
    ground_truth_dir = tmp_path / "ground_truth"
    pipeline_root = tmp_path / "pipeline"
    reports_dir = tmp_path / "reports"
    _write_selection(ground_truth_dir, ["clingen_000"])
    report = build_phase2_artifact_coverage(
        Phase2ArtifactCoverageConfig(
            ground_truth_dir=ground_truth_dir,
            pipeline_root=pipeline_root,
        )
    )

    report_path = write_phase2_artifact_coverage(report, reports_dir=reports_dir)
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert report_path.name.startswith("phase2_artifact_coverage_")
    assert payload["covered_count"] == 0
    assert payload["needs_pipeline_count"] == 1
    assert payload["rows"][0]["entry_id"] == "clingen_000"
    assert phase2_artifact_coverage_to_payload(report)["total_entries"] == 1
