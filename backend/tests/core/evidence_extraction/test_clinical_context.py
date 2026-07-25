"""Tests for ClinicalContextStage — focused supplement pass for phenotype/clinical fields."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.core.evidence_extraction.contracts import (
    ContentBlock,
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    SourceLocation,
    Track,
    TrackDocument,
)
from src.core.evidence_extraction.prompts import (
    get_clinical_context_prompt,
)
from src.core.evidence_extraction.providers import (
    EvidenceModelTier,
)
from src.core.evidence_extraction.stages.clinical_context import (
    ClinicalContextStage,
    CLINICAL_CONTEXT_FIELDS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _doc(text: str | None = None) -> TrackDocument:
    body = text or (
        "A 4-year-old female presented with progressive neurological regression, "
        "loss of acquired hand skills, stereotypic hand movements, and seizures. "
        "The variant c.1000G>A in GLA was identified as de novo in the proband."
    )
    return TrackDocument(
        document_id="doc-cc-1",
        track=Track.ORIGINAL,
        formatted_text=body,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(body))],
        blocks=[
            ContentBlock(
                type="text",
                page_idx=0,
                text=body,
            ),
        ],
    )


def _found_item(field_id: str, value: str, confidence: float = 0.9) -> EvidenceItem:
    category = field_id.split(".")[0]
    return EvidenceItem(
        field_id=field_id,
        category=category,
        field_name=field_id.split(".", 1)[1],
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=confidence,
        source=SourceLocation(
            context_type="text",
            context_ref="",
            text_snippet=value,
        ),
    )


def _not_found_item(field_id: str) -> EvidenceItem:
    category = field_id.split(".")[0]
    return EvidenceItem(
        field_id=field_id,
        category=category,
        field_name=field_id.split(".", 1)[1],
        status=EvidenceStatus.NOT_FOUND,
        value=None,
        confidence=0.0,
    )


# ---------------------------------------------------------------------------
# Test: prompt content
# ---------------------------------------------------------------------------


def test_clinical_context_prompt_contains_phenotype_extraction_guidance():
    prompt = get_clinical_context_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="sample text",
        current_items_summary="",
    )
    # Must contain explicit phenotype guidance
    assert "clinical phenotype" in prompt.lower() or "clinical_phenotypes" in prompt.lower()
    assert "symptom" in prompt.lower() or "presentation" in prompt.lower()
    # Must distinguish phenotype from disease diagnosis
    assert "diagnosis" in prompt.lower()
    # Must mention semicolon or list format for multiple phenotypes
    assert "semicolon" in prompt.lower() or "list" in prompt.lower()


def test_clinical_context_prompt_contains_all_target_fields():
    prompt = get_clinical_context_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="sample text",
        current_items_summary="",
    )
    for field_id in CLINICAL_CONTEXT_FIELDS:
        assert field_id in prompt, f"Missing field {field_id} in clinical context prompt"


def test_clinical_context_prompt_contains_age_sex_guidance():
    prompt = get_clinical_context_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="sample text",
        current_items_summary="",
    )
    # Must have guidance for age and sex
    assert "age_of_onset" in prompt or "age of onset" in prompt.lower()
    assert "sex" in prompt.lower()


def test_clinical_context_prompt_contains_inheritance_guidance():
    prompt = get_clinical_context_prompt(
        document_id="doc-1",
        track=Track.ORIGINAL,
        text="sample text",
        current_items_summary="",
    )
    assert "inheritance" in prompt.lower()
    assert "de_novo" in prompt or "de novo" in prompt.lower()


# ---------------------------------------------------------------------------
# Test: field count ≤ 10
# ---------------------------------------------------------------------------


def test_clinical_context_field_count_is_at_most_10():
    assert len(CLINICAL_CONTEXT_FIELDS) <= 10


def test_clinical_context_fields_include_required_targets():
    required = {
        "B.clinical_phenotypes",
        "B.sex",
        "B.age_of_onset",
        "B.mode_of_inheritance_reported",
        "C.inheritance_source",
        "C.de_novo_status",
    }
    assert required.issubset(set(CLINICAL_CONTEXT_FIELDS))


# ---------------------------------------------------------------------------
# Test: LLM call strategy
# ---------------------------------------------------------------------------


def test_clinical_context_stage_calls_strong_tier():
    provider = MagicMock()
    provider.invoke_structured.return_value = []

    stage = ClinicalContextStage(provider)
    stage.run(_doc(), [], DocumentEvidenceMap(relevant=True))

    call_kwargs = provider.invoke_structured.call_args
    assert call_kwargs.kwargs["tier"] == EvidenceModelTier.STRONG


def test_clinical_context_stage_returns_evidence_items():
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        EvidenceItem(
            field_id="B.clinical_phenotypes",
            category="B",
            field_name="Key clinical phenotypes",
            status=EvidenceStatus.FOUND,
            value="seizures; developmental regression",
            confidence=0.85,
            source=SourceLocation(
                context_type="text",
                context_ref="",
                text_snippet="progressive neurological regression, loss of acquired hand skills",
            ),
        ),
    ]

    stage = ClinicalContextStage(provider)
    result = stage.run(_doc(), [], DocumentEvidenceMap(relevant=True))

    assert len(result) == 1
    assert isinstance(result[0], EvidenceItem)
    assert result[0].field_id == "B.clinical_phenotypes"
    assert result[0].status == EvidenceStatus.FOUND


# ---------------------------------------------------------------------------
# Test: merge strategy — does not overwrite existing FOUND with lower confidence
# ---------------------------------------------------------------------------


def test_clinical_context_does_not_overwrite_higher_confidence_existing():
    existing = [
        _found_item("B.clinical_phenotypes", "seizures; ataxia", confidence=0.95),
    ]
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        EvidenceItem(
            field_id="B.clinical_phenotypes",
            category="B",
            field_name="Key clinical phenotypes",
            status=EvidenceStatus.FOUND,
            value="seizures only",
            confidence=0.7,
            source=SourceLocation(
                context_type="text",
                context_ref="",
                text_snippet="seizures",
            ),
        ),
    ]

    stage = ClinicalContextStage(provider)
    result = stage.run(_doc(), existing, DocumentEvidenceMap(relevant=True))

    # Should NOT include the clinical_context item since existing has higher confidence
    phenotypes = [i for i in result if i.field_id == "B.clinical_phenotypes"]
    assert len(phenotypes) == 0


# ---------------------------------------------------------------------------
# Test: merge strategy — fills in NOT_FOUND fields
# ---------------------------------------------------------------------------


def test_clinical_context_fills_not_found_fields():
    existing = [
        _not_found_item("B.clinical_phenotypes"),
        _not_found_item("B.sex"),
    ]
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        EvidenceItem(
            field_id="B.clinical_phenotypes",
            category="B",
            field_name="Key clinical phenotypes",
            status=EvidenceStatus.FOUND,
            value="seizures; regression",
            confidence=0.85,
            source=SourceLocation(
                context_type="text",
                context_ref="",
                text_snippet="seizures",
            ),
        ),
        EvidenceItem(
            field_id="B.sex",
            category="B",
            field_name="Sex",
            status=EvidenceStatus.FOUND,
            value="female",
            confidence=0.9,
            source=SourceLocation(
                context_type="text",
                context_ref="",
                text_snippet="female",
            ),
        ),
    ]

    stage = ClinicalContextStage(provider)
    result = stage.run(_doc(), existing, DocumentEvidenceMap(relevant=True))

    field_ids = {i.field_id for i in result}
    assert "B.clinical_phenotypes" in field_ids
    assert "B.sex" in field_ids


# ---------------------------------------------------------------------------
# Test: merge strategy — replaces NOT_FOUND even with existing found items of lower confidence
# ---------------------------------------------------------------------------


def test_clinical_context_replaces_lower_confidence_found():
    text = "The patient had seizures and loss of acquired hand skills."
    existing = [
        _found_item("B.clinical_phenotypes", "seizures", confidence=0.5),
    ]
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        EvidenceItem(
            field_id="B.clinical_phenotypes",
            category="B",
            field_name="Key clinical phenotypes",
            status=EvidenceStatus.FOUND,
            value="seizures; loss of acquired hand skills",
            confidence=0.85,
            source=SourceLocation(
                context_type="text",
                context_ref="",
                text_snippet="seizures and loss of acquired hand skills",
            ),
        ),
    ]

    stage = ClinicalContextStage(provider)
    result = stage.run(_doc(text), existing, DocumentEvidenceMap(relevant=True))

    pheno = [i for i in result if i.field_id == "B.clinical_phenotypes"]
    assert len(pheno) == 1
    assert "loss of acquired hand skills" in pheno[0].value


# ---------------------------------------------------------------------------
# Test: failure resilience — LLM failure does not crash pipeline
# ---------------------------------------------------------------------------


def test_clinical_context_stage_handles_llm_failure_gracefully():
    provider = MagicMock()
    provider.invoke_structured.side_effect = RuntimeError("LLM timeout")

    stage = ClinicalContextStage(provider)
    # Should not raise
    result = stage.run(_doc(), [], DocumentEvidenceMap(relevant=True))
    assert result == []


def test_clinical_context_stage_handles_malformed_response():
    provider = MagicMock()
    provider.invoke_structured.return_value = "not a list"

    stage = ClinicalContextStage(provider)
    result = stage.run(_doc(), [], DocumentEvidenceMap(relevant=True))
    assert result == []


# ---------------------------------------------------------------------------
# Test: dedup — identical value + field_id not added twice
# ---------------------------------------------------------------------------


def test_clinical_context_no_duplicate_value():
    existing = [
        _found_item("B.sex", "female", confidence=0.9),
    ]
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        EvidenceItem(
            field_id="B.sex",
            category="B",
            field_name="Sex",
            status=EvidenceStatus.FOUND,
            value="female",
            confidence=0.85,
            source=SourceLocation(
                context_type="text",
                context_ref="",
                text_snippet="female",
            ),
        ),
    ]

    stage = ClinicalContextStage(provider)
    result = stage.run(_doc(), existing, DocumentEvidenceMap(relevant=True))

    sex_items = [i for i in result if i.field_id == "B.sex"]
    assert len(sex_items) == 0  # duplicate, should not be added


# ---------------------------------------------------------------------------
# Test: prompt includes current_items_summary
# ---------------------------------------------------------------------------


def test_clinical_context_prompt_includes_current_items_summary():
    provider = MagicMock()
    provider.invoke_structured.return_value = []

    existing = [_found_item("B.disease_diagnosis", "Fabry disease")]
    stage = ClinicalContextStage(provider)
    stage.run(_doc(), existing, DocumentEvidenceMap(relevant=True))

    call_kwargs = provider.invoke_structured.call_args
    prompt = call_kwargs.kwargs["prompt"]
    assert "Fabry disease" in prompt


# ---------------------------------------------------------------------------
# Test: async variant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clinical_context_stage_async_calls_strong_tier():
    from unittest.mock import AsyncMock

    provider = MagicMock()
    provider.ainvoke_structured = AsyncMock(return_value=[])

    stage = ClinicalContextStage(provider)
    result = await stage.run_async(_doc(), [], DocumentEvidenceMap(relevant=True))

    assert result == []
    call_kwargs = provider.ainvoke_structured.call_args
    assert call_kwargs.kwargs["tier"] == EvidenceModelTier.STRONG


@pytest.mark.asyncio
async def test_clinical_context_stage_async_handles_failure():
    from unittest.mock import AsyncMock

    provider = MagicMock()
    provider.ainvoke_structured = AsyncMock(side_effect=RuntimeError("timeout"))

    stage = ClinicalContextStage(provider)
    result = await stage.run_async(_doc(), [], DocumentEvidenceMap(relevant=True))
    assert result == []
