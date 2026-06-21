"""Tests for fused-75 adjudication review queue generation."""
from __future__ import annotations

import json
from pathlib import Path

from benchmark.optimization.fused75.adjudication_review_queue import build_review_queue, write_review_queue


def _write_adjudication(path: Path, *, entry_id: str, split: str, visible_first_label: bool = False) -> None:
    labels = [
        {
            "adjudicator": "exact-match-preannotator" if visible_first_label else None,
            "expected_value": "CFTR",
            "field_id": "A.gene_symbol",
            "source_location": "source.md:1" if visible_first_label else None,
            "source_quote": "CFTR is visible." if visible_first_label else None,
            "visibility": "source_visible" if visible_first_label else None,
        },
        {
            "expected_value": "causative",
            "field_id": "A.gene_disease_relationship",
            "visibility": None,
        },
    ]
    payload = {
        "entry_id": entry_id,
        "expected_path": f"benchmark/data/ground_truth/clinvar_fused/{entry_id}/expected.json",
        "is_complete": False,
        "labels": labels,
        "source_path": f"benchmark/data/ground_truth/clinvar_fused/{entry_id}/source.md",
        "split": split,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_build_review_queue_lists_only_unresolved_labels_in_stable_order(tmp_path: Path) -> None:
    adjudication_root = tmp_path / "adjudication"
    _write_adjudication(
        adjudication_root / "dev" / "fused_001.json",
        entry_id="fused_001",
        split="adjudication_dev",
    )
    _write_adjudication(
        adjudication_root / "dev" / "fused_000.json",
        entry_id="fused_000",
        split="adjudication_dev",
        visible_first_label=True,
    )

    report = build_review_queue(adjudication_root=adjudication_root)

    assert report.total_entries == 2
    assert report.total_labels == 4
    assert report.unresolved_labels == 3
    assert [item.entry_id for item in report.items] == ["fused_000", "fused_001", "fused_001"]
    assert [item.field_id for item in report.items] == [
        "A.gene_disease_relationship",
        "A.gene_symbol",
        "A.gene_disease_relationship",
    ]


def test_write_review_queue_writes_json_and_markdown(tmp_path: Path) -> None:
    adjudication_root = tmp_path / "adjudication"
    _write_adjudication(
        adjudication_root / "test" / "fused_010.json",
        entry_id="fused_010",
        split="adjudication_test",
        visible_first_label=True,
    )
    json_path = tmp_path / "queue.json"
    markdown_path = tmp_path / "queue.md"

    report = write_review_queue(
        adjudication_root=adjudication_root,
        json_path=json_path,
        markdown_path=markdown_path,
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert report.unresolved_labels == 1
    assert payload["unresolved_labels"] == 1
    assert payload["items"][0]["entry_id"] == "fused_010"
    assert "| fused_010 | adjudication_test | A.gene_disease_relationship | causative |" in markdown
