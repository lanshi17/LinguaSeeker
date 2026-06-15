"""Tests for the arbitrator candidate dataset extraction."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from benchmark.layer3.analysis.arbitrator_dataset import (
    CandidateSample,
    DatasetSummary,
    _normalize_gold,
    _snippet_hash,
)


class TestNormalizeGold:
    def test_string_value(self) -> None:
        assert _normalize_gold("Causative") == "causative"

    def test_list_value(self) -> None:
        assert _normalize_gold(["B", "A"]) == "a|b"

    def test_none_value(self) -> None:
        assert _normalize_gold(None) == "none"


class TestSnippetHash:
    def test_none_source(self) -> None:
        assert _snippet_hash(None) == ""

    def test_valid_source(self) -> None:
        class FakeSource:
            text_snippet = "hello world"
        result = _snippet_hash(FakeSource())
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_empty_snippet(self) -> None:
        class EmptySource:
            text_snippet = ""
        assert _snippet_hash(EmptySource()) == ""


class TestDatasetSummary:
    def test_summary_fields(self) -> None:
        summary = DatasetSummary(
            entries_covered=25,
            entries_missing_artifact=5,
            candidate_count=150,
            positive_count=90,
            negative_count=60,
            per_field_counts={"A.gene_symbol": 50, "B.disease_diagnosis": 50, "A.gene_disease_relationship": 50},
            per_label_counts={1: 90, 0: 60},
            missing_entries=["clingen_025", "clingen_026"],
        )
        assert summary.entries_covered == 25
        assert summary.candidate_count == 150
        assert summary.positive_count + summary.negative_count == summary.candidate_count


class TestBuildDatasetIntegration:
    def test_build_dataset_runs_on_real_data(self) -> None:
        from benchmark.layer3.analysis.arbitrator_dataset import build_dataset
        from benchmark.layer3.evaluate import GROUND_TRUTH_DIR

        if not GROUND_TRUTH_DIR.exists():
            pytest.skip("ground_truth directory not available")

        samples, summary = build_dataset(GROUND_TRUTH_DIR)
        assert summary.entries_covered > 0
        assert summary.candidate_count > 0
        assert summary.positive_count > 0
        assert all(isinstance(s, CandidateSample) for s in samples)
        assert all(s.label in {0, 1} for s in samples)
        assert all(len(s.features.to_list()) == 21 for s in samples)
