"""Tests for fused-75 adjudication review status helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.optimization.fused75.adjudication_contracts import Fused75EntryAdjudication
from benchmark.optimization.fused75.review_status import (
    ReviewStats,
    complete_entry,
    load_review_stats,
    set_label_decision,
)


def _write_adjudication(root: Path, *, entry_id: str = "fused_000") -> Path:
    path = root / "dev" / f"{entry_id}.json"
    payload = {
        "entry_id": entry_id,
        "expected_path": f"benchmark/data/ground_truth/clinvar_fused/{entry_id}/expected.json",
        "is_complete": False,
        "labels": [
            {
                "field_id": "A.gene_symbol",
                "expected_value": "CFTR",
                "visibility": None,
            },
            {
                "field_id": "A.gene_disease_relationship",
                "expected_value": "causative",
                "visibility": None,
            },
        ],
        "source_path": f"benchmark/data/ground_truth/clinvar_fused/{entry_id}/source.md",
        "split": "adjudication_dev",
    }
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_set_label_decision_updates_one_field_and_preserves_incomplete_entry(tmp_path: Path) -> None:
    root = tmp_path / "adjudication"
    path = _write_adjudication(root)

    updated = set_label_decision(
        adjudication_root=root,
        entry_id="fused_000",
        field_id="A.gene_symbol",
        visibility="source_visible",
        reviewer="reviewer-a",
        source_quote="CFTR is visible in the source.",
        source_location="source.md:1",
        notes="checked title and abstract",
    )

    assert updated.entry_id == "fused_000"
    saved = Fused75EntryAdjudication.model_validate_json(path.read_text(encoding="utf-8"))
    assert saved.is_complete is False
    assert saved.labels[0].visibility == "source_visible"
    assert saved.labels[0].adjudicator == "reviewer-a"
    assert saved.labels[0].source_quote == "CFTR is visible in the source."
    assert saved.labels[1].visibility is None


def test_set_label_decision_requires_source_visible_evidence(tmp_path: Path) -> None:
    root = tmp_path / "adjudication"
    _write_adjudication(root)

    with pytest.raises(ValueError, match="source_visible decisions require"):
        set_label_decision(
            adjudication_root=root,
            entry_id="fused_000",
            field_id="A.gene_symbol",
            visibility="source_visible",
            reviewer="reviewer-a",
        )


def test_complete_entry_rejects_unresolved_labels(tmp_path: Path) -> None:
    root = tmp_path / "adjudication"
    _write_adjudication(root)
    set_label_decision(
        adjudication_root=root,
        entry_id="fused_000",
        field_id="A.gene_symbol",
        visibility="not_source_visible",
        reviewer="reviewer-a",
    )

    with pytest.raises(ValueError, match="unresolved labels"):
        complete_entry(adjudication_root=root, entry_id="fused_000")


def test_complete_entry_marks_entry_complete_after_all_fields_are_decided(tmp_path: Path) -> None:
    root = tmp_path / "adjudication"
    path = _write_adjudication(root)
    for field_id in ("A.gene_symbol", "A.gene_disease_relationship"):
        set_label_decision(
            adjudication_root=root,
            entry_id="fused_000",
            field_id=field_id,
            visibility="not_source_visible",
            reviewer="reviewer-a",
        )

    complete_entry(adjudication_root=root, entry_id="fused_000")

    saved = Fused75EntryAdjudication.model_validate_json(path.read_text(encoding="utf-8"))
    assert saved.is_complete is True


def test_load_review_stats_counts_complete_entries_and_visibility_values(tmp_path: Path) -> None:
    root = tmp_path / "adjudication"
    _write_adjudication(root)
    set_label_decision(
        adjudication_root=root,
        entry_id="fused_000",
        field_id="A.gene_symbol",
        visibility="not_source_visible",
        reviewer="reviewer-a",
    )

    stats = load_review_stats(adjudication_root=root)

    assert stats == ReviewStats(
        total_entries=1,
        complete_entries=0,
        total_labels=2,
        unresolved_labels=1,
        source_visible_labels=0,
        not_source_visible_labels=1,
        ambiguous_boundary_labels=0,
        unsupported_prediction_labels=0,
    )
