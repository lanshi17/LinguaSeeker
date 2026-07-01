"""Tests for layer-3 extraction diagnostics."""

from __future__ import annotations

import json
import os
from pathlib import Path

from benchmark.analysis.diagnostics.extraction import (
    build_diagnostics,
    format_diagnostics,
    latest_report_path,
)


def _write_report(path: Path, total_entries: int, f1: float) -> None:
    report = {
        "total_entries": total_entries,
        "aggregates": {
            "overall": {
                "precision": 1.0,
                "recall": 0.5,
                "f1": f1,
                "entity_standardization_accuracy": 0.25,
                "cross_lingual_consistency": 0.0,
                "over_extractions": 2,
            },
            "by_field": {
                "A.gene_symbol": {
                    "precision": 1.0,
                    "recall": 1.0,
                    "f1": 1.0,
                    "over_extractions": 0,
                }
            },
            "by_classification": {
                "Definitive": {
                    "precision": 0.75,
                    "recall": 1.0,
                    "f1": 0.8571,
                    "over_extractions": 1,
                }
            },
            "by_moi": {
                "AR": {
                    "precision": 0.5,
                    "recall": 1.0,
                    "f1": 0.6667,
                    "over_extractions": 1,
                }
            },
        },
        "per_entry": [
            {
                "pipeline_status": "completed",
                "field_matches": [
                    {"field_id": "A.gene_symbol", "match_type": "exact"},
                    {"field_id": "B.disease_diagnosis", "match_type": "missing"},
                ],
            },
            {
                "pipeline_status": "failed",
                "field_matches": [{"field_id": "A.gene_disease_relationship", "match_type": "wrong_value"}],
            },
        ],
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def test_latest_report_path_selects_most_recent_eval_report(tmp_path) -> None:
    older = tmp_path / "eval_20260101_000000.json"
    newer = tmp_path / "eval_20260102_000000.json"
    _write_report(older, total_entries=1, f1=0.1)
    _write_report(newer, total_entries=2, f1=0.2)
    os.utime(older, (100, 100))
    os.utime(newer, (200, 200))

    assert latest_report_path(tmp_path) == newer


def test_build_diagnostics_summarizes_axes_and_match_types(tmp_path) -> None:
    report_path = tmp_path / "eval_20260102_000000.json"
    _write_report(report_path, total_entries=2, f1=0.8)

    diagnostics = build_diagnostics(report_path)

    assert diagnostics.total_entries == 2
    assert diagnostics.overall.f1 == 0.8
    assert diagnostics.axis_rows[0].axis == "by_field"
    assert diagnostics.axis_rows[0].key == "A.gene_symbol"
    assert diagnostics.match_type_counts["exact"] == 1
    assert diagnostics.match_type_counts["missing"] == 1
    assert diagnostics.match_type_counts["wrong_value"] == 1
    assert diagnostics.pipeline_status_counts["completed"] == 1
    assert diagnostics.pipeline_status_counts["failed"] == 1


def test_format_diagnostics_outputs_human_readable_tables(tmp_path) -> None:
    report_path = tmp_path / "eval_20260102_000000.json"
    _write_report(report_path, total_entries=2, f1=0.8)

    output = format_diagnostics(build_diagnostics(report_path))

    assert "N=2" in output
    assert "overall: P=1.0 R=0.5 F1=0.8" in output
    assert "== by_field ==" in output
    assert "A.gene_symbol" in output
    assert "== match_type distribution ==" in output
    assert "wrong_value: 1" in output
    assert "== pipeline_status distribution ==" in output
    assert "failed: 1" in output
