"""Tests for deterministic evidence verification."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.verify.contracts import (
    EvidenceVerificationInput,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.verify.core import (
    score_candidate_support,
)


def _verification_input(
    *,
    field_id: str = "A.gene_disease_relationship",
    candidate_value: str = "causative",
    source_snippet: str,
    source_precision: str = "exact",
    target_gene: str = "TLR5",
    target_disease: str = "systemic lupus erythematosus",
    disease_aliases: tuple[str, ...] = ("systemic lupus erythematosus", "SLE"),
) -> EvidenceVerificationInput:
    return EvidenceVerificationInput(
        entry_id="clingen_024",
        field_id=field_id,
        candidate_value=candidate_value,
        source_snippet=source_snippet,
        source_precision=source_precision,
        track="original",
        target_gene=target_gene,
        target_disease=target_disease,
        disease_aliases=disease_aliases,
        moi="AD",
    )


def test_score_candidate_support_rewards_target_specific_causal_evidence() -> None:
    result = score_candidate_support(
        _verification_input(
            source_snippet=(
                "Pathogenic variants in TLR5 cause systemic lupus erythematosus "
                "through altered innate immune signaling."
            )
        )
    )

    assert result.recommended_value == "causative"
    assert result.support_score >= 0.75
    assert result.target_specificity_score == 1.0
    assert result.contradiction_score == 0.0
    assert result.requires_review is False


def test_score_candidate_support_treats_disease_causing_language_as_causative() -> None:
    result = score_candidate_support(
        _verification_input(
            source_snippet="TBC1D8B was recently discovered as a novel disease-causing gene for X-linked NPHS.",
            target_gene="TBC1D8B",
            target_disease="nephrotic syndrome, type 20",
            disease_aliases=("nephrotic syndrome, type 20", "NPHS20"),
        )
    )

    assert result.recommended_value == "causative"
    assert result.support_score >= 0.75
    assert result.requires_review is False


def test_score_candidate_support_treats_functional_model_causation_as_causative() -> None:
    result = score_candidate_support(
        _verification_input(
            source_snippet=(
                "MUT AP1G1 mRNA injection causes significant developmental abnormalities "
                "(32-47%) vs controls (1-3%), supporting a causative relationship."
            ),
            target_gene="AP1G1",
            target_disease="complex neurodevelopmental disorder",
            disease_aliases=("complex neurodevelopmental disorder", "Usmani-Riazuddin syndrome"),
        )
    )

    assert result.recommended_value == "causative"
    assert result.support_score >= 0.7
    assert result.requires_review is False


def test_score_candidate_support_marks_unclear_pathogenic_link_as_uncertain() -> None:
    result = score_candidate_support(
        _verification_input(
            candidate_value="associated",
            source_snippet=(
                "Whether this represents a pathogenic link or an incidental finding remains unclear."
            ),
        )
    )

    assert result.recommended_value == "uncertain"
    assert result.requires_review is True


def test_score_candidate_support_detects_refuting_relationship_language() -> None:
    result = score_candidate_support(
        _verification_input(
            candidate_value="causative",
            source_snippet=(
                "The study found no evidence that TLR5 is associated with systemic "
                "lupus erythematosus and refuted a causal relationship."
            ),
        )
    )

    assert result.recommended_value == "refuted"
    assert result.contradiction_score >= 0.7
    assert result.requires_review is True


def test_score_candidate_support_distinguishes_disputed_from_refuted() -> None:
    result = score_candidate_support(
        _verification_input(
            candidate_value="associated",
            source_snippet=(
                "The clinical evidence remains disputed because reports conflict and "
                "the gene-disease relationship is unresolved."
            ),
        )
    )

    assert result.recommended_value == "disputed"
    assert result.contradiction_score == 0.0
    assert result.requires_review is True


def test_score_candidate_support_uses_uncertain_for_might_be_due_language() -> None:
    result = score_candidate_support(
        _verification_input(
            candidate_value="associated",
            source_snippet="This effect might be due to its founder effect in this locality.",
            target_gene="ABCC8",
            target_disease="maturity-onset diabetes of the young",
            disease_aliases=("maturity-onset diabetes of the young", "MODY12"),
        )
    )

    assert result.recommended_value == "uncertain"
    assert result.requires_review is True


def test_score_candidate_support_penalizes_non_target_disease_lists() -> None:
    result = score_candidate_support(
        _verification_input(
            field_id="B.disease_diagnosis",
            candidate_value="influenza",
            source_snippet=(
                "TLR5 has been discussed across influenza, RSV, COVID-19, Crohn's disease, "
                "and bacterial infections in broad immune surveillance reviews."
            ),
        )
    )

    assert result.target_specificity_score < 0.5
    assert result.support_score < 0.5
    assert result.requires_review is True


def test_score_candidate_support_refutes_predicted_associated_gene_lists() -> None:
    result = score_candidate_support(
        _verification_input(
            candidate_value="associated",
            source_snippet="Predicted epilepsy associated genes",
            source_precision="ambiguous",
            target_gene="GENE",
            target_disease="epilepsy",
            disease_aliases=("epilepsy",),
        )
    )

    assert result.recommended_value == "disputed"
    assert result.requires_review is False


def test_score_candidate_support_marks_predicted_targets_as_disputed() -> None:
    result = score_candidate_support(
        _verification_input(
            candidate_value="associated",
            source_snippet=(
                "some of the targets predicted for it included several BMP receptors involved in PAH"
            ),
            source_precision="corrected",
            target_gene="BMPR2",
            target_disease="pulmonary arterial hypertension",
            disease_aliases=("pulmonary arterial hypertension", "PAH"),
        )
    )

    assert result.recommended_value == "disputed"
    assert result.requires_review is True


def test_score_candidate_support_treats_bare_association_as_uncertain() -> None:
    result = score_candidate_support(
        _verification_input(
            candidate_value="associated",
            source_snippet="associated with ALS",
            target_gene="LGALSL",
            target_disease="amyotrophic lateral sclerosis",
            disease_aliases=("amyotrophic lateral sclerosis", "ALS"),
        )
    )

    assert result.recommended_value == "uncertain"


def test_score_candidate_support_treats_related_gene_list_as_uncertain() -> None:
    result = score_candidate_support(
        _verification_input(
            candidate_value="causative",
            source_snippet=(
                "Among the 15 associated variants, 10 were located in genes previously "
                "shown to be related to ALS: SOD1, CFAP410, NEK1, KIF5A, FUS and TBK1."
            ),
            target_gene="CFAP410",
            target_disease="amyotrophic lateral sclerosis",
            disease_aliases=("amyotrophic lateral sclerosis", "ALS"),
        )
    )

    assert result.recommended_value == "uncertain"


def test_score_candidate_support_does_not_refute_without_negative_source_evidence() -> None:
    result = score_candidate_support(
        _verification_input(
            candidate_value="associated",
            source_snippet=(
                "CHRNA7 have been reported to be associated with neuropsychiatric "
                "phenotypes including epilepsy."
            ),
            target_gene="CHRNA7",
            target_disease="epilepsy",
            disease_aliases=("epilepsy",),
        )
    )

    assert result.recommended_value != "refuted"



def test_score_candidate_support_uses_uncertain_for_indirect_weak_relationship_evidence() -> None:
    result = score_candidate_support(
        _verification_input(
            candidate_value="associated",
            source_snippet=(
                "This evidence suggests that transcriptional repression of these polarity "
                "regulators may contribute to TOF pathogenesis."
            ),
            target_gene="GJA1",
            target_disease="congenital heart disease",
            disease_aliases=("congenital heart disease", "TOF"),
        )
    )

    assert result.recommended_value == "uncertain"
    assert 0.5 <= result.support_score < 0.6
    assert result.requires_review is True
