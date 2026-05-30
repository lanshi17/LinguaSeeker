"""Tests for Phase 4 LLM providers."""
import pytest

from src.core.visualize_evidence_with_expert_in_loop.providers import (
    ReasoningLLMProvider,
)


def test_reasoning_provider_uses_model_server():
    """ReasoningLLMProvider routes through model-server /v1/chat/completions."""
    provider = ReasoningLLMProvider()
    assert "localhost:8001" in provider._base_url or "model-server" in provider._base_url


def test_reasoning_provider_auth_header_not_needed():
    """ReasoningLLMProvider uses placeholder auth since model-server has no auth."""
    provider = ReasoningLLMProvider()
    assert provider._api_key == "not-needed"
