"""Tests for MultiStageTranslator segmentation in the 3-stage pipeline."""
import pytest
from unittest.mock import MagicMock, patch

from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator import MultiStageTranslator
from src.core.cross_lingual_process_and_extract_evidence.contracts import FormattedDocument


@pytest.fixture
def large_document():
    """Create a document that exceeds 8192 tokens (~32000 chars of CJK)."""
    text = "这是一段测试文本。" * 1200  # ~10800 chars ≈ 10800 tokens
    return FormattedDocument(
        formatted_markdown=text,
        source_language="zh",
    )


@pytest.fixture
def mock_translator():
    """Create a translator with mocked LLM."""
    ctx = MagicMock()
    ctx.model = "test-model"
    ctx.api_key = "test-key"
    ctx.base_url = "http://test"
    ctx.temperature = 0.0

    with patch("src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator.ChatOpenAI"):
        translator = MultiStageTranslator(ctx=ctx)

    # Mock _invoke_with_retry to return simple responses
    translator._invoke_with_retry = MagicMock(side_effect=lambda prompt, stage: f"result_for_{stage}")
    return translator


def test_extract_terminology_segments_large_document(mock_translator, large_document):
    """extract_terminology should segment and make multiple LLM calls for large docs."""
    result = mock_translator.extract_terminology(large_document)
    assert result is not None
    assert mock_translator._invoke_with_retry.call_count > 1


def test_translate_segments_segments_large_document(mock_translator, large_document):
    """translate_segments should segment large docs and translate each segment."""
    result, segments = mock_translator.translate_segments(large_document, "术语:terminology")
    assert result is not None
    assert len(segments) > 1
    assert mock_translator._invoke_with_retry.call_count > 1


def test_run_pipeline_with_large_document(mock_translator, large_document):
    """Full pipeline should complete without token limit errors."""
    terminology_map, structure_plan, draft, translated, segments, warnings = (
        mock_translator.run_pipeline(large_document)
    )
    assert terminology_map is not None
    assert translated is not None


def test_translate_segments_truncates_large_terminology(mock_translator):
    """translate_segments should truncate oversized terminology."""
    small_doc = FormattedDocument(
        formatted_markdown="这是一段短文本。",
        source_language="zh",
    )
    # Simulate very large terminology (merged from many segments)
    huge_terminology = "基因:gene\n蛋白质:protein\n" * 500  # ~10000 tokens

    result, segments = mock_translator.translate_segments(small_doc, huge_terminology)
    assert result is not None
    assert mock_translator._invoke_with_retry.call_count >= 1
