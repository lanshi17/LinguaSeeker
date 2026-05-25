"""Tests for Phase 3 standardization contracts."""
from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    CanonicalStatusRank,
    EntityMatch,
    EntityType,
    MatchStatus,
    StandardizationCandidate,
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
