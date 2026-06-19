"""Tests for deterministic fused-75 split selection."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.optimization.fused75.contracts import Fused75SplitManifest
from benchmark.optimization.fused75.select_splits import build_split_manifest, write_split_manifest


def _write_entry(root: Path, entry_id: str, source_text: str = "source\n") -> None:
    entry_root = root / entry_id
    entry_root.mkdir(parents=True)
    (entry_root / "source.md").write_text(source_text, encoding="utf-8")
    (entry_root / "expected.json").write_text(
        json.dumps({"entry_id": entry_id}, sort_keys=True),
        encoding="utf-8",
    )


def _write_selection(root: Path, entry_ids: list[str]) -> None:
    (root / "selection.json").write_text(
        json.dumps([{"entry_id": entry_id} for entry_id in entry_ids], indent=2),
        encoding="utf-8",
    )


def test_build_split_manifest_assigns_all_entries_and_freezes_dev_test(tmp_path: Path) -> None:
    dataset_root = tmp_path / "clinvar_fused"
    dataset_root.mkdir()
    entry_ids = [f"fused_{index:03d}" for index in range(25)]
    _write_selection(dataset_root, list(reversed(entry_ids)))
    for entry_id in entry_ids:
        _write_entry(dataset_root, entry_id)

    manifest = build_split_manifest(dataset_root=dataset_root, dev_count=10, test_count=10)

    assert isinstance(manifest, Fused75SplitManifest)
    assert manifest.metadata.selection_method == "sorted_entry_id_v1"
    assert manifest.metadata.split_seed == "sorted-entry-id-v1"
    assert manifest.metadata.dev_count == 10
    assert manifest.metadata.test_count == 10
    assert manifest.metadata.total_entries == 25
    assert len(manifest.entries) == 25
    assert [entry.entry_id for entry in manifest.entries] == sorted(entry_ids)
    assert [entry.split for entry in manifest.entries[:10]] == ["adjudication_dev"] * 10
    assert [entry.split for entry in manifest.entries[10:20]] == ["adjudication_test"] * 10
    assert [entry.split for entry in manifest.entries[20:]] == ["auto_pool"] * 5
    assert all(entry.source_path == dataset_root / entry.entry_id / "source.md" for entry in manifest.entries)
    assert all(entry.expected_path == dataset_root / entry.entry_id / "expected.json" for entry in manifest.entries)


def test_write_split_manifest_is_byte_stable(tmp_path: Path) -> None:
    dataset_root = tmp_path / "clinvar_fused"
    dataset_root.mkdir()
    entry_ids = [f"fused_{index:03d}" for index in range(22)]
    _write_selection(dataset_root, entry_ids)
    for entry_id in entry_ids:
        _write_entry(dataset_root, entry_id, source_text=f"{entry_id}\n")

    first_output = tmp_path / "first.json"
    second_output = tmp_path / "second.json"
    manifest = build_split_manifest(dataset_root=dataset_root, dev_count=10, test_count=10)

    write_split_manifest(manifest, first_output)
    write_split_manifest(manifest, second_output)

    assert first_output.read_bytes() == second_output.read_bytes()
    payload = json.loads(first_output.read_text(encoding="utf-8"))
    assert payload["metadata"] == {
        "dataset_root": str(dataset_root),
        "dev_count": 10,
        "selection_method": "sorted_entry_id_v1",
        "selection_path": str(dataset_root / "selection.json"),
        "split_seed": "sorted-entry-id-v1",
        "test_count": 10,
        "total_entries": 22,
    }
    assert payload["entries"][0]["entry_id"] == "fused_000"
    assert payload["entries"][0]["selection_reason"] == "first 10 sorted entries reserved for adjudication dev"


def test_build_split_manifest_fails_when_required_files_are_missing(tmp_path: Path) -> None:
    dataset_root = tmp_path / "clinvar_fused"
    dataset_root.mkdir()
    _write_selection(dataset_root, ["fused_000"])
    (dataset_root / "fused_000").mkdir()
    (dataset_root / "fused_000" / "source.md").write_text("source\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="expected.json"):
        build_split_manifest(dataset_root=dataset_root, dev_count=1, test_count=0)
