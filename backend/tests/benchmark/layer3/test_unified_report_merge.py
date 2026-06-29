"""Tests for unified report merge — by_source_dataset TP/FP/FN must match overall."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from benchmark.analysis.paper_artifacts.merge_unified_reports import (
    build_merged_report,
    compute_by_source_dataset,
)
from benchmark.core.contracts import EntryMetrics, FieldMatch


def _make_entry(
    entry_id: str,
    source_dataset: str,
    field_matches: list[FieldMatch],
) -> EntryMetrics:
    """Create a minimal EntryMetrics for testing."""
    return EntryMetrics(
        entry_id=entry_id,
        gene_symbol="GENE",
        classification="Definitive",
        language="en",
        moi="AD",
        source_dataset=source_dataset,
        field_matches=field_matches,
    )


def _make_field(
    field_id: str,
    matched: bool = False,
    match_type: str = "none",
    extra_found_values: list[str] | None = None,
) -> FieldMatch:
    """Create a minimal FieldMatch for testing."""
    return FieldMatch(
        field_id=field_id,
        expected_value="expected",
        matched=matched,
        extracted_value="extracted" if match_type not in ("missing", "none") else None,
        match_type=match_type,
        extra_found_values=extra_found_values or [],
    )


class TestBySourceDatasetAggregation:
    """by_source_dataset must use the same TP/FP/FN rules as overall."""

    def test_tp_fp_fn_basic(self):
        """One matched (TP), one wrong_value (FP), one missing (FN)."""
        metrics = [
            _make_entry("e1", "ds_a", [
                _make_field("f1", matched=True, match_type="exact"),
                _make_field("f2", match_type="wrong_value"),
                _make_field("f3", match_type="missing"),
            ]),
        ]
        result = compute_by_source_dataset(metrics)
        ds = result["ds_a"]
        assert ds["true_positives"] == 1
        assert ds["false_positives"] == 1
        assert ds["false_negatives"] == 1

    def test_extra_found_values_count_as_fp(self):
        """extra_found_values contribute to FP count."""
        metrics = [
            _make_entry("e1", "ds_a", [
                _make_field("f1", matched=True, match_type="exact"),
                _make_field("f2", match_type="exact", extra_found_values=["extra1", "extra2"]),
            ]),
        ]
        result = compute_by_source_dataset(metrics)
        ds = result["ds_a"]
        # TP=1 (f1 matched), FP=2 (two extra_found_values on f2), FN=0
        assert ds["true_positives"] == 1
        assert ds["false_positives"] == 2
        assert ds["false_negatives"] == 0

    def test_wrong_value_plus_extra_found(self):
        """wrong_value field with extra_found_values: both count as FP."""
        metrics = [
            _make_entry("e1", "ds_a", [
                _make_field("f1", match_type="wrong_value", extra_found_values=["x"]),
            ]),
        ]
        result = compute_by_source_dataset(metrics)
        ds = result["ds_a"]
        # FP = 1 (wrong_value) + 1 (extra_found) = 2
        assert ds["false_positives"] == 2
        assert ds["true_positives"] == 0
        assert ds["false_negatives"] == 0

    def test_two_datasets_sums_match_overall(self):
        """by_source_dataset sums must equal overall TP/FP/FN."""
        metrics = [
            # Dataset A: TP=1, FP=1 (wrong_value), FN=1 (missing)
            _make_entry("e1", "ds_a", [
                _make_field("f1", matched=True, match_type="exact"),
                _make_field("f2", match_type="wrong_value"),
                _make_field("f3", match_type="missing"),
            ]),
            # Dataset B: TP=2, FP=2 (1 wrong_value + 1 extra_found), FN=1 (none)
            _make_entry("e2", "ds_b", [
                _make_field("f4", matched=True, match_type="exact"),
                _make_field("f5", matched=True, match_type="exact"),
                _make_field("f6", match_type="wrong_value"),
                _make_field("f7", match_type="exact", extra_found_values=["extra"]),
                _make_field("f8", match_type="none"),
            ]),
        ]

        by_src = compute_by_source_dataset(metrics)

        # Per-dataset
        assert by_src["ds_a"]["true_positives"] == 1
        assert by_src["ds_a"]["false_positives"] == 1
        assert by_src["ds_a"]["false_negatives"] == 1

        assert by_src["ds_b"]["true_positives"] == 2
        assert by_src["ds_b"]["false_positives"] == 2
        assert by_src["ds_b"]["false_negatives"] == 1

        # Sums must match overall
        src_tp = sum(v["true_positives"] for v in by_src.values())
        src_fp = sum(v["false_positives"] for v in by_src.values())
        src_fn = sum(v["false_negatives"] for v in by_src.values())

        # Overall: TP=3, FP=3, FN=2
        assert src_tp == 3
        assert src_fp == 3
        assert src_fn == 2


class TestMergedReportIntegration:
    """Integration test: build_merged_report produces consistent aggregates."""

    def _write_shard(self, tmpdir: Path, name: str, entries: list[dict]) -> Path:
        """Write a minimal shard report JSON."""
        path = tmpdir / name
        path.write_text(json.dumps({
            "config": {"extraction_mode": "broad"},
            "total_entries": len(entries),
            "total_duration_s": 100,
            "per_entry": entries,
        }))
        return path

    def _make_per_entry(
        self, entry_id: str, source_dataset: str, field_matches: list[dict],
    ) -> dict:
        return {
            "entry_id": entry_id,
            "gene_symbol": "GENE",
            "classification": "Definitive",
            "language": "en",
            "moi": "AD",
            "source_dataset": source_dataset,
            "pipeline_status": "completed",
            "field_matches": field_matches,
            "entity_matches": [],
            "duration_s": 10,
            "evidence_count": 1,
            "found_rate": 0.5,
            "grounding_rate": 1.0,
            "standardization_accuracy": 0.0,
            "track_consistency": 0.0,
        }

    def test_merged_report_sums_consistent(self):
        """Merged report's by_source_dataset sums equal overall."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            shard1 = self._write_shard(tmpdir, "shard0.json", [
                self._make_per_entry("e1", "ds_a", [
                    {"field_id": "f1", "expected_value": "ev", "matched": True,
                     "match_type": "exact", "extra_found_values": []},
                    {"field_id": "f2", "expected_value": "ev", "matched": False,
                     "match_type": "wrong_value", "extra_found_values": ["x"]},
                    {"field_id": "f3", "expected_value": "ev", "matched": False,
                     "match_type": "missing", "extra_found_values": []},
                ]),
            ])
            shard2 = self._write_shard(tmpdir, "shard1.json", [
                self._make_per_entry("e2", "ds_b", [
                    {"field_id": "f4", "expected_value": "ev", "matched": True,
                     "match_type": "exact", "extra_found_values": []},
                    {"field_id": "f5", "expected_value": "ev", "matched": False,
                     "match_type": "none", "extra_found_values": []},
                ]),
            ])

            report = build_merged_report([shard1, shard2])
            overall = report["aggregates"]["overall"]
            by_src = report["aggregates"]["by_source_dataset"]

            src_tp = sum(v["true_positives"] for v in by_src.values())
            src_fp = sum(v["false_positives"] for v in by_src.values())
            src_fn = sum(v["false_negatives"] for v in by_src.values())

            assert src_tp == overall["true_positives"], f"TP: {src_tp} != {overall['true_positives']}"
            assert src_fp == overall["false_positives"], f"FP: {src_fp} != {overall['false_positives']}"
            assert src_fn == overall["false_negatives"], f"FN: {src_fn} != {overall['false_negatives']}"
