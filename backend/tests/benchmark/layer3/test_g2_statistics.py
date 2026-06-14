"""Tests for BIBM G2 paired statistics over reconcile ablation reports."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from benchmark.layer3.analysis.g2_statistics import (
    build_g2_statistics,
    format_g2_statistics,
)


def _field_match(
    *,
    field_id: str,
    matched: bool,
    match_type: str,
    extra_found_values: list[str] | None = None,
) -> Mapping[str, object]:
    return {
        "field_id": field_id,
        "expected": "expected",
        "matched": matched,
        "extracted": "expected" if matched else "wrong",
        "match_type": match_type,
        "source_span": {
            "text_snippet": "source evidence",
            "start_offset": 0,
            "end_offset": 15,
        },
        "extra_found_values": extra_found_values or [],
    }


def _entry(
    entry_id: str,
    *,
    field_matches: list[Mapping[str, object]],
    status: str = "completed",
) -> Mapping[str, object]:
    return {
        "entry_id": entry_id,
        "gene_symbol": "GENE",
        "classification": "Definitive",
        "moi": "AD",
        "language": "en",
        "pipeline_status": status,
        "field_matches": field_matches,
    }


def _write_report(
    path: Path,
    *,
    baseline_entries: list[Mapping[str, object]],
    candidate_entries: list[Mapping[str, object]],
) -> None:
    path.write_text(
        json.dumps(
            {
                "evaluation_id": "reconcile_ablation_test",
                "strategies": [
                    {
                        "strategy": "grounded_hard_rule",
                        "total_entries": len(baseline_entries),
                        "status_counts": {"completed": len(baseline_entries)},
                        "aggregates": {},
                        "per_entry": baseline_entries,
                    },
                    {
                        "strategy": "context_verifier_reconcile",
                        "total_entries": len(candidate_entries),
                        "status_counts": {"completed": len(candidate_entries)},
                        "aggregates": {},
                        "per_entry": candidate_entries,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_build_g2_statistics_computes_paired_delta_but_blocks_small_sample(tmp_path: Path) -> None:
    report_path = tmp_path / "reconcile_ablation.json"
    baseline_entries = [
        _entry(
            "clingen_000",
            field_matches=[
                _field_match(field_id="A.gene_symbol", matched=True, match_type="exact"),
                _field_match(field_id="B.disease_diagnosis", matched=False, match_type="wrong_value"),
            ],
        ),
        _entry(
            "clingen_001",
            field_matches=[
                _field_match(field_id="A.gene_symbol", matched=True, match_type="exact"),
                _field_match(field_id="B.disease_diagnosis", matched=False, match_type="missing"),
            ],
        ),
        _entry(
            "clingen_002",
            field_matches=[
                _field_match(field_id="A.gene_symbol", matched=True, match_type="exact"),
                _field_match(field_id="B.disease_diagnosis", matched=True, match_type="exact"),
            ],
        ),
    ]
    candidate_entries = [
        _entry(
            "clingen_000",
            field_matches=[
                _field_match(field_id="A.gene_symbol", matched=True, match_type="exact"),
                _field_match(field_id="B.disease_diagnosis", matched=True, match_type="exact"),
            ],
        ),
        _entry(
            "clingen_001",
            field_matches=[
                _field_match(field_id="A.gene_symbol", matched=True, match_type="exact"),
                _field_match(field_id="B.disease_diagnosis", matched=True, match_type="exact"),
            ],
        ),
        _entry(
            "clingen_002",
            field_matches=[
                _field_match(field_id="A.gene_symbol", matched=True, match_type="exact"),
                _field_match(field_id="B.disease_diagnosis", matched=True, match_type="exact"),
            ],
        ),
    ]
    _write_report(report_path, baseline_entries=baseline_entries, candidate_entries=candidate_entries)

    stats = build_g2_statistics(report_path, bootstrap_samples=200, seed=7)

    assert stats.sample_size == 3
    assert stats.baseline_metric == 0.8
    assert stats.candidate_metric == 1.0
    assert stats.delta_metric == 0.2
    assert not stats.main_paper_ready
    assert any("sample_size=3" in warning for warning in stats.warnings)


def test_build_g2_statistics_marks_ready_only_when_n_and_paired_test_pass(tmp_path: Path) -> None:
    report_path = tmp_path / "reconcile_ablation.json"
    baseline_entries = [
        _entry(
            f"clingen_{index:03d}",
            field_matches=[
                _field_match(field_id="A.gene_symbol", matched=True, match_type="exact"),
                _field_match(field_id="B.disease_diagnosis", matched=False, match_type="wrong_value"),
            ],
        )
        for index in range(30)
    ]
    candidate_entries = [
        _entry(
            f"clingen_{index:03d}",
            field_matches=[
                _field_match(field_id="A.gene_symbol", matched=True, match_type="exact"),
                _field_match(field_id="B.disease_diagnosis", matched=True, match_type="exact"),
            ],
        )
        for index in range(30)
    ]
    _write_report(report_path, baseline_entries=baseline_entries, candidate_entries=candidate_entries)

    stats = build_g2_statistics(report_path, bootstrap_samples=200, seed=7)

    assert stats.sample_size == 30
    assert stats.delta_metric > 0
    assert stats.bootstrap_ci_low > 0
    assert stats.sign_test_p < 0.05
    assert stats.main_paper_ready


def test_build_g2_statistics_blocks_non_completed_ablation_entries(tmp_path: Path) -> None:
    report_path = tmp_path / "reconcile_ablation.json"
    baseline_entries = [
        _entry(
            "clingen_000",
            field_matches=[_field_match(field_id="A.gene_symbol", matched=True, match_type="exact")],
        )
    ]
    candidate_entries = [
        _entry(
            "clingen_000",
            status="missing_artifact",
            field_matches=[_field_match(field_id="A.gene_symbol", matched=True, match_type="exact")],
        )
    ]
    _write_report(report_path, baseline_entries=baseline_entries, candidate_entries=candidate_entries)

    stats = build_g2_statistics(report_path, bootstrap_samples=20, seed=7, min_main_paper_n=1)

    assert not stats.main_paper_ready
    assert any("non_completed_entries" in warning for warning in stats.warnings)


def test_format_g2_statistics_includes_ci_and_gate(tmp_path: Path) -> None:
    report_path = tmp_path / "reconcile_ablation.json"
    baseline_entries = [
        _entry(
            "clingen_000",
            field_matches=[_field_match(field_id="A.gene_symbol", matched=False, match_type="wrong_value")],
        )
    ]
    candidate_entries = [
        _entry(
            "clingen_000",
            field_matches=[_field_match(field_id="A.gene_symbol", matched=True, match_type="exact")],
        )
    ]
    _write_report(report_path, baseline_entries=baseline_entries, candidate_entries=candidate_entries)

    output = format_g2_statistics(build_g2_statistics(report_path, bootstrap_samples=20, seed=7))

    assert "delta_f1=" in output
    assert "95% CI=" in output
    assert "main_paper_ready=False" in output
