from unittest.mock import MagicMock, patch

import pytest

from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    ContentBlock,
    FormattedDocument,
    TranslationSegment,
)
from src.core.cross_lingual_process_and_extract_evidence.config_context import TranslationConfigContext
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator import MultiStageTranslator


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


# ── _build_translated_blocks tests ────────────────────────────────────

_SEP = MultiStageTranslator._BLOCK_SEP


def test_build_translated_blocks_empty():
    segments = []
    result = MultiStageTranslator._build_translated_blocks([], segments, "")
    assert result == []


def test_build_translated_blocks_delimiter_split():
    original = [
        ContentBlock(type="title", text="Title", page_idx=0, bbox=[0, 0, 100, 20]),
        ContentBlock(type="text", text="Body text", page_idx=0),
    ]
    translated = f"Título{_SEP}Texto del cuerpo"
    result = MultiStageTranslator._build_translated_blocks(
        original, [], translated, text_block_indices=[0, 1],
    )

    assert len(result) == 2
    assert result[0].type == "title"
    assert result[0].text == "Título"
    assert result[0].page_idx == 0
    assert result[0].bbox == [0, 0, 100, 20]
    assert result[1].type == "text"
    assert result[1].text == "Texto del cuerpo"


def test_build_translated_blocks_title_preserves_level():
    original = [ContentBlock(type="title", text="Chapter 1", text_level=1, page_idx=0)]
    translated = "Capítulo 1"
    result = MultiStageTranslator._build_translated_blocks(original, [], translated)

    assert result[0].type == "title"
    assert result[0].text == "Capítulo 1"
    assert result[0].text_level == 1


def test_build_translated_blocks_image_copied_as_is():
    original = [ContentBlock(
        type="image",
        img_path="images/fig1.jpg",
        content="A diagram",
        image_caption=["Figure 1"],
        image_footnote=["Source: X"],
        sub_type="photo",
        page_idx=1,
    )]
    result = MultiStageTranslator._build_translated_blocks(original, [], "some text")

    assert len(result) == 1
    assert result[0].type == "image"
    assert result[0].img_path == "images/fig1.jpg"
    assert result[0].content == "A diagram"
    assert result[0].image_caption == ["Figure 1"]
    assert result[0].image_footnote == ["Source: X"]
    assert result[0].sub_type == "photo"
    assert result[0].page_idx == 1


def test_build_translated_blocks_table_copied_as_is():
    original = [ContentBlock(
        type="table",
        table_body="<table><tr><td>1</td></tr></table>",
        table_caption=["Table 1"],
        table_footnote=["* p<0.05"],
        page_idx=2,
    )]
    result = MultiStageTranslator._build_translated_blocks(original, [], "some text")

    assert result[0].type == "table"
    assert result[0].table_body == "<table><tr><td>1</td></tr></table>"
    assert result[0].table_caption == ["Table 1"]
    assert result[0].table_footnote == ["* p<0.05"]


def test_build_translated_blocks_mixed_types():
    original = [
        ContentBlock(type="title", text="Title", text_level=1, page_idx=0),
        ContentBlock(type="text", text="Body text", page_idx=0),
        ContentBlock(type="image", img_path="images/fig.jpg", page_idx=1),
    ]
    translated = f"Título{_SEP}Texto del cuerpo"
    result = MultiStageTranslator._build_translated_blocks(
        original, [], translated, text_block_indices=[0, 1],
    )

    assert len(result) == 3
    assert result[0].text == "Título"
    assert result[1].text == "Texto del cuerpo"
    assert result[2].type == "image"
    assert result[2].img_path == "images/fig.jpg"


def test_build_translated_blocks_fallback_no_delimiter():
    """When delimiter is missing, falls back to segment matching."""
    original = [
        ContentBlock(type="text", text="Hello world", page_idx=0),
    ]
    segments = [
        TranslationSegment(index=0, source_text="Hello world", translated_text="Hola mundo"),
    ]
    result = MultiStageTranslator._build_translated_blocks(original, segments, "Hola mundo")

    assert len(result) == 1
    assert result[0].text == "Hola mundo"
