from unittest.mock import MagicMock, patch

import pytest

from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    FormattedDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.config_context import TranslationConfigContext
from src.core.cross_lingual_process_and_extract_evidence.translate.translator import MultiStageTranslator


@pytest.fixture
def mock_ctx():
    return TranslationConfigContext(
        model="test-model",
        api_key="test-key",
        base_url="http://localhost:8001/v1",
    )


@pytest.fixture
def formatted_doc():
    return FormattedDocument(
        formatted_markdown="The patient carries a novel BRCA1 variant.",
        source_language="en",
    )


def test_translator_init(mock_ctx):
    t = MultiStageTranslator(ctx=mock_ctx)
    assert t._ctx == mock_ctx


def test_translator_llm(mock_ctx):
    t = MultiStageTranslator(ctx=mock_ctx)
    assert t._llm is not None


def test_to_text_none():
    assert MultiStageTranslator._to_text(None) == ""


def test_to_text_string():
    assert MultiStageTranslator._to_text(" hello ") == "hello"


def test_to_text_list():
    content = [{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}]
    assert "hello" in MultiStageTranslator._to_text(content)


# ── _parse_terminology tests ─────────────────────────────────────────


def test_parse_terminology_valid():
    raw = "基因:gene\n变异:variant\n蛋白质:protein"
    result = MultiStageTranslator._parse_terminology(raw)
    assert result == {"基因": "gene", "变异": "variant", "蛋白质": "protein"}


def test_parse_terminology_skips_ascii_only_lines():
    raw = "Note: this is important\n基因:gene"
    result = MultiStageTranslator._parse_terminology(raw)
    assert result == {"基因": "gene"}


def test_parse_terminology_skips_long_lines():
    raw = "这是一个非常长的术语超过十个字的限制: this is a very long translation that exceeds the ten word limit here"
    result = MultiStageTranslator._parse_terminology(raw)
    assert result == {}


def test_parse_terminology_empty():
    assert MultiStageTranslator._parse_terminology("") == {}


def test_parse_terminology_skips_blank_lines():
    raw = "\n\n基因:gene\n\n"
    result = MultiStageTranslator._parse_terminology(raw)
    assert result == {"基因": "gene"}


# ── _invoke_with_retry tests ─────────────────────────────────────────


def test_invoke_with_retry_success(mock_ctx):
    t = MultiStageTranslator(ctx=mock_ctx)
    mock_response = MagicMock()
    mock_response.content = "success"
    with patch("langchain_openai.ChatOpenAI.invoke", return_value=mock_response):
        result = t._invoke_with_retry("test prompt", "test")
        assert result == "success"


def test_invoke_with_retry_transient_then_success(mock_ctx):
    import httpx

    t = MultiStageTranslator(ctx=mock_ctx)
    mock_response = MagicMock()
    mock_response.content = "success"
    with patch("langchain_openai.ChatOpenAI.invoke", side_effect=[
        httpx.ConnectError("connection failed"),
        mock_response,
    ]):
        result = t._invoke_with_retry("test prompt", "test")
        assert result == "success"


def test_invoke_with_retry_non_transient_no_retry(mock_ctx):
    t = MultiStageTranslator(ctx=mock_ctx)
    with patch("langchain_openai.ChatOpenAI.invoke", side_effect=ValueError("bad input")):
        with pytest.raises(ValueError, match="bad input"):
            t._invoke_with_retry("test prompt", "test")
