"""
Unit tests for Arbitration Agent.
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock

from src.domain.agents.arbitration_agent import ArbitrationAgent, ArbitrationResult
from src.domain.agents.evidence_agent import ExtractedEvidence


@pytest.fixture
def arbitration_agent():
    """Create an arbitration agent instance."""
    return ArbitrationAgent()


@pytest.fixture
def sample_evidence():
    """Create sample evidence items."""
    return [
        ExtractedEvidence(
            acmg_code="PS3",
            supporting_text="functional studies demonstrated strong damaging effect",
            page=1,
            confidence=0.95,
            reasoning="Clear functional evidence"
        ),
        ExtractedEvidence(
            acmg_code="PM2",
            supporting_text="absent from gnomAD population database",
            page=2,
            confidence=0.80,
            reasoning="Population frequency data"
        ),
        ExtractedEvidence(
            acmg_code="PP3",
            supporting_text="multiple computational predictions support deleterious effect",
            page=3,
            confidence=0.70,
            reasoning="Computational evidence"
        )
    ]


def test_arbitration_agent_initialization(arbitration_agent):
    """Test arbitration agent initialization."""
    assert arbitration_agent.CONFIDENCE_THRESHOLD == 0.85


@pytest.mark.asyncio
async def test_arbitration_agent_process(arbitration_agent, sample_evidence):
    """Test arbitration agent processing."""
    results = await arbitration_agent.process(sample_evidence)

    assert len(results) == 3
    assert all(isinstance(result, ArbitrationResult) for result in results)

    # Check confidence scores and review flags
    assert results[0].final_confidence >= Decimal('0.85')
    assert results[0].review_required is False

    assert results[1].final_confidence < Decimal('0.85')
    assert results[1].review_required is True

    assert results[2].final_confidence < Decimal('0.85')
    assert results[2].review_required is True


def test_arbitration_agent_get_review_queue(arbitration_agent, sample_evidence):
    """Test getting review queue."""
    import asyncio
    results = asyncio.run(arbitration_agent.process(sample_evidence))
    review_queue = arbitration_agent.get_review_queue(results)

    assert len(review_queue) == 2  # PM2 and PP3 should need review
    assert all(r.review_required for r in review_queue)


def test_arbitration_agent_get_statistics(arbitration_agent, sample_evidence):
    """Test getting arbitration statistics."""
    import asyncio
    results = asyncio.run(arbitration_agent.process(sample_evidence))
    stats = arbitration_agent.get_statistics(results)

    assert stats["total"] == 3
    assert stats["auto_accepted"] == 1
    assert stats["review_required"] == 2
    assert stats["avg_confidence"] > 0.0
    assert stats["review_rate"] == 66.7  # 2/3 * 100


def test_arbitration_agent_calculate_confidence(arbitration_agent):
    """Test confidence calculation."""
    evidence = ExtractedEvidence(
        acmg_code="PS1",
        supporting_text="Strong evidence with numbers: p-value < 0.001",
        page=1,
        confidence=0.90,
        reasoning="Strong evidence"
    )

    import asyncio
    confidence = asyncio.run(arbitration_agent._calculate_confidence(evidence))

    assert isinstance(confidence, Decimal)
    assert confidence >= Decimal('0.85')  # Should be high confidence


def test_arbitration_agent_assess_text_quality(arbitration_agent):
    """Test text quality assessment."""
    # Short text should have lower quality
    short_text = "Short"
    quality = arbitration_agent._assess_text_quality(short_text)
    assert quality == 0.5

    # Comprehensive text should have higher quality
    long_text = "This is a comprehensive text with detailed information about the genetic variant and its functional impact on the protein structure."
    quality = arbitration_agent._assess_text_quality(long_text)
    assert quality == 0.9

    # Text with numbers and references should have enhanced quality
    referenced_text = "The variant has a p-value of 0.001 (Smith et al., 2023)."
    quality = arbitration_agent._assess_text_quality(referenced_text)
    assert quality >= 0.8


def test_arbitration_agent_get_code_confidence_factor(arbitration_agent):
    """Test ACMG code confidence factors."""
    # Strong evidence codes
    assert arbitration_agent._get_code_confidence_factor("PS1") == 1.0
    assert arbitration_agent._get_code_confidence_factor("BS1") == 1.0

    # Moderate evidence codes
    assert arbitration_agent._get_code_confidence_factor("PM1") == 0.95
    assert arbitration_agent._get_code_confidence_factor("PM2") == 0.95

    # Supporting evidence codes
    assert arbitration_agent._get_code_confidence_factor("PP1") == 0.9
    assert arbitration_agent._get_code_confidence_factor("BP1") == 0.9

    # Unknown codes
    assert arbitration_agent._get_code_confidence_factor("UNKNOWN") == 0.85


def test_arbitration_result_creation():
    """Test ArbitrationResult creation."""
    evidence = ExtractedEvidence(
        acmg_code="PS1",
        supporting_text="Test",
        page=1,
        confidence=0.95,
        reasoning="Test"
    )

    result = ArbitrationResult(
        evidence=evidence,
        final_confidence=Decimal('0.95'),
        review_required=False,
        arbitration_notes="High confidence PS1 evidence"
    )

    assert result.evidence == evidence
    assert result.final_confidence == Decimal('0.95')
    assert result.review_required is False
    assert result.arbitration_notes == "High confidence PS1 evidence"