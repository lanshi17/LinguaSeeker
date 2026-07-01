"""Tests for three-way comparison: B0-naive vs B7-expanded vs SYSTEM."""

from __future__ import annotations

import pytest


def _make_report(entries: list[dict]) -> dict:
    """Build a minimal report payload for testing."""
    return {
        "per_entry": entries,
        "total_entries": len(entries),
    }


def _make_entry(entry_id: str, matches: list[dict]) -> dict:
    """Build a minimal entry with field matches."""
    return {
        "entry_id": entry_id,
        "gene_symbol": "TEST",
        "classification": "Definitive",
        "language": "en",
        "moi": "AD",
        "pipeline_status": "completed",
        "field_matches": matches,
    }


def _match(field_id: str, matched: bool, match_type: str = "exact") -> dict:
    return {
        "field_id": field_id,
        "expected": "val",
        "matched": matched,
        "extracted": "val" if matched else ("wrong" if match_type == "wrong_value" else None),
        "match_type": match_type,
        "extra_found_values": [],
    }


@pytest.fixture
def sample_reports():
    """Three mock reports with 2 entries each."""
    sys_report = _make_report(
        [
            _make_entry(
                "rett_001",
                [
                    _match("A.gene_symbol", True),
                    _match("B.disease_diagnosis", True),
                    _match("B.sex", True),
                    _match("C.de_novo_status", True),
                ],
            ),
            _make_entry(
                "rett_002",
                [
                    _match("A.gene_symbol", True),
                    _match("B.disease_diagnosis", True),
                    _match("B.sex", False, "missing"),
                    _match("C.de_novo_status", False, "wrong_value"),
                ],
            ),
        ]
    )
    b0_report = _make_report(
        [
            _make_entry(
                "rett_001",
                [
                    _match("A.gene_symbol", True),
                    _match("B.disease_diagnosis", True),
                    _match("B.sex", False, "missing"),
                    _match("C.de_novo_status", False, "missing"),
                ],
            ),
            _make_entry(
                "rett_002",
                [
                    _match("A.gene_symbol", True),
                    _match("B.disease_diagnosis", True),
                    _match("B.sex", False, "missing"),
                    _match("C.de_novo_status", False, "missing"),
                ],
            ),
        ]
    )
    b7_report = _make_report(
        [
            _make_entry(
                "rett_001",
                [
                    _match("A.gene_symbol", True),
                    _match("B.disease_diagnosis", True),
                    _match("B.sex", True),
                    _match("C.de_novo_status", False, "missing"),
                ],
            ),
            _make_entry(
                "rett_002",
                [
                    _match("A.gene_symbol", True),
                    _match("B.disease_diagnosis", True),
                    _match("B.sex", False, "missing"),
                    _match("C.de_novo_status", False, "missing"),
                ],
            ),
        ]
    )
    return sys_report, b0_report, b7_report


def test_three_way_computation(sample_reports) -> None:
    """Three-way comparison must produce correct metrics for all three systems."""
    from benchmark.analysis.diagnostics.three_way_comparison import compute_three_way

    sys_report, b0_report, b7_report = sample_reports
    result = compute_three_way(sys_report, b0_report, b7_report, n_bootstrap=100, seed=42)

    assert result["n_entries"] == 2
    merged = next(c for c in result["comparisons"] if c["label"] == "merged_73")

    # SYSTEM: 4 TP + 1 FP (wrong_value) + 1 FN (missing) + 1 FN (wrong_value) = TP=4, FP=1, FN=2
    # Wait - let me recalculate. Entry 1: 4 matched (TP=4). Entry 2: 2 matched (TP=2), 1 missing (FN=1), 1 wrong_value (FP=1, FN=1)
    # Total: TP=6, FP=1, FN=2
    # P=6/7=0.8571, R=6/8=0.75, F1=2*0.8571*0.75/(0.8571+0.75)=0.8
    assert merged["system"]["f1"] > 0.7  # SYSTEM should have decent F1

    # B0: all 8 matched except 2 missing sex and 2 missing de_novo
    # Entry 1: gene=T, disease=T, sex=FN, de_novo=FN → TP=2, FP=0, FN=2
    # Entry 2: gene=T, disease=T, sex=FN, de_novo=FN → TP=2, FP=0, FN=2
    # Total: TP=4, FP=0, FN=4 → P=1.0, R=0.5, F1=0.6667
    assert merged["b0_naive"]["f1"] < merged["system"]["f1"]

    # B7: Entry 1: gene=T, disease=T, sex=T, de_novo=FN → TP=3, FP=0, FN=1
    # Entry 2: gene=T, disease=T, sex=FN, de_novo=FN → TP=2, FP=0, FN=2
    # Total: TP=5, FP=0, FN=3 → P=1.0, R=0.625, F1=0.7692
    assert merged["b7_expanded"]["f1"] > merged["b0_naive"]["f1"]

    # Verify delta is present
    assert "delta_system_vs_b7" in merged
    assert "bootstrap_ci_95" in merged["delta_system_vs_b7"]
    assert "p_value" in merged["delta_system_vs_b7"]


def test_three_way_per_field(sample_reports) -> None:
    """Per-field metrics must include all field IDs from all three reports."""
    from benchmark.analysis.diagnostics.three_way_comparison import compute_three_way

    sys_report, b0_report, b7_report = sample_reports
    result = compute_three_way(sys_report, b0_report, b7_report, n_bootstrap=100, seed=42)

    field_ids = {r["field_id"] for r in result["per_field"]}
    assert "A.gene_symbol" in field_ids
    assert "B.sex" in field_ids
    assert "C.de_novo_status" in field_ids


def test_three_way_per_field_has_difficulty_categories(sample_reports) -> None:
    """Per-field rows must include difficulty category labels."""
    from benchmark.analysis.diagnostics.three_way_comparison import compute_three_way

    result = compute_three_way(*sample_reports, n_bootstrap=100, seed=42)
    for row in result["per_field"]:
        assert row["category"] in ("simple_explicit", "medium_contextual", "complex_evidence", "other")


def test_three_way_difficulty_groups(sample_reports) -> None:
    """Difficulty groups must be present in comparisons."""
    from benchmark.analysis.diagnostics.three_way_comparison import compute_three_way

    result = compute_three_way(*sample_reports, n_bootstrap=100, seed=42)
    labels = {c["label"] for c in result["comparisons"]}
    assert "merged_simple_explicit" in labels
    assert "merged_medium_contextual" in labels
    assert "merged_complex_evidence" in labels


def test_three_way_identifies_fields_where_b7_closes_gap(sample_reports) -> None:
    """Must identify fields where B7-expanded improves over B0-naive."""
    from benchmark.analysis.diagnostics.three_way_comparison import compute_three_way

    result = compute_three_way(*sample_reports, n_bootstrap=100, seed=42)
    # B7 extracted sex for rett_001 (TP) while B0 didn't → B7 closes gap on B.sex
    gap_fields = {r["field_id"] for r in result["fields_b7_closes_gap"]}
    assert "B.sex" in gap_fields


def test_three_way_output_schema(sample_reports) -> None:
    """Output must have the expected top-level keys."""
    from benchmark.analysis.diagnostics.three_way_comparison import compute_three_way

    result = compute_three_way(*sample_reports, n_bootstrap=100, seed=42)
    assert "report_id" in result
    assert "timestamp" in result
    assert "comparisons" in result
    assert "per_field" in result
    assert "fields_b7_closes_gap" in result
    assert "fields_system_still_wins" in result
