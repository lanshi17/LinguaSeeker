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


def _coverage_report(path: Path) -> Path:
    return _write_json(
        path,
        {
            "total_entries": 30,
            "covered_count": 30,
            "needs_pipeline_count": 0,
        },
    )


def _ablation_report(path: Path) -> Path:
    return _write_json(
        path,
        {
            "strategies": [
                {
                    "strategy": "dual_union",
                    "total_entries": 30,
                    "aggregates": {"overall": {"precision": 0.8, "recall": 0.88, "f1": 0.84}},
                },
                {
                    "strategy": "context_verifier_reconcile",
                    "total_entries": 30,
                    "aggregates": {"overall": {"precision": 0.83, "recall": 0.88, "f1": 0.85}},
                },
            ],
        },
    )


def _g2_report(path: Path) -> Path:
    return _write_json(
        path,
        {
            "source_report_path": "benchmark/layer3/reports/reconcile_ablation.json",
            "baseline_strategy": "grounded_hard_rule",
            "candidate_strategy": "context_verifier_reconcile",
            "sample_size": 30,
            "baseline_f1": 0.8462,
            "candidate_f1": 0.8535,
            "delta_f1": 0.0073,
            "bootstrap_ci_low": 0.0,
            "bootstrap_ci_high": 0.0233,
            "significant": False,
            "main_paper_ready": False,
        },
    )


def _baseline_report(path: Path, *, label: str) -> Path:
    return _write_json(
        path,
        {
            "label": label,
            "total_entries": 30,
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
    manifest = build_manifest(
        coverage_report_path=_coverage_report(tmp_path / "coverage.json"),
        ablation_report_path=_ablation_report(tmp_path / "ablation.json"),
        g2_report_path=_g2_report(tmp_path / "g2.json"),
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


def test_write_manifest_persists_traceable_json(tmp_path: Path) -> None:
    manifest = build_manifest(
        coverage_report_path=_coverage_report(tmp_path / "coverage.json"),
        ablation_report_path=_ablation_report(tmp_path / "ablation.json"),
        g2_report_path=_g2_report(tmp_path / "g2.json"),
        baseline_report_paths=(),
        git_commit="abc123",
    )

    report_path = write_manifest(manifest, reports_dir=tmp_path)

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_path.name.startswith("main_paper_rescue_manifest_")
    assert saved["g2_statistics"]["main_paper_ready"] is False
    assert saved["source_reports"]["g2_report"] == str(tmp_path / "g2.json")
