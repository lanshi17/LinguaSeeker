"""Tests for pgvector terminology similarity repository."""
from __future__ import annotations

import pytest

from src.core.standardize_entities_and_align_knowledge.contracts import EntityType
from src.core.standardize_entities_and_align_knowledge.similarity_match.repositories import (
    PgvectorTerminologyRepository,
)


class _FakeSavepoint:
    """Async context manager stub for nested transactions."""

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


class FakeSession:
    """Minimal session that captures SQLAlchemy statements."""

    def __init__(self) -> None:
        self.statements = []

    async def begin_nested(self):
        return _FakeSavepoint()

    async def execute(self, statement):
        self.statements.append(statement)
        return FakeResult()

class FakeResult:
    """Empty SQLAlchemy result stand-in."""

    def mappings(self):
        return self

    def all(self):
        return []


@pytest.mark.asyncio
async def test_find_nearest_builds_pgvector_similarity_query() -> None:
    """Nearest-neighbor search filters by entity type and model."""
    session = FakeSession()
    repository = PgvectorTerminologyRepository(session)

    result = await repository.find_nearest(
        entity_type=EntityType.GENE,
        query_vector=(0.1, 0.2),
        embedding_model="Qwen/Qwen3-Embedding-0.6B",
        limit=5,
    )

    assert result == ()
    statement_text = str(session.statements[0])
    assert "terminology_embeddings" in statement_text
    assert "terminology_entries" in statement_text
    assert "embedding_model" in statement_text
