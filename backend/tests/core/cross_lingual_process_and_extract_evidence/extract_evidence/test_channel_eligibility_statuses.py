"""Tests for channel eligibility statuses in catalog backfill.

Verifies that:
- Fields excluded by channel get status NOT_APPLICABLE (not NOT_FOUND).
- Fields excluded by target/source logic get status NOT_ATTEMPTED.
- Eligible but absent fields remain NOT_FOUND.
- NOT_APPLICABLE/NOT_ATTEMPTED items are excluded from evidence chains.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import (
    EVIDENCE_FIELD_SPECS,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import (
    EvidenceChainBuilder,
    EvidenceItemNormalizer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(field_id: str, status: EvidenceStatus = EvidenceStatus.FOUND, value: str = "test") -> EvidenceItem:
    """Create a minimal EvidenceItem for testing."""
    spec = next(s for s in EVIDENCE_FIELD_SPECS if s.field_id == field_id)
    return EvidenceItem(
        field_id=field_id,
        category=spec.category_id,
        field_name=spec.field_name,
        status=status,
        value=value,
        confidence=0.8,
    )


def _get_status_by_field(items: list[EvidenceItem], field_id: str) -> EvidenceStatus:
    """Get the status of a specific field from a list of evidence items."""
    for item in items:
        if item.field_id == field_id:
            return item.status
    raise ValueError(f"Field {field_id} not found in items")


def _base_item() -> EvidenceItem:
    """Create a base item to trigger group normalization."""
    return _make_item("A.gene_symbol", EvidenceStatus.FOUND, "GLA")


# ---------------------------------------------------------------------------
# Test: case_report channel - functional-only field becomes not_applicable
# ---------------------------------------------------------------------------


def test_case_report_excludes_functional_field_as_not_applicable():
    """F.assay_type (category F) is not extractable from case_report channel."""
    normalizer = EvidenceItemNormalizer()
    items = [_base_item()]
    channel_excluded = frozenset({spec.field_id for spec in EVIDENCE_FIELD_SPECS if spec.category_id == "F"})
    normalized = normalizer.normalize_grouped(items, channel_excluded_field_ids=channel_excluded)
    assert _get_status_by_field(normalized, "F.assay_type") == EvidenceStatus.NOT_APPLICABLE
    assert _get_status_by_field(normalized, "A.gene_symbol") == EvidenceStatus.FOUND


# ---------------------------------------------------------------------------
# Test: functional_study channel - case-only field becomes not_applicable
# ---------------------------------------------------------------------------


def test_functional_study_excludes_case_field_as_not_applicable():
    """B.clinical_phenotypes (category B) is not extractable from functional_study channel."""
    normalizer = EvidenceItemNormalizer()
    items = [_base_item()]
    channel_excluded = frozenset({spec.field_id for spec in EVIDENCE_FIELD_SPECS if spec.category_id in ("B", "C")})
    normalized = normalizer.normalize_grouped(items, channel_excluded_field_ids=channel_excluded)
    assert _get_status_by_field(normalized, "B.clinical_phenotypes") == EvidenceStatus.NOT_APPLICABLE
    assert _get_status_by_field(normalized, "C.de_novo_status") == EvidenceStatus.NOT_APPLICABLE
    assert _get_status_by_field(normalized, "F.assay_type") == EvidenceStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Test: cohort_study channel - functional field becomes not_applicable
# ---------------------------------------------------------------------------


def test_cohort_study_excludes_functional_field_as_not_applicable():
    """F.assay_type (category F) is not extractable from cohort_study channel."""
    normalizer = EvidenceItemNormalizer()
    items = [_base_item()]
    channel_excluded = frozenset({spec.field_id for spec in EVIDENCE_FIELD_SPECS if spec.category_id in ("F", "I")})
    normalized = normalizer.normalize_grouped(items, channel_excluded_field_ids=channel_excluded)
    assert _get_status_by_field(normalized, "F.assay_type") == EvidenceStatus.NOT_APPLICABLE
    assert _get_status_by_field(normalized, "D.allele_frequency") == EvidenceStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Test: unknown channel - same field remains not_found (permissive)
# ---------------------------------------------------------------------------


def test_unknown_channel_keeps_field_as_not_found():
    """Unknown channel is permissive — all fields eligible, absent fields are NOT_FOUND."""
    normalizer = EvidenceItemNormalizer()
    items = [_base_item()]
    normalized = normalizer.normalize_grouped(items)
    assert _get_status_by_field(normalized, "F.assay_type") == EvidenceStatus.NOT_FOUND
    assert _get_status_by_field(normalized, "A.gene_symbol") == EvidenceStatus.FOUND
    assert _get_status_by_field(normalized, "D.allele_frequency") == EvidenceStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Test: eligible but absent - remains not_found
# ---------------------------------------------------------------------------


def test_eligible_but_absent_field_remains_not_found():
    """Fields eligible for the channel but absent from extraction remain NOT_FOUND."""
    normalizer = EvidenceItemNormalizer()
    items = [_make_item("A.gene_symbol", EvidenceStatus.FOUND, "GLA")]
    normalized = normalizer.normalize_grouped(items)
    assert _get_status_by_field(normalized, "A.gene_symbol") == EvidenceStatus.FOUND
    assert _get_status_by_field(normalized, "A.variant_hgvs_c") == EvidenceStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# Test: not_applicable items are not included in evidence chains
# ---------------------------------------------------------------------------


def test_not_applicable_items_excluded_from_evidence_chains():
    """NOT_APPLICABLE items should not be included as extracted evidence chains."""
    builder = EvidenceChainBuilder()

    found_item = _make_item("A.gene_symbol", EvidenceStatus.FOUND, "GLA")
    found_item = found_item.model_copy(
        update={"group_id": "test-group", "source": MagicMock(source_precision=MagicMock(value="exact"))}
    )

    not_applicable_item = _make_item("F.assay_type", EvidenceStatus.NOT_APPLICABLE, None)
    not_applicable_item = not_applicable_item.model_copy(update={"group_id": "test-group"})

    disease_item = _make_item("B.disease_diagnosis", EvidenceStatus.FOUND, "Fabry disease")
    disease_item = disease_item.model_copy(
        update={"group_id": "test-group", "source": MagicMock(source_precision=MagicMock(value="exact"))}
    )

    variant_item = _make_item("A.variant_hgvs_c", EvidenceStatus.FOUND, "c.1000G>A")
    variant_item = variant_item.model_copy(
        update={"group_id": "test-group", "source": MagicMock(source_precision=MagicMock(value="exact"))}
    )

    items = [found_item, not_applicable_item, disease_item, variant_item]
    chains = builder.build(items, [])

    assert len(chains) == 1
    chain = chains[0]
    assert "F.assay_type" not in chain.evidence_field_ids
    assert "A.gene_symbol" in chain.evidence_field_ids


# ---------------------------------------------------------------------------
# Test: target_excluded fields become not_attempted
# ---------------------------------------------------------------------------


def test_target_excluded_field_becomes_not_attempted():
    """Fields excluded by target/source eligibility get NOT_ATTEMPTED status."""
    normalizer = EvidenceItemNormalizer()
    items = [_base_item()]
    target_excluded = frozenset({"D.allele_frequency"})
    normalized = normalizer.normalize_grouped(items, target_excluded_field_ids=target_excluded)
    assert _get_status_by_field(normalized, "D.allele_frequency") == EvidenceStatus.NOT_ATTEMPTED
    assert _get_status_by_field(normalized, "A.gene_symbol") == EvidenceStatus.FOUND


# ---------------------------------------------------------------------------
# Test: channel_excluded takes priority over target_excluded
# ---------------------------------------------------------------------------


def test_channel_excluded_takes_priority_over_target_excluded():
    """If a field is in both channel_excluded and target_excluded, NOT_APPLICABLE wins."""
    normalizer = EvidenceItemNormalizer()
    items = [_base_item()]
    channel_excluded = frozenset({"F.assay_type"})
    target_excluded = frozenset({"F.assay_type", "D.allele_frequency"})
    normalized = normalizer.normalize_grouped(
        items, channel_excluded_field_ids=channel_excluded, target_excluded_field_ids=target_excluded
    )
    assert _get_status_by_field(normalized, "F.assay_type") == EvidenceStatus.NOT_APPLICABLE
    assert _get_status_by_field(normalized, "D.allele_frequency") == EvidenceStatus.NOT_ATTEMPTED
