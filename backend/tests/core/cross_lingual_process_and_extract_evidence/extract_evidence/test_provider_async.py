"""Tests for async provider methods."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel
from langchain_core.messages import AIMessage

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.config_context import (
    EvidenceExtractionConfigContext,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers import (
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
