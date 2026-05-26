"""Vector similarity search repository backed by pgvector."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete as sa_delete, select

from src.dao.models import TerminologyEmbedding, TerminologyEntry


class VectorRepository:
    """Repository for vector similarity search against terminology embeddings."""

    def __init__(self, session: Any) -> None:
        self.session = session

    async def search_similar(
        self,
        *,
        entity_type: str,
        embedding: list[float],
        limit: int = 10,
        min_distance: float | None = None,
        model_version: str | None = None,
    ) -> list[dict[str, object]]:
        """Search terminology embeddings by cosine similarity.

        Args:
            entity_type: Filter by entity type (gene, disease, phenotype, variant).
            embedding: The query embedding vector.
            limit: Maximum number of results.
            min_distance: Optional minimum cosine distance threshold (lower = more similar).
            model_version: Optional filter by embedding model version.

        Returns:
            List of result dicts with entry_id, entity_type, source_db, external_id,
            display_name, source_text, and distance.
        """
        distance_expr = TerminologyEmbedding.embedding.cosine_distance(embedding).label("distance")
        statement = (
            select(
                TerminologyEntry.entry_id,
                TerminologyEntry.entity_type,
                TerminologyEntry.source_db,
                TerminologyEntry.external_id,
                TerminologyEntry.display_name,
                TerminologyEmbedding.source_text,
                distance_expr,
            )
            .join(TerminologyEmbedding, TerminologyEmbedding.entry_id == TerminologyEntry.entry_id)
            .where(TerminologyEmbedding.entity_type == entity_type)
            .order_by(distance_expr)
            .limit(limit)
        )
        if model_version is not None:
            statement = statement.where(TerminologyEmbedding.model_version == model_version)
        if min_distance is not None:
            statement = statement.where(
                TerminologyEmbedding.embedding.cosine_distance(embedding) < min_distance
            )

        result = await self.session.execute(statement)
        rows = result.mappings().all()
        return [
            {
                "entry_id": row["entry_id"],
                "entity_type": row["entity_type"],
                "source_db": row["source_db"],
                "external_id": row["external_id"],
                "display_name": row["display_name"],
                "source_text": row["source_text"],
                "distance": float(row["distance"]),
            }
            for row in rows
        ]

    async def upsert_embeddings(
        self,
        *,
        entry_ids: list[uuid.UUID],
        entity_type: str,
        model_version: str,
        embeddings: list[list[float]],
        source_texts: list[str],
    ) -> None:
        """Insert or update embeddings for terminology entries.

        Existing embeddings for the same (entry_id, model_version) are replaced.
        """
        for entry_id, emb, source_text in zip(entry_ids, embeddings, source_texts):
            await self.session.execute(
                sa_delete(TerminologyEmbedding)
                .where(TerminologyEmbedding.entry_id == entry_id)
                .where(TerminologyEmbedding.model_version == model_version)
            )

            self.session.add(TerminologyEmbedding(
                entry_id=entry_id,
                entity_type=entity_type,
                embedding=emb,
                model_version=model_version,
                source_text=source_text,
            ))

        await self.session.flush()
