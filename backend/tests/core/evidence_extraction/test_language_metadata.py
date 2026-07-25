"""Regression tests for article_language propagation onto EvidenceItem (blocker #1).

Validates that the extraction workflow stamps ``article_language`` /
``is_english`` / ``evidence_source_language`` / ``requires_translation`` onto
every emitted evidence item, sourced from the document's known language track.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.core.evidence_extraction.contracts import (
    EvidenceExtractionState,
    EvidenceItem,
    EvidenceStatus,
    ExtractionTarget,
    PageSpan,
    Track,
    TrackDocument,
)
from src.core.evidence_extraction.workflow import (
    _resolve_article_language,
    _stamp_language,
    EvidenceExtractionWorkflow,
)


def _make_item(field_id: str = "A.gene_symbol", value: str = "AARS1") -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category="gene",
        field_name="Gene Symbol",
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.9,
    )


def _make_doc(
    track: Track,
    source_language: str = "",
    target: ExtractionTarget | None = None,
) -> TrackDocument:
    return TrackDocument(
        document_id="doc-1",
        track=track,
        formatted_text="some text",
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=9)],
        metadata={"source_language": source_language} if source_language else {},
        extraction_target=target,
    )


class TestResolveArticleLanguage:
    def test_translated_track_is_always_english(self) -> None:
        doc = _make_doc(Track.TRANSLATED, source_language="zh")
        assert _resolve_article_language(doc) == "en"

    def test_original_track_uses_metadata_source_language(self) -> None:
        doc = _make_doc(Track.ORIGINAL, source_language="ja")
        assert _resolve_article_language(doc) == "ja"

    def test_original_track_defaults_to_english_when_unset(self) -> None:
        doc = _make_doc(Track.ORIGINAL, source_language="")
        assert _resolve_article_language(doc) == "en"

    def test_original_track_normalizes_case(self) -> None:
        doc = _make_doc(Track.ORIGINAL, source_language="ZH")
        assert _resolve_article_language(doc) == "zh"


class TestStampLanguage:
    def test_stamps_english_metadata_on_original_english_doc(self) -> None:
        target = ExtractionTarget(gene_symbol="AARS1", disease_name="CMT2N")
        doc = _make_doc(Track.ORIGINAL, source_language="en", target=target)
        item = _stamp_language(_make_item(), doc, "en")
        assert item.article_language == "en"
        assert item.is_english is True
        assert item.requires_translation is False
        assert item.evidence_source_language == "en"
        assert item.target_gene == "AARS1"
        assert item.target_disease == "CMT2N"

    def test_stamps_non_english_metadata_on_chinese_original(self) -> None:
        target = ExtractionTarget(gene_symbol="AARS1", disease_name="CMT2N")
        doc = _make_doc(Track.ORIGINAL, source_language="zh", target=target)
        item = _stamp_language(_make_item(), doc, "zh")
        assert item.article_language == "zh"
        assert item.is_english is False
        assert item.requires_translation is True
        assert item.evidence_source_language == "zh"

    def test_does_not_overwrite_explicitly_set_language(self) -> None:
        doc = _make_doc(Track.ORIGINAL, source_language="zh")
        item = _make_item()
        pre = item.model_copy(update={"article_language": "ko", "is_english": False})
        out = _stamp_language(pre, doc, "zh")
        # Explicit language is preserved
        assert out.article_language == "ko"
        assert out.is_english is False


@pytest.mark.asyncio
async def test_language_metadata_node_stamps_all_state_items() -> None:
    """The workflow node stamps language onto all evidence items in state."""
    provider = MagicMock()
    workflow = EvidenceExtractionWorkflow(provider=provider)
    target = ExtractionTarget(gene_symbol="AARS1", disease_name="CMT2N")
    doc = _make_doc(Track.ORIGINAL, source_language="ja", target=target)
    state = EvidenceExtractionState(
        document=doc,
        evidence_items=[_make_item("A.gene_symbol", "AARS1"), _make_item("B.disease_name", "CMT")],
    )
    out = workflow._node_language_metadata(state)
    assert len(out.evidence_items) == 2
    for item in out.evidence_items:
        assert item.article_language == "ja"
        assert item.is_english is False
        assert item.requires_translation is True
        assert item.evidence_source_language == "ja"
        assert item.target_gene == "AARS1"
