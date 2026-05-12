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
