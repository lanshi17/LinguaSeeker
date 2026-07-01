"""Tests for fused-75 adjudication contracts."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from benchmark.optimization.fused75.adjudication_contracts import (
    Fused75EntryAdjudication,
    Fused75FieldAdjudication,
)


def test_source_visible_label_requires_audit_evidence() -> None:
    label = Fused75FieldAdjudication(
        field_id="variant.hgvs_c",
        expected_value="NM_000059.4:c.5946delT",
        visibility="source_visible",
        source_quote="The report describes c.5946delT in BRCA2.",
        source_location="page 2, paragraph 3",
        adjudicator="reviewer-a",
    )

    assert label.field_id == "variant.hgvs_c"
    assert label.source_quote == "The report describes c.5946delT in BRCA2."


@pytest.mark.parametrize("missing_field", ("source_quote", "source_location", "adjudicator"))
def test_source_visible_label_rejects_missing_audit_evidence(missing_field: str) -> None:
    payload = {
        "field_id": "variant.hgvs_c",
        "expected_value": "NM_000059.4:c.5946delT",
        "visibility": "source_visible",
        "source_quote": "The report describes c.5946delT in BRCA2.",
        "source_location": "page 2, paragraph 3",
        "adjudicator": "reviewer-a",
    }
    payload.pop(missing_field)

    with pytest.raises(ValidationError, match=missing_field):
        Fused75FieldAdjudication(**payload)


def test_non_source_visible_label_allows_absent_audit_evidence() -> None:
    label = Fused75FieldAdjudication(
        field_id="phenotype",
        expected_value="Hereditary breast and ovarian cancer syndrome",
        visibility="not_source_visible",
    )

    assert label.source_quote is None
    assert label.source_location is None
    assert label.adjudicator is None


def test_label_rejects_invalid_visibility() -> None:
    with pytest.raises(ValidationError, match="visibility"):
        Fused75FieldAdjudication(
            field_id="variant.hgvs_c",
            expected_value="NM_000059.4:c.5946delT",
            visibility="visible",
        )


def test_label_rejects_full_passage_quotes() -> None:
    with pytest.raises(ValidationError, match="source_quote"):
        Fused75FieldAdjudication(
            field_id="variant.hgvs_c",
            expected_value="NM_000059.4:c.5946delT",
            visibility="ambiguous_boundary",
            source_quote="x" * 501,
        )


def test_entry_adjudication_accepts_adjudication_splits() -> None:
    label = Fused75FieldAdjudication(
        field_id="variant.hgvs_c",
        expected_value="NM_000059.4:c.5946delT",
        visibility="unsupported_prediction",
        notes="Expected value is absent from the cited source.",
    )

    entry = Fused75EntryAdjudication(
        entry_id="fused-001",
        split="adjudication_dev",
        source_path=Path("sources/fused-001.pdf"),
        expected_path=Path("expected/fused-001.json"),
        labels=(label,),
    )

    assert entry.labels == (label,)
    assert entry.model_dump(mode="json")["source_path"] == "sources/fused-001.pdf"


def test_incomplete_entry_adjudication_allows_blank_decisions() -> None:
    entry = Fused75EntryAdjudication(
        entry_id="fused-001",
        split="adjudication_dev",
        source_path=Path("sources/fused-001.pdf"),
        expected_path=Path("expected/fused-001.json"),
        labels=(
            Fused75FieldAdjudication(
                field_id="variant.hgvs_c",
                expected_value="NM_000059.4:c.5946delT",
            ),
        ),
    )

    assert entry.is_complete is False
    assert entry.labels[0].visibility is None


def test_completed_entry_adjudication_rejects_blank_decisions() -> None:
    with pytest.raises(ValidationError, match="unlabeled fields"):
        Fused75EntryAdjudication(
            entry_id="fused-001",
            split="adjudication_dev",
            source_path=Path("sources/fused-001.pdf"),
            expected_path=Path("expected/fused-001.json"),
            is_complete=True,
            labels=(
                Fused75FieldAdjudication(
                    field_id="variant.hgvs_c",
                    expected_value="NM_000059.4:c.5946delT",
                ),
            ),
        )


def test_entry_adjudication_rejects_non_adjudication_split() -> None:
    with pytest.raises(ValidationError, match="split"):
        Fused75EntryAdjudication(
            entry_id="fused-001",
            split="auto_pool",
            source_path="sources/fused-001.pdf",
            expected_path="expected/fused-001.json",
            labels=(
                {
                    "field_id": "variant.hgvs_c",
                    "expected_value": "NM_000059.4:c.5946delT",
                    "visibility": "source_visible",
                    "source_quote": "The report describes c.5946delT in BRCA2.",
                    "source_location": "page 2, paragraph 3",
                    "adjudicator": "reviewer-a",
                },
            ),
        )


def test_entry_adjudication_rejects_duplicate_field_ids() -> None:
    label = {
        "field_id": "A.gene_symbol",
        "expected_value": "CFTR",
        "visibility": "not_source_visible",
    }

    with pytest.raises(ValidationError, match="Duplicate field_id"):
        Fused75EntryAdjudication(
            entry_id="fused_000",
            split="adjudication_dev",
            source_path="benchmark/data/ground_truth/clinvar_fused/fused_000/source.md",
            expected_path="benchmark/data/ground_truth/clinvar_fused/fused_000/expected.json",
            labels=(label, {**label, "visibility": "ambiguous_boundary"}),
        )
