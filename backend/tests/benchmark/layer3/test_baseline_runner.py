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
    from benchmark.analysis.baselines.runner import BaselineConfig, BaselineEvidenceItem, run_baseline_evaluation

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
    from benchmark.analysis.baselines.runner import BaselineConfig, BaselineEvidenceItem, run_baseline_evaluation

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
    from benchmark.analysis.baselines.runner import BaselineConfig, BaselineEvidenceItem, run_baseline_evaluation

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
    from benchmark.analysis.baselines import (
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
    from benchmark.analysis.baselines.llm_common import BaselineLLMResponse

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


def test_baseline_llm_response_normalizes_schema_drift() -> None:
    from benchmark.analysis.baselines.llm_common import BaselineLLMResponse

    response = BaselineLLMResponse.model_validate(
        {
            "evidence_items": [
                {
                    "field_id": "A.gene_disease_relationship",
                    "status": "uncertain",
                    "value": "uncertain",
                    "confidence": "",
                },
                {
                    "field_id": "B.disease_diagnosis",
                    "status": "not_found",
                    "value": "",
                    "confidence": "N/A",
                },
                {
                    "field_id": "A.gene_symbol",
                    "status": "not_found",
                    "value": "",
                    "confidence": None,
                },
                {
                    "field_id": "A.gene_disease_relationship",
                    "status": "not_found",
                    "value": "",
                    "confidence": "No explicit support in the source text.",
                },
            ]
        }
    )

    assert response.evidence_items[0].status == "found"
    assert response.evidence_items[0].value == "uncertain"
    assert [item.confidence for item in response.evidence_items] == [0.0, 0.0, 0.0, 0.0]


def test_baseline_llm_response_accepts_field_keyed_item_list() -> None:
    from benchmark.analysis.baselines.llm_common import BaselineLLMResponse

    response = BaselineLLMResponse.model_validate(
        {
            "evidence_items": [
                {
                    "A.gene_symbol": {
                        "status": "found",
                        "value": "MECP2",
                        "confidence": "high",
                    }
                },
                {
                    "B.disease_diagnosis": {
                        "status": "found",
                        "value": "Rett syndrome",
                        "confidence": "medium",
                    }
                },
            ]
        }
    )

    assert [(item.field_id, item.value, item.confidence) for item in response.evidence_items] == [
        ("A.gene_symbol", "MECP2", 0.9),
        ("B.disease_diagnosis", "Rett syndrome", 0.6),
    ]


def test_baseline_llm_response_accepts_multi_field_keyed_list_item() -> None:
    from benchmark.analysis.baselines.llm_common import BaselineLLMResponse

    response = BaselineLLMResponse.model_validate(
        {
            "evidence_items": [
                {
                    "A.gene_symbol": {
                        "field_id": "A.gene_symbol",
                        "status": "found",
                        "value": "MECP2",
                        "confidence": 0.93,
                    },
                    "B.disease_diagnosis": {
                        "field_id": "B.disease_diagnosis",
                        "status": "found",
                        "value": "Rett syndrome",
                        "confidence": 0.9,
                    },
                }
            ]
        }
    )

    assert [item.field_id for item in response.evidence_items] == [
        "A.gene_symbol",
        "B.disease_diagnosis",
    ]


def test_baseline_llm_response_accepts_field_keyed_evidence_map() -> None:
    from benchmark.analysis.baselines.llm_common import BaselineLLMResponse

    response = BaselineLLMResponse.model_validate(
        {
            "evidence_items": {
                "A.gene_symbol": {
                    "status": "found",
                    "value": "MECP2",
                    "confidence": "high",
                }
            }
        }
    )

    assert response.evidence_items[0].field_id == "A.gene_symbol"
    assert response.evidence_items[0].value == "MECP2"


def test_translate_then_extract_skips_translation_for_english_source() -> None:
    from benchmark.analysis.baselines.llm_common import should_translate_before_extract

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


def test_baseline_report_serializes_metadata(tmp_path: Path) -> None:
    from benchmark.analysis.baselines.runner import BaselineConfig, BaselineReport, _serialize_report

    report = BaselineReport(
        baseline_id="B6_GPT5_PROMPT_CITE",
        baseline_name="GPT-5 prompt-only citation-required",
        total_entries=0,
        total_duration_s=0.0,
        aggregates={"overall": {"precision": 0.0, "recall": 0.0, "f1": 0.0}},
        per_entry=[],
    )
    config = BaselineConfig(
        baseline_id="B6_GPT5_PROMPT_CITE",
        baseline_name="GPT-5 prompt-only citation-required",
        ground_truth_dir=tmp_path,
        reports_dir=tmp_path,
        metadata={
            "model": "gpt-5",
            "prompt_mode": "citation_required",
            "temperature": 0.0,
        },
    )

    payload = _serialize_report(report, config, None)

    assert payload["config"]["model"] == "gpt-5"
    assert payload["config"]["prompt_mode"] == "citation_required"
    assert payload["config"]["temperature"] == 0.0


def test_naive_llm_baseline_uses_canonical_gpt5_metadata() -> None:
    from benchmark.analysis.baselines.naive_llm import build_config

    config = build_config(
        ground_truth_dir=Path("benchmark/data/ground_truth/rett"),
        reports_dir=Path("benchmark/data/reports"),
        entry_ids=(),
        limit=None,
        save_report=True,
    )

    assert config.metadata["model_baseline_id"] == "B6_GPT5_PROMPT_CITE"
    assert config.metadata["model_baseline_name"] == "GPT-5 prompt-only citation-required"
    assert config.metadata["model"] == "gpt-5-2025-08-07"
    assert config.metadata["provider_family"] == "openai"
    assert config.metadata["release_cohort"] == "frontier_2025q3_aug07_sep30"
