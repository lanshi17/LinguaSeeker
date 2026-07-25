"""Tests for channel-filtered catalog extraction.

Verifies that ``CatalogExtractionStage`` intersects the existing target/source
field eligibility with the document-channel field matrix, so the LLM prompt
only contains fields extractable from the detected channel(s).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.evidence_extraction.domain.catalog import (
    EVIDENCE_FIELD_SPECS,
)
from src.core.evidence_extraction.domain.channel_contracts import (
    DocumentChannelClassification,
    DocumentEvidenceChannel,
)
from src.core.evidence_extraction.contracts import (
    ContentBlock,
    DocumentEvidenceMap,
    ExtractionTarget,
    PageSpan,
    Track,
    TrackDocument,
)
from src.core.evidence_extraction.stages.catalog_extraction import (
    CatalogExtractionStage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc(text: str = "GLA c.1000G>A Fabry disease") -> TrackDocument:
    return TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
        blocks=[ContentBlock(type="text", page_idx=0, text=text)],
    )


def _cls(channels: list[DocumentEvidenceChannel]) -> DocumentChannelClassification:
    return DocumentChannelClassification(
        selected_channels=list(channels),
        confidence=0.9,
        rationale="test classification",
        supporting_block_ids=[],
    )


def _catalog_field_ids_in_prompt(prompt: str) -> set[str]:
    """Extract field IDs from the catalog section of a prompt."""
    parts = prompt.split("EVIDENCE CATALOG", maxsplit=1)
    if len(parts) < 2:
        return set()  # retry prompt has no catalog section
    catalog_text = parts[1].split("RULES:", maxsplit=1)[0]
    all_ids = {spec.field_id for spec in EVIDENCE_FIELD_SPECS}
    return {fid for fid in all_ids if fid in catalog_text}


def _functional_field_ids() -> set[str]:
    return {spec.field_id for spec in EVIDENCE_FIELD_SPECS if spec.category_id == "F"}


def _population_field_ids() -> set[str]:
    return {spec.field_id for spec in EVIDENCE_FIELD_SPECS if spec.category_id == "D"}


# ---------------------------------------------------------------------------
# No classification (backward compatible) — existing behavior preserved
# ---------------------------------------------------------------------------


def test_no_classification_preserves_existing_behavior():
    """channel_classification=None (default) → no channel filter, existing behavior."""
    provider = MagicMock()
    provider.invoke_structured.return_value = []
    stage = CatalogExtractionStage(provider)
    stage.run(_doc(), DocumentEvidenceMap(relevant=True, gene_terms=["GLA"]))
    # Should call both high_signal and supporting groups (no channel restriction)
    stages = [c.kwargs["stage"] for c in provider.invoke_structured.call_args_list]
    assert "catalog_extraction/high_signal" in stages
    assert "catalog_extraction/supporting" in stages


# ---------------------------------------------------------------------------
# Case report — excludes functional-only F fields
# ---------------------------------------------------------------------------


def test_case_report_excludes_F_fields_from_prompt():
    provider = MagicMock()
    provider.invoke_structured.return_value = []
    stage = CatalogExtractionStage(provider)
    target = ExtractionTarget(
        gene_symbol="GLA",
        disease_name="Fabry disease",
        variant_hgvs_p="p.R227X",
    )
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="functional assay variant patient cells",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=50)],
        blocks=[ContentBlock(type="text", page_idx=0, text="functional assay variant patient cells")],
        extraction_target=target,
    )
    stage.run(
        document,
        DocumentEvidenceMap(relevant=True, gene_terms=["GLA"]),
        channel_classification=_cls([DocumentEvidenceChannel.CASE_REPORT]),
    )
    all_prompt_fields: set[str] = set()
    for call in provider.invoke_structured.call_args_list:
        all_prompt_fields |= _catalog_field_ids_in_prompt(call.kwargs["prompt"])
    func_ids = _functional_field_ids()
    assert all_prompt_fields.isdisjoint(func_ids), (
        f"Case report must exclude F fields, but found: {all_prompt_fields & func_ids}"
    )


# ---------------------------------------------------------------------------
# Functional study — includes F fields, excludes case-only B/C
# ---------------------------------------------------------------------------


def test_functional_study_includes_F_fields():
    provider = MagicMock()
    provider.invoke_structured.return_value = []
    stage = CatalogExtractionStage(provider)
    target = ExtractionTarget(
        gene_symbol="GLA",
        disease_name="Fabry disease",
        variant_hgvs_p="p.R227X",
    )
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="functional assay variant patient cells",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=50)],
        blocks=[ContentBlock(type="text", page_idx=0, text="functional assay variant patient cells")],
        extraction_target=target,
    )
    stage.run(
        document,
        DocumentEvidenceMap(relevant=True, gene_terms=["GLA"]),
        channel_classification=_cls([DocumentEvidenceChannel.FUNCTIONAL_STUDY]),
    )
    all_prompt_fields: set[str] = set()
    for call in provider.invoke_structured.call_args_list:
        all_prompt_fields |= _catalog_field_ids_in_prompt(call.kwargs["prompt"])
    assert "F.assay_id" in all_prompt_fields
    # B.case_count is category B — not in functional_study
    assert "B.case_count" not in all_prompt_fields
    # C.lod_score is category C — not in functional_study
    assert "C.lod_score" not in all_prompt_fields


# ---------------------------------------------------------------------------
# Cohort study — includes D/G, excludes F
# ---------------------------------------------------------------------------


def test_cohort_study_includes_DG_excludes_F():
    provider = MagicMock()
    provider.invoke_structured.return_value = []
    stage = CatalogExtractionStage(provider)
    # No target → base = all 143; channel filter isolates cohort (A,D,G,H,J).
    # G fields have no target-cue path, so use no-target to test pure channel filtering.
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="allele frequency population gnomad cohort study",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=50)],
        blocks=[ContentBlock(type="text", page_idx=0, text="allele frequency population gnomad cohort study")],
    )
    stage.run(
        document,
        DocumentEvidenceMap(relevant=True, gene_terms=["GLA"]),
        channel_classification=_cls([DocumentEvidenceChannel.COHORT_STUDY]),
    )
    all_prompt_fields: set[str] = set()
    for call in provider.invoke_structured.call_args_list:
        all_prompt_fields |= _catalog_field_ids_in_prompt(call.kwargs["prompt"])
    assert "D.allele_frequency" in all_prompt_fields
    assert "G.odds_ratio" in all_prompt_fields
    func_ids = _functional_field_ids()
    assert all_prompt_fields.isdisjoint(func_ids), (
        f"Cohort study must exclude F fields, but found: {all_prompt_fields & func_ids}"
    )


# ---------------------------------------------------------------------------
# Mixed case_report + functional_study — union before intersection
# ---------------------------------------------------------------------------


def test_mixed_case_and_functional_includes_both_F_and_BC():
    provider = MagicMock()
    provider.invoke_structured.return_value = []
    stage = CatalogExtractionStage(provider)
    # No target → base = all 143; channel filter = case∪functional (120).
    # C fields have no target-cue path, so use no-target to test pure channel union.
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="functional assay case report patient variant",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=50)],
        blocks=[ContentBlock(type="text", page_idx=0, text="functional assay case report patient variant")],
    )
    stage.run(
        document,
        DocumentEvidenceMap(relevant=True, gene_terms=["GLA"]),
        channel_classification=_cls(
            [
                DocumentEvidenceChannel.CASE_REPORT,
                DocumentEvidenceChannel.FUNCTIONAL_STUDY,
            ]
        ),
    )
    all_prompt_fields: set[str] = set()
    for call in provider.invoke_structured.call_args_list:
        all_prompt_fields |= _catalog_field_ids_in_prompt(call.kwargs["prompt"])
    # F fields allowed via functional_study
    assert "F.assay_id" in all_prompt_fields
    # B/C fields allowed via case_report
    assert "B.disease_diagnosis" in all_prompt_fields
    assert "C.lod_score" in all_prompt_fields
    # D fields NOT in union (cohort not selected)
    pop_ids = _population_field_ids()
    assert all_prompt_fields.isdisjoint(pop_ids), (
        f"Mixed case+functional must exclude D fields, but found: {all_prompt_fields & pop_ids}"
    )


# ---------------------------------------------------------------------------
# Unknown — permissive, preserves existing behavior
# ---------------------------------------------------------------------------


def test_unknown_classification_is_permissive():
    provider = MagicMock()
    provider.invoke_structured.return_value = []
    stage = CatalogExtractionStage(provider)
    stage.run(
        _doc(),
        DocumentEvidenceMap(relevant=True, gene_terms=["GLA"]),
        channel_classification=_cls([DocumentEvidenceChannel.UNKNOWN]),
    )
    stages = [c.kwargs["stage"] for c in provider.invoke_structured.call_args_list]
    # Unknown is permissive → both groups called (same as no classification)
    assert "catalog_extraction/high_signal" in stages
    assert "catalog_extraction/supporting" in stages


# ---------------------------------------------------------------------------
# _eligible_catalog_groups direct test
# ---------------------------------------------------------------------------


def test_eligible_catalog_groups_case_report_filters_functional():
    stage = CatalogExtractionStage(MagicMock())
    document = _doc()
    chunks = [MagicMock(index=1, total=1, text="variant patient")]
    groups = stage._eligible_catalog_groups(
        document,
        DocumentEvidenceMap(relevant=True, gene_terms=["GLA"]),
        chunks,
        channel_classification=_cls([DocumentEvidenceChannel.CASE_REPORT]),
    )
    all_field_ids: set[str] = set()
    for specs in groups.values():
        all_field_ids |= {spec.field_id for spec in specs}
    func_ids = _functional_field_ids()
    assert all_field_ids.isdisjoint(func_ids)
    assert "A.gene_symbol" in all_field_ids
    assert "B.disease_diagnosis" in all_field_ids


def test_eligible_catalog_groups_none_classification_returns_all_groups():
    stage = CatalogExtractionStage(MagicMock())
    document = _doc()
    chunks = [MagicMock(index=1, total=1, text="variant patient")]
    groups = stage._eligible_catalog_groups(
        document,
        DocumentEvidenceMap(relevant=True, gene_terms=["GLA"]),
        chunks,
        channel_classification=None,
    )
    # No channel filter → both groups present
    assert set(groups.keys()) == {"high_signal", "supporting"}


# ---------------------------------------------------------------------------
# Channel strategy guidance in prompts — sync and async
# ---------------------------------------------------------------------------


def test_run_passes_channel_strategy_into_prompt():
    """run() must include channel strategy guidance in the generated prompt."""
    provider = MagicMock()
    provider.invoke_structured.return_value = []
    stage = CatalogExtractionStage(provider)
    stage.run(
        _doc(),
        DocumentEvidenceMap(relevant=True, gene_terms=["GLA"]),
        channel_classification=_cls([DocumentEvidenceChannel.CASE_REPORT]),
    )
    prompts = [c.kwargs["prompt"] for c in provider.invoke_structured.call_args_list]
    assert prompts, "Expected at least one provider call"
    assert all("CASE-REPORT STRATEGY" in p for p in prompts)


@pytest.mark.asyncio
async def test_run_async_passes_channel_classification_into_prompt():
    """run_async() must pass channel classification into prompt generation."""
    provider = MagicMock()
    provider.ainvoke_structured = AsyncMock(return_value=[])
    stage = CatalogExtractionStage(provider)

    with patch(
        "src.core.evidence_extraction.stages.catalog_extraction.build_block_prompt_chunks",
        return_value=[MagicMock(index=1, total=1, text="GLA variant", total_tokens=100)],
    ):
        await stage.run_async(
            _doc(),
            DocumentEvidenceMap(relevant=True, gene_terms=["GLA"]),
            channel_classification=_cls([DocumentEvidenceChannel.FUNCTIONAL_STUDY]),
        )

    prompts = [c.kwargs["prompt"] for c in provider.ainvoke_structured.await_args_list]
    assert prompts, "Expected at least one async provider call"
    assert all("FUNCTIONAL-STUDY STRATEGY" in p for p in prompts)


def test_run_none_classification_uses_generic_strategy():
    """run() with no classification must use generic strategy, not crash."""
    provider = MagicMock()
    provider.invoke_structured.return_value = []
    stage = CatalogExtractionStage(provider)
    stage.run(
        _doc(),
        DocumentEvidenceMap(relevant=True, gene_terms=["GLA"]),
        channel_classification=None,
    )
    prompts = [c.kwargs["prompt"] for c in provider.invoke_structured.call_args_list]
    assert prompts
    assert all("DOCUMENT-CHANNEL STRATEGY" in p for p in prompts)
    assert all("standard catalog rules" in p for p in prompts)
