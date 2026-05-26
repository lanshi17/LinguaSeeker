"""Tests for terminology embedding service."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.standardize_entities_and_align_knowledge.contracts import EntityType
from src.core.standardize_entities_and_align_knowledge.embedding_service import (
    TerminologyEmbeddingService,
)


@pytest.mark.asyncio
async def test_generate_and_store_embeddings_upserts():
    """generate_and_store calls provider and upserts results."""
    mock_repo = MagicMock()
    mock_repo.search_similar = AsyncMock()
    mock_repo.upsert_embeddings = AsyncMock()

    mock_provider = MagicMock()
    mock_provider.generate_embeddings = AsyncMock(
        return_value=[[0.1] * 1536, [0.2] * 1536]
    )

    mock_session = MagicMock()
    # Mock the session's execute for finding entries without embeddings
    rows = [
        {"entry_id": uuid.uuid4(), "entity_type": "gene", "display_name": "BRCA1"},
        {"entry_id": uuid.uuid4(), "entity_type": "gene", "display_name": "TP53"},
    ]
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = rows
    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mappings
    mock_session.execute = AsyncMock(return_value=mock_result)

    svc = TerminologyEmbeddingService(
        session=mock_session,
        repository=mock_repo,
        provider=mock_provider,
        model_version="test-v1",
    )

    count = await svc.generate_and_store(EntityType.GENE)

    assert count == 2
    mock_provider.generate_embeddings.assert_called_once_with(["BRCA1", "TP53"])
    assert mock_repo.upsert_embeddings.call_count == 1


@pytest.mark.asyncio
async def test_search_similar_delegates_to_repository():
    """search_similar generates query embedding and delegates to repository."""
    mock_repo = MagicMock()
    mock_repo.search_similar = AsyncMock(
        return_value=[{"entry_id": "x", "distance": 0.1}]
    )

    mock_provider = MagicMock()
    mock_provider.generate_embeddings = AsyncMock(
        return_value=[[0.1] * 1536]
    )

    svc = TerminologyEmbeddingService(
        session=MagicMock(),
        repository=mock_repo,
        provider=mock_provider,
        model_version="test-v1",
    )

    results = await svc.search_similar(
        entity_type=EntityType.GENE,
        query_text="BRCA1",
        limit=5,
    )

    assert len(results) == 1
    mock_provider.generate_embeddings.assert_called_once_with(["BRCA1"])


@pytest.mark.asyncio
async def test_search_similar_empty_query():
    """search_similar returns empty list for empty query text."""
    svc = TerminologyEmbeddingService(
        session=MagicMock(),
        repository=MagicMock(),
        provider=MagicMock(),
        model_version="test-v1",
    )
    results = await svc.search_similar(EntityType.GENE, "", limit=5)
    assert results == []
