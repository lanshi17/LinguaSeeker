"""Tests for fused-75 adjudication validation."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.optimization.fused75.create_adjudication_templates import create_adjudication_templates
from benchmark.optimization.fused75.select_splits import build_split_manifest, write_split_manifest
from benchmark.optimization.fused75.validate_adjudication import validate_adjudication


def _write_entry(root: Path, entry_id: str) -> None:
    entry_root = root / entry_id
    entry_root.mkdir(parents=True)
    (entry_root / "source.md").write_text(f"{entry_id} source\n", encoding="utf-8")
    (entry_root / "expected.json").write_text(
        json.dumps(
            {
                "entry_id": entry_id,
                "expected_evidence": [{"field_id": "A.gene_symbol", "value": "CFTR"}],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _make_fixture(tmp_path: Path) -> tuple[Path, Path]:
    dataset_root = tmp_path / "clinvar_fused"
    dataset_root.mkdir()
    entry_ids = ["fused_000", "fused_001"]
    (dataset_root / "selection.json").write_text(
        json.dumps([{"entry_id": entry_id} for entry_id in entry_ids]),
        encoding="utf-8",
    )
    for entry_id in entry_ids:
        _write_entry(dataset_root, entry_id)
    split_manifest_path = tmp_path / "split.json"
    split_manifest = build_split_manifest(dataset_root=dataset_root, dev_count=1, test_count=1)
    write_split_manifest(split_manifest, split_manifest_path)
    output_root = tmp_path / "adjudication"
    create_adjudication_templates(
        split_manifest_path=split_manifest_path,
        output_root=output_root,
        dataset_root=dataset_root,
    )
    return split_manifest_path, output_root


def _complete(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["is_complete"] = True
    for label in payload["labels"]:
        label["visibility"] = "source_visible"
        label["source_quote"] = "CFTR is discussed in the source."
        label["source_location"] = "source.md:1"
        label["adjudicator"] = "reviewer-a"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_validate_adjudication_passes_completed_dev_and_test(tmp_path: Path) -> None:
    split_manifest_path, output_root = _make_fixture(tmp_path)
    for path in output_root.glob("*/*.json"):
        _complete(path)

    result = validate_adjudication(split_manifest_path=split_manifest_path, adjudication_root=output_root)

    assert result.ok is True
    assert result.checked_entries == 2
    assert result.errors == ()


def test_validate_adjudication_fails_incomplete_templates(tmp_path: Path) -> None:
    split_manifest_path, output_root = _make_fixture(tmp_path)

    result = validate_adjudication(split_manifest_path=split_manifest_path, adjudication_root=output_root)

    assert result.ok is False
    assert any("is_complete=false" in error for error in result.errors)


def test_validate_adjudication_fails_missing_source_visible_evidence(tmp_path: Path) -> None:
    split_manifest_path, output_root = _make_fixture(tmp_path)
    for path in output_root.glob("*/*.json"):
        _complete(path)
    payload = json.loads((output_root / "dev" / "fused_000.json").read_text(encoding="utf-8"))
    payload["labels"][0].pop("source_quote")
    (output_root / "dev" / "fused_000.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = validate_adjudication(split_manifest_path=split_manifest_path, adjudication_root=output_root)

    assert result.ok is False
    assert any("source_quote" in error for error in result.errors)


def test_validate_adjudication_detects_test_file_hash_drift(tmp_path: Path) -> None:
    split_manifest_path, output_root = _make_fixture(tmp_path)
    for path in output_root.glob("*/*.json"):
        _complete(path)
    result = validate_adjudication(split_manifest_path=split_manifest_path, adjudication_root=output_root)
    assert result.ok is True
    frozen_hashes = result.test_file_hashes

    payload = json.loads((output_root / "test" / "fused_001.json").read_text(encoding="utf-8"))
    payload["labels"][0]["source_quote"] = "Changed after freeze."
    (output_root / "test" / "fused_001.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    drifted = validate_adjudication(
        split_manifest_path=split_manifest_path,
        adjudication_root=output_root,
        frozen_test_hashes=frozen_hashes,
    )

    assert drifted.ok is False
    assert any("frozen test hash changed" in error for error in drifted.errors)
