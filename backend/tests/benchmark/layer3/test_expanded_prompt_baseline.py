"""Tests for B7 expanded prompt baseline (stronger single-prompt baseline)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.analysis.baselines.runner import BaselineEntry


# ---------------------------------------------------------------------------
# Prompt content tests
# ---------------------------------------------------------------------------


def test_expanded_prompt_includes_medium_and_complex_fields() -> None:
    """Expanded prompt must request all medium and complex field IDs."""
    from benchmark.analysis.baselines.llm_common import _build_extraction_prompt

    entry = BaselineEntry(
        entry_id="test_001",
        gene_symbol="MECP2",
        disease_label="Rett syndrome",
    )
    prompt = _build_extraction_prompt("expanded", entry, "dummy text")

    # Medium fields
    assert "B.sex" in prompt
    assert "B.age_of_onset" in prompt
    assert "B.mode_of_inheritance_reported" in prompt
    assert "C.inheritance_source" in prompt
    assert "B.clinical_phenotypes" in prompt

    # Complex fields
    assert "C.de_novo_status" in prompt
    assert "C.segregation" in prompt
    assert "C.functional_assay" in prompt
    assert "C.recurrence" in prompt
    assert "C.contradictory_evidence" in prompt

    # Simple fields still present
    assert "A.gene_symbol" in prompt
    assert "B.disease_diagnosis" in prompt
    assert "A.gene_disease_relationship" in prompt


def test_expanded_prompt_includes_variant_fields() -> None:
    """Expanded prompt must request variant detail fields."""
    from benchmark.analysis.baselines.llm_common import _build_extraction_prompt

    entry = BaselineEntry(
        entry_id="test_001",
        gene_symbol="LRRK2",
        disease_label="Parkinson disease",
    )
    prompt = _build_extraction_prompt("expanded", entry, "dummy text")

    assert "A.variant_hgvs_c" in prompt
    assert "A.variant_hgvs_p" in prompt
    assert "A.variant_type" in prompt
    assert "A.variant_consequence_class" in prompt


def test_expanded_prompt_does_not_leak_expected_labels() -> None:
    """Expanded prompt must not include expected evidence values from ground truth."""
    from benchmark.analysis.baselines.llm_common import _build_extraction_prompt

    entry = BaselineEntry(
        entry_id="test_001",
        gene_symbol="MECP2",
        disease_label="Rett syndrome",
        expected_evidence=[
            {"field_id": "A.gene_symbol", "value": "MECP2"},
            {"field_id": "C.de_novo_status", "value": "confirmed de novo in this family"},
        ],
    )
    prompt = _build_extraction_prompt("expanded", entry, "dummy text")

    # The specific expected value phrase must not appear in the prompt
    assert "confirmed de novo in this family" not in prompt


def test_expanded_prompt_uses_single_pass_instruction() -> None:
    """Expanded prompt must enforce single-pass extraction (no pipeline modules)."""
    from benchmark.analysis.baselines.llm_common import _build_extraction_prompt

    entry = BaselineEntry(
        entry_id="test_001",
        gene_symbol="MECP2",
        disease_label="Rett syndrome",
    )
    prompt = _build_extraction_prompt("expanded", entry, "dummy text")

    # Must prohibit pipeline modules
    lower = prompt.lower()
    assert "single" in lower or "one" in lower or "direct" in lower
    assert "no" in lower and ("multi-stage" in lower or "multi-stage" in prompt.lower())
    assert "no tools" in lower or "do not use tools" in lower or "without tools" in lower


def test_expanded_prompt_requests_json_output() -> None:
    """Expanded prompt must request structured JSON with evidence_items array."""
    from benchmark.analysis.baselines.llm_common import _build_extraction_prompt

    entry = BaselineEntry(
        entry_id="test_001",
        gene_symbol="MECP2",
        disease_label="Rett syndrome",
    )
    prompt = _build_extraction_prompt("expanded", entry, "dummy text")

    assert "evidence_items" in prompt
    assert "JSON" in prompt
    assert "field_id" in prompt
    assert "status" in prompt
    assert "found" in prompt
    assert "not_found" in prompt


# ---------------------------------------------------------------------------
# Metadata tests
# ---------------------------------------------------------------------------


def test_expanded_baseline_metadata_is_b7() -> None:
    """Expanded baseline config must use B7_GPT5_EXPANDED_PROMPT metadata."""
    from benchmark.analysis.baselines.canonical_models import CANONICAL_GPT5_EXPANDED

    metadata = CANONICAL_GPT5_EXPANDED.as_metadata()

    assert metadata["model_baseline_id"] == "B7_GPT5_EXPANDED_PROMPT"
    assert metadata["model_baseline_name"] == "GPT-5 expanded single-prompt evidence extraction"
    assert metadata["model"] == "gpt-5-2025-08-07"
    assert metadata["provider_family"] == "openai"


def test_expanded_baseline_config_metadata() -> None:
    """Expanded baseline module must produce correct BaselineConfig metadata."""
    from benchmark.analysis.baselines.expanded_prompt import build_config

    config = build_config(
        ground_truth_dir=Path("benchmark/data/ground_truth/rett"),
        reports_dir=Path("benchmark/data/reports"),
        entry_ids=(),
        limit=None,
        save_report=True,
    )

    assert config.baseline_id == "B7"
    assert config.baseline_name == "GPT-5 expanded single-prompt evidence extraction"
    assert config.metadata["model_baseline_id"] == "B7_GPT5_EXPANDED_PROMPT"
    assert config.metadata["model"] == "gpt-5-2025-08-07"
    assert config.metadata["provider_family"] == "openai"


# ---------------------------------------------------------------------------
# Module interface tests
# ---------------------------------------------------------------------------


def test_expanded_baseline_module_exposes_interface() -> None:
    """Expanded prompt module must expose BASELINE_ID, BASELINE_NAME, extract, main."""
    from benchmark.analysis.baselines import expanded_prompt

    assert expanded_prompt.BASELINE_ID == "B7"
    assert expanded_prompt.BASELINE_NAME
    assert callable(expanded_prompt.extract)
    assert callable(expanded_prompt.main)


def test_expanded_baseline_id_differs_from_b0() -> None:
    """B7 baseline ID must differ from B0 to avoid report collision."""
    from benchmark.analysis.baselines.expanded_prompt import BASELINE_ID as B7_ID
    from benchmark.analysis.baselines.naive_llm import BASELINE_ID as B0_ID

    assert B7_ID != B0_ID


# ---------------------------------------------------------------------------
# Response schema compatibility tests
# ---------------------------------------------------------------------------


def test_expanded_response_schema_compatible_with_evaluator() -> None:
    """LLM responses from expanded prompt must parse into BaselineLLMResponse."""
    from benchmark.analysis.baselines.llm_common import BaselineLLMResponse

    response = BaselineLLMResponse.model_validate(
        {
            "evidence_items": [
                {"field_id": "A.gene_symbol", "status": "found", "value": "MECP2", "confidence": 0.9},
                {"field_id": "B.disease_diagnosis", "status": "found", "value": "Rett syndrome", "confidence": 0.9},
                {"field_id": "A.gene_disease_relationship", "status": "found", "value": "causative", "confidence": 0.9},
                {"field_id": "A.variant_hgvs_c", "status": "found", "value": "c.473C>T", "confidence": 0.8},
                {"field_id": "A.variant_hgvs_p", "status": "found", "value": "p.T158M", "confidence": 0.8},
                {"field_id": "A.variant_type", "status": "found", "value": "SNV", "confidence": 0.8},
                {"field_id": "A.variant_consequence_class", "status": "found", "value": "missense", "confidence": 0.8},
                {"field_id": "B.sex", "status": "found", "value": "female", "confidence": 0.9},
                {"field_id": "B.age_of_onset", "status": "found", "value": "2 years", "confidence": 0.7},
                {"field_id": "B.mode_of_inheritance_reported", "status": "found", "value": "X-linked dominant", "confidence": 0.8},
                {"field_id": "C.inheritance_source", "status": "found", "value": "explicit", "confidence": 0.7},
                {"field_id": "B.clinical_phenotypes", "status": "found", "value": "stereotypic hand movements", "confidence": 0.7},
                {"field_id": "C.de_novo_status", "status": "found", "value": "de novo", "confidence": 0.9},
                {"field_id": "C.segregation", "status": "not_found", "value": "", "confidence": 0.0},
                {"field_id": "C.functional_assay", "status": "not_found", "value": "", "confidence": 0.0},
                {"field_id": "C.recurrence", "status": "not_found", "value": "", "confidence": 0.0},
                {"field_id": "C.contradictory_evidence", "status": "not_found", "value": "", "confidence": 0.0},
            ]
        }
    )

    assert len(response.evidence_items) == 17
    found_items = [item for item in response.evidence_items if item.status == "found"]
    assert len(found_items) == 13

    # Verify BaselineEvidenceItem conversion
    from benchmark.analysis.baselines.runner import BaselineEvidenceItem

    for llm_item in response.evidence_items:
        evidence = BaselineEvidenceItem(
            field_id=llm_item.field_id,
            status=llm_item.status,
            value=llm_item.value,
            confidence=llm_item.confidence,
        )
        extracted = evidence.to_extracted_item()
        assert "field_id" in extracted
        assert "status" in extracted
        assert "value" in extracted
        assert "confidence" in extracted


# ---------------------------------------------------------------------------
# Baseline mode registration test
# ---------------------------------------------------------------------------


def test_expanded_mode_is_registered_in_baseline_modes() -> None:
    """'expanded' must be a valid BaselineMode literal."""
    from benchmark.analysis.baselines.llm_common import BaselineMode

    # BaselineMode is a Literal type; verify 'expanded' is accepted
    assert "expanded" in BaselineMode.__args__  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Report output tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expanded_baseline_report_has_correct_baseline_id(tmp_path: Path) -> None:
    """Report JSON must have baseline_id=B7 and correct config metadata."""
    from benchmark.analysis.baselines.runner import BaselineConfig, BaselineEvidenceItem, run_baseline_evaluation

    ground_truth_dir = tmp_path / "ground_truth"
    reports_dir = tmp_path / "reports"
    entry_dir = ground_truth_dir / "test_000"
    entry_dir.mkdir(parents=True)
    (entry_dir / "source.md").write_text("MECP2 causes Rett syndrome.", encoding="utf-8")
    (entry_dir / "expected.json").write_text(
        json.dumps({
            "entry_id": "test_000",
            "gene_symbol": "MECP2",
            "disease_label": "Rett syndrome",
            "expected_evidence": [
                {"field_id": "A.gene_symbol", "value": "MECP2"},
            ],
        }),
        encoding="utf-8",
    )
    (ground_truth_dir / "selection.json").write_text(
        json.dumps([{"entry_id": "test_000", "gene_symbol": "MECP2", "disease_label": "Rett syndrome"}]),
        encoding="utf-8",
    )

    from benchmark.analysis.baselines.canonical_models import CANONICAL_GPT5_EXPANDED

    async def extractor(entry, source_text: str) -> list[BaselineEvidenceItem]:  # noqa: ANN001, ARG001
        return [BaselineEvidenceItem(field_id="A.gene_symbol", status="found", value="MECP2", confidence=0.9)]

    report = await run_baseline_evaluation(
        BaselineConfig(
            baseline_id="B7",
            baseline_name="GPT-5 expanded single-prompt evidence extraction",
            ground_truth_dir=ground_truth_dir,
            reports_dir=reports_dir,
            metadata=CANONICAL_GPT5_EXPANDED.as_metadata(),
        ),
        extractor,
    )

    assert report.baseline_id == "B7"
    assert report.report_path is not None
    saved = json.loads(report.report_path.read_text(encoding="utf-8"))
    assert saved["baseline_id"] == "B7"
    assert saved["config"]["model_baseline_id"] == "B7_GPT5_EXPANDED_PROMPT"
    assert saved["config"]["model"] == "gpt-5-2025-08-07"
