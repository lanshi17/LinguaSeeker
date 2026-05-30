"""Tests for Phase 4 LLM providers."""
from src.core.visualize_evidence_with_expert_in_loop.providers import (
    ReasoningLLMProvider,
)


def test_reasoning_provider_uses_reasoning_config():
    """ReasoningLLMProvider reads base_url from reasoning config, not model-server."""
    provider = ReasoningLLMProvider()
    # Should use cfg.reasoning.base_url (direct API), not cfg.model_server_url
    assert provider._base_url is not None


def test_reasoning_provider_timeout_from_nested_config():
    """ReasoningLLMProvider reads timeout from cfg.reasoning.timeout."""
    provider = ReasoningLLMProvider()
    assert isinstance(provider._timeout, int)
    assert provider._timeout > 0
