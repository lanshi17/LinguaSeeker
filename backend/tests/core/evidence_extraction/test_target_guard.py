"""Tests for target entity validation."""

from __future__ import annotations

from src.core.evidence_extraction.contracts import (
    EvidenceItem,
    EvidenceStatus,
    ExtractionTarget,
)
from src.core.evidence_extraction.core import (
    TargetEntityGuard,
)


def _gene_item(value: object) -> EvidenceItem:
    return EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene symbol",
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.91,
    )


def _variant_item(value: object) -> EvidenceItem:
    return EvidenceItem(
        field_id="A.variant_hgvs_p",
        category="A",
        field_name="HGVS protein variant",
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.91,
    )


def test_target_guard_corrects_gene_list_string_when_target_present() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")

    guarded = TargetEntityGuard().apply([_gene_item("['ABCA3', 'CFTR']")], target)

    assert guarded[0].status == EvidenceStatus.FOUND
    assert guarded[0].value == "ABCA3"
    assert "list_to_target" in guarded[0].notes


def test_target_guard_marks_wrong_gene_as_context_contamination() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")

    guarded = TargetEntityGuard().apply([_gene_item("CFTR")], target)

    assert guarded[0].status == EvidenceStatus.CONTEXT_CONTAMINATION
    assert "expected ABCA3" in guarded[0].notes


def test_target_guard_returns_input_unchanged_when_no_target() -> None:
    item = _gene_item("CFTR")

    guarded = TargetEntityGuard().apply([item], None)

    assert guarded[0] is item
    assert guarded[0].status == EvidenceStatus.FOUND


def test_target_guard_preserves_assigned_acmg_codes() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")
    item = _gene_item("CFTR")
    item.assigned_acmg_codes = ["PVS1", "PS1"]

    guarded = TargetEntityGuard().apply([item], target)

    assert guarded[0].assigned_acmg_codes == []


def test_target_guard_handles_list_value_with_target() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")

    guarded = TargetEntityGuard().apply([_gene_item(["CFTR", "ABCA3"])], target)

    assert guarded[0].status == EvidenceStatus.FOUND
    assert guarded[0].value == "ABCA3"


def test_target_guard_ignores_non_gene_symbol_fields() -> None:
    target = ExtractionTarget(gene_symbol="ABCA3", disease_name="ABCA3 deficiency")
    item = EvidenceItem(
        field_id="B.disease_diagnosis",
        category="B",
        field_name="Disease diagnosis",
        status=EvidenceStatus.FOUND,
        value="Anti-NF155 autoimmune nodopathy",
        confidence=0.9,
    )

    guarded = TargetEntityGuard().apply([item], target)

    assert guarded[0] is item
    assert guarded[0].status == EvidenceStatus.FOUND


def test_target_guard_collapses_variant_alias_to_target_variant() -> None:
    target = ExtractionTarget(
        gene_symbol="MECP2",
        disease_name="Rett syndrome",
        variant_hgvs_p="p.R168X",
    )

    guarded = TargetEntityGuard().apply([_variant_item("Arg168Ter")], target)

    assert guarded[0].status == EvidenceStatus.FOUND
    assert guarded[0].value == "p.R168X"
    assert "variant_to_target" in guarded[0].notes


def test_target_guard_marks_wrong_variant_as_context_contamination() -> None:
    target = ExtractionTarget(
        gene_symbol="MECP2",
        disease_name="Rett syndrome",
        variant_hgvs_p="p.R168X",
    )

    guarded = TargetEntityGuard().apply([_variant_item("p.T158M")], target)

    assert guarded[0].status == EvidenceStatus.CONTEXT_CONTAMINATION
    assert "expected p.R168X" in guarded[0].notes
