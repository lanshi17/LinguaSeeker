"""Tests for Phase 3 standardization contracts."""

from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.contracts import (
    AcmgReadyEvidenceItem,
    AcmgReadyEvidenceSet,
    BindingRole,
    CanonicalStatusRank,
    EntityMatch,
    EntityType,
    MatchMethod,
    MatchStatus,
    SimilarityCandidate,
    StandardizationCandidate,
    StandardizationInput,
    StandardizationResult,
    TerminologyCandidate,
)


def test_candidate_contract_requires_typed_entity_and_role() -> None:
    """Standardization candidates capture typed entity and binding-role fields."""
    candidate = StandardizationCandidate(
        candidate_id="chain-1:gene",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain-1",
        track="original",
    )

    assert candidate.entity_type == EntityType.GENE
    assert candidate.role == BindingRole.SUBJECT
    assert candidate.raw_text == "BRCA1"


def test_match_status_includes_ambiguous() -> None:
    """The match-status enum includes the ambiguous outcome."""
    assert MatchStatus.AMBIGUOUS.value == "ambiguous"


def test_canonical_status_rank_preserves_priority_order() -> None:
    """Canonical status labels preserve the documented priority order."""
    assert [status.value for status in CanonicalStatusRank] == [
        "found",
        "source_invalid",
        "ocr_gap",
        "table_ungrounded",
        "not_found",
    ]


def test_terminology_candidate_preserves_alias_contract_fields() -> None:
    """Terminology candidates keep the lookup alias metadata needed by matchers."""
    candidate = TerminologyCandidate(
        entry_id="entry-1",
        entity_type=EntityType.VARIANT,
        source_db="ClinVar",
        external_id="ClinVarVariation:12345",
        display_name="NM_000059.4(BRCA2):c.5946del",
        normalized_alias="nm_000059.4(brca2):c.5946del",
        alias_type="hgvs",
        raw_payload={"review_status": "criteria provided, single submitter"},
    )

    assert candidate.entity_type == EntityType.VARIANT
    assert candidate.alias_type == "hgvs"
    assert candidate.raw_payload["review_status"] == "criteria provided, single submitter"


def test_entity_match_keeps_candidate_status_and_resolution_details() -> None:
    """Entity matches preserve the original candidate and resolved terminology options."""
    standardization_candidate = StandardizationCandidate(
        candidate_id="chain-2:variant",
        entity_type=EntityType.VARIANT,
        role=BindingRole.TARGET,
        raw_text="rs80359550",
        chain_id="chain-2",
        track="translated",
    )
    terminology_candidate = TerminologyCandidate(
        entry_id="entry-2",
        entity_type=EntityType.VARIANT,
        source_db="ClinVar",
        external_id="ClinVarVariation:12345",
        display_name="NM_000059.4(BRCA2):c.5946del",
        normalized_alias="rs80359550",
        alias_type="rsid",
    )

    match = EntityMatch(
        candidate=standardization_candidate,
        status=MatchStatus.STANDARDIZED,
        external_id="ClinVarVariation:12345",
        display_name="NM_000059.4(BRCA2):c.5946del",
        terminology_candidates=(terminology_candidate,),
        rationale="exact rsid match",
    )

    assert match.candidate is standardization_candidate
    assert match.status == MatchStatus.STANDARDIZED
    assert match.terminology_candidates == (terminology_candidate,)
    assert match.rationale == "exact rsid match"


def test_entity_match_defaults_to_precise_method() -> None:
    """Existing exact matches keep precise matching as the default method."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain-1",
        track="original",
    )

    match = EntityMatch(
        candidate=candidate,
        status=MatchStatus.UNMAPPED,
        external_id=None,
        display_name="BRCA1",
    )

    assert match.match_method == MatchMethod.PRECISE
    assert match.similarity_score is None


def test_similarity_candidate_contract_is_typed() -> None:
    """Similarity retrieval returns typed candidates, not raw dictionaries."""
    candidate = SimilarityCandidate(
        terminology=TerminologyCandidate(
            entry_id="entry-1",
            entity_type=EntityType.GENE,
            source_db="HGNC",
            external_id="HGNC:1100",
            display_name="BRCA1",
            normalized_alias="brca1",
            alias_type="semantic",
        ),
        embedding_text="BRCA1 BRCA1 DNA repair associated",
        vector_distance=0.12,
        rerank_score=None,
    )

    assert candidate.terminology.external_id == "HGNC:1100"
    assert candidate.vector_distance == 0.12


def test_standardization_result_carries_matches() -> None:
    """StandardizationResult includes the full match tuple for audit output."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain-1",
        track="original",
    )
    match = EntityMatch(
        candidate=candidate,
        status=MatchStatus.STANDARDIZED,
        external_id="HGNC:1100",
        display_name="BRCA1",
        rationale="unique HGNC primary match",
    )
    result = StandardizationResult(
        document_id="doc-1",
        match_count=1,
        standardized_count=1,
        ambiguous_count=0,
        unmapped_count=0,
        normalized_entity_ids=("e1",),
        matches=(match,),
    )
    assert len(result.matches) == 1
    assert result.matches[0].candidate.raw_text == "BRCA1"


def test_acmg_ready_contracts_capture_hpo_ids_and_normalized_values() -> None:
    item = AcmgReadyEvidenceItem(
        field_id="B.clinical_phenotypes",
        normalized_key="clinical_phenotypes",
        normalized_value=["HP:0001263", "HP:0001252"],
        raw_values=("global developmental delay", "hypotonia"),
        source_field_ids=("B.clinical_phenotypes",),
    )
    evidence_set = AcmgReadyEvidenceSet(document_id="doc-1", items=(item,))

    assert evidence_set.items[0].normalized_value == ["HP:0001263", "HP:0001252"]


def test_standardization_input_carries_extraction_target() -> None:
    from src.core.evidence_extraction.contracts import (
        ExtractionTarget,
    )

    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")
    input_data = StandardizationInput(
        document_id="doc",
        source_document_id="source",
        processing_run_id="run",
        candidates=(),
        evidence_items=(),
        extraction_target=target,
    )

    assert input_data.extraction_target == target
