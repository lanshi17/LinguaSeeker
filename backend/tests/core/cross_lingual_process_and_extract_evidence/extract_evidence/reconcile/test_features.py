"""Tests for the candidate feature extractor."""

from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SourcePrecision,
    Track,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.contracts import (
    CandidateScore,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.reconcile.features import (
    CandidateFeatureVector,
    extract_features,
)


def _make_score(**overrides: float | str) -> CandidateScore:
    defaults = {
        "field_id": "A.gene_symbol",
        "track": Track.ORIGINAL,
        "normalized_value": "test",
        "score": 0.8,
        "source_score": 1.0,
        "confidence_score": 0.9,
        "agreement_score": 1.0,
        "status_score": 1.0,
        "verifier_support_score": 0.7,
        "target_specificity_score": 0.5,
        "contradiction_penalty": 0.1,
    }
    defaults.update(overrides)
    return CandidateScore(**defaults)


def _make_item(
    *,
    source_precision: SourcePrecision = SourcePrecision.EXACT,
    status: EvidenceStatus = EvidenceStatus.FOUND,
    start: int = 100,
    end: int = 200,
) -> EvidenceItem:
    return EvidenceItem(
        field_id="A.gene_symbol",
        category="A",
        field_name="Gene Symbol",
        status=status,
        value="TEST",
        confidence=0.9,
        source=SourceLocation(
            span_id="span-1",
            page=1,
            start_offset=start,
            end_offset=end,
            context_type="text",
            context_ref="block-1",
            text_snippet="test snippet",
            source_precision=source_precision,
        ),
    )


class TestExtractFeatures:
    def test_basic_feature_extraction(self) -> None:
        score = _make_score()
        item = _make_item()
        features = extract_features(score, item, Track.ORIGINAL)

        assert features.source_score == 1.0
        assert features.has_source == 1.0
        assert features.source_is_exact == 1.0
        assert features.source_is_corrected == 0.0
        assert features.confidence_score == 0.9
        assert features.status_is_found == 1.0
        assert features.status_is_not_found == 0.0
        assert features.agreement_score == 1.0
        assert features.verifier_support_score == 0.7
        assert features.field_is_gene == 1.0
        assert features.field_is_disease == 0.0
        assert features.track_is_original == 1.0

    def test_interaction_features(self) -> None:
        score = _make_score(source_score=0.8, agreement_score=0.5, contradiction_penalty=0.2)
        item = _make_item()
        features = extract_features(score, item, Track.ORIGINAL)

        assert features.source_x_agreement == 0.8 * 0.5
        assert features.no_contradiction == 1.0 - 0.2
        assert features.verifier_x_no_contradiction == score.verifier_support_score * (1.0 - 0.2)

    def test_no_source_item(self) -> None:
        score = _make_score(source_score=0.0)
        item = EvidenceItem(
            field_id="A.gene_symbol",
            category="A",
            field_name="Gene Symbol",
            status=EvidenceStatus.NOT_FOUND,
            value=None,
            confidence=0.0,
        )
        features = extract_features(score, item, Track.TRANSLATED)

        assert features.has_source == 0.0
        assert features.source_is_exact == 0.0
        assert features.span_length == 0.0
        assert features.track_is_original == 0.0

    def test_corrected_source(self) -> None:
        score = _make_score()
        item = _make_item(source_precision=SourcePrecision.CORRECTED)
        features = extract_features(score, item, Track.ORIGINAL)

        assert features.source_is_exact == 0.0
        assert features.source_is_corrected == 1.0

    def test_span_length_normalized(self) -> None:
        score = _make_score()
        item = _make_item(start=0, end=250)
        features = extract_features(score, item, Track.ORIGINAL)
        assert features.span_length == 0.5

    def test_span_length_capped_at_one(self) -> None:
        score = _make_score()
        item = _make_item(start=0, end=1000)
        features = extract_features(score, item, Track.ORIGINAL)
        assert features.span_length == 1.0


class TestCandidateFeatureVector:
    def test_to_list_length(self) -> None:
        score = _make_score()
        item = _make_item()
        features = extract_features(score, item, Track.ORIGINAL)
        assert len(features.to_list()) == len(CandidateFeatureVector.feature_names())

    def test_feature_names_match_vector_length(self) -> None:
        names = CandidateFeatureVector.feature_names()
        assert len(names) == 21
        assert names[0] == "source_score"
        assert names[-1] == "source_x_verifier"
