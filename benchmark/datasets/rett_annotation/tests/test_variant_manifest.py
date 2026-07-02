"""Tests for the Rett variant-centered annotation manifest builder."""
from __future__ import annotations

from benchmark.datasets.rett_annotation.src.variant_manifest import build_manifest


def test_default_manifest_uses_rett_annotation_ground_truth_source() -> None:
    payload = build_manifest()

    assert payload["summary"]["total_entries"] == 53
    assert payload["summary"]["in_unified_benchmark"] == 51
    assert payload["summary"]["annotation_only_entries"] == 2
    assert payload["annotation_root"].endswith("benchmark/datasets/rett_annotation/ground_truth")
    assert all(
        "benchmark/datasets/rett_annotation/ground_truth" in entry["source_md_path"]
        for entry in payload["entries"]
    )


def test_rett_067_remains_critical_manual_multivariant_case() -> None:
    payload = build_manifest()
    entries_by_id = {entry["annotation_entry_id"]: entry for entry in payload["entries"]}

    rett_067 = entries_by_id["rett_067"]

    assert rett_067["unified_entry_id"] == "gs_134"
    assert rett_067["language"] == "ko"
    assert rett_067["priority"] == "CRITICAL_MANUAL"
    assert len(rett_067["hit_biological_variant_units"]) >= 10
