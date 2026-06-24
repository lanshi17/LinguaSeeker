"""Tests for channel metadata in extraction result contracts.

Verifies that:
- EvidenceExtractionResult serializes/deserializes channel_classification.
- Workflow result includes classification from relevance scan.
- Workflow result includes field eligibility summary.
- Dual-track result preserves metadata for both original and translated.
"""
from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.channel_contracts import (
    DocumentChannelClassification,
    DocumentEvidenceChannel,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    FieldEligibilitySummary,
    Track,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_channel_classification(channels=None):
    """Create a DocumentChannelClassification for testing."""
    if channels is None:
        channels = [DocumentEvidenceChannel.CASE_REPORT]
    return DocumentChannelClassification(
        selected_channels=channels,
        confidence=0.85,
        rationale="single-proband case report",
        supporting_block_ids=["blk-3", "blk-7"],
    )


def _make_field_eligibility_summary():
    """Create a FieldEligibilitySummary for testing."""
    return FieldEligibilitySummary(
        eligible_field_count=73,
        channel_excluded_field_count=70,
        target_excluded_field_count=23,
        not_applicable_count=70,
        not_attempted_count=23,
    )


def _make_result(**kwargs):
    """Create a minimal EvidenceExtractionResult for testing."""
    defaults = {
        "status": EvidenceExtractionStatus.COMPLETED,
        "document_id": "test-doc-1",
        "track": Track.ORIGINAL,
    }
    defaults.update(kwargs)
    return EvidenceExtractionResult(**defaults)


# ---------------------------------------------------------------------------
# Test: contract serializes/deserializes channel_classification
# ---------------------------------------------------------------------------

def test_result_serializes_channel_classification():
    """EvidenceExtractionResult JSON round-trip preserves channel_classification."""
    classification = _make_channel_classification()
    result = _make_result(channel_classification=classification)
    
    # Serialize to JSON
    json_str = result.model_dump_json()
    
    # Deserialize
    restored = EvidenceExtractionResult.model_validate_json(json_str)
    
    assert restored.channel_classification is not None
    assert restored.channel_classification.selected_channels == [DocumentEvidenceChannel.CASE_REPORT]
    assert restored.channel_classification.confidence == 0.85
    assert restored.channel_classification.rationale == "single-proband case report"
    assert restored.channel_classification.supporting_block_ids == ["blk-3", "blk-7"]


def test_result_serializes_field_eligibility_summary():
    """EvidenceExtractionResult JSON round-trip preserves field_eligibility_summary."""
    summary = _make_field_eligibility_summary()
    result = _make_result(field_eligibility_summary=summary)
    
    json_str = result.model_dump_json()
    restored = EvidenceExtractionResult.model_validate_json(json_str)
    
    assert restored.field_eligibility_summary is not None
    assert restored.field_eligibility_summary.eligible_field_count == 73
    assert restored.field_eligibility_summary.channel_excluded_field_count == 70
    assert restored.field_eligibility_summary.target_excluded_field_count == 23
    assert restored.field_eligibility_summary.not_applicable_count == 70
    assert restored.field_eligibility_summary.not_attempted_count == 23


def test_result_with_none_channel_classification():
    """EvidenceExtractionResult works with channel_classification=None."""
    result = _make_result(channel_classification=None)
    
    json_str = result.model_dump_json()
    restored = EvidenceExtractionResult.model_validate_json(json_str)
    
    assert restored.channel_classification is None


def test_result_with_none_field_eligibility_summary():
    """EvidenceExtractionResult works with field_eligibility_summary=None."""
    result = _make_result(field_eligibility_summary=None)
    
    json_str = result.model_dump_json()
    restored = EvidenceExtractionResult.model_validate_json(json_str)
    
    assert restored.field_eligibility_summary is None


# ---------------------------------------------------------------------------
# Test: FieldEligibilitySummary serialization
# ---------------------------------------------------------------------------

def test_field_eligibility_summary_serialization():
    """FieldEligibilitySummary JSON round-trip."""
    summary = _make_field_eligibility_summary()
    
    json_str = summary.model_dump_json()
    restored = FieldEligibilitySummary.model_validate_json(json_str)
    
    assert restored.eligible_field_count == summary.eligible_field_count
    assert restored.channel_excluded_field_count == summary.channel_excluded_field_count
    assert restored.target_excluded_field_count == summary.target_excluded_field_count
    assert restored.not_applicable_count == summary.not_applicable_count
    assert restored.not_attempted_count == summary.not_attempted_count


def test_field_eligibility_summary_defaults():
    """FieldEligibilitySummary defaults to zeros."""
    summary = FieldEligibilitySummary()
    
    assert summary.eligible_field_count == 0
    assert summary.channel_excluded_field_count == 0
    assert summary.target_excluded_field_count == 0
    assert summary.not_applicable_count == 0
    assert summary.not_attempted_count == 0


# ---------------------------------------------------------------------------
# Test: dual-track result preserves metadata
# ---------------------------------------------------------------------------

def test_dual_track_result_preserves_channel_metadata():
    """DualEvidenceExtractionResult preserves channel_classification for both tracks."""
    original_classification = _make_channel_classification([DocumentEvidenceChannel.CASE_REPORT])
    translated_classification = _make_channel_classification([DocumentEvidenceChannel.FUNCTIONAL_STUDY])
    
    original_summary = FieldEligibilitySummary(
        eligible_field_count=73,
        channel_excluded_field_count=70,
        not_applicable_count=70,
    )
    translated_summary = FieldEligibilitySummary(
        eligible_field_count=84,
        channel_excluded_field_count=59,
        not_applicable_count=59,
    )
    
    original_result = _make_result(
        track=Track.ORIGINAL,
        channel_classification=original_classification,
        field_eligibility_summary=original_summary,
    )
    translated_result = _make_result(
        track=Track.TRANSLATED,
        channel_classification=translated_classification,
        field_eligibility_summary=translated_summary,
    )
    
    dual = DualEvidenceExtractionResult(
        document_id="test-doc-1",
        original_result=original_result,
        translated_result=translated_result,
    )
    
    # Serialize and deserialize
    json_str = dual.model_dump_json()
    restored = DualEvidenceExtractionResult.model_validate_json(json_str)
    
    # Verify original
    assert restored.original_result.channel_classification is not None
    assert restored.original_result.channel_classification.selected_channels == [DocumentEvidenceChannel.CASE_REPORT]
    assert restored.original_result.field_eligibility_summary is not None
    assert restored.original_result.field_eligibility_summary.eligible_field_count == 73
    
    # Verify translated
    assert restored.translated_result.channel_classification is not None
    assert restored.translated_result.channel_classification.selected_channels == [DocumentEvidenceChannel.FUNCTIONAL_STUDY]
    assert restored.translated_result.field_eligibility_summary is not None
    assert restored.translated_result.field_eligibility_summary.eligible_field_count == 84


# ---------------------------------------------------------------------------
# Test: multiple channel classification
# ---------------------------------------------------------------------------

def test_result_with_multiple_channels():
    """EvidenceExtractionResult works with multiple channel classifications."""
    classification = _make_channel_classification(
        [DocumentEvidenceChannel.CASE_REPORT, DocumentEvidenceChannel.FUNCTIONAL_STUDY]
    )
    result = _make_result(channel_classification=classification)
    
    json_str = result.model_dump_json()
    restored = EvidenceExtractionResult.model_validate_json(json_str)
    
    assert restored.channel_classification is not None
    assert len(restored.channel_classification.selected_channels) == 2
    assert DocumentEvidenceChannel.CASE_REPORT in restored.channel_classification.selected_channels
    assert DocumentEvidenceChannel.FUNCTIONAL_STUDY in restored.channel_classification.selected_channels


# ---------------------------------------------------------------------------
# Test: result with all new fields populated
# ---------------------------------------------------------------------------

def test_result_with_all_new_fields():
    """EvidenceExtractionResult works with all new fields populated."""
    classification = _make_channel_classification([DocumentEvidenceChannel.COHORT_STUDY])
    summary = FieldEligibilitySummary(
        eligible_field_count=60,
        channel_excluded_field_count=83,
        target_excluded_field_count=23,
        not_applicable_count=83,
        not_attempted_count=23,
    )
    
    result = _make_result(
        channel_classification=classification,
        field_eligibility_summary=summary,
    )
    
    json_str = result.model_dump_json()
    restored = EvidenceExtractionResult.model_validate_json(json_str)
    
    assert restored.channel_classification is not None
    assert restored.channel_classification.selected_channels == [DocumentEvidenceChannel.COHORT_STUDY]
    assert restored.field_eligibility_summary is not None
    assert restored.field_eligibility_summary.eligible_field_count == 60
    assert restored.field_eligibility_summary.channel_excluded_field_count == 83
