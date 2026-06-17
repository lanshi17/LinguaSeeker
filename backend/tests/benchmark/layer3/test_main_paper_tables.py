"""Tests for BIBM Main Paper table generation."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.layer3.analysis.main_paper_tables import (
    build_main_paper_tables,
    main_paper_tables_to_payload,
    write_main_paper_tables,
)


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _manifest_report(path: Path) -> Path:
    return _manifest_report_with_extras(path, alignment=True, augmentation=True, runtime=True)


def _alignment_report(path: Path) -> Path:
    return _write_json(
        path,
        {
            "overall": {
                "alignment": {
                    "alignment_accuracy": 0.95,
                    "support_label_accuracy": 0.94,
                    "drift_detection_f1": 0.81,
                    "conflict_detection_f1": 0.72,
                }
            },
            "by_field": {},
            "counts": {"total": 40},
        },
    )


def _augmentation_report(path: Path) -> Path:
    return _write_json(
        path,
        {
            "overall": {
                "evidence_coverage_gain": 0.12,
                "non_english_evidence_yield": 0.08,
                "unique_evidence_gain": 3,
                "traceable_augmentation_rate": 0.25,
                "interpretation_relevant_evidence_gain": 0.11,
                "reviewer_burden": 0.04,
            },
            "per_case": [{"matrix": {"non_english_added_evidence_count": 2}}],
        },
    )


def _runtime_report(path: Path) -> Path:
    return _write_json(
        path,
        {
            "runtime_summary": {
                "attempted_samples": 12,
                "phase2_completed": 10,
                "timeout_count": 1,
                "failed_count": 1,
                "completed_queue_ids": [
                    "clingen_000:ja",
                    "clingen_000:ko",
                    "clingen_000:zh",
                    "clingen_001:ja",
                    "clingen_001:ko",
                    "clingen_001:zh",
                    "clingen_002:ja",
                    "clingen_003:ko",
                    "clingen_003:zh",
                    "clingen_004:ja",
                ],
                "failed_queue_ids": ["clingen_005:ja"],
                "incomplete_queue_ids": ["clingen_006:ko"],
                "attempted_distinct_entries": [
                    "clingen_000",
                    "clingen_001",
                    "clingen_002",
                    "clingen_003",
                    "clingen_004",
                    "clingen_005",
                    "clingen_006",
                ],
                "attempted_languages": ["ja", "ko", "zh"],
                "completed_distinct_entries": [
                    "clingen_000",
                    "clingen_001",
                    "clingen_002",
                    "clingen_003",
                    "clingen_004",
                ],
                "completed_languages": ["ja", "ko", "zh"],
            },
            "per_case": [],
        },
    )


def _manifest_report_with_extras(
    path: Path,
    *,
    alignment: bool,
    augmentation: bool,
    runtime: bool,
) -> Path:
    reports_root = path.parent
    alignment_path = reports_root / "alignment_metrics_20260616_144749.json"
    augmentation_path = reports_root / "evidence_augmentation_metrics_20260616_124445.json"
    runtime_path = reports_root / "benchmark_b_phase2_runtime_metrics_20260616_161809.json"
    if alignment:
        _alignment_report(alignment_path)
    if augmentation:
        _augmentation_report(augmentation_path)
    if runtime:
        _runtime_report(runtime_path)
    return _write_json(
        path,
        {
            "generated_at": "2026-06-14T23:00:00+0800",
            "git_commit": "abc123",
            "source_reports": {
                "coverage_report": "benchmark/layer3/reports/coverage.json",
                "ablation_report": "benchmark/layer3/reports/reconcile_ablation_20260614_230554.json",
                "g2_report": "benchmark/layer3/reports/g2_statistics_20260614_230555.json",
                "traceability_report": "benchmark/layer3/reports/traceability_context_verifier_reconcile_20260614_213054.json",
                "benchmark_a_readiness_report": "benchmark/layer3/reports/benchmark_readiness_20260615_180000.json",
                "benchmark_b_pilot_selection_report": "benchmark/layer3/reports/benchmark_b_pilot_selection.json",
                "alignment_report": str(alignment_path) if alignment else None,
                "evidence_augmentation_report": str(augmentation_path) if augmentation else None,
                "benchmark_b_runtime_report": str(runtime_path) if runtime else None,
                "baseline_reports": [
                    "benchmark/layer3/reports/baseline_b0_20260613_031120.json",
                ],
            },
            "reproducibility": {
                "git_commit": "abc123",
                "entry_ids": ["clingen_000", "clingen_001"],
                "generated_reports": [
                    "benchmark/layer3/reports/reconcile_ablation_20260614_230554.json",
                ],
                "commands": {
                    "ablation": "PYTHONPATH=.:backend uv run --project backend --no-sync python -m benchmark.layer3.analysis.reconcile_ablation --write",
                },
            },
            "no_leakage": {
                "uses_expected_fields_at_runtime": False,
                "uses_clingen_classification_at_runtime": False,
                "allowed_runtime_context": ["article source text", "dual-track candidates"],
            },
            "coverage": {
                "total_entries": 30,
                "covered_count": 30,
                "needs_pipeline_count": 0,
            },
            "strategies": [
                {"strategy": "grounded_hard_rule", "total_entries": 30, "precision": 0.8068, "recall": 0.9726, "f1": 0.8820},
                {"strategy": "context_verifier_reconcile", "total_entries": 30, "precision": 0.8977, "recall": 0.9753, "f1": 0.9349},
            ],
            "g2_statistics": {
                "source_report_path": "benchmark/layer3/reports/reconcile_ablation_20260614_230554.json",
                "baseline_strategy": "grounded_hard_rule",
                "candidate_strategy": "context_verifier_reconcile",
                "sample_size": 30,
                "baseline_f1": 0.8820,
                "candidate_f1": 0.9349,
                "delta_f1": 0.0529,
                "bootstrap_ci_low": 0.0133,
                "bootstrap_ci_high": 0.0962,
                "sign_test_p": 0.0391,
                "significant": True,
                "main_paper_ready": True,
            },
            "baselines": [
                {
                    "label": "B0",
                    "report_path": "benchmark/layer3/reports/baseline_b0_20260613_031120.json",
                    "total_entries": 30,
                    "precision": 0.7935,
                    "recall": 0.9733,
                    "f1": 0.8743,
                }
            ],
            "source_inventory_summary": {
                "clinvar_fused_entry_count": 75,
                "main_multilingual_pdf_count": 185,
                "structured_anchor_count": 3,
                "raw_pdf_count": 185,
            },
        },
    )


def test_main_paper_tables_uses_frozen_manifest_and_reports(tmp_path: Path) -> None:
    manifest_path = _manifest_report(tmp_path / "manifest.json")

    tables = build_main_paper_tables(manifest_path=manifest_path)
    payload = main_paper_tables_to_payload(tables)

    assert payload["manifest_path"] == str(manifest_path)
    assert payload["tables"]["Table 1 Dataset composition"][0]["covered_count"] == 30
    assert payload["tables"]["Table 2 Main method vs baselines"][1]["f1"] == 0.9349
    assert payload["tables"]["Table 3 Ablation study"][0]["strategy"] == "grounded_hard_rule"
    assert payload["tables"]["Table 4 Traceability metrics"][0]["strategy_or_baseline_id"] == "context_verifier_reconcile"
    assert payload["tables"]["Table 5 Error breakdown"][0]["root_cause"] == "wrong_relationship_semantics"
    assert payload["tables"]["Table 6 Benchmark readiness and pilot selection"][0]["status"] == "report-available"


def test_main_paper_tables_includes_alignment_evidence_and_runtime_tables(tmp_path: Path) -> None:
    manifest_path = _manifest_report(tmp_path / "manifest.json")

    tables = build_main_paper_tables(manifest_path=manifest_path)
    payload = main_paper_tables_to_payload(tables)

    alignment_rows = payload["tables"]["Table 7 Alignment and drift/conflict detection"]
    overall = next(row for row in alignment_rows if row["scope"] == "overall")
    assert overall["alignment_accuracy"] == 0.95
    assert overall["support_accuracy"] == 0.94
    assert overall["drift_detection_f1"] == 0.81
    assert overall["conflict_detection_f1"] == 0.72
    assert overall["N"] == 40

    augmentation_rows = payload["tables"]["Table 8 Evidence augmentation metrics"]
    aug_overall = next(row for row in augmentation_rows if row["scope"] == "overall")
    assert aug_overall["evidence_coverage_gain"] == 0.12
    assert aug_overall["traceable_augmentation_rate"] == 0.25
    assert aug_overall["N"] == 1

    runtime_rows = payload["tables"]["Table 9 Benchmark B runtime pilot"]
    runtime_overall = next(row for row in runtime_rows if row["scope"] == "overall")
    assert runtime_overall["attempted_samples"] == 12
    assert runtime_overall["phase2_completed"] == 10
    assert runtime_overall["timeout_count"] == 1
    assert runtime_overall["failed_count"] == 1
    assert runtime_overall["attempted_distinct_entries"] == 7
    assert runtime_overall["attempted_languages"] == "ja,ko,zh"
    assert runtime_overall["completed_distinct_entries"] == 5
    assert runtime_overall["completed_languages"] == "ja,ko,zh"


def test_main_paper_tables_emits_status_row_when_report_is_missing(tmp_path: Path) -> None:
    manifest_path = _manifest_report_with_extras(
        tmp_path / "manifest.json",
        alignment=False,
        augmentation=False,
        runtime=False,
    )

    tables = build_main_paper_tables(manifest_path=manifest_path)
    payload = main_paper_tables_to_payload(tables)

    alignment_rows = payload["tables"]["Table 7 Alignment and drift/conflict detection"]
    assert alignment_rows[0]["alignment_accuracy"] is None

    augmentation_rows = payload["tables"]["Table 8 Evidence augmentation metrics"]
    assert augmentation_rows[0]["status"] == "not-yet-reportable"

    runtime_rows = payload["tables"]["Table 9 Benchmark B runtime pilot"]
    assert runtime_rows[0]["status"] == "not-yet-reportable"
    assert runtime_rows[0]["attempted_distinct_entries"] is None
    assert runtime_rows[0]["completed_distinct_entries"] is None


def test_main_paper_tables_prefers_manifest_path_over_glob(tmp_path: Path) -> None:
    manifest_path = _manifest_report(tmp_path / "manifest.json")
    stale_alignment = tmp_path / "alignment_metrics_20200101_000000.json"
    _write_json(
        stale_alignment,
        {
            "overall": {
                "alignment": {
                    "alignment_accuracy": 0.01,
                    "support_label_accuracy": 0.01,
                    "drift_detection_f1": 0.01,
                    "conflict_detection_f1": 0.01,
                }
            },
            "by_field": {},
            "counts": {"total": 1},
        },
    )

    tables = build_main_paper_tables(manifest_path=manifest_path)
    payload = main_paper_tables_to_payload(tables)

    overall = next(
        row
        for row in payload["tables"]["Table 7 Alignment and drift/conflict detection"]
        if row["scope"] == "overall"
    )
    assert overall["alignment_accuracy"] == 0.95


def test_write_main_paper_tables_persists_md_and_csv(tmp_path: Path) -> None:
    manifest_path = _manifest_report(tmp_path / "manifest.json")
    tables = build_main_paper_tables(manifest_path=manifest_path)

    report_paths = write_main_paper_tables(tables, reports_dir=tmp_path)

    assert report_paths.markdown.exists()
    assert report_paths.csv.exists()


def test_write_main_paper_tables_uses_lf_csv_line_endings(tmp_path: Path) -> None:
    manifest_path = _manifest_report(tmp_path / "manifest.json")
    tables = build_main_paper_tables(manifest_path=manifest_path)

    report_paths = write_main_paper_tables(tables, reports_dir=tmp_path)

    assert b"\r\n" not in report_paths.csv.read_bytes()
