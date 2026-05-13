from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    PipelineState,
    SentenceRegion,
    FormattedDocument,
    TranslationSegment,
    TranslationResult,
)


def test_sentence_region_span():
    region = SentenceRegion(
        page=1,
        start_offset=0,
        end_offset=50,
        text="Hello world.",
    )
    assert region.span == 50


def test_formatted_document_from_pages():
    pages = [
        {"page_number": 1, "markdown": "First page content."},
        {"page_number": 2, "markdown": "Second page content."},
    ]
    doc = FormattedDocument.from_pages(pages, formatted_markdown="First page content.\n\nSecond page content.")
    assert doc.source_language == ""
    assert len(doc.sentences) == 0
    assert "First page" in doc.formatted_markdown


def test_translation_segment_defaults():
    seg = TranslationSegment(
        index=0,
        source_text="Original text.",
        translated_text="Translated text.",
    )
    assert seg.source_bbox is None


def test_translation_result_fields():
    result = TranslationResult(
        formatted_original="原文",
        translated_english="English",
        source_language="zh",
        terminology_map={"基因": "gene"},
        translation_warnings=[],
        sentences=[],
        segments=[],
    )
    assert result.formatted_original == "原文"
    assert result.translated_english == "English"
    assert result.source_language == "zh"


def test_pipeline_state_defaults():
    state = PipelineState(pages=[{"page_number": 1, "markdown": "test"}])
    assert state.source_language == ""
    assert state.needs_translation is True
    assert state.formatted is None
    assert state.translation_result is None


def test_pipeline_state_rejects_missing_pages():
    import pytest
    with pytest.raises(Exception):
        PipelineState()  # pages is required
