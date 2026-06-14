"""Tests for contextual reconcile no-lift diagnostics."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.layer3.analysis.contextual_reconcile_diagnosis import (
    build_contextual_reconcile_diagnosis,
    contextual_diagnosis_to_payload,
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
        "moi": "UD",
        "language": "en",
        "pipeline_status": "completed",
        "evidence_count": 3,
        "found_rate": 1.0,
        "field_matches": field_matches,
    }


def _write_report(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "strategy": "grounded_hard_rule",
                        "total_entries": 1,
                        "per_entry": [
                            _entry(
                                "clingen_000",
                                [
                                    _field_match(
                                        field_id="A.gene_disease_relationship",
                                        expected="causative",
                                        extracted="associated",
                                        match_type="wrong_value",
                                    )
                                ],
                            )
                        ],
                    },
                    {
                        "strategy": "context_verifier_reconcile",
                        "total_entries": 4,
                        "per_entry": [
                            _entry(
                                "clingen_001",
                                [
                                    _field_match(
                                        field_id="A.gene_disease_relationship",
                                        expected="causative",
                                        extracted="associated",
                                        match_type="wrong_value",
                                    )
                                ],
                            ),
                            _entry(
                                "clingen_002",
                                [
                                    _field_match(
                                        field_id="B.disease_diagnosis",
                                        expected="target disease",
                                        extracted=None,
                                        match_type="missing",
                                        source_precision=None,
                                    )
                                ],
                            ),
                            _entry(
                                "clingen_003",
                                [
                                    _field_match(
                                        field_id="A.gene_symbol",
                                        expected="GENE",
                                        extracted="GENE",
                                        matched=True,
                                        match_type="exact",
                                        extra_found_values=["OFFTARGET"],
                                    )
                                ],
                            ),
                            _entry(
                                "clingen_004",
                                [
                                    _field_match(
                                        field_id="A.gene_symbol",
                                        expected="GENE",
                                        extracted="GENE",
                                        matched=True,
                                        match_type="exact",
                                        extra_found_values=[],
                                    )
                                ],
                            ),
                            _entry(
                                "clingen_004",
                                [
                                    _field_match(
                                        field_id="B.disease_diagnosis",
                                        expected="target disease",
                                        extracted="target disease",
                                        matched=True,
                                        match_type="fuzzy",
                                        extra_found_values=[],
                                    )
                                ],
                            ),
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_diagnosis_filters_strategy_and_assigns_one_root_cause(tmp_path: Path) -> None:
    diagnosis = build_contextual_reconcile_diagnosis(
        _write_report(tmp_path / "ablation.json"),
        strategy="context_verifier_reconcile",
    )

    root_causes = {f"{row.entry_id}:{row.field_id}": row.root_cause for row in diagnosis.rows}

    assert len(diagnosis.rows) == 4
    assert root_causes == {
        "clingen_001:A.gene_disease_relationship": "wrong_relationship_semantics",
        "clingen_002:B.disease_diagnosis": "candidate_absent",
        "clingen_003:A.gene_symbol": "non_target_contamination",
        "clingen_004:B.disease_diagnosis": "disease_boundary_error",
    }


def test_diagnosis_payload_includes_counts_scores_and_summary(tmp_path: Path) -> None:
    diagnosis = build_contextual_reconcile_diagnosis(
        _write_report(tmp_path / "ablation.json"),
        strategy="context_verifier_reconcile",
    )

    payload = contextual_diagnosis_to_payload(diagnosis)

    assert payload["strategy"] == "context_verifier_reconcile"
    assert payload["total_rows"] == 4
    assert payload["summary"]["by_root_cause"] == {
        "candidate_absent": 1,
        "disease_boundary_error": 1,
        "non_target_contamination": 1,
        "wrong_relationship_semantics": 1,
    }
    relationship_row = next(
        row for row in payload["rows"] if row["field_id"] == "A.gene_disease_relationship"
    )
    assert relationship_row["candidate_count"] == 1
    assert relationship_row["found_candidate_count"] == 1
    assert relationship_row["source_valid_candidate_count"] == 1
    assert relationship_row["best_score"] is None
    assert relationship_row["verifier_support_score"] is None
    assert relationship_row["target_specificity_score"] is None
    assert relationship_row["contradiction_penalty"] is None
