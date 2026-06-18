"""Tests for source-grounding diagnostics."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.analysis.diagnostics.grounding import (
    build_grounding_diagnostics,
    format_grounding_diagnostics,
)


def _write_report(path: Path, per_entry: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {
                "total_entries": len(per_entry),
                "aggregates": {"overall": {"precision": 1.0, "recall": 0.5, "f1": 0.6667}},
                "per_entry": per_entry,
            }
        ),
        encoding="utf-8",
    )


def test_build_grounding_diagnostics_computes_span_validity_when_spans_exist(tmp_path) -> None:
    report_path = tmp_path / "eval_20260102_000000.json"
    _write_report(
        report_path,
        [
            {
                "entry_id": "clingen_001",
                "pipeline_status": "awaiting_review",
                "grounding_rate": 0.5,
                "field_matches": [
                    {
                        "field_id": "A.gene_symbol",
                        "matched": True,
                        "match_type": "exact",
                        "source_span": {"text": "AARS2", "start": 10, "end": 15},
                    },
                    {
                        "field_id": "B.disease_diagnosis",
                        "matched": False,
                        "match_type": "wrong_value",
                        "source_span": {"text": "", "start": None, "end": None},
                    },
                    {
                        "field_id": "A.gene_disease_relationship",
                        "matched": False,
                        "match_type": "missing",
                    },
                ],
            }
        ],
    )

    diagnostics = build_grounding_diagnostics(report_path)

    assert diagnostics.total_entries == 1
    assert diagnostics.entries_with_grounding_rate == 1
    assert diagnostics.mean_grounding_rate == 0.5
    assert diagnostics.span_evidence_count == 2
    assert diagnostics.valid_span_count == 1
    assert diagnostics.invalid_span_count == 1
    assert diagnostics.citation_validity_rate == 0.5
    assert diagnostics.hallucinated_citation_rate == 0.5
    assert diagnostics.grounded_matched == 1
    assert diagnostics.ungrounded_wrong_or_over == 1
    assert not diagnostics.missing_span_evidence


def test_build_grounding_diagnostics_accepts_text_snippet_and_zero_offsets(tmp_path) -> None:
    report_path = tmp_path / "eval_20260102_000000.json"
    _write_report(
        report_path,
        [
            {
                "entry_id": "clingen_001",
                "pipeline_status": "awaiting_review",
                "grounding_rate": 1.0,
                "field_matches": [
                    {
                        "field_id": "A.gene_symbol",
                        "matched": True,
                        "match_type": "exact",
                        "source_span": {
                            "text_snippet": "AARS2 variant evidence",
                            "start_offset": 0,
                            "end_offset": 22,
                        },
                    }
                ],
            }
        ],
    )

    diagnostics = build_grounding_diagnostics(report_path)

    assert diagnostics.valid_span_count == 1
    assert diagnostics.citation_validity_rate == 1.0


def test_build_grounding_diagnostics_flags_missing_span_evidence(tmp_path) -> None:
    report_path = tmp_path / "eval_20260102_000000.json"
    _write_report(
        report_path,
        [
            {
                "entry_id": "clingen_001",
                "pipeline_status": "awaiting_review",
                "grounding_rate": 0.0,
                "field_matches": [{"field_id": "A.gene_symbol", "matched": True, "match_type": "exact"}],
            }
        ],
    )

    diagnostics = build_grounding_diagnostics(report_path)

    assert diagnostics.span_evidence_count == 0
    assert diagnostics.citation_validity_rate is None
    assert diagnostics.hallucinated_citation_rate is None
    assert diagnostics.missing_span_evidence


def test_format_grounding_diagnostics_reports_uncomputable_cvr_hcr(tmp_path) -> None:
    report_path = tmp_path / "eval_20260102_000000.json"
    _write_report(
        report_path,
        [
            {
                "entry_id": "clingen_001",
                "pipeline_status": "timeout",
                "grounding_rate": 0.0,
                "field_matches": [],
            }
        ],
    )

    output = format_grounding_diagnostics(build_grounding_diagnostics(report_path))

    assert "N=1" in output
    assert "mean_grounding_rate=0.0" in output
    assert "CVR=uncomputable" in output
    assert "HCR=uncomputable" in output
    assert "missing per-evidence source spans" in output
