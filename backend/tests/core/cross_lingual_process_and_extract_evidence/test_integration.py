"""Integration test for the full translation pipeline with mocked LLM."""
from unittest.mock import MagicMock, patch

import pytest

from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    TranslationResult,
)
from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService


@pytest.fixture
def mock_cfg():
    cfg = MagicMock()
    cfg.translation.api_key = "test-key"
    cfg.translation.base_url = "http://localhost:8001/v1"
    cfg.translation.model = "test-model"
    cfg.translation.temperature = 0.0
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


def _mock_llm_response(text: str):
    """Create a mock LLM response."""
    response = MagicMock()
    response.content = text
    return response


@patch("src.core.cross_lingual_process_and_extract_evidence.translate.translator.ChatOpenAI")
def test_full_pipeline_chinese(mock_chat_cls, mock_cfg, chinese_pages):
    """Full pipeline: Chinese → English with all stages."""
    mock_llm = MagicMock()
    mock_chat_cls.return_value = mock_llm

    # Mock each LLM call in order
    mock_llm.invoke.side_effect = [
        _mock_llm_response("基因:gene\n变异:variant"),          # terminology
        _mock_llm_response("Section 1: Patient variant info"),  # structure
        _mock_llm_response("The patient carries a novel BRCA1 gene variant. This variant leads to loss of protein function."),  # draft
        _mock_llm_response("The patient carries a novel BRCA1 gene variant. This variant leads to loss of protein function."),  # polish
        _mock_llm_response("Translation accurate, no gaps found."),  # review
    ]

    service = TranslationService(cfg=mock_cfg)
    result = service.run_sync(chinese_pages)

    assert isinstance(result, TranslationResult)
    assert result.source_language != "en"
    assert len(result.translated_english) > 0
    assert result.translated_english != result.formatted_original
    assert len(result.sentences) > 0


@patch("src.core.cross_lingual_process_and_extract_evidence.translate.translator.ChatOpenAI")
def test_pipeline_skip_english(mock_chat_cls, mock_cfg, english_pages):
    """Pipeline should skip translation for English documents."""
    mock_llm = MagicMock()
    mock_chat_cls.return_value = mock_llm

    service = TranslationService(cfg=mock_cfg)
    result = service.run_sync(english_pages)

    assert isinstance(result, TranslationResult)
    assert result.source_language == "en"
    assert result.formatted_original == result.translated_english
    assert len(result.segments) == 0
