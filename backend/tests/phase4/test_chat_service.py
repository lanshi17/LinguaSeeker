"""Tests for chat service intent detection."""
import pytest
from unittest.mock import MagicMock

from src.core.visualize_evidence_with_expert_in_loop.chat_service import ChatService


@pytest.fixture
def mock_session():
    return MagicMock()


def test_detect_intent_question_with_change_keyword(mock_session):
    """Questions containing 'change' are classified as questions, not corrections."""
    service = ChatService(mock_session)
    assert service._detect_intent("What should I change?") == "question"
    assert service._detect_intent("How do I change this?") == "question"


def test_detect_intent_plain_question(mock_session):
    """Simple questions are detected correctly."""
    service = ChatService(mock_session)
    assert service._detect_intent("What is the evidence?") == "question"
    assert service._detect_intent("Why was this classified?") == "question"


def test_detect_intent_correction(mock_session):
    """Clear corrections without question marks are detected."""
    service = ChatService(mock_session)
    assert service._detect_intent("change the classification to benign") == "correction"
    assert service._detect_intent("update the gene to BRCA1") == "correction"


def test_detect_intent_note(mock_session):
    """Ambiguous messages default to "question" (per docstring contract)."""
    service = ChatService(mock_session)
    assert service._detect_intent("I reviewed this evidence") == "question"


def test_detect_intent_identity_questions_default_to_question(mock_session):
    """Identity questions (who are you / 你是谁) reach the LLM, not 'note'."""
    service = ChatService(mock_session)
    assert service._detect_intent("who are you") == "question"
    assert service._detect_intent("Who are you?") == "question"
    assert service._detect_intent("你是谁") == "question"
