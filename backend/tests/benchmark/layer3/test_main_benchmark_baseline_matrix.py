"""Tests for the main-benchmark baseline matrix exporter."""

from __future__ import annotations

import json
from pathlib import Path


def _write_entry(root: Path, entry_id: str) -> None:
    entry_dir = root / entry_id
    entry_dir.mkdir(parents=True)
    (entry_dir / "source.md").write_text("MECP2 causes Rett syndrome.", encoding="utf-8")
    (entry_dir / "expected.json").write_text("{}", encoding="utf-8")


def _write_report(
    path: Path,
    *,
    baseline_id: str | None,
    total_entries: int,
    error_entries: int = 0,
) -> None:
    per_entry = [
        {
            "entry_id": f"gs_{index:03d}",
            "pipeline_status": "error" if index < error_entries else "completed",
        }
        for index in range(total_entries)
    ]
    payload = {
        "evaluation_id": "eval_unified_test" if baseline_id is None else f"baseline_{baseline_id.lower()}_test",
        "timestamp": "2026-07-04T00:00:00",
        "config": {
            "ground_truth_dir": "benchmark/data/ground_truth/unified",
            "model": "gpt-5-2025-08-07",
            "prompt_mode": "prompt-only",
        },
        "total_entries": total_entries,
        "total_duration_s": 20.0,
        "aggregates": {
            "overall": {
                "true_positives": 8,
                "false_positives": 2,
                "false_negatives": 4,
                "precision": 0.8,
                "recall": 0.6667,
                "f1": 0.7273,
            }
        },
        "per_entry": per_entry,
    }
    if baseline_id is not None:
        payload["baseline_id"] = baseline_id
        payload["baseline_name"] = "Test baseline"
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_count_ground_truth_entries_uses_manifest_and_source_files(tmp_path) -> None:
    from benchmark.analysis.baselines.main_benchmark_baseline_matrix import count_ground_truth_entries

    _write_entry(tmp_path, "gs_000")
    (tmp_path / "gs_001").mkdir()
    (tmp_path / "manifest.json").write_text(
        json.dumps({"entries": [{"unified_id": "gs_000"}, {"unified_id": "gs_001"}]}),
        encoding="utf-8",
    )

    assert count_ground_truth_entries(tmp_path) == 1


def test_build_baseline_matrix_marks_partial_coverage_and_errors(tmp_path) -> None:
    from benchmark.analysis.baselines.main_benchmark_baseline_matrix import build_baseline_matrix

    report_path = tmp_path / "baseline_b0.json"
    _write_report(report_path, baseline_id="B0", total_entries=1, error_entries=1)

    payload = build_baseline_matrix(
        report_paths=(report_path,),
        ground_truth_dir=tmp_path,
        expected_entries=2,
    )

    row = payload["rows"][0]
    assert row["method_id"] == "B0"
    assert row["role"] == "baseline"
    assert row["coverage_status"] == "partial"
    assert row["error_entries"] == 1
    assert row["warnings"] == "coverage 1/2; 1 error entries"
    assert row["f1"] == 0.7273


def test_write_baseline_matrix_persists_all_formats(tmp_path) -> None:
    from benchmark.analysis.baselines.main_benchmark_baseline_matrix import (
        build_baseline_matrix,
        write_baseline_matrix,
    )

    report_path = tmp_path / "eval.json"
    _write_report(report_path, baseline_id=None, total_entries=2)
    payload = build_baseline_matrix(
        report_paths=(report_path,),
        ground_truth_dir=tmp_path,
        expected_entries=2,
    )

    paths = write_baseline_matrix(payload, reports_dir=tmp_path / "reports")

    assert paths.json.exists()
    assert paths.csv.exists()
    assert paths.markdown.exists()
    assert "LinguaSeeker" in paths.markdown.read_text(encoding="utf-8")
    assert "coverage_status" in paths.csv.read_text(encoding="utf-8")


def test_merge_baseline_reports_replaces_retry_entries_and_recomputes_metrics(tmp_path) -> None:
    from benchmark.analysis.baselines.merge_baseline_reports import merge_baseline_reports

    primary_path = tmp_path / "primary.json"
    retry_path = tmp_path / "retry.json"
    field_match_missing = {
        "field_id": "A.gene_symbol",
        "expected": "MECP2",
        "matched": False,
        "extracted": None,
        "source_span": None,
        "match_type": "missing",
        "extra_found_values": [],
    }
    field_match_found = {
        **field_match_missing,
        "matched": True,
        "extracted": "MECP2",
        "match_type": "exact",
    }
    base_payload = {
        "evaluation_id": "baseline_b1_test",
        "timestamp": "2026-07-04T00:00:00",
        "baseline_id": "B1",
        "baseline_name": "Translate-then-extract",
        "config": {},
        "total_entries": 1,
        "total_duration_s": 1.0,
        "aggregates": {},
        "per_entry": [
            {
                "entry_id": "gs_001",
                "gene_symbol": "MECP2",
                "classification": "",
                "moi": "",
                "language": "en",
                "pipeline_status": "error",
                "error_message": "timeout",
                "duration_s": 1.0,
                "evidence_count": 0,
                "found_rate": 0.0,
                "field_matches": [field_match_missing],
            }
        ],
    }
    retry_payload = {
        **base_payload,
        "per_entry": [
            {
                **base_payload["per_entry"][0],
                "pipeline_status": "completed",
                "error_message": None,
                "evidence_count": 1,
                "found_rate": 1.0,
                "field_matches": [field_match_found],
            }
        ],
    }
    primary_path.write_text(json.dumps(base_payload), encoding="utf-8")
    retry_path.write_text(json.dumps(retry_payload), encoding="utf-8")

    merged_path = merge_baseline_reports(
        primary_report_path=primary_path,
        retry_report_paths=(retry_path,),
        reports_dir=tmp_path / "reports",
    )

    merged = json.loads(merged_path.read_text(encoding="utf-8"))
    assert merged["per_entry"][0]["pipeline_status"] == "completed"
    assert merged["aggregates"]["overall"]["true_positives"] == 1
    assert merged["aggregates"]["overall"]["f1"] == 1.0
    assert merged["config"]["retry_replaced_entries"] == ["gs_001"]


def test_main_benchmark_baseline_figure_renders_complete_rows(tmp_path) -> None:
    from benchmark.analysis.baselines.main_benchmark_baseline_figure import write_prf1_figure

    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-07-04T00:00:00",
                "ground_truth_dir": "ground_truth",
                "expected_entries": 2,
                "rows": [
                    {
                        "method_id": "LinguaSeeker",
                        "coverage_status": "complete",
                        "error_entries": 0,
                        "precision": 0.6,
                        "recall": 0.4,
                        "f1": 0.48,
                        "total_entries": 2,
                    },
                    {
                        "method_id": "B0",
                        "coverage_status": "partial",
                        "error_entries": 0,
                        "precision": 1.0,
                        "recall": 1.0,
                        "f1": 1.0,
                        "total_entries": 1,
                    },
                    {
                        "method_id": "B2",
                        "coverage_status": "complete",
                        "error_entries": 0,
                        "precision": 0.8,
                        "recall": 0.2,
                        "f1": 0.32,
                        "total_entries": 2,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    svg_path = write_prf1_figure(matrix_path=matrix_path, output_dir=tmp_path)

    svg_text = svg_path.read_text(encoding="utf-8")
    assert "LinguaSeeker" in svg_text
    assert "GPT-5 prompt-only" not in svg_text
    assert "GPT-5 original-only" in svg_text
    assert "N=2" in svg_text


def test_original_only_config_uses_canonical_model_metadata(tmp_path) -> None:
    from benchmark.analysis.baselines.original_only import build_config

    config = build_config(
        ground_truth_dir=tmp_path / "gt",
        reports_dir=tmp_path / "reports",
        entry_ids=("gs_001",),
        limit=1,
        save_report=False,
    )

    assert config.baseline_id == "B2"
    assert config.metadata["model"] == "gpt-5-2025-08-07"
    assert config.metadata["prompt_mode"] == "original_only"
