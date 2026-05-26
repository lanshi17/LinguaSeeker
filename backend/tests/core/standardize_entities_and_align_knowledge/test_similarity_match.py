"""Tests for semantic similarity terminology matching."""
from __future__ import annotations

import pytest

from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityType,
    MatchMethod,
    MatchStatus,
    SimilarityCandidate,
    StandardizationCandidate,
    TerminologyCandidate,
)
from src.core.standardize_entities_and_align_knowledge.similarity_match.core import (
    SemanticMatchServiceError,
    SimilarityMatchConfig,
    SimilarityTerminologyMatcher,
)


class FakeEmbeddingProvider:
    async def embed_texts(self, texts):
        return type("EmbeddingResult", (), {"model": "model-a", "vectors": ((0.1, 0.2),)})()


class FakeRerankProvider:
    async def rerank(self, query, documents, *, top_k):
        return type(
            "RerankResult",
            (),
            {
                "model": "rerank-a",
                "results": (
                    type("RerankItem", (), {"index": 0, "document": documents[0], "relevance_score": 0.91})(),
                ),
            },
        )()


class FakeSimilarityRepository:
    async def find_nearest(self, *, entity_type, query_vector, embedding_model, limit):
        return (
            SimilarityCandidate(
                terminology=TerminologyCandidate(
                    entry_id="entry-1",
                    entity_type=EntityType.GENE,
                    source_db="HGNC",
                    external_id="HGNC:1100",
                    display_name="BRCA1",
                    normalized_alias="BRCA1",
                    alias_type="semantic",
                ),
                embedding_text="BRCA1\nBRCC1\nHGNC:1100\nHGNC",
                vector_distance=0.08,
            ),
        )


@pytest.mark.asyncio
async def test_similarity_matcher_accepts_high_rerank_score() -> None:
    """A high-confidence semantic candidate becomes a standardized match."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA one",
        chain_id="chain-1",
        track="original",
    )
    matcher = SimilarityTerminologyMatcher(
        embedding_provider=FakeEmbeddingProvider(),
        rerank_provider=FakeRerankProvider(),
        repository=FakeSimilarityRepository(),
        config=SimilarityMatchConfig(
            embedding_model="model-a",
            rerank_top_k=10,
            rerank_score_threshold=0.7,
        ),
    )

    match = await matcher.match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "HGNC:1100"
    assert match.match_method == MatchMethod.SIMILARITY
    assert match.similarity_score == 0.91


class FailingEmbeddingProvider:
    async def embed_texts(self, texts):
        raise ConnectionError("model-server unreachable")


class FailingRerankProvider:
    async def rerank(self, query, documents, *, top_k):
        raise TimeoutError("rerank service timeout")


class FailingRepository:
    async def find_nearest(self, *, entity_type, query_vector, embedding_model, limit):
        raise RuntimeError("database connection lost")


def _build_candidate() -> StandardizationCandidate:
    return StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA one",
        chain_id="chain-1",
        track="original",
    )


@pytest.mark.asyncio
async def test_similarity_matcher_propagates_embedding_provider_error() -> None:
    """Embedding provider errors propagate as-is (not swallowed)."""
    matcher = SimilarityTerminologyMatcher(
        embedding_provider=FailingEmbeddingProvider(),
        rerank_provider=FakeRerankProvider(),
        repository=FakeSimilarityRepository(),
        config=SimilarityMatchConfig(
            embedding_model="model-a",
            rerank_top_k=10,
            rerank_score_threshold=0.7,
        ),
    )

    with pytest.raises(ConnectionError, match="model-server unreachable"):
        await matcher.match(_build_candidate())


@pytest.mark.asyncio
async def test_similarity_matcher_propagates_rerank_provider_error() -> None:
    """Rerank provider errors propagate as-is (not swallowed)."""
    matcher = SimilarityTerminologyMatcher(
        embedding_provider=FakeEmbeddingProvider(),
        rerank_provider=FailingRerankProvider(),
        repository=FakeSimilarityRepository(),
        config=SimilarityMatchConfig(
            embedding_model="model-a",
            rerank_top_k=10,
            rerank_score_threshold=0.7,
        ),
    )

    with pytest.raises(TimeoutError, match="rerank service timeout"):
        await matcher.match(_build_candidate())


@pytest.mark.asyncio
async def test_similarity_matcher_propagates_repository_error() -> None:
    """Repository errors propagate as-is (not swallowed)."""
    matcher = SimilarityTerminologyMatcher(
        embedding_provider=FakeEmbeddingProvider(),
        rerank_provider=FakeRerankProvider(),
        repository=FailingRepository(),
        config=SimilarityMatchConfig(
            embedding_model="model-a",
            rerank_top_k=10,
            rerank_score_threshold=0.7,
        ),
    )

    with pytest.raises(RuntimeError, match="database connection lost"):
        await matcher.match(_build_candidate())


class EmptyRepository:
    async def find_nearest(self, *, entity_type, query_vector, embedding_model, limit):
        return ()


@pytest.mark.asyncio
async def test_similarity_matcher_returns_unmapped_when_no_nearest_neighbors() -> None:
    """No nearest neighbors is a normal negative result, not an error."""
    matcher = SimilarityTerminologyMatcher(
        embedding_provider=FakeEmbeddingProvider(),
        rerank_provider=FakeRerankProvider(),
        repository=EmptyRepository(),
        config=SimilarityMatchConfig(
            embedding_model="model-a",
            rerank_top_k=10,
            rerank_score_threshold=0.7,
        ),
    )

    match = await matcher.match(_build_candidate())

    assert match.status == MatchStatus.UNMAPPED
    assert match.match_method == MatchMethod.SIMILARITY
    assert "no semantic terminology candidate" in match.rationale
