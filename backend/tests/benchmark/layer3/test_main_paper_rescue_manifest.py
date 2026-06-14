"""Tests for BIBM Main Paper rescue baseline manifests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.layer3.analysis.main_paper_rescue_manifest import (
    build_manifest,
    manifest_to_payload,
    write_manifest,
)


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _coverage_report(path: Path, *, total_entries: int = 30) -> Path:
    return _write_json(
        path,
        {
            "total_entries": total_entries,
            "covered_count": total_entries,
            "needs_pipeline_count": 0,
        },
    )


def _ablation_report(path: Path, *, entry_ids: tuple[str, ...] = ()) -> Path:
    total_entries = len(entry_ids) if entry_ids else 30
    per_entry = [{"entry_id": entry_id, "pipeline_status": "completed"} for entry_id in entry_ids]
    return _write_json(
        path,
        {
            "strategies": [
                {
                    "strategy": "dual_union",
                    "total_entries": total_entries,
                    "per_entry": per_entry,
                    "aggregates": {"overall": {"precision": 0.8, "recall": 0.88, "f1": 0.84}},
                },
                {
                    "strategy": "context_verifier_reconcile",
                    "total_entries": total_entries,
                    "per_entry": per_entry,
                    "aggregates": {"overall": {"precision": 0.83, "recall": 0.88, "f1": 0.85}},
                },
            ],
        },
    )


def _g2_report(path: Path, *, source_report_path: Path | None = None, sample_size: int = 30) -> Path:
    return _write_json(
        path,
        {
            "source_report_path": str(source_report_path or Path("benchmark/layer3/reports/reconcile_ablation.json")),
            "baseline_strategy": "grounded_hard_rule",
            "candidate_strategy": "context_verifier_reconcile",
            "sample_size": sample_size,
            "baseline_f1": 0.8462,
            "candidate_f1": 0.8535,
            "delta_f1": 0.0073,
            "bootstrap_ci_low": 0.0,
            "bootstrap_ci_high": 0.0233,
            "significant": False,
            "main_paper_ready": False,
        },
    )


def _baseline_report(path: Path, *, label: str, entry_ids: tuple[str, ...] = ()) -> Path:
    total_entries = len(entry_ids) if entry_ids else 30
    return _write_json(
        path,
        {
            "label": label,
            "total_entries": total_entries,
            "per_entry": [{"entry_id": entry_id} for entry_id in entry_ids],
            "aggregates": {"overall": {"precision": 0.9, "recall": 0.9, "f1": 0.9}},
        },
    )


def test_build_manifest_rejects_missing_report_paths(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_manifest(
            coverage_report_path=tmp_path / "missing_coverage.json",
            ablation_report_path=tmp_path / "missing_ablation.json",
            g2_report_path=tmp_path / "missing_g2.json",
            baseline_report_paths=(),
        )


def test_manifest_payload_records_baseline_and_no_go_gate(tmp_path: Path) -> None:
    ablation_report = _ablation_report(tmp_path / "ablation.json")
    manifest = build_manifest(
        coverage_report_path=_coverage_report(tmp_path / "coverage.json"),
        ablation_report_path=ablation_report,
        g2_report_path=_g2_report(tmp_path / "g2.json", source_report_path=ablation_report),
        baseline_report_paths=(
            _baseline_report(tmp_path / "baseline_b0.json", label="B0"),
            _baseline_report(tmp_path / "baseline_b1.json", label="B1"),
        ),
        git_commit="abc123",
    )

    payload = manifest_to_payload(manifest)

    assert payload["git_commit"] == "abc123"
    assert payload["coverage"]["covered_count"] == 30
    assert payload["g2_statistics"]["main_paper_ready"] is False
    assert payload["g2_statistics"]["significant"] is False
    assert payload["strategies"][1]["strategy"] == "context_verifier_reconcile"
    assert payload["baselines"][0]["label"] == "B0"


def test_manifest_payload_records_reproducibility_and_no_leakage(tmp_path: Path) -> None:
    entry_ids = ("clingen_000", "clingen_001")
    ablation_report = _ablation_report(tmp_path / "ablation.json", entry_ids=entry_ids)
    manifest = build_manifest(
        coverage_report_path=_coverage_report(tmp_path / "coverage.json", total_entries=2),
        ablation_report_path=ablation_report,
        g2_report_path=_g2_report(tmp_path / "g2.json", source_report_path=ablation_report, sample_size=2),
        baseline_report_paths=(_baseline_report(tmp_path / "baseline_b0.json", label="B0", entry_ids=entry_ids),),
        git_commit="abc123",
        entry_ids=entry_ids,
    )

    payload = manifest_to_payload(manifest)

    assert payload["reproducibility"]["git_commit"] == "abc123"
    assert payload["reproducibility"]["entry_ids"] == ["clingen_000", "clingen_001"]
    assert payload["reproducibility"]["commands"]["ablation"].startswith("PYTHONPATH=.:backend uv run")
    assert payload["no_leakage"]["uses_expected_fields_at_runtime"] is False
    assert payload["source_reports"]["ablation_report"] == payload["g2_statistics"]["source_report_path"]


def test_build_manifest_rejects_misaligned_g2_source_report(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="G2 source_report_path"):
        build_manifest(
            coverage_report_path=_coverage_report(tmp_path / "coverage.json"),
            ablation_report_path=_ablation_report(tmp_path / "ablation.json"),
            g2_report_path=_g2_report(tmp_path / "g2.json", source_report_path=tmp_path / "older_ablation.json"),
            baseline_report_paths=(),
        )


def test_write_manifest_persists_traceable_json(tmp_path: Path) -> None:
    ablation_report = _ablation_report(tmp_path / "ablation.json")
    manifest = build_manifest(
        coverage_report_path=_coverage_report(tmp_path / "coverage.json"),
        ablation_report_path=ablation_report,
        g2_report_path=_g2_report(tmp_path / "g2.json", source_report_path=ablation_report),
        baseline_report_paths=(),
        git_commit="abc123",
    )

    report_path = write_manifest(manifest, reports_dir=tmp_path)

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_path.name.startswith("main_paper_rescue_manifest_")
    assert saved["g2_statistics"]["main_paper_ready"] is False
    assert saved["source_reports"]["g2_report"] == str(tmp_path / "g2.json")
