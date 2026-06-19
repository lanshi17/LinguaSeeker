from collections import Counter

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import (
    EVIDENCE_FIELD_SPECS,
    get_field_spec,
)


def test_catalog_has_expected_category_counts():
    counts = Counter(spec.category_id for spec in EVIDENCE_FIELD_SPECS)
    assert counts == {
        "A": 22,
        "B": 19,
        "C": 17,
        "D": 8,
        "E": 7,
        "F": 24,
        "G": 15,
        "H": 9,
        "I": 16,
        "J": 6,
        "K": 23,
    }
    assert sum(counts.values()) == 166


def test_catalog_field_ids_are_unique():
    field_ids = [spec.field_id for spec in EVIDENCE_FIELD_SPECS]
    assert len(field_ids) == len(set(field_ids))


def test_catalog_lookup_returns_spec():
    spec = get_field_spec("A.variant_type")
    assert spec.field_id == "A.variant_type"
    assert "PVS1" in spec.acmg_codes
