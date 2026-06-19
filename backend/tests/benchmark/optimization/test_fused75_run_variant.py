"""Tests for fused-75 pipeline variant runner wrapper."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.optimization.fused75.adjudication_contracts import (
    Fused75EntryAdjudication,
    Fused75FieldAdjudication,
)
from benchmark.optimization.fused75.run_contracts import PipelineFlag, PipelineVariantConfig
from benchmark.optimization.fused75.run_variant import run_variant


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_config(path: Path, dataset_split: str = "dev") -> None:
    config = PipelineVariantConfig(
        variant_id="stub-variant",
        git_commit="a" * 40,
        dataset_split=dataset_split,
        pipeline_flags=(PipelineFlag(key="stub", value=True),),
        model_config_names=("LLM_MODEL",),
    )
    _write_json(path, config.model_dump(mode="json"))


def _write_adjudication(path: Path) -> None:
    payload = Fused75EntryAdjudication(
        entry_id="fused_000",
        split="adjudication_dev",
        source_path=Path("source.md"),
        expected_path=Path("expected.json"),
        is_complete=True,
        labels=(
            Fused75FieldAdjudication(
                field_id="A.gene_symbol",
                expected_value="CFTR",
                visibility="source_visible",
                source_quote="CFTR appears in the source.",
                source_location="source.md:1",
                adjudicator="reviewer-a",
            ),
        ),
    )
    _write_json(path, payload.model_dump(mode="json"))


def test_run_variant_refuses_test_split_without_checkpoint(tmp_path: Path) -> None:
    config_path = tmp_path / "variant.json"
    _write_config(config_path, dataset_split="test")

    with pytest.raises(ValueError, match="checkpoint"):
        run_variant(
            split="test",
            config_path=config_path,
            adjudication_root=tmp_path / "adjudication",
            extraction_root=tmp_path / "extractions",
            output_path=tmp_path / "report.json",
            checkpoint=False,
        )


def test_run_variant_rejects_config_split_mismatch(tmp_path: Path) -> None:
    config_path = tmp_path / "variant.json"
    _write_config(config_path, dataset_split="test")

    with pytest.raises(ValueError, match="dataset_split"):
        run_variant(
            split="dev",
            config_path=config_path,
            adjudication_root=tmp_path / "adjudication",
            extraction_root=tmp_path / "extractions",
            output_path=tmp_path / "report.json",
            checkpoint=True,
        )


def test_run_variant_rejects_incomplete_adjudication(tmp_path: Path) -> None:
    config_path = tmp_path / "variant.json"
    _write_config(config_path)
    payload = Fused75EntryAdjudication(
        entry_id="fused_000",
        split="adjudication_dev",
        source_path=Path("source.md"),
        expected_path=Path("expected.json"),
        labels=(
            Fused75FieldAdjudication(
                field_id="A.gene_symbol",
                expected_value="CFTR",
            ),
        ),
    )
    _write_json(tmp_path / "adjudication" / "dev" / "fused_000.json", payload.model_dump(mode="json"))

    with pytest.raises(ValueError, match="incomplete adjudication"):
        run_variant(
            split="dev",
            config_path=config_path,
            adjudication_root=tmp_path / "adjudication",
            extraction_root=tmp_path / "extractions",
            output_path=tmp_path / "report.json",
        )


def test_run_variant_writes_stubbed_dev_report(tmp_path: Path) -> None:
    config_path = tmp_path / "variant.json"
    output_path = tmp_path / "report.json"
    _write_config(config_path)
    _write_adjudication(tmp_path / "adjudication" / "dev" / "fused_000.json")
    _write_json(
        tmp_path / "extractions" / "fused_000.json",
        {"items": [{"field_id": "A.gene_symbol", "value": "CFTR"}]},
    )

    report = run_variant(
        split="dev",
        config_path=config_path,
        adjudication_root=tmp_path / "adjudication",
        extraction_root=tmp_path / "extractions",
        output_path=output_path,
    )

    assert report.metric.precision == 1.0
    assert report.metric.recall == 1.0
    assert report.metric.f1 == 1.0
    assert report.metric.source_visible_f1 == 1.0
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["config"]["variant_id"] == "stub-variant"
    assert payload["decision"]["decision"] == "checkpoint_only"
