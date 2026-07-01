"""Tests for document channel classification in the relevance scan stage."""

from __future__ import annotations

import json
from unittest.mock import MagicMock


from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.channel_contracts import (
    DocumentChannelClassification,
    DocumentEvidenceChannel,
    RelevanceScanResult,
    merge_channel_classifications,
    parse_channel_classification,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    DocumentEvidenceMap,
    EvidenceExtractionState,
    EvidenceExtractionStatus,
    PageSpan,
    RelevanceScanOutput,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers import (
    EvidenceModelTier,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.evidence_map import (
    RelevanceScanStage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc() -> TrackDocument:
    return TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="Patient 1 had Fabry disease and carried a hemizygous GLA c.1000G>A variant.",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=78)],
        blocks=[
            ContentBlock(
                type="text",
                page_idx=0,
                text="Patient 1 had Fabry disease and carried a hemizygous GLA c.1000G>A variant.",
            )
        ],
    )


def _scan_output(
    relevant: bool = True,
    channels: list[str] | None = None,
    confidence: float = 0.85,
    rationale: str = "test rationale",
    supporting_block_ids: list[str] | None = None,
) -> RelevanceScanOutput:
    return RelevanceScanOutput(
        relevant=relevant,
        disease_terms=["Fabry disease"],
        gene_terms=["GLA"],
        variant_terms=["c.1000G>A"],
        selected_channels=channels if channels is not None else ["case_report"],
        confidence=confidence,
        rationale=rationale,
        supporting_block_ids=supporting_block_ids if supporting_block_ids is not None else ["block_0"],
    )


# ---------------------------------------------------------------------------
# parse_channel_classification unit tests
# ---------------------------------------------------------------------------


def test_parse_case_report_string():
    cls = parse_channel_classification(["case_report"], confidence=0.9, rationale="single proband")
    assert cls.selected_channels == [DocumentEvidenceChannel.CASE_REPORT]
    assert cls.confidence == 0.9
    assert cls.rationale == "single proband"


def test_parse_functional_study_string():
    cls = parse_channel_classification(["functional_study"], confidence=0.88)
    assert cls.selected_channels == [DocumentEvidenceChannel.FUNCTIONAL_STUDY]


def test_parse_cohort_study_string():
    cls = parse_channel_classification(["cohort_study"], confidence=0.75)
    assert cls.selected_channels == [DocumentEvidenceChannel.COHORT_STUDY]


def test_parse_mixed_string():
    cls = parse_channel_classification(["mixed"], confidence=0.7)
    assert cls.selected_channels == [DocumentEvidenceChannel.MIXED]


def test_parse_multiple_concrete_channels():
    cls = parse_channel_classification(["case_report", "functional_study"], confidence=0.82, rationale="hybrid")
    assert cls.selected_channels == [
        DocumentEvidenceChannel.CASE_REPORT,
        DocumentEvidenceChannel.FUNCTIONAL_STUDY,
    ]


def test_parse_unknown_string():
    cls = parse_channel_classification(["unknown"], confidence=0.3)
    assert cls.selected_channels == [DocumentEvidenceChannel.UNKNOWN]


def test_parse_invalid_channel_string_dropped():
    cls = parse_channel_classification(["case_report", "bogus_channel"], confidence=0.5)
    assert cls.selected_channels == [DocumentEvidenceChannel.CASE_REPORT]


def test_parse_all_invalid_falls_back_to_unknown():
    cls = parse_channel_classification(["bogus1", "bogus2"], confidence=0.5)
    assert cls.selected_channels == [DocumentEvidenceChannel.UNKNOWN]
    assert cls.confidence == 0.0
    assert "unavailable" in cls.rationale.lower()


def test_parse_empty_list_falls_back_to_unknown():
    cls = parse_channel_classification([], confidence=0.5)
    assert cls.selected_channels == [DocumentEvidenceChannel.UNKNOWN]


def test_parse_none_list_falls_back_to_unknown():
    cls = parse_channel_classification(None, confidence=0.5)
    assert cls.selected_channels == [DocumentEvidenceChannel.UNKNOWN]


def test_parse_confidence_clamped_to_range():
    cls = parse_channel_classification(["case_report"], confidence=1.5)
    assert cls.confidence == 1.0
    cls = parse_channel_classification(["case_report"], confidence=-0.5)
    assert cls.confidence == 0.0


def test_parse_case_insensitive():
    cls = parse_channel_classification(["Case_Report", "FUNCTIONAL_STUDY"])
    assert cls.selected_channels == [
        DocumentEvidenceChannel.CASE_REPORT,
        DocumentEvidenceChannel.FUNCTIONAL_STUDY,
    ]


def test_parse_deduplicates_channels():
    cls = parse_channel_classification(["case_report", "case_report", "functional_study"])
    assert cls.selected_channels == [
        DocumentEvidenceChannel.CASE_REPORT,
        DocumentEvidenceChannel.FUNCTIONAL_STUDY,
    ]


# ---------------------------------------------------------------------------
# Stage run() — channel parsing from mocked provider
# ---------------------------------------------------------------------------


def test_stage_case_report_response_parses_to_case_report():
    provider = MagicMock()
    provider.invoke_structured.return_value = _scan_output(channels=["case_report"])
    result = RelevanceScanStage(provider).run(_doc())
    assert isinstance(result, RelevanceScanResult)
    assert result.evidence_map.relevant is True
    assert result.channel_classification.selected_channels == [DocumentEvidenceChannel.CASE_REPORT]
    assert result.channel_classification.confidence == 0.85


def test_stage_functional_study_response_parses_to_functional_study():
    provider = MagicMock()
    provider.invoke_structured.return_value = _scan_output(channels=["functional_study"])
    result = RelevanceScanStage(provider).run(_doc())
    assert result.channel_classification.selected_channels == [DocumentEvidenceChannel.FUNCTIONAL_STUDY]


def test_stage_cohort_response_parses_to_cohort_study():
    provider = MagicMock()
    provider.invoke_structured.return_value = _scan_output(channels=["cohort_study"])
    result = RelevanceScanStage(provider).run(_doc())
    assert result.channel_classification.selected_channels == [DocumentEvidenceChannel.COHORT_STUDY]


def test_stage_mixed_with_multiple_concrete_channels_preserves_both():
    provider = MagicMock()
    provider.invoke_structured.return_value = _scan_output(channels=["case_report", "functional_study"])
    result = RelevanceScanStage(provider).run(_doc())
    assert set(result.channel_classification.selected_channels) == {
        DocumentEvidenceChannel.CASE_REPORT,
        DocumentEvidenceChannel.FUNCTIONAL_STUDY,
    }


def test_stage_mixed_label_normalizes_through_validator():
    provider = MagicMock()
    provider.invoke_structured.return_value = _scan_output(channels=["mixed"])
    result = RelevanceScanStage(provider).run(_doc())
    assert DocumentEvidenceChannel.MIXED in result.channel_classification.selected_channels


def test_stage_missing_channel_fields_falls_back_to_unknown():
    """When the provider returns a plain DocumentEvidenceMap (no channel fields),
    the stage must fall back to UNKNOWN."""
    provider = MagicMock()
    provider.invoke_structured.return_value = DocumentEvidenceMap(relevant=True, gene_terms=["GLA"])
    result = RelevanceScanStage(provider).run(_doc())
    assert result.evidence_map.relevant is True
    assert result.channel_classification.selected_channels == [DocumentEvidenceChannel.UNKNOWN]
    assert result.channel_classification.confidence == 0.0


def test_stage_empty_channel_list_falls_back_to_unknown():
    provider = MagicMock()
    provider.invoke_structured.return_value = _scan_output(channels=[])
    result = RelevanceScanStage(provider).run(_doc())
    assert result.channel_classification.selected_channels == [DocumentEvidenceChannel.UNKNOWN]


def test_stage_uses_relevance_scan_output_schema():
    provider = MagicMock()
    provider.invoke_structured.return_value = _scan_output()
    RelevanceScanStage(provider).run(_doc())
    call_kwargs = provider.invoke_structured.call_args
    assert call_kwargs.kwargs["output_schema"] is RelevanceScanOutput
    assert call_kwargs.kwargs["tier"] == EvidenceModelTier.FAST
    assert call_kwargs.kwargs["response_method"] == "json_mode"


def test_stage_relevant_false_still_returns_result_with_map():
    """relevant=false must still produce a RelevanceScanResult (caller sets NOT_RELEVANT)."""
    provider = MagicMock()
    provider.invoke_structured.return_value = _scan_output(relevant=False, channels=["case_report"])
    result = RelevanceScanStage(provider).run(_doc())
    assert result.evidence_map.relevant is False
    # Channel classification is still parsed — it does not make a doc irrelevant by itself
    assert result.channel_classification.selected_channels == [DocumentEvidenceChannel.CASE_REPORT]


def test_stage_prompt_contains_channel_classification_instructions():
    provider = MagicMock()
    provider.invoke_structured.return_value = _scan_output()
    RelevanceScanStage(provider).run(_doc())
    prompt = provider.invoke_structured.call_args.kwargs["prompt"]
    assert "CHANNEL CLASSIFICATION" in prompt
    assert "case_report" in prompt
    assert "functional_study" in prompt
    assert "cohort_study" in prompt
    assert "selected_channels" in prompt


# ---------------------------------------------------------------------------
# Workflow behavior — relevant=false sets NOT_RELEVANT
# ---------------------------------------------------------------------------


def test_relevant_false_sets_not_relevant_in_state():
    """Simulate the workflow node logic: relevant=false → NOT_RELEVANT status,
    but channel_classification is still stored."""
    provider = MagicMock()
    provider.invoke_structured.return_value = _scan_output(relevant=False, channels=["case_report"])
    result = RelevanceScanStage(provider).run(_doc())

    state = EvidenceExtractionState(document=_doc())
    state.evidence_map = result.evidence_map
    state.channel_classification = result.channel_classification
    if not result.evidence_map.relevant:
        state.status = EvidenceExtractionStatus.NOT_RELEVANT

    assert state.status == EvidenceExtractionStatus.NOT_RELEVANT
    assert state.evidence_map.relevant is False
    assert state.channel_classification is not None
    assert state.channel_classification.selected_channels == [DocumentEvidenceChannel.CASE_REPORT]


def test_relevant_true_preserves_completed_status_and_channel():
    provider = MagicMock()
    provider.invoke_structured.return_value = _scan_output(relevant=True, channels=["functional_study"])
    result = RelevanceScanStage(provider).run(_doc())

    state = EvidenceExtractionState(document=_doc())
    state.evidence_map = result.evidence_map
    state.channel_classification = result.channel_classification
    if not result.evidence_map.relevant:
        state.status = EvidenceExtractionStatus.NOT_RELEVANT

    assert state.status == EvidenceExtractionStatus.COMPLETED
    assert state.channel_classification.selected_channels == [DocumentEvidenceChannel.FUNCTIONAL_STUDY]


# ---------------------------------------------------------------------------
# JSON round trip: mocked provider response → EvidenceExtractionState
# ---------------------------------------------------------------------------


def test_json_round_trip_from_mocked_response_to_state():
    """Full round trip: LLM JSON → RelevanceScanOutput → stage → state.channel_classification."""
    raw_json = json.dumps(
        {
            "relevant": True,
            "disease_terms": ["Fabry disease"],
            "gene_terms": ["GLA"],
            "variant_terms": ["p.R227X"],
            "case_references": ["proband"],
            "authority_references": [],
            "contradictions": [],
            "structure_hints": [],
            "selected_channels": ["case_report", "functional_study"],
            "confidence": 0.82,
            "rationale": "Case report with functional assay evidence.",
            "supporting_block_ids": ["block_3", "block_7"],
        }
    )
    parsed = RelevanceScanOutput.model_validate_json(raw_json)

    provider = MagicMock()
    provider.invoke_structured.return_value = parsed
    result = RelevanceScanStage(provider).run(_doc())

    state = EvidenceExtractionState(document=_doc())
    state.evidence_map = result.evidence_map
    state.channel_classification = result.channel_classification

    assert state.channel_classification is not None
    assert set(state.channel_classification.selected_channels) == {
        DocumentEvidenceChannel.CASE_REPORT,
        DocumentEvidenceChannel.FUNCTIONAL_STUDY,
    }
    assert state.channel_classification.confidence == 0.82
    assert state.channel_classification.rationale == "Case report with functional assay evidence."
    assert state.channel_classification.supporting_block_ids == ["block_3", "block_7"]
    # Evidence map preserved
    assert state.evidence_map.relevant is True
    assert state.evidence_map.gene_terms == ["GLA"]


def test_state_channel_classification_json_round_trip():
    """channel_classification stored in state survives JSON serialization."""
    cls = DocumentChannelClassification(
        selected_channels=[DocumentEvidenceChannel.CASE_REPORT],
        confidence=0.9,
        rationale="single proband case report",
        supporting_block_ids=["b1"],
    )
    state = EvidenceExtractionState(
        document=_doc(),
        channel_classification=cls,
    )
    dumped = state.model_dump_json()
    restored = EvidenceExtractionState.model_validate_json(dumped)
    assert restored.channel_classification is not None
    assert restored.channel_classification.selected_channels == [DocumentEvidenceChannel.CASE_REPORT]
    assert restored.channel_classification.confidence == 0.9


# ---------------------------------------------------------------------------
# Multi-chunk merge behavior
# ---------------------------------------------------------------------------


def test_multi_chunk_merges_channel_classifications():
    """When chunks produce different channels, the merge unions concrete channels."""
    provider = MagicMock()
    call_count = 0

    def _invoke(**kwargs):  # noqa: ANN003
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _scan_output(channels=["case_report"], confidence=0.9, rationale="chunk1 case")
        return _scan_output(channels=["functional_study"], confidence=0.8, rationale="chunk2 functional")

    provider.invoke_structured.side_effect = _invoke

    document = TrackDocument(
        document_id="doc-multi",
        track=Track.ORIGINAL,
        formatted_text="chunk1 content\n\nchunk2 content\n\n" + "X" * 400,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=500)],
    )
    stage = RelevanceScanStage(provider, input_budget_tokens=200)
    result = stage.run(document)

    assert provider.invoke_structured.call_count >= 2
    assert set(result.channel_classification.selected_channels) == {
        DocumentEvidenceChannel.CASE_REPORT,
        DocumentEvidenceChannel.FUNCTIONAL_STUDY,
    }
    # Highest confidence among concrete chunks wins
    assert result.channel_classification.confidence == 0.9


def test_multi_chunk_all_unknown_returns_unknown():
    provider = MagicMock()

    def _invoke(**kwargs):  # noqa: ANN003
        return _scan_output(channels=["unknown"], confidence=0.3)

    provider.invoke_structured.side_effect = _invoke

    document = TrackDocument(
        document_id="doc-unk",
        track=Track.ORIGINAL,
        formatted_text="chunk1\n\nchunk2\n\n" + "X" * 400,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=500)],
    )
    stage = RelevanceScanStage(provider, input_budget_tokens=200)
    result = stage.run(document)

    assert provider.invoke_structured.call_count >= 2
    assert result.channel_classification.selected_channels == [DocumentEvidenceChannel.UNKNOWN]


# ---------------------------------------------------------------------------
# merge_channel_classifications unit tests
# ---------------------------------------------------------------------------


def test_merge_empty_returns_unknown():
    merged = merge_channel_classifications([])
    assert merged.selected_channels == [DocumentEvidenceChannel.UNKNOWN]
    assert merged.confidence == 0.0


def test_merge_single_returns_as_is():
    cls = DocumentChannelClassification(
        selected_channels=[DocumentEvidenceChannel.CASE_REPORT],
        confidence=0.9,
        rationale="single",
        supporting_block_ids=["b1"],
    )
    merged = merge_channel_classifications([cls])
    assert merged is cls


def test_merge_concrete_unknown_mix_prefers_concrete():
    concrete = DocumentChannelClassification(
        selected_channels=[DocumentEvidenceChannel.FUNCTIONAL_STUDY],
        confidence=0.7,
        rationale="functional",
        supporting_block_ids=["b2"],
    )
    unknown = DocumentChannelClassification(
        selected_channels=[DocumentEvidenceChannel.UNKNOWN],
        confidence=0.95,
        rationale="unknown",
        supporting_block_ids=["b1"],
    )
    merged = merge_channel_classifications([unknown, concrete])
    assert DocumentEvidenceChannel.FUNCTIONAL_STUDY in merged.selected_channels
    assert DocumentEvidenceChannel.UNKNOWN not in merged.selected_channels
    assert merged.confidence == 0.7
