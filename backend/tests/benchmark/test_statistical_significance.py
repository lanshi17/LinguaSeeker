"""Tests for bootstrap CI and paired significance testing."""
from __future__ import annotations

import numpy as np
import pytest

from benchmark.analysis.diagnostics.statistical_significance import (
    bootstrap_ci,
    bootstrap_ci_paired_delta,
    compute_per_entry_outcomes,
    paired_permutation_test,
)


class TestPerEntryOutcome:
    """Tests for per-entry TP/FP/FN computation."""

    def test_perfect_match(self) -> None:
        matches = [
            {"field_id": "A.gene_symbol", "matched": True, "match_type": "exact"},
            {"field_id": "B.disease", "matched": True, "match_type": "exact"},
        ]
        outcome = compute_per_entry_outcomes(matches)
        assert outcome.tp == 2
        assert outcome.fp == 0
        assert outcome.fn == 0

    def test_all_missing(self) -> None:
        matches = [
            {"field_id": "A.gene_symbol", "matched": False, "match_type": "missing"},
            {"field_id": "B.disease", "matched": False, "match_type": "missing"},
        ]
        outcome = compute_per_entry_outcomes(matches)
        assert outcome.tp == 0
        assert outcome.fp == 0
        assert outcome.fn == 2

    def test_wrong_value_counts_fp_and_fn(self) -> None:
        matches = [
            {"field_id": "A.gene_symbol", "matched": False, "match_type": "wrong_value"},
        ]
        outcome = compute_per_entry_outcomes(matches)
        assert outcome.tp == 0
        assert outcome.fp == 1
        assert outcome.fn == 1

    def test_mixed(self) -> None:
        matches = [
            {"field_id": "A.gene_symbol", "matched": True, "match_type": "exact"},
            {"field_id": "B.disease", "matched": False, "match_type": "missing"},
            {"field_id": "A.variant", "matched": False, "match_type": "wrong_value"},
        ]
        outcome = compute_per_entry_outcomes(matches)
        assert outcome.tp == 1
        assert outcome.fp == 1
        assert outcome.fn == 2

    def test_empty_matches(self) -> None:
        outcome = compute_per_entry_outcomes([])
        assert outcome.tp == 0
        assert outcome.fp == 0
        assert outcome.fn == 0


class TestBootstrapCI:
    """Tests for bootstrap confidence interval computation."""

    def test_constant_statistic(self) -> None:
        """When all values are the same, CI should be tight."""
        samples = np.ones(100) * 0.5
        lo, hi = bootstrap_ci(samples, confidence=0.95)
        assert lo == pytest.approx(0.5, abs=0.01)
        assert hi == pytest.approx(0.5, abs=0.01)

    def test_ci_contains_mean(self) -> None:
        rng = np.random.default_rng(42)
        samples = rng.normal(0.5, 0.1, 1000)
        lo, hi = bootstrap_ci(samples, confidence=0.95)
        assert lo < 0.5 < hi

    def test_wider_ci_for_lower_confidence(self) -> None:
        rng = np.random.default_rng(42)
        samples = rng.normal(0.5, 0.1, 1000)
        lo95, hi95 = bootstrap_ci(samples, confidence=0.95)
        lo99, hi99 = bootstrap_ci(samples, confidence=0.99)
        assert (hi95 - lo95) < (hi99 - lo99)

    def test_deterministic_with_seed(self) -> None:
        rng = np.random.default_rng(42)
        samples = rng.normal(0.5, 0.1, 100)
        ci1 = bootstrap_ci(samples, confidence=0.95, rng=np.random.default_rng(123))
        ci2 = bootstrap_ci(samples, confidence=0.95, rng=np.random.default_rng(123))
        assert ci1 == ci2


class TestBootstrapCiPairedDelta:
    """Tests for paired bootstrap delta CI."""

    def test_identical_distributions_delta_near_zero(self) -> None:
        rng = np.random.default_rng(42)
        samples = rng.normal(0.5, 0.1, 200)
        lo, hi = bootstrap_ci_paired_delta(samples, samples, confidence=0.95, rng=np.random.default_rng(99))
        # When both samples are identical, delta is exactly 0
        assert lo <= 0.0 <= hi

    def test_system_clearly_better(self) -> None:
        rng = np.random.default_rng(42)
        sys_samples = rng.normal(0.8, 0.05, 200)
        b0_samples = rng.normal(0.5, 0.05, 200)
        lo, hi = bootstrap_ci_paired_delta(sys_samples, b0_samples, confidence=0.95, rng=np.random.default_rng(99))
        assert lo > 0  # delta should be entirely positive


class TestPairedPermutationTest:
    """Tests for paired permutation test."""

    def test_identical_distributions_p_not_significant(self) -> None:
        rng = np.random.default_rng(42)
        samples = rng.normal(0.5, 0.1, 100)
        result = paired_permutation_test(samples, samples, n_permutations=1000, rng=np.random.default_rng(99))
        assert result.p_value > 0.05  # should not be significant

    def test_very_different_distributions_p_significant(self) -> None:
        rng = np.random.default_rng(42)
        sys_samples = rng.normal(0.9, 0.02, 100)
        b0_samples = rng.normal(0.3, 0.02, 100)
        result = paired_permutation_test(sys_samples, b0_samples, n_permutations=5000, rng=np.random.default_rng(99))
        assert result.p_value < 0.01

    def test_result_fields(self) -> None:
        rng = np.random.default_rng(42)
        samples = rng.normal(0.5, 0.1, 50)
        result = paired_permutation_test(samples, samples, n_permutations=100, rng=np.random.default_rng(99))
        assert hasattr(result, "p_value")
        assert hasattr(result, "observed_delta")
        assert hasattr(result, "significant_at_0_05")
        assert hasattr(result, "significant_at_0_01")
        assert 0 <= result.p_value <= 1
