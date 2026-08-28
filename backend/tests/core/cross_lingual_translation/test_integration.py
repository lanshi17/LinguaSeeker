"""Integration test for the full translation pipeline with mocked LLM."""

from collections.abc import Iterable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.cross_lingual_translation.contracts import (
    TranslationResult,
)
from src.core.cross_lingual_translation.api import TranslationService
# The pipeline obtains LLM clients through ``create_llm_client``
# (src/utils/llm_adapter.py).  The translator's clients (create_llm /
# create_json_llm in providers.py) call the factory name bound in the
# providers module, while the formatter's client is built via a
# function-local import inside TranslationService.__init__ that resolves
# the factory on the llm_adapter module itself.
_PROVIDERS_FACTORY = "src.core.cross_lingual_translation.translate.providers.create_llm_client"
_ADAPTER_FACTORY = "src.utils.llm_adapter.create_llm_client"


@pytest.fixture
def mock_cfg():
    cfg = MagicMock()
    cfg.llm.api_key = "test-key"
    cfg.llm.base_url = "http://localhost:8001/v1"
    cfg.llm.model = "test-model"
    cfg.llm.temperature = 0.0
    return cfg


@pytest.fixture
def chinese_pages():
    return [
        {
            "page_number": 1,
            "markdown": "该患者携带BRCA1基因的新变异。该变异导致蛋白质功能丧失。",
        },
    ]


@pytest.fixture
def english_pages():
    return [
        {
            "page_number": 1,
            "markdown": "The patient carries a novel BRCA1 variant. This variant results in loss of protein function.",
        },
    ]


def _mock_llm_response(text: str) -> MagicMock:
    """Create a mock LLM response whose ``content`` attribute is ``text``."""
    response = MagicMock()
    response.content = text
    return response


def _make_mock_client(ainvoke_responses: Iterable) -> MagicMock:
    """Build a mock LLM client matching the LLMPoolAdapter interface.

    ``ainvoke`` backs the translation pipeline (called through
    ``invoke_with_retry`` / ``invoke_json_with_retry``); ``invoke`` backs the
    formatter.  Both must return an object with a ``content`` attribute.
    """
    mock_client = MagicMock()
    mock_client.ainvoke = AsyncMock(side_effect=list(ainvoke_responses))
    mock_client.invoke = MagicMock(
        return_value=_mock_llm_response(
            "The patient carries a novel BRCA1 gene variant. This variant leads to loss of protein function."
        )
    )
    return mock_client


@patch(_ADAPTER_FACTORY)
@patch(_PROVIDERS_FACTORY)
def test_full_pipeline_chinese(mock_providers_factory, mock_api_factory, mock_cfg, chinese_pages):
    """Full pipeline: Chinese → English with 3-stage pipeline."""
    # Mock each LLM call: (terminology + system prompt gen + translate + self-review) × 2 runs
    _translate_response = (
        "The patient carries a novel BRCA1 gene variant. This variant leads to loss of protein function."
    )
    _sys_prompt = (
        "You are a biomedical translation engine. Translate from Chinese to English. Preserve markdown structure."
    )

    def _pipeline_run_responses() -> list[MagicMock]:
        return [
            _mock_llm_response("基因:gene\n变异:variant"),  # terminology
            _mock_llm_response(_sys_prompt),  # system prompt generation
            _mock_llm_response(_translate_response),  # full-document translate
            _mock_llm_response(_translate_response),  # self-review
        ]

    mock_llm = _make_mock_client(_pipeline_run_responses() + _pipeline_run_responses())
    mock_providers_factory.return_value = mock_llm
    mock_api_factory.return_value = mock_llm

    service = TranslationService(cfg=mock_cfg)
    result = service.run_sync(chinese_pages)

    assert isinstance(result, TranslationResult)
    assert result.source_language != "en"
    assert len(result.translated_english) > 0
    assert result.translated_english != result.formatted_original
    assert len(result.sentences) > 0
    assert mock_llm.ainvoke.await_count > 0


@patch(_ADAPTER_FACTORY)
@patch(_PROVIDERS_FACTORY)
def test_pipeline_skip_english(mock_providers_factory, mock_api_factory, mock_cfg, english_pages):
    """Pipeline should skip translation for English documents."""
    _english = (
        "The patient carries a novel BRCA1 variant. This variant results in loss of protein function."
    )
    mock_llm = _make_mock_client([_mock_llm_response(_english)])
    mock_providers_factory.return_value = mock_llm
    mock_api_factory.return_value = mock_llm

    service = TranslationService(cfg=mock_cfg)
    result = service.run_sync(english_pages)

    assert isinstance(result, TranslationResult)
    assert result.source_language == "en"
    assert result.formatted_original == result.translated_english
    assert len(result.segments) == 0
