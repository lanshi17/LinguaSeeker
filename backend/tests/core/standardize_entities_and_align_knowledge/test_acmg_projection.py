"""Tests for ACMG-ready normalized evidence projection."""

from __future__ import annotations

from src.core.evidence_extraction.contracts import (
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


def test_maternal_phenotype_not_projected_as_proband_hpo() -> None:
    candidate = StandardizationCandidate(
        candidate_id="phenotype-maternal",
        entity_type=EntityType.PHENOTYPE,
        role=BindingRole.CONTEXT,
        raw_text="hypotonia",
        chain_id="chain-1",
        track="original",
        field_id="C.maternal_phenotype",
    )
    match = EntityMatch(
        candidate=candidate,
        status=MatchStatus.STANDARDIZED,
        external_id="HP:0001252",
        display_name="Hypotonia",
    )
    input_data = StandardizationInput(
        document_id="doc-1",
        source_document_id="source-1",
        processing_run_id="run-1",
        candidates=(candidate,),
        evidence_items=(),
    )

    result = AcmgReadyProjector().project(input_data, (match,))

    assert result.items == ()


def test_projector_maps_found_field_bridge_gates_without_granting_codes() -> None:
    items = (
        EvidenceItem(
            field_id="A.variant_hgvs_c",
            category="A",
            field_name="HGVS c.",
            status=EvidenceStatus.FOUND,
            value="c.538C&gt;T",
            confidence=0.9,
        ),
        EvidenceItem(
            field_id="C.de_novo_status",
            category="C",
            field_name="De novo status",
            status=EvidenceStatus.FOUND,
            value="de_novo",
            confidence=0.88,
        ),
        EvidenceItem(
            field_id="C.parentage_confirmed",
            category="C",
            field_name="Parentage confirmed",
            status=EvidenceStatus.FOUND,
            value="not_confirmed",
            confidence=1.0,
        ),
        EvidenceItem(
            field_id="C.maternal_genotype",
            category="C",
            field_name="Maternal genotype",
            status=EvidenceStatus.NOT_FOUND,
            value=None,
            confidence=0.0,
        ),
    )
    input_data = StandardizationInput(
        document_id="doc-gates",
        source_document_id="source-gates",
        processing_run_id="run-gates",
        candidates=(),
        evidence_items=items,
    )

    result = AcmgReadyProjector().project(input_data, ())

    by_key = {item.normalized_key: item for item in result.items}
    assert "hpo_terms" not in by_key
    assert by_key["variant_hgvs_c"].normalized_value == "c.538C>T"
    assert by_key["de_novo_status"].normalized_value == "de_novo"
    assert by_key["parentage_confirmed"].normalized_value == "not_confirmed"
    assert "maternal_genotype" not in by_key

