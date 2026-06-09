"""Tests for ACMG-oriented evidence value normalization."""
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


def test_coordinate_only_value_is_rejected_for_hgvs_g() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize([_item("A.variant_hgvs_g", "chr6_44270253")])

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].field_id == "A.variant_hgvs_g"
    assert issues[0].issue_type.value == "invalid_hgvs"


def test_reference_sequence_does_not_accept_coordinate_only_value() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize([_item("A.reference_sequence", "chr6_44270253")])

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].field_id == "A.reference_sequence"


def test_valid_hgvs_g_is_preserved() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize([_item("A.variant_hgvs_g", "NC_000006.12:g.44270253G>A")])

    assert items[0].status == EvidenceStatus.FOUND
    assert items[0].value == "NC_000006.12:g.44270253G>A"
    assert issues == []


def test_valid_hgvs_g_indel_dup_forms_are_preserved() -> None:
    values = [
        "NC_000006.12:g.44270253del",
        "NC_000006.12:g.44270253_44270254insA",
        "NC_000006.12:g.44270253dup",
        "NC_000006.12:g.44270253_44270260inv",
    ]

    items, issues = AcmgEvidenceValueNormalizer().normalize([
        _item("A.variant_hgvs_g", value) for value in values
    ])

    assert [item.value for item in items] == values
    assert issues == []


def test_lowercase_hgvs_g_is_rejected() -> None:
    items, issues = AcmgEvidenceValueNormalizer().normalize([
        _item("A.variant_hgvs_g", "nc_000006.12:g.44270253g>a"),
    ])

    assert items[0].status == EvidenceStatus.NOT_FOUND
    assert items[0].value is None
    assert issues[0].issue_type.value == "invalid_hgvs"


def test_rejected_item_clears_stale_assigned_codes() -> None:
    item = _item("A.variant_hgvs_g", "chr6_44270253").model_copy(update={
        "assigned_acmg_codes": ["PS1"],
        "assigned_clingen_modules": ["variant_evidence"],
    })

    items, _ = AcmgEvidenceValueNormalizer().normalize([item])

    assert items[0].assigned_acmg_codes == []
    assert items[0].assigned_clingen_modules == []


def test_de_novo_status_is_normalized_to_enum_value() -> None:
    inputs = [
        _item("C.de_novo_status", "not de novo"),
        _item("C.de_novo_status", False),
        _item("C.de_novo_status", 0),
    ]

    items, issues = AcmgEvidenceValueNormalizer().normalize(inputs)

    assert [item.value for item in items] == ["not_de_novo", "not_de_novo", "not_de_novo"]
    assert [issue.issue_type.value for issue in issues] == [
        "value_normalized",
        "value_normalized",
        "value_normalized",
    ]


def test_consanguinity_preserves_detail_and_normalizes_status() -> None:
    items, _ = AcmgEvidenceValueNormalizer().normalize([
        _item("B.consanguinity", "first-degree maternal cousins"),
    ])

    assert items[0].value == "present:first-degree maternal cousins"


def test_consanguinity_unknown_is_not_marked_present() -> None:
    inputs = [
        _item("B.consanguinity", "unknown"),
        _item("B.consanguinity", "N/A"),
        _item("B.consanguinity", "not applicable"),
    ]

    items, _ = AcmgEvidenceValueNormalizer().normalize(inputs)

    assert [item.value for item in items] == ["unknown", "unknown", "unknown"]


def test_obligate_carriers_numeric_and_parent_text_normalize_to_count() -> None:
    inputs = [_item("C.obligate_carriers", "parents"), _item("C.obligate_carriers", True)]

    items, _ = AcmgEvidenceValueNormalizer().normalize(inputs)

    assert [item.value for item in items] == [2, 2]
