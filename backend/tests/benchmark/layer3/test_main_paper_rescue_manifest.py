"""Tests for BIBM Main Paper rescue baseline manifests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.analysis.paper_artifacts.main_paper_rescue_manifest import (
    build_manifest,
    manifest_to_payload,
    write_manifest,
)
from benchmark.core.paths import GROUND_TRUTH_CLINGEN_ROOT


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
    alignment_report = _write_json(
        tmp_path / "alignment_metrics_20260616_124445.json",
        {
            "overall": {
                "alignment": {
                    "alignment_accuracy": 0.8667,
                    "support_label_accuracy": 0.9,
                    "drift_detection_f1": 0.0,
                    "conflict_detection_f1": 0.0,
                }
            },
            "counts": {"total": 90},
            "by_field": {},
        },
    )
    evidence_augmentation_report = _write_json(
        tmp_path / "evidence_augmentation_metrics_20260615_224236.json",
        {
            "overall": {
                "evidence_coverage_gain": 0.0647,
                "non_english_evidence_yield": 0.0608,
                "unique_evidence_gain": 56,
                "traceable_augmentation_rate": 1.0,
                "interpretation_relevant_evidence_gain": 0.1964,
                "reviewer_burden": 0.0,
            },
            "per_case": [],
        },
    )
    benchmark_b_runtime_report = _write_json(
        tmp_path / "benchmark_b_phase2_runtime_metrics_20260616_135521.json",
        {
            "overall": {
                "evidence_coverage_gain": 1.0,
                "non_english_evidence_yield": 0.5,
                "unique_evidence_gain": 6,
                "traceable_augmentation_rate": 1.0,
                "interpretation_relevant_evidence_gain": 0.1667,
                "reviewer_burden": 0.0,
            },
            "per_case": [{"phase2_status": "completed"}],
            "warnings": [],
        },
    )
    source_inventory_report = _write_json(
        tmp_path / "source_inventory_20260616_165214.json",
        {
            "summary": {
                "structured_anchor_count": 3,
                "clinvar_fused_entry_count": 75,
                "raw_pdf_count": 185,
                "main_multilingual_pdf_count": 185,
            }
        },
    )
    manifest = build_manifest(
        coverage_report_path=_coverage_report(tmp_path / "coverage.json"),
        ablation_report_path=ablation_report,
        g2_report_path=_g2_report(tmp_path / "g2.json", source_report_path=ablation_report),
        baseline_report_paths=(
            _baseline_report(tmp_path / "baseline_b0.json", label="B0"),
            _baseline_report(tmp_path / "baseline_b1.json", label="B1"),
        ),
        git_commit="abc123",
        ground_truth_root=GROUND_TRUTH_CLINGEN_ROOT,
        alignment_report_path=alignment_report,
        evidence_augmentation_report_path=evidence_augmentation_report,
        benchmark_b_runtime_report_path=benchmark_b_runtime_report,
        source_inventory_report_path=source_inventory_report,
    )

    payload = manifest_to_payload(manifest)

    assert payload["git_commit"] == "abc123"
    assert payload["coverage"]["covered_count"] == 30
    assert payload["g2_statistics"]["main_paper_ready"] is False
    assert payload["g2_statistics"]["significant"] is False
    assert payload["strategies"][1]["strategy"] == "context_verifier_reconcile"
    assert payload["baselines"][0]["label"] == "B0"
    assert payload["source_reports"]["benchmark_a_readiness_report"] is None
    assert payload["source_reports"]["benchmark_b_pilot_selection_report"] is None
    assert payload["source_reports"]["alignment_report"] == str(alignment_report)
    assert payload["source_reports"]["evidence_augmentation_report"] == str(evidence_augmentation_report)
    assert payload["source_reports"]["benchmark_b_runtime_report"] == str(benchmark_b_runtime_report)
    assert payload["source_reports"]["source_inventory_report"] == str(source_inventory_report)


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
        ground_truth_root=GROUND_TRUTH_CLINGEN_ROOT,
    )

    report_path = write_manifest(manifest, reports_dir=tmp_path)

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_path.name.startswith("main_paper_rescue_manifest_")
    assert saved["g2_statistics"]["main_paper_ready"] is False
    assert saved["source_reports"]["g2_report"] == str(tmp_path / "g2.json")


def test_manifest_payload_records_readiness_reports(tmp_path: Path) -> None:
    ablation_report = _ablation_report(tmp_path / "ablation.json")
    readiness_report = _write_json(tmp_path / "benchmark_readiness.json", {"status": "ok"})
    pilot_report = _write_json(tmp_path / "benchmark_b_pilot_selection.json", {"status": "ok"})
    manifest = build_manifest(
        coverage_report_path=_coverage_report(tmp_path / "coverage.json"),
        ablation_report_path=ablation_report,
        g2_report_path=_g2_report(tmp_path / "g2.json", source_report_path=ablation_report),
        baseline_report_paths=(),
        ground_truth_root=GROUND_TRUTH_CLINGEN_ROOT,
        benchmark_a_readiness_report_path=readiness_report,
        benchmark_b_pilot_selection_report_path=pilot_report,
    )

    payload = manifest_to_payload(manifest)

    assert payload["source_reports"]["benchmark_a_readiness_report"] == str(readiness_report)
    assert payload["source_reports"]["benchmark_b_pilot_selection_report"] == str(pilot_report)
