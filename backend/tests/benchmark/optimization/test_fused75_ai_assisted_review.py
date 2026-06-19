"""Tests for fused-75 AI-assisted adjudication drafts."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.optimization.fused75.ai_assisted_review import assist_adjudication_directory
from benchmark.optimization.fused75.adjudication_contracts import Fused75EntryAdjudication


def _write_fixture(tmp_path: Path) -> tuple[Path, Path]:
    dataset_root = tmp_path / "benchmark" / "data" / "ground_truth" / "clinvar_fused" / "fused_000"
    dataset_root.mkdir(parents=True)
    source_path = dataset_root / "source.md"
    source_path.write_text(
        "Cystic fibrosis is underdiagnosed due to CFTR variant screening panel bias.\n"
        "Cystic fibrosis is caused by mutations in the CFTR gene.\n"
        "Cystic fibrosis is an autosomal recessive disorder.\n",
        encoding="utf-8",
    )
    (dataset_root / "expected.json").write_text(
        json.dumps(
            {
                "clingen": {
                    "gene_symbol": "CFTR",
                    "disease_label": "cystic fibrosis",
                }
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    adjudication_root = tmp_path / "adjudication"
    path = adjudication_root / "dev" / "fused_000.json"
    payload = {
        "entry_id": "fused_000",
        "expected_path": "benchmark/data/ground_truth/clinvar_fused/fused_000/expected.json",
        "is_complete": False,
        "labels": [
            {
                "field_id": "A.gene_disease_relationship",
                "expected_value": "causative",
                "visibility": None,
            },
            {
                "field_id": "B.mode_of_inheritance_reported",
                "expected_value": "AR",
                "visibility": None,
            },
        ],
        "source_path": "benchmark/data/ground_truth/clinvar_fused/fused_000/source.md",
        "split": "adjudication_dev",
    }
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return adjudication_root, path


def test_assist_adjudication_directory_fills_high_confidence_source_visible_labels(tmp_path: Path) -> None:
    adjudication_root, path = _write_fixture(tmp_path)

    result = assist_adjudication_directory(
        adjudication_root=adjudication_root,
        project_root=tmp_path,
        adjudicator="ai-assisted-reviewer",
    )

    assert result.processed_entries == 1
    assert result.source_visible_labels == 2
    updated = Fused75EntryAdjudication.model_validate_json(path.read_text(encoding="utf-8"))
    assert updated.is_complete is False
    assert updated.labels[0].visibility == "source_visible"
    assert updated.labels[0].source_location.endswith("source.md:2")
    assert updated.labels[0].adjudicator == "ai-assisted-reviewer"
    assert updated.labels[1].visibility == "source_visible"
    assert updated.labels[1].source_location.endswith("source.md:3")


def test_assist_adjudication_directory_preserves_human_decisions(tmp_path: Path) -> None:
    adjudication_root, path = _write_fixture(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["labels"][0]["visibility"] = "not_source_visible"
    payload["labels"][0]["adjudicator"] = "human-reviewer"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    assist_adjudication_directory(
        adjudication_root=adjudication_root,
        project_root=tmp_path,
        adjudicator="ai-assisted-reviewer",
    )

    updated = Fused75EntryAdjudication.model_validate_json(path.read_text(encoding="utf-8"))
    assert updated.labels[0].visibility == "not_source_visible"
    assert updated.labels[0].adjudicator == "human-reviewer"
