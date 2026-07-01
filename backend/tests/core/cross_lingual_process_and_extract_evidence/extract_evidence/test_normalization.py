"""Tests for gene symbol pre-normalization in evidence value normalization."""

from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.normalization import (
    AcmgEvidenceValueNormalizer,
)


def _item(field_id: str, value: object) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.9,
    )


def test_gene_symbol_lowercased_is_uppercased() -> None:
    items, _ = AcmgEvidenceValueNormalizer().normalize([_item("A.gene_symbol", "brca1")])
    assert items[0].value == "BRCA1"


def test_gene_symbol_with_whitespace_is_trimmed() -> None:
    items, _ = AcmgEvidenceValueNormalizer().normalize([_item("A.gene_symbol", "  BRCA1  ")])
    assert items[0].value == "BRCA1"


def test_gene_symbol_fullwidth_is_nfkc_normalized() -> None:
    items, _ = AcmgEvidenceValueNormalizer().normalize([_item("A.gene_symbol", "ｂｒｃａ２")])
    assert items[0].value == "BRCA2"


def test_gene_symbol_list_values_are_uppercased() -> None:
    items, _ = AcmgEvidenceValueNormalizer().normalize([_item("A.gene_aliases", ["brca1", "tp53"])])
    assert items[0].value == ["BRCA1", "TP53"]


def test_non_gene_fields_are_not_uppercased() -> None:
    items, _ = AcmgEvidenceValueNormalizer().normalize([_item("B.disease_name", "Rett syndrome")])
    assert items[0].value == "Rett syndrome"
