"""
Unit tests for Evidence Agent.
"""

import pytest
from unittest.mock import Mock, AsyncMock

from src.domain.agents.evidence_agent import EvidenceAgent, ExtractedEvidence


@pytest.fixture
def mock_llm_adapter():
    """Create a mock LLM adapter."""
    adapter = Mock()
    adapter.generate = AsyncMock()
    return adapter


@pytest.fixture
def evidence_agent(mock_llm_adapter):
    """Create an evidence agent instance."""
    return EvidenceAgent(mock_llm_adapter)


def test_evidence_agent_initialization(evidence_agent, mock_llm_adapter):
    """Test evidence agent initialization."""
    assert evidence_agent.llm == mock_llm_adapter


def test_evidence_agent_acmg_criteria():
    """Test ACMG criteria definitions."""
    # Check that key criteria are defined
    assert "PS1" in evidence_agent.ACMG_CRITERIA
    assert "PM2" in evidence_agent.ACMG_CRITERIA
    assert "PP3" in evidence_agent.ACMG_CRITERIA
    assert "BS3" in evidence_agent.ACMG_CRITERIA
    assert "BP4" in evidence_agent.ACMG_CRITERIA


def test_evidence_agent_validate_evidence_code_valid(evidence_agent):
    """Test evidence code validation with valid codes."""
    assert evidence_agent.validate_evidence_code("PS1") is True
    assert evidence_agent.validate_evidence_code("PM2") is True
    assert evidence_agent.validate_evidence_code("PP3") is True


def test_evidence_agent_validate_evidence_code_invalid(evidence_agent):
    """Test evidence code validation with invalid codes."""
    assert evidence_agent.validate_evidence_code("INVALID") is False
    assert evidence_agent.validate_evidence_code("PX1") is False
    assert evidence_agent.validate_evidence_code("") is False


@pytest.mark.asyncio
async def test_evidence_agent_process(evidence_agent):
    """Test evidence agent processing."""
    # Mock the LLM response with valid JSON
    mock_response = Mock()
    mock_response.content = '''[
        {
            "code": "PS3",
            "text": "functional studies demonstrated...",
            "confidence": 0.9,
            "reasoning": "Clear functional evidence"
        }
    ]'''
    evidence_agent.llm.generate.return_value = mock_response

    text = "This is a test document with PS3 evidence."
    evidence_list = await evidence_agent.process(text, page_number=5)

    assert len(evidence_list) == 1
    evidence = evidence_list[0]
    assert isinstance(evidence, ExtractedEvidence)
    assert evidence.acmg_code == "PS3"
    assert evidence.supporting_text == "functional studies demonstrated..."
    assert evidence.page == 5
    assert evidence.confidence == 0.9
    assert evidence.reasoning == "Clear functional evidence"


@pytest.mark.asyncio
async def test_evidence_agent_process_invalid_json(evidence_agent):
    """Test evidence agent processing with invalid JSON response."""
    # Mock the LLM response with invalid JSON
    mock_response = Mock()
    mock_response.content = "Invalid JSON response"
    evidence_agent.llm.generate.return_value = mock_response

    text = "This is a test document."
    evidence_list = await evidence_agent.process(text)

    # Should return empty list on parsing failure
    assert evidence_list == []


def test_extracted_evidence_creation():
    """Test ExtractedEvidence creation."""
    evidence = ExtractedEvidence(
        acmg_code="PS1",
        supporting_text="Supporting text here",
        page=1,
        confidence=0.95,
        reasoning="Good reasoning"
    )

    assert evidence.acmg_code == "PS1"
    assert evidence.supporting_text == "Supporting text here"
    assert evidence.page == 1
    assert evidence.confidence == 0.95
    assert evidence.reasoning == "Good reasoning"


def test_extracted_evidence_validation():
    """Test ExtractedEvidence field validation."""
    # This should work fine
    evidence = ExtractedEvidence(
        acmg_code="PS1",
        supporting_text="Valid text",
        page=1,
        confidence=0.85,
        reasoning="Valid reasoning"
    )
    assert evidence.confidence == 0.85

    # Confidence should be a float
    evidence2 = ExtractedEvidence(
        acmg_code="PM2",
        supporting_text="Text",
        page=2,
        confidence=0.7,  # Float
        reasoning="Reasoning"
    )
    assert evidence2.confidence == 0.7