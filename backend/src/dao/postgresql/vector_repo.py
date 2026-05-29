"""Vector similarity search repository backed by pgvector."""
from __future__ import annotations

import hashlib
import uuid
from typing import Any, TypedDict

from sqlalchemy import delete as sa_delete, select

from src.dao.models import TerminologyEmbedding, TerminologyEntry


class VectorSearchRow(TypedDict):
    """Typed projection row returned by vector similarity search."""

    entry_id: uuid.UUID
    entity_type: str
    source_db: str
    external_id: str
    display_name: str
    embedding_text: str
    distance: float


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
        embedding_model: str | None = None,
    ) -> list[VectorSearchRow]:
        """Search terminology embeddings by cosine similarity.

        Args:
            entity_type: Filter by entity type (gene, disease, phenotype, variant).
            embedding: The query embedding vector.
            limit: Maximum number of results.
            min_distance: Optional minimum cosine distance threshold (lower = more similar).
            embedding_model: Optional filter by embedding model identity.

        Returns:
            List of result dicts with entry_id, entity_type, source_db, external_id,
            display_name, embedding_text, and distance.
        """
        distance_expr = TerminologyEmbedding.embedding.cosine_distance(embedding).label("distance")
        statement = (
            select(
                TerminologyEntry.entry_id,
                TerminologyEntry.entity_type,
                TerminologyEntry.source_db,
                TerminologyEntry.external_id,
                TerminologyEntry.display_name,
                TerminologyEmbedding.embedding_text,
                distance_expr,
            )
            .join(TerminologyEmbedding, TerminologyEmbedding.entry_id == TerminologyEntry.entry_id)
            .where(TerminologyEmbedding.entity_type == entity_type)
            .order_by(distance_expr)
            .limit(limit)
        )
        if embedding_model is not None:
            statement = statement.where(TerminologyEmbedding.embedding_model == embedding_model)
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
                "embedding_text": row["embedding_text"],
                "distance": float(row["distance"]),
            }
            for row in rows
        ]

    async def upsert_embeddings(
        self,
        *,
        entry_ids: list[uuid.UUID],
        entity_type: str,
        source_db: str,
        external_ids: list[str],
        embedding_model: str,
        embeddings: list[list[float]],
        embedding_texts: list[str],
    ) -> None:
        """Insert or update embeddings for terminology entries.

        Existing embeddings for the same (entry_id, embedding_model) are replaced.
        """
        input_lengths = {len(entry_ids), len(external_ids), len(embeddings), len(embedding_texts)}
        if len(input_lengths) != 1:
            raise ValueError("entry_ids, external_ids, embeddings, and embedding_texts must have the same length.")

        for entry_id, external_id, emb, embedding_text in zip(entry_ids, external_ids, embeddings, embedding_texts):
            await self.session.execute(
                sa_delete(TerminologyEmbedding)
                .where(TerminologyEmbedding.entry_id == entry_id)
                .where(TerminologyEmbedding.embedding_model == embedding_model)
            )

            self.session.add(TerminologyEmbedding(
                entry_id=entry_id,
                entity_type=entity_type,
                source_db=source_db,
                external_id=external_id,
                embedding_text=embedding_text,
                embedding_text_hash=hashlib.sha256(embedding_text.encode("utf-8")).hexdigest(),
                embedding_model=embedding_model,
                embedding=emb,
            ))

        await self.session.flush()
