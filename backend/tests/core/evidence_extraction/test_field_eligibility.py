import pytest

from src.core.evidence_extraction.domain.catalog import (
    CATALOG_GROUPS,
    EVIDENCE_FIELD_SPECS,
)
from src.core.evidence_extraction.domain.channel_contracts import (
    DocumentChannelClassification,
    DocumentEvidenceChannel,
)
from src.core.evidence_extraction.contracts import (
    DocumentEvidenceMap,
    ExtractionTarget,
)
from src.core.evidence_extraction.domain.field_eligibility import (
    FieldEligibilityDecision,
    FieldEligibilityPolicy,
)


def _extractable_field_ids() -> frozenset[str]:
    return frozenset(
        spec.field_id for group_name, group in CATALOG_GROUPS.items() if group_name != "curation" for spec in group
    )


def test_no_target_allows_all_non_curation_extractable_fields() -> None:
    decision = FieldEligibilityPolicy().decide(extraction_target=None, evidence_map=None)

    assert decision.allowed_field_ids == _extractable_field_ids()
    assert all(not field_id.startswith("K.") for field_id in decision.allowed_field_ids)
    assert decision.reasons == ("no_target:all_extractable",)


def test_decision_is_frozen_and_uses_immutable_typed_containers() -> None:
    decision = FieldEligibilityDecision(
        allowed_field_ids=frozenset({"A.gene_symbol"}),
        excluded_field_ids=frozenset(),
        reasons=("target:core_identity",),
    )

    assert isinstance(decision.allowed_field_ids, frozenset)
    assert isinstance(decision.reasons, tuple)
    with pytest.raises(AttributeError):
        decision.reasons = ()


def test_target_always_includes_core_identity_fields() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")

    decision = FieldEligibilityPolicy().decide(extraction_target=target, evidence_map=None)

    assert {"A.gene_symbol", "A.gene_disease_relationship", "B.disease_diagnosis"}.issubset(decision.allowed_field_ids)
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
        "B.mode_of_inheritance_reported",
        "F.tested_variant",
    }.issubset(decision.allowed_field_ids)
    assert "cue:variant" in decision.reasons


def test_variant_cues_include_variant_evidence_module_fields() -> None:
    target = ExtractionTarget(
        gene_symbol="CFTR",
        disease_name="cystic fibrosis",
        variant_hgvs_p="p.Phe508del",
    )

    decision = FieldEligibilityPolicy().decide(extraction_target=target, evidence_map=None)

    assert {
        "A.variant_type",
        "B.mode_of_inheritance_reported",
        "F.tested_variant",
    }.issubset(decision.allowed_field_ids)


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
        "B.mode_of_inheritance_reported",
        "F.tested_variant",
    }.issubset(decision.allowed_field_ids)
    assert "cue:variant" in decision.reasons


def test_authority_cues_include_clinvar_assertion_fields() -> None:
    target = ExtractionTarget(gene_symbol="CFTR", disease_name="cystic fibrosis")

    decision = FieldEligibilityPolicy().decide(
        extraction_target=target,
        selected_text="ClinVar classified the variant as Pathogenic.",
    )

    assert {
        "J.clinvar_assertion",
        "J.authority_classification",
        "J.known_pathogenic_variant_reference",
    }.issubset(decision.allowed_field_ids)
    assert "cue:authority" in decision.reasons


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


# ---------------------------------------------------------------------------
# Channel-aware eligibility (decide_with_channels)
# ---------------------------------------------------------------------------

_ALL_FIELD_IDS = frozenset(spec.field_id for spec in EVIDENCE_FIELD_SPECS)
_NON_K_FIELD_IDS = frozenset(spec.field_id for spec in EVIDENCE_FIELD_SPECS if spec.category_id != "K")


def _cls(channels: list[DocumentEvidenceChannel]) -> DocumentChannelClassification:
    return DocumentChannelClassification(
        selected_channels=list(channels),
        confidence=0.9,
        rationale="test",
        supporting_block_ids=[],
    )


def test_decide_with_channels_none_classification_returns_base():
    """channel_classification=None is permissive — base decision unchanged."""
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")
    base = FieldEligibilityPolicy().decide(extraction_target=target)
    composed = FieldEligibilityPolicy().decide_with_channels(
        extraction_target=target,
        channel_classification=None,
    )
    assert composed.allowed_field_ids == base.allowed_field_ids
    assert composed.reasons == base.reasons


def test_decide_with_channels_no_target_case_report():
    """No target + case_report → all extractable ∩ case_report fields = case_report fields."""
    composed = FieldEligibilityPolicy().decide_with_channels(
        extraction_target=None,
        channel_classification=_cls([DocumentEvidenceChannel.CASE_REPORT]),
    )
    # F fields are functional-only, not in case_report
    assert "F.assay_id" not in composed.allowed_field_ids
    assert "B.disease_diagnosis" in composed.allowed_field_ids
    assert "C.lod_score" in composed.allowed_field_ids
    assert "channel:case_report" in composed.reasons


def test_case_report_excludes_functional_only_F_fields():
    target = ExtractionTarget(gene_symbol="GLA", disease_name="Fabry disease")
    # Add functional cue so base decision includes F fields
    composed = FieldEligibilityPolicy().decide_with_channels(
        extraction_target=target,
        selected_text="functional assay results",
        channel_classification=_cls([DocumentEvidenceChannel.CASE_REPORT]),
    )
    assert "F.assay_id" not in composed.allowed_field_ids
    assert "F.functional_result" not in composed.allowed_field_ids
    # Common fields (A, B, H, J) still allowed
    assert "A.gene_symbol" in composed.allowed_field_ids
    assert "B.disease_diagnosis" in composed.allowed_field_ids
    assert "rejected:not_extractable_for_channel" in composed.reasons


def test_functional_study_includes_F_fields_but_excludes_case_only_BC():
    target = ExtractionTarget(gene_symbol="GLA", disease_name="Fabry disease")
    composed = FieldEligibilityPolicy().decide_with_channels(
        extraction_target=target,
        selected_text="functional assay results",
        channel_classification=_cls([DocumentEvidenceChannel.FUNCTIONAL_STUDY]),
    )
    assert "F.assay_id" in composed.allowed_field_ids
    assert "I.animal_model_type" in composed.allowed_field_ids
    # B.case_count is category B (case_report-only, not in functional_study)
    assert "B.case_count" not in composed.allowed_field_ids
    # C.lod_score is category C (case_report-only)
    assert "C.lod_score" not in composed.allowed_field_ids
    assert "channel:functional_study" in composed.reasons


def test_cohort_study_includes_DG_fields_but_excludes_F_fields():
    # No target → base = all 143 extractable; channel filter isolates cohort fields.
    # G fields have no target-cue path, so use no-target to test pure channel filtering.
    composed = FieldEligibilityPolicy().decide_with_channels(
        extraction_target=None,
        channel_classification=_cls([DocumentEvidenceChannel.COHORT_STUDY]),
    )
    assert "D.allele_frequency" in composed.allowed_field_ids
    assert "G.odds_ratio" in composed.allowed_field_ids
    assert "F.assay_id" not in composed.allowed_field_ids
    assert "C.lod_score" not in composed.allowed_field_ids
    assert "channel:cohort_study" in composed.reasons


def test_mixed_case_and_functional_uses_union_before_intersection():
    # No target → base = all 143; channel filter = case∪functional (120 fields).
    # C fields have no target-cue path, so use no-target to test pure channel union.
    composed = FieldEligibilityPolicy().decide_with_channels(
        extraction_target=None,
        channel_classification=_cls(
            [
                DocumentEvidenceChannel.CASE_REPORT,
                DocumentEvidenceChannel.FUNCTIONAL_STUDY,
            ]
        ),
    )
    # F fields allowed via functional_study
    assert "F.assay_id" in composed.allowed_field_ids
    # B/C fields allowed via case_report
    assert "B.disease_diagnosis" in composed.allowed_field_ids
    assert "C.lod_score" in composed.allowed_field_ids
    # D fields NOT in union (cohort not selected)
    assert "D.allele_frequency" not in composed.allowed_field_ids
    assert "channel:case_report" in composed.reasons
    assert "channel:functional_study" in composed.reasons


def test_unknown_classification_is_permissive_preserves_base():
    target = ExtractionTarget(gene_symbol="GLA", disease_name="Fabry disease")
    base = FieldEligibilityPolicy().decide(
        extraction_target=target,
        selected_text="functional assay results population frequency",
    )
    composed = FieldEligibilityPolicy().decide_with_channels(
        extraction_target=target,
        selected_text="functional assay results population frequency",
        channel_classification=_cls([DocumentEvidenceChannel.UNKNOWN]),
    )
    # Unknown is permissive — all non-K fields, so composition = base ∩ all_non_K = base
    assert composed.allowed_field_ids == base.allowed_field_ids
    assert "channel:unknown" in composed.reasons


def test_decide_with_channels_result_is_subset_of_base():
    """Channel-filtered decision must always be a subset of the base decision."""
    target = ExtractionTarget(gene_symbol="GLA", disease_name="Fabry disease")
    base = FieldEligibilityPolicy().decide(
        extraction_target=target,
        selected_text="functional assay variant population frequency",
    )
    for channel in [
        DocumentEvidenceChannel.CASE_REPORT,
        DocumentEvidenceChannel.FUNCTIONAL_STUDY,
        DocumentEvidenceChannel.COHORT_STUDY,
        DocumentEvidenceChannel.MIXED,
        DocumentEvidenceChannel.UNKNOWN,
    ]:
        composed = FieldEligibilityPolicy().decide_with_channels(
            extraction_target=target,
            selected_text="functional assay variant population frequency",
            channel_classification=_cls([channel]),
        )
        assert composed.allowed_field_ids <= base.allowed_field_ids


def test_decide_with_channels_excludes_curation_always():
    target = ExtractionTarget(gene_symbol="GLA", disease_name="Fabry disease")
    k_fields = frozenset(spec.field_id for spec in EVIDENCE_FIELD_SPECS if spec.category_id == "K")
    for channel in DocumentEvidenceChannel:
        composed = FieldEligibilityPolicy().decide_with_channels(
            extraction_target=target,
            channel_classification=_cls([channel]),
        )
        assert composed.allowed_field_ids.isdisjoint(k_fields)


def test_decide_with_channels_no_target_and_unknown_is_all_non_k():
    composed = FieldEligibilityPolicy().decide_with_channels(
        extraction_target=None,
        channel_classification=_cls([DocumentEvidenceChannel.UNKNOWN]),
    )
    assert composed.allowed_field_ids == _NON_K_FIELD_IDS


def test_decide_with_channels_no_target_and_case_report_is_case_fields():
    """No target → base = all extractable (143). Case report filter → 73."""
    composed = FieldEligibilityPolicy().decide_with_channels(
        extraction_target=None,
        channel_classification=_cls([DocumentEvidenceChannel.CASE_REPORT]),
    )
    assert len(composed.allowed_field_ids) == 73
    assert composed.allowed_field_ids <= _ALL_FIELD_IDS
    assert "rejected:not_extractable_for_channel" in composed.reasons
