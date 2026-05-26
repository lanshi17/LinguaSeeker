"""Tests for model-server semantic matching providers."""
from __future__ import annotations

import httpx
import pytest

from src.core.standardize_entities_and_align_knowledge.similarity_match.providers import (
    ModelServerEmbeddingProvider,
    ModelServerRerankProvider,
)


@pytest.mark.asyncio
async def test_embedding_provider_calls_model_server_embeddings() -> None:
    """Embedding provider maps OpenAI-style model-server responses into vectors."""
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "object": "list",
                "model": "Qwen/Qwen3-Embedding-0.6B",
                "data": [
                    {"object": "embedding", "embedding": [0.1, 0.2], "index": 0},
                    {"object": "embedding", "embedding": [0.3, 0.4], "index": 1},
                ],
                "usage": {"prompt_tokens": 2, "total_tokens": 2},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ModelServerEmbeddingProvider(
            base_url="http://model-server",
            model="Qwen/Qwen3-Embedding-0.6B",
            client=client,
        )
        result = await provider.embed_texts(("BRCA1", "Fabry disease"))

    assert requests[0].url.path == "/v1/embeddings"
    assert result.model == "Qwen/Qwen3-Embedding-0.6B"
    assert result.vectors == ((0.1, 0.2), (0.3, 0.4))


@pytest.mark.asyncio
async def test_embedding_provider_wraps_single_string() -> None:
    """Embedding provider wraps a single string in a tuple instead of splitting characters."""
    import json

    captured_input: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured_input.extend(body["input"])
        return httpx.Response(
            200,
            json={
                "object": "list",
                "model": "Qwen/Qwen3-Embedding-0.6B",
                "data": [{"object": "embedding", "embedding": [0.1, 0.2], "index": 0}],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ModelServerEmbeddingProvider(
            base_url="http://model-server",
            model="Qwen/Qwen3-Embedding-0.6B",
            client=client,
        )
        result = await provider.embed_texts("BRCA1")

    assert captured_input == ["BRCA1"]
    assert result.vectors == ((0.1, 0.2),)


@pytest.mark.asyncio
async def test_rerank_provider_returns_ranked_scores() -> None:
    """Rerank provider maps model-server rerank results into typed scores."""
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "BAAI/bge-reranker-v2-m3",
                "results": [
                    {"index": 1, "document": "candidate-b", "relevance_score": 0.91},
                    {"index": 0, "document": "candidate-a", "relevance_score": 0.44},
                ],
                "usage": {"prompt_tokens": 3, "total_tokens": 3},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ModelServerRerankProvider(
            base_url="http://model-server",
            model="BAAI/bge-reranker-v2-m3",
            client=client,
        )
        result = await provider.rerank("query", ("candidate-a", "candidate-b"), top_k=2)

    assert result.model == "BAAI/bge-reranker-v2-m3"
    assert result.results[0].index == 1
    assert result.results[0].relevance_score == 0.91
