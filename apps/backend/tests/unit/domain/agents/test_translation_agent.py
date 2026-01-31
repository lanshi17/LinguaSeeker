"""
Unit tests for Translation Agent.
"""

import pytest
from unittest.mock import Mock, AsyncMock

from src.domain.agents.translation_agent import TranslationAgent, TranslationPair


@pytest.fixture
def mock_llm_adapter():
    """Create a mock LLM adapter."""
    adapter = Mock()
    adapter.generate = AsyncMock()
    return adapter


@pytest.fixture
def translation_agent(mock_llm_adapter):
    """Create a translation agent instance."""
    return TranslationAgent(mock_llm_adapter)


def test_translation_agent_initialization(translation_agent, mock_llm_adapter):
    """Test translation agent initialization."""
    assert translation_agent.llm == mock_llm_adapter


def test_translation_agent_split_paragraphs(translation_agent):
    """Test paragraph splitting."""
    markdown = "Paragraph 1\n\nParagraph 2\n\n\nParagraph 3"
    paragraphs = translation_agent._split_paragraphs(markdown)

    assert len(paragraphs) == 3
    assert paragraphs[0] == "Paragraph 1"
    assert paragraphs[1] == "Paragraph 2"
    assert paragraphs[2] == "Paragraph 3"


def test_translation_agent_detect_language_english(translation_agent):
    """Test language detection for English text."""
    text = "This is an English text with some biomedical terms."
    result = translation_agent._detect_language(text)
    assert result == "EN"


def test_translation_agent_detect_language_chinese(translation_agent):
    """Test language detection for Chinese text."""
    text = "这是一段中文文本，包含一些生物医学术语。"
    result = translation_agent._detect_language(text)
    assert result == "ZH"


def test_translation_agent_detect_language_mixed(translation_agent):
    """Test language detection for mixed text."""
    # Mostly English with some Chinese
    text = "This is mostly English text. 这里有一些中文。"
    result = translation_agent._detect_language(text)
    assert result == "EN"

    # Mostly Chinese with some English
    text = "这是一段主要的中文文本。This has some English."
    result = translation_agent._detect_language(text)
    assert result == "ZH"


@pytest.mark.asyncio
async def test_translation_agent_process(translation_agent):
    """Test translation agent processing."""
    # Mock the LLM response
    mock_response = Mock()
    mock_response.content = "Translated text"
    translation_agent.llm.generate.return_value = mock_response

    markdown = "English paragraph 1\n\nEnglish paragraph 2"
    pairs = await translation_agent.process(markdown)

    assert len(pairs) == 2
    assert all(isinstance(pair, TranslationPair) for pair in pairs)
    assert pairs[0].source_language == "EN"
    assert pairs[0].target_text == "Translated text"
    assert pairs[0].confidence == 0.9


def test_translation_pair_validation():
    """Test translation pair validation."""
    from src.domain.models.translation_pair import TranslationPair
    from uuid import uuid4

    # Valid translation pair
    valid_pair = TranslationPair(
        document_id=uuid4(),
        source_text="Hello",
        target_text="你好",
        source_language="EN",
        target_language="ZH",
        confidence_score=0.95,
        paragraph_index=0
    )
    assert valid_pair.source_text == "Hello"

    # Invalid: same source and target language
    with pytest.raises(ValueError, match="Source and target languages must be different"):
        TranslationPair(
            document_id=uuid4(),
            source_text="Hello",
            target_text="Bonjour",
            source_language="EN",
            target_language="EN",  # Same language
            confidence_score=0.95,
            paragraph_index=0
        )

    # Invalid: confidence score out of range
    with pytest.raises(ValueError, match="Confidence score"):
        TranslationPair(
            document_id=uuid4(),
            source_text="Hello",
            target_text="你好",
            source_language="EN",
            target_language="ZH",
            confidence_score=1.5,  # Out of range
            paragraph_index=0
        )