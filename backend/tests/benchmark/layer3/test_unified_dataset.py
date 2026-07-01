"""Tests for unified dataset as default benchmark, sharding, provenance, and queued status."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.core.paths import (
    GROUND_TRUTH_ROOT,
    GROUND_TRUTH_UNIFIED_ROOT,
    GROUND_TRUTH_CLINGEN_ROOT,
)
from benchmark.core.contracts import EntryMetrics
from benchmark.core.pipeline_client import (
    QUEUED_STATUSES,
    TERMINAL_STATUSES,
    _apply_shard,
    _compute_stratified_metrics,
    _load_entries,
)


# ── Default root is unified ────────────────────────────────────────────


class TestDefaultRoot:
    """GROUND_TRUTH_ROOT must point to the unified dataset."""

    def test_ground_truth_root_is_unified(self) -> None:
        assert GROUND_TRUTH_ROOT == GROUND_TRUTH_UNIFIED_ROOT

    def test_ground_truth_root_ends_with_unified(self) -> None:
        assert GROUND_TRUTH_ROOT.name == "unified"

    def test_clingen_root_still_accessible(self) -> None:
        assert GROUND_TRUTH_CLINGEN_ROOT.name == "clingen"
        assert GROUND_TRUTH_CLINGEN_ROOT != GROUND_TRUTH_ROOT


# ── Entry loading ──────────────────────────────────────────────────────


class TestLoadEntries:
    """_load_entries() handles both manifest.json and selection.json."""

    def test_loads_from_manifest(self, tmp_path: Path) -> None:
        manifest = {
            "schema_version": "1.0.0",
            "entries": [
                {
                    "unified_id": "gs_000",
                    "original_entry_id": "clingen_000",
                    "source_dataset": "clingen",
                    "gene_symbol": "AARS1",
                    "classification": "Definitive",
                    "moi": "AD",
                    "disease_label": "Test disease",
                },
            ],
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        entry_dir = tmp_path / "gs_000"
        entry_dir.mkdir()
        expected = {
            "gene_symbol": "AARS1",
            "classification": "Definitive",
            "moi": "AD",
            "disease_label": "Test disease",
            "source_dataset": "clingen",
            "original_entry_id": "clingen_000",
            "expected_evidence": [{"field_id": "A.gene_symbol", "value": "AARS1"}],
            "expected_standardization": {"gene": "HGNC:20"},
        }
        (entry_dir / "expected.json").write_text(json.dumps(expected))

        entries = _load_entries(tmp_path)
        assert len(entries) == 1
        assert entries[0]["entry_id"] == "gs_000"
        assert entries[0]["source_dataset"] == "clingen"
        assert entries[0]["original_entry_id"] == "clingen_000"

    def test_loads_from_selection_json(self, tmp_path: Path) -> None:
        selection = [
            {
                "entry_id": "clingen_000",
                "gene_symbol": "AARS1",
                "classification": "Definitive",
                "moi": "AD",
                "disease_label": "Test disease",
            },
        ]
        (tmp_path / "selection.json").write_text(json.dumps(selection))

        entries = _load_entries(tmp_path)
        assert len(entries) == 1
        assert entries[0]["entry_id"] == "clingen_000"

    def test_raises_when_neither_file_exists(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="No selection.json or manifest.json"):
            _load_entries(tmp_path)

    def test_skips_entries_without_expected_json(self, tmp_path: Path) -> None:
        manifest = {
            "entries": [
                {"unified_id": "gs_000", "source_dataset": "clingen", "gene_symbol": "A"},
                {"unified_id": "gs_001", "source_dataset": "rett", "gene_symbol": "B"},
            ],
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        # Only gs_000 has expected.json
        (tmp_path / "gs_000").mkdir()
        (tmp_path / "gs_000" / "expected.json").write_text(
            json.dumps(
                {
                    "gene_symbol": "A",
                    "expected_evidence": [],
                }
            )
        )

        entries = _load_entries(tmp_path)
        assert len(entries) == 1
        assert entries[0]["entry_id"] == "gs_000"


# ── Sharding ───────────────────────────────────────────────────────────


class TestApplyShard:
    """_apply_shard() supports entry_ids, shard_index+size, and limit."""

    @pytest.fixture()
    def entries(self) -> list[dict]:
        return [{"entry_id": f"gs_{i:03d}"} for i in range(20)]

    def test_entry_ids_filter(self, entries: list[dict]) -> None:
        result = _apply_shard(entries, entry_ids=["gs_002", "gs_005"])
        assert len(result) == 2
        assert [e["entry_id"] for e in result] == ["gs_002", "gs_005"]

    def test_shard_index_and_size(self, entries: list[dict]) -> None:
        # Shard 0 of size 5: gs_000..gs_004
        shard_0 = _apply_shard(entries, shard_index=0, shard_size=5)
        assert [e["entry_id"] for e in shard_0] == [f"gs_{i:03d}" for i in range(5)]

        # Shard 1 of size 5: gs_005..gs_009
        shard_1 = _apply_shard(entries, shard_index=1, shard_size=5)
        assert [e["entry_id"] for e in shard_1] == [f"gs_{i:03d}" for i in range(5, 10)]

        # Last shard with fewer entries (shard 2 of size 7: gs_014..gs_019)
        shard_2 = _apply_shard(entries, shard_index=2, shard_size=7)
        assert [e["entry_id"] for e in shard_2] == [f"gs_{i:03d}" for i in range(14, 20)]

        # Shard beyond data returns empty
        shard_overflow = _apply_shard(entries, shard_index=10, shard_size=7)
        assert shard_overflow == []

    def test_limit(self, entries: list[dict]) -> None:
        result = _apply_shard(entries, limit=3)
        assert len(result) == 3

    def test_entry_ids_takes_priority_over_shard(self, entries: list[dict]) -> None:
        result = _apply_shard(entries, entry_ids=["gs_019"], shard_index=0, shard_size=5)
        assert len(result) == 1
        assert result[0]["entry_id"] == "gs_019"

    def test_no_filter_returns_all(self, entries: list[dict]) -> None:
        result = _apply_shard(entries)
        assert len(result) == 20


# ── Provenance ─────────────────────────────────────────────────────────


class TestProvenance:
    """EntryMetrics carries source_dataset and original_entry_id."""

    def test_entry_metrics_has_provenance_fields(self) -> None:
        m = EntryMetrics(
            entry_id="gs_000",
            gene_symbol="AARS1",
            classification="Definitive",
            language="en",
            source_dataset="clingen",
            original_entry_id="clingen_000",
        )
        assert m.source_dataset == "clingen"
        assert m.original_entry_id == "clingen_000"

    def test_entry_metrics_provenance_defaults_empty(self) -> None:
        m = EntryMetrics(
            entry_id="test_001",
            gene_symbol="BRCA1",
            classification="Definitive",
            language="en",
        )
        assert m.source_dataset == ""
        assert m.original_entry_id == ""


# ── Stratified metrics ─────────────────────────────────────────────────


class TestStratifiedMetrics:
    """_compute_stratified_metrics() groups by source_dataset."""

    def test_groups_by_source_dataset(self) -> None:
        from benchmark.core.contracts import FieldMatch

        m1 = EntryMetrics(
            entry_id="gs_000", gene_symbol="A", classification="Definitive", language="en", source_dataset="clingen"
        )
        m1.field_matches = [FieldMatch(field_id="A.gene_symbol", expected_value="A", matched=True)]
        m2 = EntryMetrics(
            entry_id="gs_001", gene_symbol="B", classification="Moderate", language="en", source_dataset="rett"
        )
        m2.field_matches = [
            FieldMatch(field_id="A.gene_symbol", expected_value="B", matched=False, match_type="missing")
        ]

        result = _compute_stratified_metrics([m1, m2])
        assert "clingen" in result
        assert "rett" in result
        assert result["clingen"]["count"] == 1
        assert result["rett"]["count"] == 1
        assert result["clingen"]["true_positives"] == 1
        assert result["rett"]["false_negatives"] == 1

    def test_empty_metrics_returns_empty_dict(self) -> None:
        result = _compute_stratified_metrics([])
        assert result == {}


# ── Queued status handling ─────────────────────────────────────────────


class TestQueuedStatus:
    """'queued' is a normal waiting state, not terminal or error."""

    def test_queued_not_in_terminal(self) -> None:
        assert "queued" not in TERMINAL_STATUSES

    def test_queued_in_queued_statuses(self) -> None:
        assert "queued" in QUEUED_STATUSES

    def test_queued_and_terminal_are_disjoint(self) -> None:
        assert QUEUED_STATUSES.isdisjoint(TERMINAL_STATUSES)
