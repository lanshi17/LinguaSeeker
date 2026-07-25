"""Tests for document evidence channel contracts."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.core.evidence_extraction.domain.catalog import (
    EVIDENCE_FIELD_SPECS,
)
from src.core.evidence_extraction.domain.channel_contracts import (
    ChannelFieldEligibility,
    DocumentChannelClassification,
    DocumentEvidenceChannel,
    FieldEligibilityReason,
    channel_categories,
    compute_channel_eligibility,
)


EXPECTED_CHANNEL_CATEGORIES: dict[DocumentEvidenceChannel, frozenset[str]] = {
    DocumentEvidenceChannel.CASE_REPORT: frozenset({"A", "B", "C", "H", "J"}),
    DocumentEvidenceChannel.FUNCTIONAL_STUDY: frozenset({"A", "E", "F", "I", "H", "J"}),
    DocumentEvidenceChannel.COHORT_STUDY: frozenset({"A", "D", "G", "H", "J"}),
}

_NON_CURATION_CATEGORIES = frozenset(spec.category_id for spec in EVIDENCE_FIELD_SPECS if spec.category_id != "K")


def _field_ids_for_categories(categories: frozenset[str]) -> frozenset[str]:
    return frozenset(spec.field_id for spec in EVIDENCE_FIELD_SPECS if spec.category_id in categories)


def _all_field_ids() -> frozenset[str]:
    return frozenset(spec.field_id for spec in EVIDENCE_FIELD_SPECS)


def _classification(channels, **kwargs) -> DocumentChannelClassification:
    return DocumentChannelClassification(
        selected_channels=list(channels),
        confidence=kwargs.get("confidence", 0.9),
        rationale=kwargs.get("rationale", "case report describing a single proband"),
        supporting_block_ids=kwargs.get("supporting_block_ids", ["blk-1", "blk-2"]),
    )


# -- enum ----------------------------------------------------------------


def test_channel_enum_has_required_members() -> None:
    values = {ch.value for ch in DocumentEvidenceChannel}
    assert values == {
        "case_report",
        "functional_study",
        "cohort_study",
        "mixed",
        "unknown",
    }


# -- channel_categories --------------------------------------------------


@pytest.mark.parametrize("channel,expected", list(EXPECTED_CHANNEL_CATEGORIES.items()))
def test_channel_categories_for_concrete_channels(channel: DocumentEvidenceChannel, expected: frozenset[str]) -> None:
    assert channel_categories(channel) == expected


def test_mixed_channel_categories_is_union_of_all_concrete() -> None:
    mixed = channel_categories(DocumentEvidenceChannel.MIXED)
    expected = frozenset().union(*EXPECTED_CHANNEL_CATEGORIES.values())
    assert mixed == expected
    assert mixed == _NON_CURATION_CATEGORIES


def test_unknown_channel_categories_is_all_single_paper() -> None:
    assert channel_categories(DocumentEvidenceChannel.UNKNOWN) == _NON_CURATION_CATEGORIES


def test_every_channel_excludes_curation_category() -> None:
    for channel in DocumentEvidenceChannel:
        assert "K" not in channel_categories(channel)


# -- DocumentChannelClassification ---------------------------------------


def test_classification_round_trips_required_fields() -> None:
    cls = _classification([DocumentEvidenceChannel.CASE_REPORT])
    assert cls.selected_channels == [DocumentEvidenceChannel.CASE_REPORT]
    assert cls.confidence == 0.9
    assert cls.rationale
    assert cls.supporting_block_ids == ["blk-1", "blk-2"]


def test_classification_confidence_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        _classification([DocumentEvidenceChannel.CASE_REPORT], confidence=-0.1)
    with pytest.raises(ValidationError):
        _classification([DocumentEvidenceChannel.CASE_REPORT], confidence=1.5)


def test_classification_requires_at_least_one_channel() -> None:
    with pytest.raises(ValidationError):
        DocumentChannelClassification(selected_channels=[], confidence=0.9, rationale="x")


def test_classification_deduplicates_selected_channels() -> None:
    cls = _classification([DocumentEvidenceChannel.CASE_REPORT, DocumentEvidenceChannel.CASE_REPORT])
    assert cls.selected_channels == [DocumentEvidenceChannel.CASE_REPORT]


def test_classification_drops_unknown_when_concrete_present() -> None:
    cls = _classification([DocumentEvidenceChannel.UNKNOWN, DocumentEvidenceChannel.CASE_REPORT])
    assert cls.selected_channels == [DocumentEvidenceChannel.CASE_REPORT]


def test_classification_keeps_unknown_when_alone() -> None:
    cls = _classification([DocumentEvidenceChannel.UNKNOWN])
    assert cls.selected_channels == [DocumentEvidenceChannel.UNKNOWN]


def test_effective_channels_concrete_returned_as_is() -> None:
    cls = _classification([DocumentEvidenceChannel.CASE_REPORT, DocumentEvidenceChannel.FUNCTIONAL_STUDY])
    assert cls.effective_channels == [
        DocumentEvidenceChannel.CASE_REPORT,
        DocumentEvidenceChannel.FUNCTIONAL_STUDY,
    ]


def test_effective_channels_bare_mixed_expands_to_all_concrete() -> None:
    cls = _classification([DocumentEvidenceChannel.MIXED])
    assert set(cls.effective_channels) == {
        DocumentEvidenceChannel.CASE_REPORT,
        DocumentEvidenceChannel.FUNCTIONAL_STUDY,
        DocumentEvidenceChannel.COHORT_STUDY,
    }


def test_effective_channels_unknown_is_empty() -> None:
    cls = _classification([DocumentEvidenceChannel.UNKNOWN])
    assert cls.effective_channels == []


# -- compute_channel_eligibility -----------------------------------------


@pytest.mark.parametrize("channel", list(EXPECTED_CHANNEL_CATEGORIES))
def test_single_channel_eligibility_matches_category_set(
    channel: DocumentEvidenceChannel,
) -> None:
    eligibility = compute_channel_eligibility(_classification([channel]))
    assert eligibility.channels == [channel]
    assert eligibility.allowed_field_ids == _field_ids_for_categories(EXPECTED_CHANNEL_CATEGORIES[channel])


def test_case_report_excludes_functional_and_population_fields() -> None:
    eligibility = compute_channel_eligibility(_classification([DocumentEvidenceChannel.CASE_REPORT]))
    assert "F.assay_id" not in eligibility.allowed_field_ids
    assert "D.allele_frequency" not in eligibility.allowed_field_ids
    assert "G.odds_ratio" not in eligibility.allowed_field_ids
    assert "B.disease_diagnosis" in eligibility.allowed_field_ids
    assert "C.lod_score" in eligibility.allowed_field_ids


def test_functional_study_includes_functional_and_computational_fields() -> None:
    eligibility = compute_channel_eligibility(_classification([DocumentEvidenceChannel.FUNCTIONAL_STUDY]))
    assert "F.assay_id" in eligibility.allowed_field_ids
    assert "I.animal_model_type" in eligibility.allowed_field_ids
    assert "E.conservation_score" in eligibility.allowed_field_ids
    assert "B.case_count" not in eligibility.allowed_field_ids
    assert "D.allele_frequency" not in eligibility.allowed_field_ids


def test_cohort_study_includes_population_and_case_control_fields() -> None:
    eligibility = compute_channel_eligibility(_classification([DocumentEvidenceChannel.COHORT_STUDY]))
    assert "D.allele_frequency" in eligibility.allowed_field_ids
    assert "G.odds_ratio" in eligibility.allowed_field_ids
    assert "F.assay_id" not in eligibility.allowed_field_ids
    assert "C.lod_score" not in eligibility.allowed_field_ids


def test_curation_fields_always_excluded() -> None:
    eligibility = compute_channel_eligibility(_classification([DocumentEvidenceChannel.MIXED]))
    k_fields = {spec.field_id for spec in EVIDENCE_FIELD_SPECS if spec.category_id == "K"}
    assert k_fields.isdisjoint(eligibility.allowed_field_ids)
    assert k_fields <= eligibility.excluded_field_ids


@pytest.mark.parametrize(
    "channel",
    [
        DocumentEvidenceChannel.CASE_REPORT,
        DocumentEvidenceChannel.FUNCTIONAL_STUDY,
        DocumentEvidenceChannel.COHORT_STUDY,
        DocumentEvidenceChannel.MIXED,
        DocumentEvidenceChannel.UNKNOWN,
    ],
)
def test_allowed_plus_excluded_partitions_full_catalog(
    channel: DocumentEvidenceChannel,
) -> None:
    eligibility = compute_channel_eligibility(_classification([channel]))
    assert eligibility.allowed_field_ids.isdisjoint(eligibility.excluded_field_ids)
    assert eligibility.allowed_field_ids | eligibility.excluded_field_ids == _all_field_ids()


def test_reasons_cover_every_catalog_field() -> None:
    eligibility = compute_channel_eligibility(_classification([DocumentEvidenceChannel.CASE_REPORT]))
    assert len(eligibility.reasons) == len(EVIDENCE_FIELD_SPECS)
    assert {r.field_id for r in eligibility.reasons} == _all_field_ids()
    eligible = [r for r in eligibility.reasons if r.eligible]
    ineligible = [r for r in eligibility.reasons if not r.eligible]
    assert {r.field_id for r in eligible} == eligibility.allowed_field_ids
    assert {r.field_id for r in ineligible} == eligibility.excluded_field_ids


def test_eligible_reasons_cite_covering_channels_for_concrete_classification() -> None:
    eligibility = compute_channel_eligibility(_classification([DocumentEvidenceChannel.CASE_REPORT]))
    for reason in eligibility.reasons:
        if reason.eligible:
            assert reason.channels == [DocumentEvidenceChannel.CASE_REPORT]


def test_unknown_classification_falls_back_to_all_single_paper_fields() -> None:
    eligibility = compute_channel_eligibility(_classification([DocumentEvidenceChannel.UNKNOWN]))
    assert eligibility.channels == [DocumentEvidenceChannel.UNKNOWN]
    assert eligibility.allowed_field_ids == _field_ids_for_categories(_NON_CURATION_CATEGORIES)
    for reason in eligibility.reasons:
        if reason.eligible:
            assert reason.channels == []


# -- mixed-channel behavior ----------------------------------------------


def test_mixed_is_superset_of_each_single_channel() -> None:
    mixed = compute_channel_eligibility(_classification([DocumentEvidenceChannel.MIXED]))
    for channel in EXPECTED_CHANNEL_CATEGORIES:
        single = compute_channel_eligibility(_classification([channel]))
        assert single.allowed_field_ids <= mixed.allowed_field_ids


def test_two_concrete_channels_yields_union_of_their_fields() -> None:
    eligibility = compute_channel_eligibility(
        _classification([DocumentEvidenceChannel.CASE_REPORT, DocumentEvidenceChannel.FUNCTIONAL_STUDY])
    )
    expected = _field_ids_for_categories(
        EXPECTED_CHANNEL_CATEGORIES[DocumentEvidenceChannel.CASE_REPORT]
        | EXPECTED_CHANNEL_CATEGORIES[DocumentEvidenceChannel.FUNCTIONAL_STUDY]
    )
    assert eligibility.allowed_field_ids == expected
    assert set(eligibility.channels) == {
        DocumentEvidenceChannel.CASE_REPORT,
        DocumentEvidenceChannel.FUNCTIONAL_STUDY,
    }


def test_bare_mixed_equals_all_concrete_union() -> None:
    bare = compute_channel_eligibility(_classification([DocumentEvidenceChannel.MIXED]))
    explicit = compute_channel_eligibility(
        _classification(
            [
                DocumentEvidenceChannel.CASE_REPORT,
                DocumentEvidenceChannel.FUNCTIONAL_STUDY,
                DocumentEvidenceChannel.COHORT_STUDY,
            ]
        )
    )
    assert bare.allowed_field_ids == explicit.allowed_field_ids
    assert bare.allowed_field_ids == _field_ids_for_categories(_NON_CURATION_CATEGORIES)
    assert set(bare.channels) == {
        DocumentEvidenceChannel.CASE_REPORT,
        DocumentEvidenceChannel.FUNCTIONAL_STUDY,
        DocumentEvidenceChannel.COHORT_STUDY,
    }


def test_mixed_field_covered_by_multiple_channels_lists_all() -> None:
    eligibility = compute_channel_eligibility(
        _classification([DocumentEvidenceChannel.CASE_REPORT, DocumentEvidenceChannel.FUNCTIONAL_STUDY])
    )
    # A and H are common to both channels.
    a_reason = next(r for r in eligibility.reasons if r.field_id == "A.gene_symbol")
    assert set(a_reason.channels) == {
        DocumentEvidenceChannel.CASE_REPORT,
        DocumentEvidenceChannel.FUNCTIONAL_STUDY,
    }
    # B is case_report-only.
    b_reason = next(r for r in eligibility.reasons if r.field_id == "B.disease_diagnosis")
    assert b_reason.channels == [DocumentEvidenceChannel.CASE_REPORT]


# -- serialization -------------------------------------------------------


def test_classification_json_round_trip() -> None:
    cls = _classification(
        [DocumentEvidenceChannel.CASE_REPORT, DocumentEvidenceChannel.FUNCTIONAL_STUDY],
        confidence=0.77,
        rationale="hybrid paper: case report with functional assay",
        supporting_block_ids=["b1", "b2", "b3"],
    )
    restored = DocumentChannelClassification.model_validate_json(cls.model_dump_json())
    assert restored.selected_channels == cls.selected_channels
    assert restored.confidence == cls.confidence
    assert restored.rationale == cls.rationale
    assert restored.supporting_block_ids == cls.supporting_block_ids


def test_field_eligibility_reason_json_round_trip() -> None:
    reason = FieldEligibilityReason(
        field_id="F.assay_id",
        eligible=True,
        category_id="F",
        channels=[DocumentEvidenceChannel.FUNCTIONAL_STUDY],
        reason="category F covered by channel(s): functional_study",
    )
    restored = FieldEligibilityReason.model_validate_json(reason.model_dump_json())
    assert restored == reason


def test_channel_field_eligibility_json_round_trip_preserves_field_sets() -> None:
    eligibility = compute_channel_eligibility(_classification([DocumentEvidenceChannel.FUNCTIONAL_STUDY]))
    restored = ChannelFieldEligibility.model_validate_json(eligibility.model_dump_json())
    assert restored.channels == eligibility.channels
    assert restored.allowed_field_ids == eligibility.allowed_field_ids
    assert restored.excluded_field_ids == eligibility.excluded_field_ids
    assert len(restored.reasons) == len(eligibility.reasons)


def test_classification_model_dump_json_mode_serializes_enum_values() -> None:
    cls = _classification([DocumentEvidenceChannel.MIXED])
    dumped = cls.model_dump(mode="json")
    assert dumped["selected_channels"] == ["mixed"]
    # Must be plain JSON-serializable (no enum objects leak through).
    json.dumps(dumped)
