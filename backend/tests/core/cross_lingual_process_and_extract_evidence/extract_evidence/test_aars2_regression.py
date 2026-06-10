"""Regression tests for AARS2 extraction review findings."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.normalization import (
    AcmgEvidenceValueNormalizer,
)


def _found(field_id: str, value: object, confidence: float = 0.9) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=confidence,
        group_id="gene=AARS2|variant=__missing__",
    )


def test_aars2_review_errors_are_normalized_or_rejected() -> None:
    items = [
        _found("A.gene_symbol", "AARS2", 0.8),
        _found("A.gene_symbol", "AARS2", 0.9),
        _found("A.variant_hgvs_g", "chr6_44270253"),
        _found("A.reference_sequence", "chr6_44270253"),
        _found("A.variant_legacy_name", "chr6_44270253"),
        _found("A.splice_or_synonymous_effect", "flanking the splice site acceptor sequence of exon 18"),
        _found("B.age_of_onset", "started sitting with support at the age of 15 months"),
        _found("B.age_current_or_last_followup", "10 years"),
        _found("B.age_current_or_last_followup", "10 years"),
        _found("F.functional_result", "functional analysis by in silico tools"),
        _found("E.prediction_tools_list", "in silico tools"),
        _found("C.de_novo_status", "not de novo"),
        _found("B.consanguinity", "first-degree maternal cousins"),
        _found("C.obligate_carriers", "parents"),
    ]

    normalized, issues = AcmgEvidenceValueNormalizer().normalize(items)
    by_field = {item.field_id: item for item in normalized}

    assert by_field["A.gene_symbol"].confidence == 0.9
    assert by_field["A.variant_hgvs_g"].status == EvidenceStatus.NOT_FOUND
    assert by_field["A.reference_sequence"].status == EvidenceStatus.NOT_FOUND
    assert by_field["A.variant_legacy_name"].status == EvidenceStatus.NOT_FOUND
    assert by_field["B.age_of_onset"].status == EvidenceStatus.NOT_FOUND
    assert by_field["F.functional_result"].status == EvidenceStatus.NOT_FOUND
    assert by_field["E.prediction_tools_list"].status == EvidenceStatus.NOT_FOUND
    assert by_field["C.de_novo_status"].value == "not_de_novo"
    assert by_field["B.consanguinity"].value == "present:first-degree maternal cousins"
    assert by_field["C.obligate_carriers"].value == 2
    assert len([item for item in normalized if item.field_id == "B.age_current_or_last_followup"]) == 1
    assert len(issues) >= 8
