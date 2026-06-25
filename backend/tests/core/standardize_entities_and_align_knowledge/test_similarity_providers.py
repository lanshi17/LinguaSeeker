"""Tests for inference service semantic matching providers."""
from __future__ import annotations

import httpx
import pytest

from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityType,
    MatchStatus,
    StandardizationCandidate,
)
from src.core.standardize_entities_and_align_knowledge.matchers import HybridTerminologyMatcher
from src.core.standardize_entities_and_align_knowledge.similarity_match.core import (
    SemanticMatchServiceError,
)
from src.core.standardize_entities_and_align_knowledge.similarity_match.providers import (
    EmbeddingHttpProvider,
    RerankHttpProvider,
)


@pytest.mark.asyncio
async def test_embedding_provider_calls_inference_service_embeddings() -> None:
    """Embedding provider maps OpenAI-style inference service responses into vectors."""
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
        provider = EmbeddingHttpProvider(
            base_url="http://inference-service",
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
        provider = EmbeddingHttpProvider(
            base_url="http://inference-service",
            model="Qwen/Qwen3-Embedding-0.6B",
            client=client,
        )
        result = await provider.embed_texts("BRCA1")

    assert captured_input == ["BRCA1"]
    assert result.vectors == ((0.1, 0.2),)


@pytest.mark.asyncio
async def test_embedding_provider_does_not_duplicate_v1_prefix() -> None:
    """A base URL already ending in `/v1` should still call `/v1/embeddings` once."""
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
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
        provider = EmbeddingHttpProvider(
            base_url="http://inference-service/v1",
            model="Qwen/Qwen3-Embedding-0.6B",
            client=client,
        )
        await provider.embed_texts("BRCA1")

    assert requests[0].url.path == "/v1/embeddings"


@pytest.mark.asyncio
async def test_rerank_provider_returns_ranked_scores() -> None:
    """Rerank provider maps inference service rerank results into typed scores."""
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
        provider = RerankHttpProvider(
            base_url="http://inference-service",
            model="BAAI/bge-reranker-v2-m3",
            client=client,
        )
        result = await provider.rerank("query", ("candidate-a", "candidate-b"), top_k=2)

    assert result.model == "BAAI/bge-reranker-v2-m3"
    assert result.results[0].index == 1
    assert result.results[0].relevance_score == 0.91


@pytest.mark.asyncio
async def test_hybrid_matcher_downgrades_similarity_service_errors_to_unmapped() -> None:
    """Inference service outages should not crash Phase 3 matching."""

    class FakePreciseMatcher:
        async def match(self, candidate):
            from src.core.standardize_entities_and_align_knowledge.contracts import (
                EntityMatch,
                MatchMethod,
            )

            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.UNMAPPED,
                external_id=None,
                display_name=candidate.raw_text,
                rationale="no deterministic terminology candidate",
                match_method=MatchMethod.PRECISE,
            )

    class FailingSimilarityMatcher:
        async def match(self, candidate):
            raise SemanticMatchServiceError("inference service unavailable")

    matcher = HybridTerminologyMatcher(FakePreciseMatcher(), FailingSimilarityMatcher())
    candidate = StandardizationCandidate(
        candidate_id="chain-1:variant",
        entity_type=EntityType.VARIANT,
        role=BindingRole.SUBJECT,
        raw_text="p.R227X",
        chain_id="chain-1",
        track="original",
    )

    result = await matcher.match(candidate)

    assert result.status == MatchStatus.UNMAPPED
    assert "semantic matching unavailable" in result.rationale
