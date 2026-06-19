"""Tests for fused-75 adjudication template generation."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.optimization.fused75.adjudication_contracts import Fused75EntryAdjudication
from benchmark.optimization.fused75.create_adjudication_templates import create_adjudication_templates
from benchmark.optimization.fused75.select_splits import build_split_manifest, write_split_manifest


def _write_entry(root: Path, entry_id: str) -> None:
    entry_root = root / entry_id
    entry_root.mkdir(parents=True)
    (entry_root / "source.md").write_text(f"{entry_id} source\n", encoding="utf-8")
    (entry_root / "expected.json").write_text(
        json.dumps(
            {
                "entry_id": entry_id,
                "expected_evidence": [
                    {"field_id": "A.gene_symbol", "value": "CFTR"},
                    {"field_id": "B.disease_diagnosis", "value": "cystic fibrosis"},
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def test_create_adjudication_templates_generates_dev_and_test_payloads(tmp_path: Path) -> None:
    dataset_root = tmp_path / "clinvar_fused"
    dataset_root.mkdir()
    entry_ids = [f"fused_{index:03d}" for index in range(5)]
    (dataset_root / "selection.json").write_text(
        json.dumps([{"entry_id": entry_id} for entry_id in entry_ids]),
        encoding="utf-8",
    )
    for entry_id in entry_ids:
        _write_entry(dataset_root, entry_id)
    split_manifest = build_split_manifest(dataset_root=dataset_root, dev_count=2, test_count=2)
    split_manifest_path = tmp_path / "split.json"
    write_split_manifest(split_manifest, split_manifest_path)

    output_root = tmp_path / "adjudication"
    created = create_adjudication_templates(
        split_manifest_path=split_manifest_path,
        output_root=output_root,
        dataset_root=dataset_root,
    )

    assert len(created.templates) == 4
    assert sorted(path.relative_to(output_root).as_posix() for path in created.templates) == [
        "dev/fused_000.json",
        "dev/fused_001.json",
        "test/fused_002.json",
        "test/fused_003.json",
    ]
    payload = json.loads((output_root / "dev" / "fused_000.json").read_text(encoding="utf-8"))
    template = Fused75EntryAdjudication.model_validate(payload)
    assert template.is_complete is False
    assert template.entry_id == "fused_000"
    assert template.split == "adjudication_dev"
    assert [label.field_id for label in template.labels] == ["A.gene_symbol", "B.disease_diagnosis"]
    assert [label.expected_value for label in template.labels] == ["CFTR", "cystic fibrosis"]
    assert {label.visibility for label in template.labels} == {None}


def test_create_adjudication_templates_is_stable(tmp_path: Path) -> None:
    dataset_root = tmp_path / "clinvar_fused"
    dataset_root.mkdir()
    entry_ids = [f"fused_{index:03d}" for index in range(3)]
    (dataset_root / "selection.json").write_text(
        json.dumps([{"entry_id": entry_id} for entry_id in entry_ids]),
        encoding="utf-8",
    )
    for entry_id in entry_ids:
        _write_entry(dataset_root, entry_id)
    split_manifest_path = tmp_path / "split.json"
    write_split_manifest(build_split_manifest(dataset_root=dataset_root, dev_count=1, test_count=1), split_manifest_path)

    output_root = tmp_path / "adjudication"
    create_adjudication_templates(split_manifest_path=split_manifest_path, output_root=output_root, dataset_root=dataset_root)
    first = (output_root / "dev" / "fused_000.json").read_bytes()
    create_adjudication_templates(split_manifest_path=split_manifest_path, output_root=output_root, dataset_root=dataset_root)

    assert (output_root / "dev" / "fused_000.json").read_bytes() == first
