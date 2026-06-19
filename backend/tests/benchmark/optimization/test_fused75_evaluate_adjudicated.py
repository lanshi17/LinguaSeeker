"""Tests for fused-75 adjudicated evaluation."""
from __future__ import annotations

from pathlib import Path

from benchmark.optimization.fused75.adjudication_contracts import (
    Fused75EntryAdjudication,
    Fused75FieldAdjudication,
)
from benchmark.optimization.fused75.evaluate_adjudicated import evaluate_adjudicated_entry


def _entry(labels: tuple[Fused75FieldAdjudication, ...]) -> Fused75EntryAdjudication:
    return Fused75EntryAdjudication(
        entry_id="fused_000",
        split="adjudication_dev",
        source_path=Path("source.md"),
        expected_path=Path("expected.json"),
        is_complete=True,
        labels=labels,
    )


def _visible(field_id: str, value: str) -> Fused75FieldAdjudication:
    return Fused75FieldAdjudication(
        field_id=field_id,
        expected_value=value,
        visibility="source_visible",
        source_quote=f"{value} appears in the source.",
        source_location="source.md:1",
        adjudicator="reviewer-a",
    )


def test_evaluate_adjudicated_entry_counts_true_positive() -> None:
    result = evaluate_adjudicated_entry(
        _entry((_visible("A.gene_symbol", "CFTR"),)),
        extracted_items=(PipelineItem(field_id="A.gene_symbol", value="CFTR"),),
    )

    assert result.metric.precision == 1.0
    assert result.metric.recall == 1.0
    assert result.metric.f1 == 1.0
    assert result.field_results[0].outcome == "tp"


def test_evaluate_adjudicated_entry_counts_false_negative() -> None:
    result = evaluate_adjudicated_entry(
        _entry((_visible("A.gene_symbol", "CFTR"),)),
        extracted_items=(),
    )

    assert result.metric.precision == 0.0
    assert result.metric.recall == 0.0
    assert result.metric.f1 == 0.0
    assert result.field_results[0].outcome == "fn"


def test_evaluate_adjudicated_entry_excludes_not_source_visible_from_recall() -> None:
    result = evaluate_adjudicated_entry(
        _entry(
            (
                Fused75FieldAdjudication(
                    field_id="A.gene_symbol",
                    expected_value="CFTR",
                    visibility="not_source_visible",
                ),
            )
        ),
        extracted_items=(),
    )

    assert result.metric.precision == 0.0
    assert result.metric.recall == 0.0
    assert result.metric.f1 == 0.0
    assert result.field_results == ()


def test_evaluate_adjudicated_entry_counts_unsupported_output_as_false_positive() -> None:
    result = evaluate_adjudicated_entry(
        _entry((_visible("A.gene_symbol", "CFTR"),)),
        extracted_items=(
            PipelineItem(field_id="A.gene_symbol", value="CFTR"),
            PipelineItem(field_id="B.disease_diagnosis", value="unreviewed disease"),
        ),
    )

    assert result.metric.precision == 0.5
    assert result.metric.recall == 1.0
    assert round(result.metric.f1, 4) == 0.6667
    assert [field.outcome for field in result.field_results] == ["tp", "fp"]


def test_evaluate_adjudicated_entry_handles_wrong_boundary() -> None:
    result = evaluate_adjudicated_entry(
        _entry((_visible("B.disease_diagnosis", "cystic fibrosis"),)),
        extracted_items=(PipelineItem(field_id="B.disease_diagnosis", value="CFTR-related disorder"),),
    )

    assert result.metric.precision == 0.0
    assert result.metric.recall == 0.0
    assert result.metric.f1 == 0.0
    assert [field.outcome for field in result.field_results] == ["fn", "fp"]


class PipelineItem:
    """Minimal extracted item shape accepted by the evaluator."""

    def __init__(self, *, field_id: str, value: str):
        self.field_id = field_id
        self.value = value
