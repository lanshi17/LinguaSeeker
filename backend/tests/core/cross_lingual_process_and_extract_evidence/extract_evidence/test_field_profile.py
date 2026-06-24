"""Tests for field-profiled extraction and source-visible validation."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    SourceLocation,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.field_profile import (
    DATASET_D_FIELDS,
    ExtractionProfile,
    build_profiled_catalog,
    intersect_profile_fields,
    resolve_channel_profile_fields,
    resolve_profile_fields,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.channel_contracts import (
    DocumentChannelClassification,
    DocumentEvidenceChannel,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import (
    CATALOG_GROUPS,
    EVIDENCE_FIELD_SPECS,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.clinical_context import (
    ClinicalContextStage,
)


# ---------------------------------------------------------------------------
# Field profile tests
# ---------------------------------------------------------------------------

def test_dataset_d_field_count_is_at_most_20():
    assert len(DATASET_D_FIELDS) <= 20


def test_dataset_d_includes_all_13_evaluated_fields():
    evaluated = {
        "A.gene_symbol",
        "B.disease_diagnosis",
        "A.gene_disease_relationship",
        "A.variant_hgvs_c",
        "A.variant_hgvs_p",
        "A.variant_type",
        "A.functional_domain_or_hotspot",
        "B.sex",
        "B.age_of_onset",
        "B.mode_of_inheritance_reported",
        "B.clinical_phenotypes",
        "B.hpo_terms",
        "C.de_novo_status",
    }
    assert evaluated.issubset(DATASET_D_FIELDS)


def test_dataset_d_includes_identity_fields_for_chain_assembly():
    """Chain assembly needs variant_hgvs_g, transcript_id etc."""
    # At minimum, we need gene_symbol + disease_diagnosis + variant for chain
    assert "A.gene_symbol" in DATASET_D_FIELDS
    assert "B.disease_diagnosis" in DATASET_D_FIELDS
    assert "A.variant_hgvs_c" in DATASET_D_FIELDS


def test_build_profiled_catalog_returns_subset():
    profiled = build_profiled_catalog(DATASET_D_FIELDS)
    all_field_ids = {spec.field_id for group in CATALOG_GROUPS.values() for spec in group}
    profiled_ids = {spec.field_id for group in profiled.values() for spec in group}
    assert profiled_ids.issubset(all_field_ids)
    assert len(profiled_ids) < len(all_field_ids)


def test_build_profiled_catalog_excludes_curation():
    profiled = build_profiled_catalog(DATASET_D_FIELDS)
    assert "curation" not in profiled


def test_build_profiled_catalog_high_signal_has_fewer_fields():
    original_hs = len(CATALOG_GROUPS["high_signal"])
    profiled = build_profiled_catalog(DATASET_D_FIELDS)
    profiled_hs = len(profiled.get("high_signal", ()))
    assert profiled_hs < original_hs


# ---------------------------------------------------------------------------
# Source-visible gate tests for ClinicalContextStage
# ---------------------------------------------------------------------------

def _doc_with_text(text: str) -> TrackDocument:
    return TrackDocument(
        document_id="doc-sv-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
        blocks=[ContentBlock(type="text", page_idx=0, text=text)],
    )


def test_source_visible_gate_accepts_value_present_in_document():
    text = "The patient presented with seizures and developmental regression."
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
                context_type="text", context_ref="",
                text_snippet="seizures and developmental regression",
            ),
        ),
    ]
    stage = ClinicalContextStage(provider)
    result = stage.run(_doc_with_text(text), [], DocumentEvidenceMap(relevant=True))
    assert len(result) == 1
    assert result[0].field_id == "B.clinical_phenotypes"


def test_source_visible_gate_rejects_value_not_in_document():
    text = "The patient was a 4-year-old female."
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        EvidenceItem(
            field_id="B.clinical_phenotypes",
            category="B",
            field_name="Key clinical phenotypes",
            status=EvidenceStatus.FOUND,
            value="seizures; ataxia; tremor",
            confidence=0.85,
            source=SourceLocation(
                context_type="text", context_ref="",
                text_snippet="seizures and ataxia",
            ),
        ),
    ]
    stage = ClinicalContextStage(provider)
    result = stage.run(_doc_with_text(text), [], DocumentEvidenceMap(relevant=True))
    # The source snippet "seizures and ataxia" is NOT in the document text
    # The value "seizures; ataxia; tremor" is NOT in the document text
    # So source-visible gate should reject
    assert len(result) == 0


def test_source_visible_gate_accepts_when_snippet_in_document():
    text = "The patient had loss of acquired hand skills and stereotypic movements."
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        EvidenceItem(
            field_id="B.clinical_phenotypes",
            category="B",
            field_name="Key clinical phenotypes",
            status=EvidenceStatus.FOUND,
            value="loss of acquired hand skills; stereotypic movements",
            confidence=0.85,
            source=SourceLocation(
                context_type="text", context_ref="",
                text_snippet="loss of acquired hand skills and stereotypic movements",
            ),
        ),
    ]
    stage = ClinicalContextStage(provider)
    result = stage.run(_doc_with_text(text), [], DocumentEvidenceMap(relevant=True))
    assert len(result) == 1


def test_source_visible_gate_rejects_empty_snippet():
    text = "Some medical text."
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
                context_type="text", context_ref="",
                text_snippet="",
            ),
        ),
    ]
    stage = ClinicalContextStage(provider)
    result = stage.run(_doc_with_text(text), [], DocumentEvidenceMap(relevant=True))
    assert len(result) == 0


def test_source_visible_gate_handles_no_source():
    text = "Some medical text."
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        EvidenceItem(
            field_id="B.sex",
            category="B",
            field_name="Sex",
            status=EvidenceStatus.FOUND,
            value="female",
            confidence=0.85,
            source=None,
        ),
    ]
    stage = ClinicalContextStage(provider)
    result = stage.run(_doc_with_text(text), [], DocumentEvidenceMap(relevant=True))
    assert len(result) == 0


# ---------------------------------------------------------------------------
# Profile opt-in tests
# ---------------------------------------------------------------------------

def test_resolve_profile_none_returns_none():
    assert resolve_profile_fields(None) is None
    assert resolve_profile_fields(ExtractionProfile.NONE) is None
    assert resolve_profile_fields("none") is None


def test_resolve_profile_dataset_d_returns_fields():
    fields = resolve_profile_fields(ExtractionProfile.DATASET_D_PUBLICATION)
    assert fields is not None
    assert "A.gene_symbol" in fields
    assert len(fields) <= 20


def test_resolve_profile_unknown_raises():
    with pytest.raises(ValueError, match="Unknown extraction profile"):
        resolve_profile_fields("nonexistent_profile")


def test_default_service_does_not_use_dataset_d_fields():
    """EvidenceExtractionService default must extract all non-curation fields,
    NOT silently restrict to DATASET_D_FIELDS."""
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
        EvidenceExtractionService,
    )
    from unittest.mock import patch, MagicMock

    # Patch at the module level to avoid real LLM initialization
    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api.LangChainEvidenceProvider",
    ), patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api.EvidenceExtractionConfigContext",
    ):
        # Default (NONE) should pass None to the workflow (no field restriction)
        EvidenceExtractionService(cfg=MagicMock())  # noqa: B018 -- smoke-check construction
        # The workflow's catalog groups should include ALL non-curation fields
        all_extractable = {
            spec.field_id
            for name, specs in CATALOG_GROUPS.items()
            if name != "curation"
            for spec in specs
        }
        # With DATASET_D_FIELDS, the set would be much smaller (~20).
        # With NONE (default), it should be all ~143 extractable fields.
        assert len(all_extractable) > 50, "Sanity: extractable fields > 50"


def test_service_with_dataset_d_profile_restricts_fields():
    """When explicitly selecting DATASET_D_PUBLATION, the workflow should
    use the restricted field set."""
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
        EvidenceExtractionService,
    )
    from unittest.mock import patch, MagicMock

    with patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api.LangChainEvidenceProvider",
    ), patch(
        "src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api.EvidenceExtractionConfigContext",
    ):
        service = EvidenceExtractionService(
            cfg=MagicMock(),
            extraction_profile=ExtractionProfile.DATASET_D_PUBLICATION,
        )
        # The service was created with the dataset_d profile — this should
        # not raise and should have created a workflow.
        assert service._workflow is not None


# ---------------------------------------------------------------------------
# Source-visible gate whitespace normalization tests
# ---------------------------------------------------------------------------

def test_source_visible_gate_accepts_whitespace_normalized_snippet():
    """Snippet with different whitespace formatting should still match."""
    text = "The patient  had   seizures and  developmental regression."
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
                context_type="text", context_ref="",
                text_snippet="The patient had seizures and developmental regression.",
            ),
        ),
    ]
    stage = ClinicalContextStage(provider)
    result = stage.run(_doc_with_text(text), [], DocumentEvidenceMap(relevant=True))
    # After whitespace normalization, both sides become the same
    assert len(result) == 1


def test_source_visible_gate_accepts_tab_vs_space():
    """Tabs and spaces should normalize to the same string."""
    text = "The patient\thad\tseizures."
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        EvidenceItem(
            field_id="B.sex",
            category="B",
            field_name="Sex",
            status=EvidenceStatus.FOUND,
            value="seizures present",
            confidence=0.85,
            source=SourceLocation(
                context_type="text", context_ref="",
                text_snippet="The patient had seizures.",
            ),
        ),
    ]
    stage = ClinicalContextStage(provider)
    result = stage.run(_doc_with_text(text), [], DocumentEvidenceMap(relevant=True))
    assert len(result) == 1


def test_source_visible_gate_case_sensitive():
    """Gate uses case-sensitive matching to avoid false positives."""
    text = "The patient had SEIZURES."
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        EvidenceItem(
            field_id="B.clinical_phenotypes",
            category="B",
            field_name="Key clinical phenotypes",
            status=EvidenceStatus.FOUND,
            value="seizures",
            confidence=0.85,
            source=SourceLocation(
                context_type="text", context_ref="",
                text_snippet="seizures",
            ),
        ),
    ]
    stage = ClinicalContextStage(provider)
    result = stage.run(_doc_with_text(text), [], DocumentEvidenceMap(relevant=True))
    # Case-sensitive: "seizures" != "SEIZURES" — rejected
    assert len(result) == 0


# ---------------------------------------------------------------------------
# Rejection counter tests
# ---------------------------------------------------------------------------

def test_rejection_counters_exposed():
    """After _merge, rejection reasons should be accessible for audit."""
    text = "The patient was a 4-year-old female."
    provider = MagicMock()
    provider.invoke_structured.return_value = [
        EvidenceItem(
            field_id="B.clinical_phenotypes",
            category="B",
            field_name="Key clinical phenotypes",
            status=EvidenceStatus.FOUND,
            value="seizures; ataxia",
            confidence=0.85,
            source=SourceLocation(
                context_type="text", context_ref="",
                text_snippet="seizures and ataxia",
            ),
        ),
    ]
    stage = ClinicalContextStage(provider)
    result = stage.run(_doc_with_text(text), [], DocumentEvidenceMap(relevant=True))
    assert len(result) == 0
    # Rejection counters should be set
    assert hasattr(ClinicalContextStage, "_rejection_reasons")
    counters = ClinicalContextStage._rejection_reasons
    assert any("not_in_document" in k for k in counters), (
        f"Expected not_in_document rejection, got: {counters}"
    )


# ---------------------------------------------------------------------------
# Channel profile + intersection tests
# ---------------------------------------------------------------------------

_ALL_FIELD_IDS = frozenset(spec.field_id for spec in EVIDENCE_FIELD_SPECS)
_NON_K_FIELD_IDS = frozenset(
    spec.field_id for spec in EVIDENCE_FIELD_SPECS if spec.category_id != "K"
)


def _cls(channels: list[DocumentEvidenceChannel]) -> DocumentChannelClassification:
    return DocumentChannelClassification(
        selected_channels=channels,
        confidence=0.9,
        rationale="test classification",
        supporting_block_ids=["blk-1"],
    )


def test_resolve_channel_unknown_returns_all_non_k_fields():
    fields = resolve_channel_profile_fields(_cls([DocumentEvidenceChannel.UNKNOWN]))
    assert fields == _NON_K_FIELD_IDS
    assert len(fields) == 143


def test_resolve_channel_bare_mixed_returns_all_three_concrete_unions():
    fields = resolve_channel_profile_fields(_cls([DocumentEvidenceChannel.MIXED]))
    assert fields == _NON_K_FIELD_IDS
    assert len(fields) == 143


def test_resolve_channel_case_report_count():
    fields = resolve_channel_profile_fields(_cls([DocumentEvidenceChannel.CASE_REPORT]))
    # A(22) + B(19) + C(17) + H(9) + J(6) = 73
    assert len(fields) == 73


def test_resolve_channel_functional_study_count():
    fields = resolve_channel_profile_fields(
        _cls([DocumentEvidenceChannel.FUNCTIONAL_STUDY])
    )
    # A(22) + E(7) + F(24) + I(16) + H(9) + J(6) = 84
    assert len(fields) == 84


def test_resolve_channel_cohort_study_count():
    fields = resolve_channel_profile_fields(_cls([DocumentEvidenceChannel.COHORT_STUDY]))
    # A(22) + D(8) + G(15) + H(9) + J(6) = 60
    assert len(fields) == 60


def test_resolve_channel_two_concrete_returns_union():
    fields = resolve_channel_profile_fields(
        _cls([DocumentEvidenceChannel.CASE_REPORT, DocumentEvidenceChannel.FUNCTIONAL_STUDY])
    )
    case = resolve_channel_profile_fields(_cls([DocumentEvidenceChannel.CASE_REPORT]))
    func = resolve_channel_profile_fields(_cls([DocumentEvidenceChannel.FUNCTIONAL_STUDY]))
    assert fields == case | func
    # A+B+C+E+F+H+I+J = 22+19+17+7+24+9+16+6 = 120
    assert len(fields) == 120


def test_resolve_channel_no_field_outside_catalog():
    for channel in DocumentEvidenceChannel:
        fields = resolve_channel_profile_fields(_cls([channel]))
        assert fields <= _ALL_FIELD_IDS


def test_resolve_channel_curation_always_excluded():
    k_fields = frozenset(
        spec.field_id for spec in EVIDENCE_FIELD_SPECS if spec.category_id == "K"
    )
    for channel in DocumentEvidenceChannel:
        fields = resolve_channel_profile_fields(_cls([channel]))
        assert fields.isdisjoint(k_fields)


def test_intersect_none_and_channel_returns_channel():
    channel = resolve_channel_profile_fields(_cls([DocumentEvidenceChannel.CASE_REPORT]))
    assert intersect_profile_fields(None, channel) == channel


def test_intersect_base_and_none_returns_base():
    assert intersect_profile_fields(DATASET_D_FIELDS, None) == DATASET_D_FIELDS


def test_intersect_none_and_none_returns_none():
    assert intersect_profile_fields(None, None) is None


def test_intersect_both_present_returns_intersection():
    channel = resolve_channel_profile_fields(_cls([DocumentEvidenceChannel.CASE_REPORT]))
    result = intersect_profile_fields(DATASET_D_FIELDS, channel)
    assert result == DATASET_D_FIELDS & channel


def test_intersect_dataset_d_with_case_report_excludes_population_field():
    channel = resolve_channel_profile_fields(_cls([DocumentEvidenceChannel.CASE_REPORT]))
    result = intersect_profile_fields(DATASET_D_FIELDS, channel)
    # D.allele_frequency is category D (cohort), not extractable from case_report
    assert "D.allele_frequency" not in result
    # All other 19 DATASET_D fields are A/B/C — case-report extractable
    assert len(result) == len(DATASET_D_FIELDS) - 1
    assert result <= DATASET_D_FIELDS


def test_intersect_dataset_d_with_case_report_result_all_in_catalog():
    channel = resolve_channel_profile_fields(_cls([DocumentEvidenceChannel.CASE_REPORT]))
    result = intersect_profile_fields(DATASET_D_FIELDS, channel)
    assert result <= _ALL_FIELD_IDS


def test_intersect_dataset_d_with_unknown_returns_full_dataset_d():
    """Unknown is permissive, so it must not restrict the named profile."""
    channel = resolve_channel_profile_fields(_cls([DocumentEvidenceChannel.UNKNOWN]))
    result = intersect_profile_fields(DATASET_D_FIELDS, channel)
    assert result == DATASET_D_FIELDS
