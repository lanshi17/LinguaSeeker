"""Regression coverage for target anchoring extraction failures."""

from __future__ import annotations

from src.core.evidence_extraction.contracts import (
    EvidenceItem,
    EvidenceRole,
    EvidenceStatus,
    ExtractionTarget,
)
from src.core.evidence_extraction.stages.role_routing import (
    EvidenceRoleRouter,
)
from src.core.evidence_extraction.core import (
    TargetEntityGuard,
)


def _item(field_id: str, value: object, role: EvidenceRole = EvidenceRole.PRIMARY) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.9,
        evidence_role=role,
    )


def test_abca3_target_rejects_cftr_context_gene() -> None:
    target = ExtractionTarget(
        gene_symbol="ABCA3",
        disease_name="interstitial lung disease due to ABCA3 deficiency",
    )

    guarded = TargetEntityGuard().apply([_item("A.gene_symbol", "CFTR")], target)

    assert guarded[0].status == EvidenceStatus.CONTEXT_CONTAMINATION


def test_abca3_target_corrects_gene_list_containing_target() -> None:
    target = ExtractionTarget(
        gene_symbol="ABCA3",
        disease_name="interstitial lung disease due to ABCA3 deficiency",
    )

    guarded = TargetEntityGuard().apply([_item("A.gene_symbol", "['CFTR', 'ABCA3']")], target)

    assert guarded[0].status == EvidenceStatus.FOUND
    assert guarded[0].value == "ABCA3"


def test_aars2_syndromes_and_nodopathy_do_not_enter_primary_evidence() -> None:
    primary, phenotype, discarded = EvidenceRoleRouter().route(
        [
            _item("A.gene_symbol", "AARS2"),
            _item("B.disease_diagnosis", "COXPD8", EvidenceRole.PHENOTYPE),
            _item("B.disease_diagnosis", "LKENP", EvidenceRole.PHENOTYPE),
            _item("B.disease_diagnosis", "Anti-NF155 autoimmune nodopathy", EvidenceRole.COMPARATOR),
        ]
    )

    assert [item.value for item in primary] == ["AARS2"]
    assert [item.value for item in phenotype] == ["COXPD8", "LKENP"]
    assert [item.value for item in discarded] == ["Anti-NF155 autoimmune nodopathy"]
