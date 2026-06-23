"""Tests for field-difficulty stratified evaluation.

Covers field classification, metric aggregation, and edge cases.
"""
from __future__ import annotations

import pytest

from benchmark.analysis.diagnostics.field_difficulty_stratified import (
    COMPLEX_EVIDENCE,
    MEDIUM_CONTEXTUAL,
    SIMPLE_EXPLICIT,
    CategoryMetrics,
    classify_field,
    compute_stratified_metrics,
)


# ── Field classification ────────────────────────────────────────────────


class TestClassifyField:
    """Tests for field_id → difficulty tier classification."""

    @pytest.mark.parametrize("field_id", [
        "A.gene_symbol",
        "B.disease_diagnosis",
        "A.gene_disease_relationship",
        "A.variant_hgvs_p",
        "A.variant_hgvs_c",
        "A.variant_type",
        "A.variant_consequence_class",
    ])
    def test_simple_explicit_fields(self, field_id: str) -> None:
        assert classify_field(field_id) == "simple_explicit"

    @pytest.mark.parametrize("field_id", [
        "B.mode_of_inheritance_reported",
        "B.clinical_phenotypes",
        "B.hpo_terms",
        "B.sex",
        "B.age_of_onset",
        "K.mode_of_inheritance",
    ])
    def test_medium_contextual_fields(self, field_id: str) -> None:
        assert classify_field(field_id) == "medium_contextual"

    @pytest.mark.parametrize("field_id", [
        "C.de_novo_status",
        "C.segregation",
        "C.functional_assay",
        "C.contradictory_evidence",
        "C.source_grounded_evidence",
    ])
    def test_complex_evidence_fields(self, field_id: str) -> None:
        assert classify_field(field_id) == "complex_evidence"

    def test_unknown_field_returns_other(self) -> None:
        assert classify_field("X.unknown_field") == "other"

    def test_a_prefix_defaults_to_simple(self) -> None:
        assert classify_field("A.new_field") == "simple_explicit"

    def test_b_prefix_defaults_to_medium(self) -> None:
        assert classify_field("B.new_field") == "medium_contextual"

    def test_c_prefix_defaults_to_complex(self) -> None:
        assert classify_field("C.new_field") == "complex_evidence"

    def test_no_overlap_between_sets(self) -> None:
        """Ensure classification sets are disjoint."""
        overlap_simple_medium = SIMPLE_EXPLICIT & MEDIUM_CONTEXTUAL
        overlap_simple_complex = SIMPLE_EXPLICIT & COMPLEX_EVIDENCE
        overlap_medium_complex = MEDIUM_CONTEXTUAL & COMPLEX_EVIDENCE
        assert not overlap_simple_medium
        assert not overlap_simple_complex
        assert not overlap_medium_complex


# ── CategoryMetrics ─────────────────────────────────────────────────────


class TestCategoryMetrics:
    """Tests for CategoryMetrics computation."""

    def test_perfect_system(self) -> None:
        cm = CategoryMetrics(category="simple_explicit", dataset="test")
        cm.system_tp = 10
        cm.expected_count = 10
        assert cm.system_precision == 1.0
        assert cm.system_recall == 1.0
        assert cm.system_f1 == 1.0

    def test_zero_metrics(self) -> None:
        cm = CategoryMetrics(category="simple_explicit", dataset="test")
        assert cm.system_precision == 0.0
        assert cm.system_recall == 0.0
        assert cm.system_f1 == 0.0

    def test_partial_match(self) -> None:
        cm = CategoryMetrics(category="medium_contextual", dataset="test")
        cm.system_tp = 3
        cm.system_fp = 1
        cm.system_fn = 2
        assert cm.system_precision == pytest.approx(0.75, abs=0.001)
        assert cm.system_recall == pytest.approx(0.6, abs=0.001)
        assert cm.system_f1 == pytest.approx(0.6667, abs=0.001)

    def test_delta_f1(self) -> None:
        cm = CategoryMetrics(category="simple_explicit", dataset="test")
        cm.system_tp = 8
        cm.system_fp = 2
        cm.system_fn = 2
        cm.b0_tp = 7
        cm.b0_fp = 0
        cm.b0_fn = 3
        # system: P=0.8, R=0.8, F1=0.8
        # b0: P=1.0, R=0.7, F1=0.8235
        assert cm.delta_f1 == pytest.approx(cm.system_f1 - cm.b0_f1, abs=0.001)

    def test_to_dict(self) -> None:
        cm = CategoryMetrics(category="simple_explicit", dataset="test")
        cm.system_tp = 5
        cm.expected_count = 10
        d = cm.to_dict()
        assert d["category"] == "simple_explicit"
        assert d["dataset"] == "test"
        assert d["expected_count"] == 10
        assert d["system_tp"] == 5


# ── compute_stratified_metrics ──────────────────────────────────────────


class TestComputeStratifiedMetrics:
    """Tests for the main metric computation function."""

    def _make_report(self, entries: list[dict]) -> dict:
        return {"per_entry": entries}

    def _make_entry(self, entry_id: str, matches: list[dict]) -> dict:
        return {"entry_id": entry_id, "field_matches": matches}

    def _make_match(self, field_id: str, matched: bool, match_type: str = "exact") -> dict:
        return {
            "field_id": field_id,
            "expected": "val",
            "matched": matched,
            "match_type": match_type if not matched else "exact",
            "extracted": "val" if matched else None,
        }

    def test_simple_field_system_wins(self) -> None:
        """SYSTEM matches gene_symbol, B0 doesn't."""
        sys_report = self._make_report([
            self._make_entry("e1", [
                self._make_match("A.gene_symbol", True),
                self._make_match("B.disease_diagnosis", True),
            ]),
        ])
        b0_report = self._make_report([
            self._make_entry("e1", [
                self._make_match("A.gene_symbol", False, "wrong_value"),
                self._make_match("B.disease_diagnosis", True),
            ]),
        ])
        cats, field_gl, unknowns = compute_stratified_metrics(sys_report, b0_report, "test")
        simple = cats["simple_explicit"]
        assert simple.system_tp == 2
        assert simple.b0_tp == 1

    def test_medium_field_system_wins(self) -> None:
        """SYSTEM matches inheritance, B0 misses it."""
        sys_report = self._make_report([
            self._make_entry("e1", [
                self._make_match("A.gene_symbol", True),
                self._make_match("B.mode_of_inheritance_reported", True),
            ]),
        ])
        b0_report = self._make_report([
            self._make_entry("e1", [
                self._make_match("A.gene_symbol", True),
                self._make_match("B.mode_of_inheritance_reported", False, "missing"),
            ]),
        ])
        cats, _, _ = compute_stratified_metrics(sys_report, b0_report, "test")
        assert cats["medium_contextual"].system_tp == 1
        assert cats["medium_contextual"].b0_fn == 1

    def test_unknown_field_classified(self) -> None:
        """Unknown field_ids go to 'other' category."""
        sys_report = self._make_report([
            self._make_entry("e1", [
                self._make_match("X.new_field", True),
            ]),
        ])
        b0_report = self._make_report([
            self._make_entry("e1", [
                self._make_match("X.new_field", False, "missing"),
            ]),
        ])
        cats, _, unknowns = compute_stratified_metrics(sys_report, b0_report, "test")
        assert "other" in cats
        assert "X.new_field" in unknowns

    def test_empty_reports(self) -> None:
        """Empty reports produce no categories."""
        cats, field_gl, unknowns = compute_stratified_metrics(
            self._make_report([]), self._make_report([]), "test",
        )
        assert len(cats) == 0
        assert len(field_gl) == 0

    def test_common_entries_only(self) -> None:
        """Only entries present in both reports are compared."""
        sys_report = self._make_report([
            self._make_entry("e1", [self._make_match("A.gene_symbol", True)]),
            self._make_entry("e2", [self._make_match("A.gene_symbol", True)]),
        ])
        b0_report = self._make_report([
            self._make_entry("e1", [self._make_match("A.gene_symbol", True)]),
        ])
        cats, _, _ = compute_stratified_metrics(sys_report, b0_report, "test")
        assert cats["simple_explicit"].expected_count == 1  # only e1
