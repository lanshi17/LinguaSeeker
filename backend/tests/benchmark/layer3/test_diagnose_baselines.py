"""Tests for layer-3 system-vs-baseline diagnostics."""
from __future__ import annotations

import json
import os
from pathlib import Path

from benchmark.layer3.analysis.diagnose_baselines import (
    build_comparison,
    format_comparison,
)


def _write_expected(ground_truth_dir: Path, entry_id: str, gene: str = "MECP2") -> None:
    entry_dir = ground_truth_dir / entry_id
    entry_dir.mkdir(parents=True)
    (entry_dir / "expected.json").write_text(
        json.dumps(
            {
                "entry_id": entry_id,
                "gene_symbol": gene,
                "disease_label": "Rett syndrome",
                "classification": "Definitive",
                "moi": "XL",
                "expected_evidence": [
                    {"field_id": "A.gene_symbol", "value": gene},
                    {"field_id": "B.disease_diagnosis", "value": "Rett syndrome"},
                    {"field_id": "A.gene_disease_relationship", "value": "causative"},
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_system_report(path: Path) -> None:
    report = {
        "total_entries": 2,
        "aggregates": {
            "overall": {
                "precision": 1.0,
                "recall": 1.0,
                "f1": 1.0,
                "entity_standardization_accuracy": 0.0,
                "cross_lingual_consistency": 0.0,
                "over_extractions": 0,
            }
        },
        "per_entry": [
            {
                "entry_id": "clingen_000",
                "gene_symbol": "MECP2",
                "classification": "Definitive",
                "moi": "XL",
                "pipeline_status": "awaiting_review",
                "field_matches": [
                    {
                        "field_id": "A.gene_symbol",
                        "expected": "MECP2",
                        "matched": True,
                        "extracted": "MECP2",
                        "match_type": "exact",
                        "extra_found_values": [],
                    },
                    {
                        "field_id": "B.disease_diagnosis",
                        "expected": "Rett syndrome",
                        "matched": True,
                        "extracted": "Rett syndrome",
                        "match_type": "exact",
                        "extra_found_values": [],
                    },
                    {
                        "field_id": "A.gene_disease_relationship",
                        "expected": "causative",
                        "matched": True,
                        "extracted": "causative",
                        "match_type": "exact",
                        "extra_found_values": [],
                    },
                ],
            },
            {
                "entry_id": "clingen_001",
                "gene_symbol": "AARS2",
                "classification": "Definitive",
                "moi": "AR",
                "pipeline_status": "timeout",
                "field_matches": [],
            },
        ],
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def _write_baseline_report(path: Path, baseline_id: str, f1: float) -> None:
    report = {
        "baseline_id": baseline_id,
        "baseline_name": f"{baseline_id} baseline",
        "total_entries": 2,
        "aggregates": {
            "overall": {
                "precision": 0.8,
                "recall": 1.0,
                "f1": f1,
                "over_extractions": 0,
                "entity_standardization_accuracy": 0.0,
                "cross_lingual_consistency": 0.0,
            }
        },
        "per_entry": [],
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def _write_baseline_report_with_entries(path: Path, baseline_id: str) -> None:
    report = {
        "baseline_id": baseline_id,
        "baseline_name": f"{baseline_id} baseline",
        "total_entries": 30,
        "aggregates": {
            "overall": {
                "precision": 0.1,
                "recall": 0.1,
                "f1": 0.1,
                "over_extractions": 0,
                "entity_standardization_accuracy": 0.0,
                "cross_lingual_consistency": 0.0,
            }
        },
        "per_entry": [
            {
                "entry_id": "clingen_000",
                "gene_symbol": "MECP2",
                "classification": "Definitive",
                "moi": "XL",
                "pipeline_status": "completed",
                "field_matches": [
                    {
                        "field_id": "A.gene_symbol",
                        "expected": "MECP2",
                        "matched": True,
                        "extracted": "MECP2",
                        "match_type": "exact",
                        "extra_found_values": [],
                    }
                ],
            },
            {
                "entry_id": "clingen_999",
                "gene_symbol": "BRCA1",
                "classification": "Limited",
                "moi": "AD",
                "pipeline_status": "completed",
                "field_matches": [
                    {
                        "field_id": "A.gene_symbol",
                        "expected": "BRCA1",
                        "matched": False,
                        "extracted": None,
                        "match_type": "missing",
                        "extra_found_values": [],
                    }
                ],
            },
        ],
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def test_build_comparison_recomputes_system_metrics_for_empty_failed_entries(tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    ground_truth_dir = tmp_path / "ground_truth"
    reports_dir.mkdir()
    _write_expected(ground_truth_dir, "clingen_000")
    _write_expected(ground_truth_dir, "clingen_001", gene="AARS2")
    system_report = reports_dir / "eval_20260101_000000.json"
    _write_system_report(system_report)
    _write_baseline_report(reports_dir / "baseline_b0_20260101_000000.json", "B0", f1=0.8889)

    comparison = build_comparison(reports_dir=reports_dir, ground_truth_dir=ground_truth_dir)

    system_row = comparison.rows[0]
    assert system_row.label == "SYSTEM"
    assert system_row.f1 == 0.6667
    assert system_row.adjusted
    assert system_row.repaired_missing_entries == 1
    assert comparison.rows[1].label == "B0"


def test_build_comparison_uses_latest_baseline_per_id(tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    ground_truth_dir = tmp_path / "ground_truth"
    reports_dir.mkdir()
    _write_expected(ground_truth_dir, "clingen_000")
    _write_system_report(reports_dir / "eval_20260101_000000.json")
    older = reports_dir / "baseline_b0_20260101_000000.json"
    newer = reports_dir / "baseline_b0_20260102_000000.json"
    _write_baseline_report(older, "B0", f1=0.1)
    _write_baseline_report(newer, "B0", f1=0.9)
    os.utime(older, (100, 100))
    os.utime(newer, (200, 200))

    comparison = build_comparison(reports_dir=reports_dir, ground_truth_dir=ground_truth_dir)

    assert comparison.rows[1].f1 == 0.9


def test_format_comparison_marks_adjusted_system_metrics(tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    ground_truth_dir = tmp_path / "ground_truth"
    reports_dir.mkdir()
    _write_expected(ground_truth_dir, "clingen_000")
    _write_expected(ground_truth_dir, "clingen_001", gene="AARS2")
    _write_system_report(reports_dir / "eval_20260101_000000.json")
    _write_baseline_report(reports_dir / "baseline_b4_20260101_000000.json", "B4", f1=0.8889)

    output = format_comparison(build_comparison(reports_dir=reports_dir, ground_truth_dir=ground_truth_dir))

    assert "SYSTEM" in output
    assert "adjusted" in output
    assert "repaired_missing=1" in output
    assert "B4" in output


def test_format_comparison_marks_baseline_n_mismatch(tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    ground_truth_dir = tmp_path / "ground_truth"
    reports_dir.mkdir()
    _write_expected(ground_truth_dir, "clingen_000")
    _write_system_report(reports_dir / "eval_20260101_000000.json")
    baseline_path = reports_dir / "baseline_b0_20260101_000000.json"
    _write_baseline_report(baseline_path, "B0", f1=0.8889)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline["total_entries"] = 30
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

    output = format_comparison(build_comparison(reports_dir=reports_dir, ground_truth_dir=ground_truth_dir))

    assert "N_mismatch_vs_system=2" in output


def test_build_comparison_can_recompute_baselines_on_system_entry_subset(tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    ground_truth_dir = tmp_path / "ground_truth"
    reports_dir.mkdir()
    _write_expected(ground_truth_dir, "clingen_000")
    _write_system_report(reports_dir / "eval_20260101_000000.json")
    _write_baseline_report_with_entries(reports_dir / "baseline_b0_20260101_000000.json", "B0")

    comparison = build_comparison(
        reports_dir=reports_dir,
        ground_truth_dir=ground_truth_dir,
        match_system_entries=True,
    )

    baseline_row = comparison.rows[1]
    assert baseline_row.total_entries == 1
    assert baseline_row.f1 == 1.0
    assert baseline_row.matched_to_system_entries
