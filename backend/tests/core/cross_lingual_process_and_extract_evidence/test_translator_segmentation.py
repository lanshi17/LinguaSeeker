"""Tests for MultiStageTranslator segmentation in all stages."""
import pytest
from unittest.mock import MagicMock, patch

from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator import MultiStageTranslator
from src.core.cross_lingual_process_and_extract_evidence.contracts import FormattedDocument


@pytest.fixture
def large_document():
    """Create a document that exceeds 8192 tokens (~32000 chars of CJK)."""
    # CJK chars are ~1 token each, so 10000 chars ≈ 10000 tokens
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
    # Should be called multiple times (once per segment + possible dedup)
    assert mock_translator._invoke_with_retry.call_count > 1


def test_plan_structure_segments_large_document(mock_translator, large_document):
    """plan_structure should segment and make multiple LLM calls for large docs."""
    result = mock_translator.plan_structure(large_document)
    assert result is not None
    assert mock_translator._invoke_with_retry.call_count > 1


def test_polish_segments_large_draft(mock_translator):
    """polish should segment large drafts before sending to LLM."""
    large_draft = "This is a translated sentence. " * 2000  # ~60000 chars
    terminology = "gene: 基因\nprotein: 蛋白质"

    result = mock_translator.polish(large_draft, terminology)
    assert result is not None
    assert mock_translator._invoke_with_retry.call_count > 1


def test_review_segments_large_documents(mock_translator):
    """review should segment large source+translated pairs."""
    large_source = "这是源文档。" * 2000
    large_translated = "This is translated. " * 2000

    result = mock_translator.review(large_source, large_translated)
    assert result is not None
    assert mock_translator._invoke_with_retry.call_count > 1


def test_run_pipeline_with_large_document(mock_translator, large_document):
    """Full pipeline should complete without token limit errors."""
    terminology_map, structure_plan, draft, translated, segments, warnings = (
        mock_translator.run_pipeline(large_document)
    )
    assert terminology_map is not None
    assert translated is not None
