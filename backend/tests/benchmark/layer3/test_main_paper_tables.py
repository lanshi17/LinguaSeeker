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
