"""Service for generating and querying terminology embeddings via pgvector."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from src.core.standardize_entities_and_align_knowledge.contracts import EntityType
from src.dao.models import TerminologyEmbedding, TerminologyEntry


class TerminologyEmbeddingService:
    """Generate embeddings for terminology entries and perform similarity search."""

    def __init__(
        self,
        *,
        session: Any,
        repository: Any,  # VectorRepository
        provider: Any,  # EmbeddingProvider
        model_version: str,
    ) -> None:
        self.session = session
        self.repo = repository
        self.provider = provider
        self.model_version = model_version

    async def generate_and_store(
        self,
        entity_type: EntityType,
        *,
        limit: int | None = None,
    ) -> int:
        """Generate and store embeddings for terminology entries that lack them.

        Returns the number of embeddings generated.
        """
        # Find entries that don't have embeddings for this model version
        subquery = (
            select(TerminologyEmbedding.entry_id)
            .where(TerminologyEmbedding.model_version == self.model_version)
        ).subquery()

        statement = (
            select(
                TerminologyEntry.entry_id,
                TerminologyEntry.entity_type,
                TerminologyEntry.display_name,
            )
            .where(TerminologyEntry.entity_type == entity_type.value)
            .where(TerminologyEntry.entry_id.not_in(select(subquery.c.entry_id)))
        )
        if limit is not None:
            statement = statement.limit(limit)

        result = await self.session.execute(statement)
        rows = result.mappings().all()
        if not rows:
            return 0

        entry_ids: list[uuid.UUID] = [row["entry_id"] for row in rows]
        source_texts: list[str] = [str(row["display_name"]) for row in rows]

        embeddings = await self.provider.generate_embeddings(source_texts)
        if not embeddings:
            return 0

        await self.repo.upsert_embeddings(
            entry_ids=entry_ids,
            entity_type=entity_type.value,
            model_version=self.model_version,
            embeddings=embeddings,
            source_texts=source_texts,
        )

        return len(embeddings)

    async def search_similar(
        self,
        entity_type: EntityType,
        query_text: str,
        *,
        limit: int = 10,
        min_distance: float | None = None,
    ) -> list[dict[str, object]]:
        """Search for similar terminology entries by embedding similarity.

        Args:
            entity_type: Entity type filter.
            query_text: Raw text to search by.
            limit: Max results.
            min_distance: Optional max cosine distance threshold.

        Returns:
            List of result dicts (entry_id, entity_type, source_db, external_id,
            display_name, source_text, distance).
        """
        if not query_text or not query_text.strip():
            return []

        embeddings = await self.provider.generate_embeddings([query_text.strip()])
        if not embeddings:
            return []

        return await self.repo.search_similar(
            entity_type=entity_type.value,
            embedding=embeddings[0],
            limit=limit,
            min_distance=min_distance,
        )
