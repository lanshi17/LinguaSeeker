"""Tests for core identity retry in CatalogExtractionStage."""
from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceStatus,
    ExtractionTarget,
    PageSpan,
    SourceLocation,
    SourcePrecision,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers import (
    EvidenceModelTier,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.catalog_extraction import (
    CatalogExtractionStage,
)


def _target_doc(
    text: str = "MECP2 mutations cause Rett syndrome. The variant c.880C>T (p.R294X) was identified.",
    gene: str = "MECP2",
    disease: str = "Rett syndrome",
) -> TrackDocument:
    return TrackDocument(
        document_id="doc-retry-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
        blocks=[ContentBlock(type="text", page_idx=0, text=text)],
        extraction_target=ExtractionTarget(gene_symbol=gene, disease_name=disease),
    )


def _no_target_doc() -> TrackDocument:
    return TrackDocument(
        document_id="doc-notgt-1",
        track=Track.ORIGINAL,
        formatted_text="Some text about MECP2.",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=22)],
        blocks=[ContentBlock(type="text", page_idx=0, text="Some text about MECP2.")],
        extraction_target=None,
    )


def _found(field_id: str, value: str, confidence: float = 0.9) -> EvidenceItem:
    cat = field_id.split(".")[0]
    return EvidenceItem(
        field_id=field_id,
        category=cat,
        field_name=field_id.split(".", 1)[1],
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=confidence,
        source=SourceLocation(
            context_type="text", context_ref="",
            text_snippet=value,
        ),
    )


def _not_found(field_id: str) -> EvidenceItem:
    cat = field_id.split(".")[0]
    return EvidenceItem(
        field_id=field_id,
        category=cat,
        field_name=field_id.split(".", 1)[1],
        status=EvidenceStatus.NOT_FOUND,
        value=None,
        confidence=0.0,
    )


# CatalogExtractionStage runs 2 groups (high_signal, supporting) by default.
# Each group produces one invoke_structured call.  Tests must supply enough
# return values for the normal extraction calls BEFORE any retry call.

def _normal_ok() -> list[EvidenceItem]:
    """Normal extraction that returns both core identity fields."""
    return [
        _found("A.gene_symbol", "MECP2"),
        _found("B.disease_diagnosis", "Rett syndrome"),
        _not_found("A.variant_hgvs_c"),
    ]


def _normal_missing_gene() -> list[EvidenceItem]:
    """Normal extraction missing A.gene_symbol."""
    return [
        _not_found("A.gene_symbol"),
        _found("B.disease_diagnosis", "Rett syndrome"),
    ]


def _normal_missing_both() -> list[EvidenceItem]:
    """Normal extraction missing both core fields."""
    return [
        _not_found("A.gene_symbol"),
        _not_found("B.disease_diagnosis"),
    ]


# ── Test 1: No retry when both core fields are FOUND ─────────────────

def test_no_retry_when_core_fields_present():
    """Retry must not fire when A.gene_symbol AND B.disease_diagnosis are FOUND."""
    provider = MagicMock()
    # 2 groups × 1 chunk = 2 normal calls, both return OK
    provider.invoke_structured.return_value = _normal_ok()
    stage = CatalogExtractionStage(provider)

    stage.run(_target_doc(), DocumentEvidenceMap(relevant=True))

    # Exactly 2 calls (one per group) — no retry
    assert provider.invoke_structured.call_count == 2


# ── Test 2: Retry fires when A.gene_symbol missing ──────────────────

def test_retry_when_gene_symbol_missing():
    """Retry must fire when A.gene_symbol is not FOUND."""
    provider = MagicMock()
    # First 2 calls: normal extraction (2 groups), both missing gene symbol
    # Third call: retry
    provider.invoke_structured.side_effect = [
        _normal_missing_gene(),   # group 1
        _normal_missing_gene(),   # group 2
        [_found("A.gene_symbol", "MECP2", confidence=0.85)],  # retry
    ]
    stage = CatalogExtractionStage(provider)

    result = stage.run(_target_doc(), DocumentEvidenceMap(relevant=True))

    assert provider.invoke_structured.call_count == 3
    # Retry stage name contains "core_identity_retry"
    retry_stage = provider.invoke_structured.call_args_list[2].kwargs.get("stage", "")
    assert "core_identity_retry" in retry_stage
    # Result should include the rescued gene symbol
    gene_items = [i for i in result if i.field_id == "A.gene_symbol" and i.status == EvidenceStatus.FOUND]
    assert len(gene_items) >= 1
    assert any(i.value == "MECP2" for i in gene_items)


# ── Test 3: Retry fires when B.disease_diagnosis missing ────────────

def test_retry_when_disease_diagnosis_missing():
    """Retry must fire when B.disease_diagnosis is not FOUND."""
    provider = MagicMock()
    normal_no_disease = [
        _found("A.gene_symbol", "MECP2"),
        _not_found("B.disease_diagnosis"),
    ]
    provider.invoke_structured.side_effect = [
        normal_no_disease,   # group 1
        normal_no_disease,   # group 2
        [_found("B.disease_diagnosis", "Rett syndrome", confidence=0.8)],  # retry
    ]
    stage = CatalogExtractionStage(provider)

    result = stage.run(_target_doc(), DocumentEvidenceMap(relevant=True))

    assert provider.invoke_structured.call_count == 3
    disease_items = [i for i in result if i.field_id == "B.disease_diagnosis" and i.status == EvidenceStatus.FOUND]
    assert len(disease_items) >= 1


# ── Test 4: Retry output merges into final result ───────────────────

def test_retry_output_merged_into_result():
    """Items from retry must appear in the final merged output."""
    provider = MagicMock()
    provider.invoke_structured.side_effect = [
        _normal_missing_both(),   # group 1
        _normal_missing_both(),   # group 2
        [   # retry
            _found("A.gene_symbol", "MECP2", confidence=0.85),
            _found("B.disease_diagnosis", "Rett syndrome", confidence=0.8),
            _found("A.variant_hgvs_c", "c.880C>T", confidence=0.75),
        ],
    ]
    stage = CatalogExtractionStage(provider)

    result = stage.run(_target_doc(), DocumentEvidenceMap(relevant=True))

    found_ids = {i.field_id for i in result if i.status == EvidenceStatus.FOUND}
    assert "A.gene_symbol" in found_ids
    assert "B.disease_diagnosis" in found_ids
    assert "A.variant_hgvs_c" in found_ids


# ── Test 5: Retry does not overwrite higher-confidence FOUND ────────

def test_retry_does_not_overwrite_higher_confidence():
    """Retry must not replace an existing FOUND item with lower confidence."""
    provider = MagicMock()
    # group 1: gene found at 0.95, disease missing
    # group 2: same
    # retry: gene at 0.5 (lower), disease at 0.8
    normal_gene_high = [
        _found("A.gene_symbol", "MECP2", confidence=0.95),
        _not_found("B.disease_diagnosis"),
    ]
    provider.invoke_structured.side_effect = [
        normal_gene_high,
        normal_gene_high,
        [
            _found("A.gene_symbol", "MECP2", confidence=0.5),
            _found("B.disease_diagnosis", "Rett syndrome", confidence=0.8),
        ],
    ]
    stage = CatalogExtractionStage(provider)

    result = stage.run(_target_doc(), DocumentEvidenceMap(relevant=True))

    gene_items = [i for i in result if i.field_id == "A.gene_symbol" and i.status == EvidenceStatus.FOUND]
    # The 0.95 item from normal extraction should be kept, not overwritten by 0.5
    assert any(i.confidence == 0.95 for i in gene_items)


# ── Test 6: No retry when extraction_target is absent ───────────────

def test_no_retry_without_extraction_target():
    """Retry must not fire when document.extraction_target is None."""
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        _not_found("A.gene_symbol"),
        _not_found("B.disease_diagnosis"),
    ]
    stage = CatalogExtractionStage(provider)

    stage.run(_no_target_doc(), DocumentEvidenceMap(relevant=True))

    # Only 2 calls (one per group) — no retry
    assert provider.invoke_structured.call_count == 2


# ── Test 7: Async path has equivalent retry behavior ────────────────

@pytest.mark.asyncio
async def test_async_retry_when_gene_symbol_missing():
    """Async path must also trigger retry when A.gene_symbol is missing."""
    from unittest.mock import AsyncMock

    provider = MagicMock()
    call_count = 0

    async def _async_invoke(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return _normal_missing_gene()
        return [_found("A.gene_symbol", "MECP2", confidence=0.85)]

    provider.ainvoke_structured = AsyncMock(side_effect=_async_invoke)
    provider.invoke_structured.return_value = _normal_missing_gene()

    stage = CatalogExtractionStage(provider)
    result = await stage.run_async(_target_doc(), DocumentEvidenceMap(relevant=True))

    gene_items = [i for i in result if i.field_id == "A.gene_symbol" and i.status == EvidenceStatus.FOUND]
    assert len(gene_items) >= 1
    assert any(i.value == "MECP2" for i in gene_items)


# ── Test 8: Retry prompt contains only four core identity fields ────

def test_retry_prompt_contains_only_core_fields():
    """The retry prompt must list only A.gene_symbol, B.disease_diagnosis,
    A.variant_hgvs_c, A.variant_hgvs_p — not the full catalog."""
    provider = MagicMock()
    provider.invoke_structured.side_effect = [
        _normal_missing_both(),
        _normal_missing_both(),
        [_found("A.gene_symbol", "MECP2")],  # retry
    ]
    stage = CatalogExtractionStage(provider)

    stage.run(_target_doc(), DocumentEvidenceMap(relevant=True))

    # The third call is the retry
    retry_prompt = provider.invoke_structured.call_args_list[2].kwargs["prompt"]

    # Must contain the 4 core fields
    assert "A.gene_symbol" in retry_prompt
    assert "B.disease_diagnosis" in retry_prompt
    assert "A.variant_hgvs_c" in retry_prompt
    assert "A.variant_hgvs_p" in retry_prompt

    # Must NOT contain fields from the full catalog that are not core identity
    assert "D.allele_frequency" not in retry_prompt
    assert "F.assay_type" not in retry_prompt
    assert "G.case_count" not in retry_prompt
    assert "H.contradictory_evidence" not in retry_prompt

    # Must include target info
    assert "MECP2" in retry_prompt
    assert "Rett syndrome" in retry_prompt
