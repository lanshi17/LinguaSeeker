"""Tests for the B8 primary broad extraction stage."""

from __future__ import annotations

import pytest

from src.core.evidence_extraction.contracts import (
    EvidenceStatus,
    ExtractionTarget,
    PrimaryBroadEvidenceCandidate,
    PrimaryBroadExtractionResponse,
    Track,
    TrackDocument,
)
from src.core.evidence_extraction.providers import EvidenceModelTier
from src.core.evidence_extraction.stages.primary_broad_extraction import (
    PrimaryBroadExtractionStage,
    _normalize_candidates,
    _resolve_field_alias,
)


class BroadProvider:
    """Provider that captures prompts and returns one broad candidate."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.stages: list[str] = []

    def invoke_structured(self, prompt, output_schema, tier, stage, response_method="json_schema"):
        del response_method
        self.prompts.append(prompt)
        self.stages.append(stage)
        assert output_schema is PrimaryBroadExtractionResponse
        assert tier == EvidenceModelTier.STRONG
        return PrimaryBroadExtractionResponse(
            evidence_items=[
                PrimaryBroadEvidenceCandidate(
                    field_id="A.gene_symbol",
                    status=EvidenceStatus.FOUND,
                    value="BRCA1",
                    confidence=0.91,
                    source_quote="BRCA1 c.5266dupC was identified",
                )
            ]
        )

    async def ainvoke_structured(self, prompt, output_schema, tier, stage, response_method="json_schema"):
        return self.invoke_structured(prompt, output_schema, tier, stage, response_method)


def _document() -> TrackDocument:
    return TrackDocument(
        document_id="doc-b8",
        track=Track.ORIGINAL,
        formatted_text="BRCA1 c.5266dupC was identified in a family with breast cancer.",
        page_spans=[],
        extraction_target=ExtractionTarget(gene_symbol="BRCA1", disease_name="Breast cancer"),
    )


def test_primary_broad_stage_prompts_for_b8_fields_and_source_quote() -> None:
    provider = BroadProvider()
    stage = PrimaryBroadExtractionStage(provider)

    items = stage.run(_document())

    assert provider.stages == ["primary_broad_extraction"]
    prompt = provider.prompts[0]
    assert "single high-recall primary extraction pass" in prompt
    assert "source_quote" in prompt
    assert "A.gene_symbol" in prompt
    assert "F.assay_type" in prompt
    assert "J.clinvar_assertion" in prompt
    assert items[0].field_id == "A.gene_symbol"
    assert items[0].category == "A"
    assert items[0].field_name == "Gene symbol"
    assert items[0].raw_source is not None
    assert items[0].raw_source.text_snippet == "BRCA1 c.5266dupC was identified"
    assert items[0].raw_source.context_ref == "primary_broad_extraction"
    assert items[0].raw_source.block_index == -1


@pytest.mark.asyncio
async def test_primary_broad_stage_supports_async_provider() -> None:
    provider = BroadProvider()
    stage = PrimaryBroadExtractionStage(provider)

    items = await stage.run_async(_document())

    assert provider.stages == ["primary_broad_extraction"]
    assert items[0].field_id == "A.gene_symbol"


# ── Field-id alias mapping tests ────────────────────────────────────────


def test_resolve_field_alias_maps_known_aliases() -> None:
    """Known benchmark aliases should resolve to business catalog field_ids."""
    assert _resolve_field_alias("C.segregation") == "C.g_plus_p_plus_count"
    assert _resolve_field_alias("C.functional_assay") == "F.functional_result"
    assert _resolve_field_alias("C.contradictory_evidence") == "H.contradiction_type"
    assert _resolve_field_alias("C.recurrence") == "B.case_count"


def test_resolve_field_alias_passes_through_valid_ids() -> None:
    """Valid business catalog field_ids should pass through unchanged."""
    assert _resolve_field_alias("A.gene_symbol") == "A.gene_symbol"
    assert _resolve_field_alias("B.disease_diagnosis") == "B.disease_diagnosis"
    assert _resolve_field_alias("F.functional_result") == "F.functional_result"


def test_resolve_field_alias_returns_unknown_ids_unchanged() -> None:
    """Unknown field_ids are returned unchanged (KeyError raised by get_field_spec)."""
    assert _resolve_field_alias("Z.nonexistent") == "Z.nonexistent"


def test_normalize_candidates_maps_alias_to_business_field() -> None:
    """Candidates with alias field_ids should be mapped to business fields."""
    candidates = [
        PrimaryBroadEvidenceCandidate(
            field_id="C.segregation",
            status=EvidenceStatus.FOUND,
            value="3/4 affected family members",
            confidence=0.85,
            source_quote="3/4 affected family members carried the variant",
        ),
        PrimaryBroadEvidenceCandidate(
            field_id="C.functional_assay",
            status=EvidenceStatus.FOUND,
            value="reduced enzyme activity",
            confidence=0.8,
            source_quote="enzyme activity was reduced by 80%",
        ),
        PrimaryBroadEvidenceCandidate(
            field_id="C.contradictory_evidence",
            status=EvidenceStatus.FOUND,
            value="none reported",
            confidence=0.7,
            source_quote="no contradictory evidence was identified",
        ),
    ]
    items = _normalize_candidates(candidates)
    field_ids = [item.field_id for item in items]
    assert "C.g_plus_p_plus_count" in field_ids
    assert "F.functional_result" in field_ids
    assert "H.contradiction_type" in field_ids
    assert "C.segregation" not in field_ids
    assert "C.functional_assay" not in field_ids
    assert "C.contradictory_evidence" not in field_ids


def test_normalize_candidates_preserves_source_quote_for_mapped_items() -> None:
    """Mapped items should keep the original source_quote as raw_source.text_snippet."""
    candidates = [
        PrimaryBroadEvidenceCandidate(
            field_id="C.segregation",
            status=EvidenceStatus.FOUND,
            value="co-segregated",
            confidence=0.8,
            source_quote="the variant co-segregated with disease in 5 family members",
        ),
    ]
    items = _normalize_candidates(candidates)
    assert len(items) == 1
    assert items[0].field_id == "C.g_plus_p_plus_count"
    assert items[0].raw_source is not None
    assert items[0].raw_source.text_snippet == "the variant co-segregated with disease in 5 family members"


def test_normalize_candidates_projects_consequence_class_to_variant_type() -> None:
    """ClinVar-style consequence labels should remain scoreable as A.variant_type."""
    candidates = [
        PrimaryBroadEvidenceCandidate(
            field_id="A.variant_hgvs_p",
            status=EvidenceStatus.FOUND,
            value="p.R69C",
            confidence=0.9,
            source_quote="MTM1 p.R69C mouse model",
        ),
        PrimaryBroadEvidenceCandidate(
            field_id="A.variant_type",
            status=EvidenceStatus.FOUND,
            value="SNV/substitution",
            confidence=0.85,
            source_quote="point mutation (c.205C>T)",
        ),
        PrimaryBroadEvidenceCandidate(
            field_id="A.variant_consequence_class",
            status=EvidenceStatus.FOUND,
            value="missense",
            confidence=0.6,
            source_quote="p.R69C",
        ),
    ]

    items = _normalize_candidates(candidates)

    variant_type_items = [item for item in items if item.field_id == "A.variant_type"]
    assert len(variant_type_items) == 1
    assert variant_type_items[0].value == "missense"
    assert variant_type_items[0].raw_source is not None
    assert variant_type_items[0].raw_source.text_snippet == "p.R69C"


# ── Round 2: prompt coverage tests ───────────────────────────────────────


def test_prompt_contains_gene_disease_relationship_guidance() -> None:
    """B8 prompt must include A.gene_disease_relationship with inference rules."""
    provider = BroadProvider()
    stage = PrimaryBroadExtractionStage(provider)
    stage.run(_document())
    prompt = provider.prompts[0]
    assert "A.gene_disease_relationship" in prompt
    assert "causative" in prompt
    assert "disputed" in prompt
    assert "refuted" in prompt
    assert "uncertain" in prompt


def test_prompt_contains_variant_type_inference_guidance() -> None:
    """B8 prompt must define variant_type using benchmark consequence-class semantics."""
    provider = BroadProvider()
    stage = PrimaryBroadExtractionStage(provider)
    stage.run(_document())
    prompt = provider.prompts[0]
    assert "A.variant_type" in prompt
    assert "missense" in prompt
    assert "nonsense" in prompt
    assert "deletion" in prompt
    assert "frameshift" in prompt
    assert "Do NOT use SNV/substitution" in prompt


def test_prompt_contains_clinical_phenotypes_guidance() -> None:
    """B8 prompt must include clinical_phenotypes with target-specific extraction rules."""
    provider = BroadProvider()
    stage = PrimaryBroadExtractionStage(provider)
    stage.run(_document())
    prompt = provider.prompts[0]
    assert "B.clinical_phenotypes" in prompt
    assert "semicolon-separated" in prompt.lower() or "semicolon" in prompt.lower()
    assert "target" in prompt.lower()


def test_prompt_contains_strong_verbatim_source_quote_instruction() -> None:
    """B8 prompt must have explicit verbatim source_quote rules."""
    provider = BroadProvider()
    stage = PrimaryBroadExtractionStage(provider)
    stage.run(_document())
    prompt = provider.prompts[0]
    assert "CRITICAL source_quote rules" in prompt
    assert "verbatim contiguous substring" in prompt
    assert "not_found" in prompt


# ── Round 2: source_quote verbatim check tests ───────────────────────────


def test_normalize_candidates_warns_on_non_verbatim_source_quote() -> None:
    """Non-verbatim source_quote should log a warning but still produce raw_source."""
    doc_text = "The patient presented with Leigh syndrome and a pathogenic MT-ATP6 variant."
    candidates = [
        PrimaryBroadEvidenceCandidate(
            field_id="A.gene_symbol",
            status=EvidenceStatus.FOUND,
            value="MT-ATP6",
            confidence=0.9,
            source_quote="A pathogenic variant was found in MT-ATP6",  # paraphrased
        ),
    ]
    items = _normalize_candidates(candidates, document_text=doc_text)
    # Item is still produced (not dropped) — warning is for monitoring only
    assert len(items) == 1
    assert items[0].raw_source is not None
    assert items[0].raw_source.text_snippet == "A pathogenic variant was found in MT-ATP6"


def test_normalize_candidates_accepts_verbatim_source_quote() -> None:
    """Verbatim source_quote should not trigger warning and produces normal raw_source."""
    doc_text = "The patient presented with Leigh syndrome and a pathogenic MT-ATP6 variant."
    verbatim_quote = "presented with Leigh syndrome"
    candidates = [
        PrimaryBroadEvidenceCandidate(
            field_id="B.disease_diagnosis",
            status=EvidenceStatus.FOUND,
            value="Leigh syndrome",
            confidence=0.95,
            source_quote=verbatim_quote,
        ),
    ]
    items = _normalize_candidates(candidates, document_text=doc_text)
    assert len(items) == 1
    assert items[0].raw_source is not None
    assert items[0].raw_source.text_snippet == verbatim_quote
    assert items[0].value == "Leigh syndrome"


def test_normalize_candidates_skips_check_when_no_document_text() -> None:
    """When document_text is empty, verbatim check is skipped (backward compat)."""
    candidates = [
        PrimaryBroadEvidenceCandidate(
            field_id="A.gene_symbol",
            status=EvidenceStatus.FOUND,
            value="BRCA1",
            confidence=0.9,
            source_quote="some quote that may or may not be verbatim",
        ),
    ]
    items = _normalize_candidates(candidates, document_text="")
    assert len(items) == 1
    assert items[0].raw_source is not None


def test_normalize_candidates_empty_source_quote_produces_no_raw_source() -> None:
    """FOUND with empty source_quote should not produce raw_source."""
    candidates = [
        PrimaryBroadEvidenceCandidate(
            field_id="A.gene_symbol",
            status=EvidenceStatus.FOUND,
            value="BRCA1",
            confidence=0.9,
            source_quote="",
        ),
    ]
    items = _normalize_candidates(candidates, document_text="BRCA1 was found.")
    assert len(items) == 1
    assert items[0].raw_source is None


# ── Round 3: J.clinvar_assertion prompt guidance test ────────────────────


def test_prompt_contains_clinvar_assertion_guidance() -> None:
    """B8 prompt must include J.clinvar_assertion with explicit ClinVar detection rules."""
    provider = BroadProvider()
    stage = PrimaryBroadExtractionStage(provider)
    stage.run(_document())
    prompt = provider.prompts[0]
    assert "J.clinvar_assertion" in prompt
    assert "ClinVar" in prompt
    assert "Pathogenic" in prompt or "pathogenic" in prompt
    assert "expert panel" in prompt.lower()
    assert "ONLY when" in prompt or "Extract ONLY" in prompt


def test_prompt_contains_high_recall_global_field_guidance() -> None:
    """Primary prompt should explicitly cover the high-FN document-level fields."""
    provider = BroadProvider()
    stage = PrimaryBroadExtractionStage(provider)
    stage.run(_document())
    prompt = provider.prompts[0]

    assert "B.hpo_terms" in prompt
    assert "HPO" in prompt
    assert "A.functional_domain_or_hotspot" in prompt
    assert "domain" in prompt.lower()
    assert "document-level" in prompt.lower()


def test_prompt_treats_inheritance_and_clinvar_as_recall_first_candidates() -> None:
    """Primary extraction should ask for explicit low-confidence candidates instead of blank fields."""
    provider = BroadProvider()
    stage = PrimaryBroadExtractionStage(provider)
    stage.run(_document())
    prompt = provider.prompts[0]

    assert "family history" in prompt.lower()
    assert "inheritance section" in prompt.lower()
    assert "ClinVar" in prompt
    assert "ACMG" in prompt
    assert "low-confidence" in prompt.lower()
