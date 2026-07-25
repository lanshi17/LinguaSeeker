"""Tests for async provider methods."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from src.core.evidence_extraction.config_context import (
    EvidenceExtractionConfigContext,
)
from src.core.evidence_extraction.providers import (
    EvidenceModelTier,
    LangChainEvidenceProvider,
)


class _SampleOutput(BaseModel):
    value: str


@pytest.fixture
def ctx() -> EvidenceExtractionConfigContext:
    return EvidenceExtractionConfigContext(
        api_key="test-key",
        base_url="http://test",
        reasoning_api_key="test-reasoning-key",
        reasoning_base_url="http://test-reasoning",
        fast_model="fast-model",
        standard_model="std-model",
        strong_model="strong-model",
    )


@pytest.fixture
def provider(ctx: EvidenceExtractionConfigContext) -> LangChainEvidenceProvider:
    return LangChainEvidenceProvider(ctx)


@pytest.mark.asyncio
async def test_ainvoke_structured_returns_parsed_model(
    provider: LangChainEvidenceProvider,
) -> None:
    """ainvoke_structured should return a parsed Pydantic model."""
    mock_result = _SampleOutput(value="hello")

    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(return_value=mock_result)

    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

    with patch.object(provider, "_client_for_tier", return_value=mock_llm):
        result = await provider.ainvoke_structured(
            prompt="test prompt",
            output_schema=_SampleOutput,
            tier=EvidenceModelTier.FAST,
            stage="test",
        )

    assert result == mock_result
    mock_structured.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_concurrent_ainvoke_structured_calls(
    provider: LangChainEvidenceProvider,
) -> None:
    """Multiple ainvoke_structured calls should be awaitable concurrently."""
    call_log: list[float] = []

    async def _mock_ainvoke(msg):  # noqa: ANN001
        import time

        call_log.append(time.monotonic())
        await asyncio.sleep(0.05)
        return _SampleOutput(value="ok")

    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(side_effect=_mock_ainvoke)

    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

    with patch.object(provider, "_client_for_tier", return_value=mock_llm):
        results = await asyncio.gather(
            provider.ainvoke_structured("p1", _SampleOutput, EvidenceModelTier.FAST, "s1"),
            provider.ainvoke_structured("p2", _SampleOutput, EvidenceModelTier.FAST, "s2"),
            provider.ainvoke_structured("p3", _SampleOutput, EvidenceModelTier.FAST, "s3"),
        )

    assert len(results) == 3
    assert all(r.value == "ok" for r in results)
    # All 3 should have started before any finished (concurrent)
    assert len(call_log) == 3
    assert call_log[2] - call_log[0] < 0.03


@pytest.mark.asyncio
async def test_ainvoke_json_text_falls_back_to_raw_client_after_attribute_error(
    provider: LangChainEvidenceProvider,
) -> None:
    """JSON fallback should bypass pool wrappers that fail on list schemas."""
    raw_client = MagicMock()
    raw_client.ainvoke = AsyncMock(return_value=AIMessage(content='{"value": "raw-ok"}'))

    pool_client = MagicMock()
    pool_client._clients = [raw_client]
    pool_client.ainvoke = AsyncMock(side_effect=AttributeError("'list' object has no attribute 'model_dump'"))

    result = await provider._ainvoke_json_text(pool_client, "prompt", _SampleOutput)

    assert result == _SampleOutput(value="raw-ok")
    pool_client.ainvoke.assert_awaited_once()
    raw_client.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_ainvoke_structured_falls_back_to_json_text_on_response_format_429(
    provider: LangChainEvidenceProvider,
) -> None:
    """A 429 whose body indicates response_format/json-mode incompatibility is
    not retryable — it must fall back to JSON-text instead of raising."""
    import openai

    incompat_msg = (
        "Error code: 429 - {'error': {'message': "
        "\"'messages' must contain the word 'json' in some form, to use "
        "'response_format' of type 'json_object'.\", 'type': 'invalid_request_error', "
        "'param': 'messages', 'code': None}}"
    )
    rate_limit_exc = openai.RateLimitError(incompat_msg, response=MagicMock(), body=None)

    mock_structured = MagicMock()
    # Every structured attempt raises the masking 429.
    mock_structured.ainvoke = AsyncMock(side_effect=rate_limit_exc)

    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)
    # JSON-text fallback succeeds.
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content='{"value": "recovered"}'))

    with patch.object(provider, "_client_for_tier", return_value=mock_llm):
        result = await provider.ainvoke_structured(
            prompt="extract evidence",
            output_schema=_SampleOutput,
            tier=EvidenceModelTier.STRONG,
            stage="special_evidence",
            response_method="json_mode",
        )

    assert result == _SampleOutput(value="recovered")
    # Must NOT have burned all retries on a non-retryable error.
    assert mock_structured.ainvoke.await_count == 1
    mock_llm.ainvoke.assert_awaited()


@pytest.mark.asyncio
async def test_ainvoke_structured_falls_back_to_json_text_on_structured_output_400(
    provider: LangChainEvidenceProvider,
) -> None:
    """Provider 400s for JSON schema mode should route to JSON-text fallback."""
    response = MagicMock()
    response.status_code = 400

    class StructuredOutputBadRequest(Exception):
        pass

    bad_request = StructuredOutputBadRequest(
        "Error code: 400 - {'error': {'message': 'json_schema is not supported by this model', "
        "'type': 'invalid_request_error'}}"
    )
    bad_request.response = response

    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(side_effect=bad_request)

    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content='{"value": "json-text"}'))

    with patch.object(provider, "_client_for_tier", return_value=mock_llm):
        result = await provider.ainvoke_structured(
            prompt="extract evidence",
            output_schema=_SampleOutput,
            tier=EvidenceModelTier.FAST,
            stage="relevance_scan/1",
            response_method="json_mode",
        )

    assert result == _SampleOutput(value="json-text")
    assert mock_structured.ainvoke.await_count == 1
    mock_llm.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_ainvoke_structured_falls_back_to_json_text_on_parser_error(
    provider: LangChainEvidenceProvider,
) -> None:
    """HTTP 200 structured responses that fail LangChain parsing should fall back."""
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(side_effect=OutputParserException("Invalid json output: not json"))

    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content='{"value": "parsed"}'))

    with patch.object(provider, "_client_for_tier", return_value=mock_llm):
        result = await provider.ainvoke_structured(
            prompt="extract evidence",
            output_schema=_SampleOutput,
            tier=EvidenceModelTier.STRONG,
            stage="primary_broad_extraction",
        )

    assert result == _SampleOutput(value="parsed")
    assert mock_structured.ainvoke.await_count == 1
    mock_llm.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_ainvoke_structured_retries_genuine_rate_limit_without_response_format() -> None:
    """A plain rate-limit 429 (no response_format incompatibility) still retries."""
    import openai

    from src.core.evidence_extraction.config_context import (
        EvidenceExtractionConfigContext,
    )

    retry_ctx = EvidenceExtractionConfigContext(
        api_key="test-key",
        base_url="http://test",
        reasoning_api_key="test-reasoning-key",
        reasoning_base_url="http://test-reasoning",
        fast_model="fast-model",
        standard_model="std-model",
        strong_model="strong-model",
        max_retries=3,
    )
    provider = LangChainEvidenceProvider(retry_ctx)

    plain_429 = openai.RateLimitError(
        "Error code: 429 - {'error': {'message': 'Rate limit exceeded'}}",
        response=MagicMock(),
        body=None,
    )
    mock_result = _SampleOutput(value="ok")
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(side_effect=[plain_429, mock_result])

    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

    with patch.object(provider, "_client_for_tier", return_value=mock_llm):
        result = await provider.ainvoke_structured(
            prompt="extract evidence",
            output_schema=_SampleOutput,
            tier=EvidenceModelTier.STRONG,
            stage="special_evidence",
            response_method="json_mode",
        )

    assert result == _SampleOutput(value="ok")
    # First attempt hit the plain 429 (retried, not fallen back); second succeeded.
    assert mock_structured.ainvoke.await_count == 2
