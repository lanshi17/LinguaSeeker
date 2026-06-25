"""Tests for the embedding provider."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.standardize_entities_and_align_knowledge.providers import EmbeddingProvider


def _make_mock_response(data):
    """Create a mock response with synchronous json() and raise_for_status()."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=data)
    return mock_response


@pytest.mark.asyncio
async def test_generate_embeddings_calls_inference_service():
    """generate_embeddings POSTs to inference service and returns embeddings."""
    mock_response = _make_mock_response({
        "data": [
            {"index": 0, "embedding": [0.1, 0.2, 0.3]},
            {"index": 1, "embedding": [0.4, 0.5, 0.6]},
        ],
        "usage": {"prompt_tokens": 10, "total_tokens": 10},
    })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        provider = EmbeddingProvider(base_url="http://localhost:8001", model="test-model")
        result = await provider.generate_embeddings(["BRCA1", "TP53"])

    assert len(result) == 2
    assert result[0] == [0.1, 0.2, 0.3]
    assert result[1] == [0.4, 0.5, 0.6]
    mock_post.assert_called_once()
    call_args = mock_post.call_args[1]
    assert call_args["json"]["input"] == ["BRCA1", "TP53"]


@pytest.mark.asyncio
async def test_generate_embeddings_batches_large_inputs():
    """generate_embeddings splits large inputs into batches."""
    call_count = 0

    def make_batch_response(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        batch_size = len(kwargs.get("json", {}).get("input", []))
        return _make_mock_response({
            "data": [{"index": i, "embedding": [float(i)]} for i in range(batch_size)],
            "usage": {"prompt_tokens": batch_size, "total_tokens": batch_size},
        })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=make_batch_response) as mock_post:
        provider = EmbeddingProvider(
            base_url="http://localhost:8001", model="test", batch_size=2
        )
        result = await provider.generate_embeddings(["a", "b", "c", "d", "e"])

    assert len(result) == 5
    assert mock_post.call_count == 3  # 2 + 2 + 1


@pytest.mark.asyncio
async def test_provider_sends_auth_header_when_api_key_set():
    """generate_embeddings includes Authorization: Bearer header when api_key is configured."""
    mock_response = _make_mock_response({
        "data": [{"index": 0, "embedding": [0.1, 0.2]}],
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        provider = EmbeddingProvider(base_url="http://localhost:8001", model="test", api_key="secret-key")
        await provider.generate_embeddings(["text"])

    call_args = mock_post.call_args[1]
    assert call_args["headers"] == {"Authorization": "Bearer secret-key"}


@pytest.mark.asyncio
async def test_provider_omits_auth_header_when_no_api_key():
    """generate_embeddings sends no Authorization header when api_key is not configured."""
    mock_response = _make_mock_response({
        "data": [{"index": 0, "embedding": [0.1, 0.2]}],
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    })

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        provider = EmbeddingProvider(base_url="http://localhost:8001", model="test")
        await provider.generate_embeddings(["text"])

    call_args = mock_post.call_args[1]
    assert call_args["headers"] == {}


@pytest.mark.asyncio
async def test_provider_raises_on_http_error():
    """generate_embeddings raises on non-2xx response."""
    mock_response = _make_mock_response({})
    mock_response.raise_for_status = MagicMock(side_effect=Exception("HTTP 500"))

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        provider = EmbeddingProvider(base_url="http://localhost:8001", model="test")
        with pytest.raises(Exception, match="HTTP 500"):
            await provider.generate_embeddings(["text"])
