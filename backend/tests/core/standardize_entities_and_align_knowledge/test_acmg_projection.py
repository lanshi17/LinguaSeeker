"""Tests for ACMG-ready normalized evidence projection."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
)
from src.core.standardize_entities_and_align_knowledge.acmg_projection import AcmgReadyProjector
from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityMatch,
    EntityType,
    MatchStatus,
    StandardizationCandidate,
    StandardizationInput,
)


def test_projector_maps_clinical_phenotypes_to_hpo_ids() -> None:
    item = EvidenceItem(
        field_id="B.clinical_phenotypes",
        category="B",
        field_name="Key clinical phenotypes",
        status=EvidenceStatus.FOUND,
        value="global developmental delay, hypotonia",
        confidence=0.9,
        group_id="gene=AARS2|variant=__missing__",
    )
    candidate = StandardizationCandidate(
        candidate_id="gene=AARS2|variant=__missing__:phenotype:0",
        entity_type=EntityType.PHENOTYPE,
        role=BindingRole.CONTEXT,
        raw_text="global developmental delay",
        chain_id="gene=AARS2|variant=__missing__",
        track="original",
        field_id="B.clinical_phenotypes",
    )
    match = EntityMatch(
        candidate=candidate,
        status=MatchStatus.STANDARDIZED,
        external_id="HP:0001263",
        display_name="Global developmental delay",
    )
    input_data = StandardizationInput(
        document_id="doc-1",
        source_document_id="source-1",
        processing_run_id="run-1",
        candidates=(candidate,),
        evidence_items=(item,),
    )

    result = AcmgReadyProjector().project(input_data, (match,))

    assert result.document_id == "doc-1"
    assert result.items[0].field_id == "B.clinical_phenotypes"
    assert result.items[0].normalized_key == "hpo_terms"
    assert result.items[0].normalized_value == ["HP:0001263"]
