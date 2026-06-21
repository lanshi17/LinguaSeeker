"""Tests for fused-75 source-visible draft preannotation."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.optimization.fused75.adjudication_contracts import Fused75EntryAdjudication
from benchmark.optimization.fused75.source_visible_drafts import preannotate_adjudication_directory


def _write_adjudication(path: Path, source_path: Path) -> None:
    payload = {
        "entry_id": "fused_000",
        "expected_path": str(source_path.parent / "expected.json"),
        "is_complete": False,
        "labels": [
            {
                "field_id": "A.gene_symbol",
                "expected_value": "CFTR",
                "visibility": None,
            },
            {
                "field_id": "B.disease_diagnosis",
                "expected_value": "not in article",
                "visibility": None,
            },
        ],
        "source_path": str(source_path),
        "split": "adjudication_dev",
    }
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_preannotate_adjudication_directory_marks_exact_source_visible_matches(tmp_path: Path) -> None:
    source_path = tmp_path / "dataset" / "fused_000" / "source.md"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("This paper discusses CFTR in cystic fibrosis.\n", encoding="utf-8")
    adjudication_path = tmp_path / "adjudication" / "dev" / "fused_000.json"
    _write_adjudication(adjudication_path, source_path)

    result = preannotate_adjudication_directory(
        adjudication_root=tmp_path / "adjudication",
        adjudicator="exact-match-preannotator",
    )

    assert result.processed_entries == 1
    assert result.source_visible_labels == 1
    updated = Fused75EntryAdjudication.model_validate_json(adjudication_path.read_text(encoding="utf-8"))
    assert updated.is_complete is False
    assert updated.labels[0].visibility == "source_visible"
    assert updated.labels[0].source_quote == "This paper discusses CFTR in cystic fibrosis."
    assert updated.labels[0].source_location == f"{source_path}:1"
    assert updated.labels[0].adjudicator == "exact-match-preannotator"
    assert updated.labels[1].visibility is None


def test_preannotate_adjudication_directory_preserves_existing_manual_decisions(tmp_path: Path) -> None:
    source_path = tmp_path / "dataset" / "fused_000" / "source.md"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("CFTR is mentioned here.\n", encoding="utf-8")
    adjudication_path = tmp_path / "adjudication" / "dev" / "fused_000.json"
    _write_adjudication(adjudication_path, source_path)
    payload = json.loads(adjudication_path.read_text(encoding="utf-8"))
    payload["labels"][0]["visibility"] = "not_source_visible"
    payload["labels"][0]["adjudicator"] = "human-reviewer"
    adjudication_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = preannotate_adjudication_directory(
        adjudication_root=tmp_path / "adjudication",
        adjudicator="exact-match-preannotator",
    )

    assert result.source_visible_labels == 0
    updated = Fused75EntryAdjudication.model_validate_json(adjudication_path.read_text(encoding="utf-8"))
    assert updated.labels[0].visibility == "not_source_visible"
    assert updated.labels[0].adjudicator == "human-reviewer"


def test_preannotate_adjudication_directory_resolves_relative_source_paths_from_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    source_path = project_root / "benchmark" / "data" / "ground_truth" / "clinvar_fused" / "fused_000" / "source.md"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("CFTR is visible in this source.\n", encoding="utf-8")
    adjudication_path = tmp_path / "adjudication" / "dev" / "fused_000.json"
    _write_adjudication(adjudication_path, Path("benchmark/data/ground_truth/clinvar_fused/fused_000/source.md"))

    result = preannotate_adjudication_directory(
        adjudication_root=tmp_path / "adjudication",
        adjudicator="exact-match-preannotator",
        project_root=project_root,
    )

    assert result.processed_entries == 1
    assert result.missing_sources == ()
    updated = Fused75EntryAdjudication.model_validate_json(adjudication_path.read_text(encoding="utf-8"))
    assert updated.labels[0].visibility == "source_visible"
    assert updated.labels[0].source_location == f"{source_path}:1"


def test_preannotate_adjudication_directory_does_not_match_short_values_inside_words(tmp_path: Path) -> None:
    source_path = tmp_path / "dataset" / "fused_000" / "source.md"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("Caribbean cohorts were discussed.\nInheritance: AR.\n", encoding="utf-8")
    adjudication_path = tmp_path / "adjudication" / "dev" / "fused_000.json"
    _write_adjudication(adjudication_path, source_path)
    payload = json.loads(adjudication_path.read_text(encoding="utf-8"))
    payload["labels"] = [
        {
            "field_id": "B.mode_of_inheritance_reported",
            "expected_value": "AR",
            "visibility": None,
        }
    ]
    adjudication_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    preannotate_adjudication_directory(
        adjudication_root=tmp_path / "adjudication",
        adjudicator="exact-match-preannotator",
    )

    updated = Fused75EntryAdjudication.model_validate_json(adjudication_path.read_text(encoding="utf-8"))
    assert updated.labels[0].visibility == "source_visible"
    assert updated.labels[0].source_location == f"{source_path}:2"
    assert updated.labels[0].source_quote == "Inheritance: AR."


def test_preannotate_adjudication_directory_refreshes_existing_machine_decisions(tmp_path: Path) -> None:
    source_path = tmp_path / "dataset" / "fused_000" / "source.md"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("Caribbean cohorts were discussed.\n", encoding="utf-8")
    adjudication_path = tmp_path / "adjudication" / "dev" / "fused_000.json"
    _write_adjudication(adjudication_path, source_path)
    payload = json.loads(adjudication_path.read_text(encoding="utf-8"))
    payload["labels"] = [
        {
            "adjudicator": "exact-match-preannotator",
            "expected_value": "AR",
            "field_id": "B.mode_of_inheritance_reported",
            "source_location": f"{source_path}:1",
            "source_quote": "Caribbean cohorts were discussed.",
            "visibility": "source_visible",
        }
    ]
    adjudication_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = preannotate_adjudication_directory(
        adjudication_root=tmp_path / "adjudication",
        adjudicator="exact-match-preannotator",
    )

    assert result.source_visible_labels == 0
    updated = Fused75EntryAdjudication.model_validate_json(adjudication_path.read_text(encoding="utf-8"))
    assert updated.labels[0].visibility is None
    assert updated.labels[0].source_location is None
    assert updated.labels[0].source_quote is None
    assert updated.labels[0].adjudicator is None
