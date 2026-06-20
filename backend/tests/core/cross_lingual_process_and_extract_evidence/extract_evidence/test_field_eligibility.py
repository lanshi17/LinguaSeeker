import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import (
    CATALOG_GROUPS,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DocumentEvidenceMap,
    ExtractionTarget,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.field_eligibility import (
    FieldEligibilityDecision,
    FieldEligibilityPolicy,
)


def _extractable_field_ids() -> frozenset[str]:
    return frozenset(
        spec.field_id
        for group_name, group in CATALOG_GROUPS.items()
        if group_name != "curation"
        for spec in group
    )


def test_no_target_allows_all_non_curation_extractable_fields() -> None:
    decision = FieldEligibilityPolicy().decide(extraction_target=None, evidence_map=None)

    assert decision.allowed_field_ids == _extractable_field_ids()
    assert all(not field_id.startswith("K.") for field_id in decision.allowed_field_ids)
    assert decision.reasons == ("no_target:all_extractable",)


def test_decision_is_frozen_and_uses_immutable_typed_containers() -> None:
    decision = FieldEligibilityDecision(
        allowed_field_ids=frozenset({"A.gene_symbol"}),
        reasons=("target:core_identity",),
    )

    assert isinstance(decision.allowed_field_ids, frozenset)
    assert isinstance(decision.reasons, tuple)
    with pytest.raises(AttributeError):
        decision.reasons = ()


def test_target_always_includes_core_identity_fields() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")

    decision = FieldEligibilityPolicy().decide(extraction_target=target, evidence_map=None)

    assert {"A.gene_symbol", "A.gene_disease_relationship", "B.disease_diagnosis"}.issubset(
        decision.allowed_field_ids
    )
    assert "target:core_identity" in decision.reasons


def test_target_variant_cues_include_variant_fields() -> None:
    target = ExtractionTarget(
        gene_symbol="ABCA3",
        disease_name="ABCA3 deficiency",
        variant_hgvs_p="p.Arg43Leu",
    )
    evidence_map = DocumentEvidenceMap(
        relevant=True,
        variant_terms=["c.128G>T", "p.Arg43Leu"],
    )

    decision = FieldEligibilityPolicy().decide(extraction_target=target, evidence_map=evidence_map)

    assert {
        "A.variant_hgvs_c",
        "A.variant_hgvs_p",
        "A.variant_hgvs_g",
        "A.variant_type",
        "F.tested_variant",
    }.issubset(decision.allowed_field_ids)
    assert "cue:variant" in decision.reasons


def test_functional_cues_include_functional_fields() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")
    evidence_map = DocumentEvidenceMap(
        relevant=True,
        structure_hints=["Functional assay measured surfactant transport in patient cells."],
    )

    decision = FieldEligibilityPolicy().decide(extraction_target=target, evidence_map=evidence_map)

    assert {"F.functional_result", "F.assay_type", "I.functional_alteration_patient_cells"}.issubset(
        decision.allowed_field_ids
    )
    assert "cue:functional" in decision.reasons


def test_population_cues_include_population_frequency_fields() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")
    evidence_map = DocumentEvidenceMap(
        relevant=True,
        structure_hints=["gnomAD allele frequency and ancestry were reported."],
    )

    decision = FieldEligibilityPolicy().decide(extraction_target=target, evidence_map=evidence_map)

    assert {
        "D.population_database_name",
        "D.allele_frequency",
        "D.population_subgroup",
        "B.ancestry_or_population",
        "A.identity_by_descent_variant",
    }.issubset(decision.allowed_field_ids)
    assert "cue:population" in decision.reasons


def test_selected_text_functional_cue_includes_functional_fields_without_evidence_map() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")

    decision = FieldEligibilityPolicy().decide(
        extraction_target=target,
        evidence_map=None,
        selected_text="Functional assay measured surfactant transport in patient cells.",
    )

    assert {"F.functional_result", "F.assay_type", "I.functional_alteration_patient_cells"}.issubset(
        decision.allowed_field_ids
    )
    assert "cue:functional" in decision.reasons


def test_selected_text_population_cue_includes_population_fields_without_evidence_map() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")

    decision = FieldEligibilityPolicy().decide(
        extraction_target=target,
        evidence_map=None,
        selected_text="gnomAD allele frequency and population ancestry were reported.",
    )

    assert {
        "D.population_database_name",
        "D.allele_frequency",
        "D.population_subgroup",
        "B.ancestry_or_population",
        "A.identity_by_descent_variant",
    }.issubset(decision.allowed_field_ids)
    assert "cue:population" in decision.reasons


def test_selected_text_variant_cue_includes_variant_fields_without_target_variant_or_map() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")

    decision = FieldEligibilityPolicy().decide(
        extraction_target=target,
        evidence_map=None,
        selected_text="The patient carried c.128G>T, a missense variant causing p.Arg43Leu.",
    )

    assert {
        "A.variant_hgvs_c",
        "A.variant_hgvs_p",
        "A.variant_hgvs_g",
        "A.variant_type",
        "F.tested_variant",
    }.issubset(decision.allowed_field_ids)
    assert "cue:variant" in decision.reasons


def test_target_gene_map_cue_does_not_expand_to_all_extractable_fields() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")
    evidence_map = DocumentEvidenceMap(
        relevant=True,
        gene_terms=["ABCA3"],
        disease_terms=["ABCA3 deficiency"],
    )

    decision = FieldEligibilityPolicy().decide(extraction_target=target, evidence_map=evidence_map)

    assert decision.allowed_field_ids != _extractable_field_ids()
    assert "cue:ambiguous_all_extractable" not in decision.reasons


def test_cell_disease_phrase_does_not_trigger_functional_fields() -> None:
    target = ExtractionTarget(gene_symbol="HBB", disease_name="sickle cell disease")

    decision = FieldEligibilityPolicy().decide(
        extraction_target=target,
        selected_text="Patients with sickle cell disease were enrolled.",
    )

    assert "F.functional_result" not in decision.allowed_field_ids
    assert "I.functional_alteration_patient_cells" not in decision.allowed_field_ids
    assert "cue:functional" not in decision.reasons
