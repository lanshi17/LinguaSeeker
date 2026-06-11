"""Tests for evidence role routing."""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceRole,
    EvidenceStatus,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.role_routing import (
    EvidenceRoleRouter,
)


def _item(field_id: str, value: str, role: EvidenceRole) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.9,
        evidence_role=role,
    )


def test_role_router_keeps_only_primary_for_extraction_flow() -> None:
    primary, phenotype, discarded = EvidenceRoleRouter().route([
        _item("A.gene_symbol", "AARS2", EvidenceRole.PRIMARY),
        _item("B.disease_diagnosis", "COXPD8", EvidenceRole.PHENOTYPE),
        _item("B.disease_diagnosis", "Anti-NF155 autoimmune nodopathy", EvidenceRole.COMPARATOR),
        _item("A.gene_symbol", "CFTR", EvidenceRole.CONTEXT),
    ])

    assert [item.value for item in primary] == ["AARS2"]
    assert [item.value for item in phenotype] == ["COXPD8"]
    assert [item.value for item in discarded] == [
        "Anti-NF155 autoimmune nodopathy",
        "CFTR",
    ]


def test_role_router_preserves_input_order() -> None:
    items = [
        _item("A.gene_symbol", "GENE1", EvidenceRole.PRIMARY),
        _item("A.gene_symbol", "GENE2", EvidenceRole.PRIMARY),
        _item("B.disease_diagnosis", "D1", EvidenceRole.PHENOTYPE),
        _item("B.disease_diagnosis", "D2", EvidenceRole.PHENOTYPE),
        _item("B.disease_diagnosis", "C1", EvidenceRole.COMPARATOR),
        _item("B.disease_diagnosis", "CTX1", EvidenceRole.CONTEXT),
    ]
    primary, phenotype, discarded = EvidenceRoleRouter().route(items)

    assert [item.value for item in primary] == ["GENE1", "GENE2"]
    assert [item.value for item in phenotype] == ["D1", "D2"]
    assert [item.value for item in discarded] == ["C1", "CTX1"]


def test_role_router_handles_empty_input() -> None:
    primary, phenotype, discarded = EvidenceRoleRouter().route([])

    assert primary == []
    assert phenotype == []
    assert discarded == []
