"""Tests for reconcile error decomposition diagnostics."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.layer3.analysis.diagnose_reconcile_errors import (
    build_reconcile_error_diagnostics,
    diagnostics_to_payload,
)


def _field_match(
    *,
    field_id: str,
    expected: str = "expected",
    extracted: str | None = "wrong",
    matched: bool = False,
    match_type: str = "wrong_value",
    source_precision: str | None = "corrected",
    extra_found_values: list[str] | None = None,
) -> dict[str, object]:
    source_span = None
    if source_precision is not None:
        source_span = {
            "text_snippet": "source evidence",
            "source_precision": source_precision,
        }
    return {
        "field_id": field_id,
        "expected": expected,
        "matched": matched,
        "extracted": extracted,
        "source_span": source_span,
        "match_type": match_type,
        "extra_found_values": extra_found_values or [],
    }


def _entry(entry_id: str, field_matches: list[dict[str, object]]) -> dict[str, object]:
    return {
        "entry_id": entry_id,
        "gene_symbol": "GENE",
        "classification": "Limited",
        "moi": "AD",
        "language": "en",
        "pipeline_status": "completed",
        "field_matches": field_matches,
    }


def _write_report(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "strategy": "source_grounded_reconcile",
                        "total_entries": 2,
                        "per_entry": [
                            _entry(
                                "clingen_000",
                                [
                                    _field_match(
                                        field_id="A.gene_disease_relationship",
                                        expected="causative",
                                        extracted="associated",
                                        match_type="wrong_value",
                                        source_precision="corrected",
                                    ),
                                    _field_match(
                                        field_id="B.disease_diagnosis",
                                        expected="target disease",
                                        extracted="target disease",
                                        matched=True,
                                        match_type="exact",
                                        extra_found_values=["off-target disease"],
                                    ),
                                ],
                            ),
                            _entry(
                                "clingen_001",
                                [
                                    _field_match(
                                        field_id="A.gene_symbol",
                                        expected="GENE",
                                        extracted=None,
                                        match_type="missing",
                                        source_precision=None,
                                    )
                                ],
                            ),
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_build_reconcile_error_diagnostics_classifies_field_errors(tmp_path: Path) -> None:
    diagnostics = build_reconcile_error_diagnostics(_write_report(tmp_path / "ablation.json"))

    rows = diagnostics.rows

    assert len(rows) == 3
    by_field = {row.field_id: row for row in rows}
    assert by_field["A.gene_disease_relationship"].error_types == (
        "wrong_value",
        "wrong_value_with_valid_span",
        "relationship_semantics_error",
    )
    assert by_field["B.disease_diagnosis"].error_types == (
        "over_extraction",
        "disease_boundary_error",
    )
    assert by_field["A.gene_symbol"].error_types == (
        "missing",
        "missing_without_any_candidate",
        "gene_symbol_error",
    )


def test_diagnostics_payload_summarizes_by_strategy_field_and_error_type(tmp_path: Path) -> None:
    diagnostics = build_reconcile_error_diagnostics(_write_report(tmp_path / "ablation.json"))

    payload = diagnostics_to_payload(diagnostics)

    assert payload["report_path"] == str(tmp_path / "ablation.json")
    assert payload["summary"]["by_strategy"]["source_grounded_reconcile"] == 3
    assert payload["summary"]["by_field"]["A.gene_disease_relationship"] == 1
    assert payload["summary"]["by_error_type"]["relationship_semantics_error"] == 1
    assert payload["summary"]["by_classification"]["Limited"] == 3
    assert payload["summary"]["by_moi"]["AD"] == 3
    assert payload["summary"]["by_source_precision"]["corrected"] == 2
