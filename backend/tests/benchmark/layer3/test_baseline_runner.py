"""Tests for layer-3 baseline evaluation runners."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_ground_truth_entry(root: Path, entry_id: str, source_text: str) -> None:
    entry_dir = root / entry_id
    entry_dir.mkdir(parents=True)
    (entry_dir / "source.md").write_text(source_text, encoding="utf-8")
    (entry_dir / "expected.json").write_text(
        json.dumps(
            {
                "entry_id": entry_id,
                "gene_symbol": "MECP2",
                "disease_label": "Rett syndrome",
                "classification": "Definitive",
                "moi": "XL",
                "expected_evidence": [
                    {"field_id": "A.gene_symbol", "value": "MECP2"},
                    {"field_id": "B.disease_diagnosis", "value": "Rett syndrome"},
                    {"field_id": "A.gene_disease_relationship", "value": "causative"},
                ],
                "expected_standardization": {
                    "gene": "HGNC:6990",
                    "disease": "MONDO:0010726",
                },
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_run_baseline_evaluation_reuses_layer3_metrics(tmp_path) -> None:
    from benchmark.layer3.baselines.runner import BaselineConfig, BaselineEvidenceItem, run_baseline_evaluation

    ground_truth_dir = tmp_path / "ground_truth"
    reports_dir = tmp_path / "reports"
    _write_ground_truth_entry(
        ground_truth_dir,
        "clingen_000",
        "The MECP2 gene is causative for Rett syndrome.",
    )
    (ground_truth_dir / "selection.json").write_text(
        json.dumps(
            [
                {
                    "entry_id": "clingen_000",
                    "gene_symbol": "MECP2",
                    "disease_label": "Rett syndrome",
                    "classification": "Definitive",
                    "moi": "XL",
                }
            ]
        ),
        encoding="utf-8",
    )

    async def extractor(entry, source_text: str) -> list[BaselineEvidenceItem]:  # noqa: ANN001
        assert entry.entry_id == "clingen_000"
        assert "MECP2" in source_text
        return [
            BaselineEvidenceItem(field_id="A.gene_symbol", status="found", value="MECP2", confidence=0.9),
            BaselineEvidenceItem(
                field_id="B.disease_diagnosis",
                status="found",
                value="Rett syndrome",
                confidence=0.9,
            ),
            BaselineEvidenceItem(
                field_id="A.gene_disease_relationship",
                status="found",
                value="uncertain",
                confidence=0.4,
            ),
        ]

    report = await run_baseline_evaluation(
        BaselineConfig(
            baseline_id="B-test",
            baseline_name="test baseline",
            ground_truth_dir=ground_truth_dir,
            reports_dir=reports_dir,
        ),
        extractor,
    )

    assert report.total_entries == 1
    assert report.aggregates["overall"]["true_positives"] == 2
    assert report.aggregates["overall"]["false_positives"] == 1
    assert report.aggregates["overall"]["false_negatives"] == 0
    assert report.per_entry[0].field_matches[2].match_type == "wrong_value"
    assert report.report_path is not None
    assert report.report_path.exists()


@pytest.mark.asyncio
async def test_run_baseline_evaluation_filters_entry_ids_and_limit(tmp_path) -> None:
    from benchmark.layer3.baselines.runner import BaselineConfig, BaselineEvidenceItem, run_baseline_evaluation

    ground_truth_dir = tmp_path / "ground_truth"
    reports_dir = tmp_path / "reports"
    _write_ground_truth_entry(ground_truth_dir, "clingen_000", "MECP2 Rett syndrome.")
    _write_ground_truth_entry(ground_truth_dir, "clingen_001", "AARS2 cardiomyopathy.")
    (ground_truth_dir / "selection.json").write_text(
        json.dumps(
            [
                {"entry_id": "clingen_000", "gene_symbol": "MECP2", "disease_label": "Rett syndrome"},
                {"entry_id": "clingen_001", "gene_symbol": "AARS2", "disease_label": "cardiomyopathy"},
            ]
        ),
        encoding="utf-8",
    )
    seen: list[str] = []

    async def extractor(entry, source_text: str) -> list[BaselineEvidenceItem]:  # noqa: ANN001, ARG001
        seen.append(entry.entry_id)
        return []

    report = await run_baseline_evaluation(
        BaselineConfig(
            baseline_id="B-test",
            baseline_name="test baseline",
            ground_truth_dir=ground_truth_dir,
            reports_dir=reports_dir,
            entry_ids=("clingen_001",),
            limit=1,
        ),
        extractor,
    )

    assert seen == ["clingen_001"]
    assert [entry.entry_id for entry in report.per_entry] == ["clingen_001"]


@pytest.mark.asyncio
async def test_run_baseline_evaluation_counts_extractor_error_as_missing_fields(tmp_path) -> None:
    from benchmark.layer3.baselines.runner import BaselineConfig, BaselineEvidenceItem, run_baseline_evaluation

    ground_truth_dir = tmp_path / "ground_truth"
    reports_dir = tmp_path / "reports"
    _write_ground_truth_entry(ground_truth_dir, "clingen_000", "MECP2 Rett syndrome.")
    (ground_truth_dir / "selection.json").write_text(
        json.dumps(
            [
                {"entry_id": "clingen_000", "gene_symbol": "MECP2", "disease_label": "Rett syndrome"},
            ]
        ),
        encoding="utf-8",
    )

    async def extractor(entry, source_text: str) -> list[BaselineEvidenceItem]:  # noqa: ANN001, ARG001
        raise RuntimeError("LLM unavailable")

    report = await run_baseline_evaluation(
        BaselineConfig(
            baseline_id="B-test",
            baseline_name="test baseline",
            ground_truth_dir=ground_truth_dir,
            reports_dir=reports_dir,
        ),
        extractor,
    )

    assert report.per_entry[0].pipeline_status == "error"
    assert report.aggregates["overall"]["false_negatives"] == 3
    assert report.aggregates["overall"]["recall"] == 0.0


def test_all_baseline_modules_expose_metadata_and_extractor() -> None:
    from benchmark.layer3.baselines import (
        naive_llm,
        original_only,
        rag_llm,
        single_agent_cot,
        translate_then_extract,
    )

    modules = [naive_llm, translate_then_extract, original_only, rag_llm, single_agent_cot]

    assert [module.BASELINE_ID for module in modules] == ["B0", "B1", "B2", "B3", "B4"]
    for module in modules:
        assert module.BASELINE_NAME
        assert callable(module.extract)
        assert callable(module.main)


def test_baseline_llm_response_normalizes_confidence_labels() -> None:
    from benchmark.layer3.baselines.llm_common import BaselineLLMResponse

    response = BaselineLLMResponse.model_validate(
        {
            "evidence_items": [
                {"field_id": "A.gene_symbol", "status": "found", "value": "MECP2", "confidence": "high"},
                {"field_id": "A.gene_symbol", "status": "found", "value": "MECP2", "confidence": "strong"},
                {
                    "field_id": "B.disease_diagnosis",
                    "status": "found",
                    "value": "Rett syndrome",
                    "confidence": "medium",
                },
                {
                    "field_id": "A.gene_disease_relationship",
                    "status": "found",
                    "value": "causative",
                    "confidence": "low",
                },
            ]
        }
    )

    assert [item.confidence for item in response.evidence_items] == [0.9, 0.9, 0.6, 0.3]


def test_translate_then_extract_skips_translation_for_english_source() -> None:
    from benchmark.layer3.baselines.llm_common import should_translate_before_extract

    assert not should_translate_before_extract(
        "translate_then_extract",
        "The MECP2 gene is causative for Rett syndrome.",
    )
    assert should_translate_before_extract(
        "translate_then_extract",
        "MECP2 基因突变可导致 Rett 综合征。",
    )
    assert not should_translate_before_extract(
        "naive",
        "MECP2 基因突变可导致 Rett 综合征。",
    )
