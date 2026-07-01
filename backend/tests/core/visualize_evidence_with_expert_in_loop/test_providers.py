"""Tests for Phase 4 LLM providers."""

import pytest
from src.core.visualize_evidence_with_expert_in_loop.providers import (
    ReasoningLLMProvider,
)


def test_reasoning_provider_uses_reasoning_config():
    """ReasoningLLMProvider reads base_url from reasoning config."""
    provider = ReasoningLLMProvider()
    # Should use cfg.reasoning.base_url (direct API)
    assert provider._base_url is not None


def test_reasoning_provider_timeout_from_nested_config():
    """ReasoningLLMProvider reads timeout from cfg.reasoning.timeout."""
    provider = ReasoningLLMProvider()
    assert isinstance(provider._timeout, int)
    assert provider._timeout > 0


@pytest.mark.asyncio
async def test_reasoning_llm_provider_reuses_httpx_client():
    """ReasoningLLMProvider should reuse a single httpx.AsyncClient across calls."""
    from unittest.mock import AsyncMock, MagicMock, patch

    with patch("src.core.visualize_evidence_with_expert_in_loop.providers.get_config") as mock_cfg:
        mock_cfg.return_value.reasoning = MagicMock(
            api_key="test-key",
            model="test-model",
            base_url="http://localhost:8001",
            timeout=30,
        )
        from src.core.visualize_evidence_with_expert_in_loop.providers import (
            ReasoningLLMProvider,
        )

        provider = ReasoningLLMProvider()

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "test"}}]}
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with patch("httpx.AsyncClient", return_value=mock_client):
            await provider.generate(system_prompt="test", user_message="test")
            await provider.generate(system_prompt="test", user_message="test")

            # httpx.AsyncClient should only be instantiated once
            import httpx

            assert httpx.AsyncClient.call_count == 1

        await provider.close()


@pytest.mark.asyncio
async def test_chat_service_uses_injected_provider():
    """ChatService should use an injected provider, not create a new one per call."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from src.core.visualize_evidence_with_expert_in_loop.chat_service import ChatService

    mock_session = AsyncMock()
    mock_provider = MagicMock()
    mock_provider.generate = AsyncMock(return_value="test reply")

    service = ChatService(session=mock_session, chat_provider=mock_provider)

    with patch.object(service, "_build_evidence_context", new_callable=AsyncMock, return_value="ctx"):
        await service.generate_reply(
            session_id=MagicMock(),
            user_message="What is BRCA1?",
            evidence_id=MagicMock(),
        )

    mock_provider.generate.assert_awaited_once()
