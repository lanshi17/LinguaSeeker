"""Vector similarity search repository backed by pgvector."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import literal_column, select, text

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
    ) -> list[dict[str, object]]:
        """Search terminology embeddings by cosine similarity.

        Args:
            entity_type: Filter by entity type (gene, disease, phenotype, variant).
            embedding: The query embedding vector.
            limit: Maximum number of results.
            min_distance: Optional minimum cosine distance threshold (lower = more similar).

        Returns:
            List of result dicts with entry_id, entity_type, source_db, external_id,
            display_name, source_text, and distance.
        """
        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
        statement = (
            select(
                TerminologyEntry.entry_id,
                TerminologyEntry.entity_type,
                TerminologyEntry.source_db,
                TerminologyEntry.external_id,
                TerminologyEntry.display_name,
                TerminologyEmbedding.source_text,
                literal_column(f"embedding <=> '{embedding_str}'::vector").label("distance"),
            )
            .join(TerminologyEmbedding, TerminologyEmbedding.entry_id == TerminologyEntry.entry_id)
            .where(TerminologyEmbedding.entity_type == entity_type)
            .order_by(text("distance"))
            .limit(limit)
        )
        if min_distance is not None:
            statement = statement.where(text(f"embedding <=> '{embedding_str}'::vector < {min_distance}"))

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
            # Delete existing embedding for this entry + model
            del_stmt = (
                select(TerminologyEmbedding)
                .where(TerminologyEmbedding.entry_id == entry_id)
                .where(TerminologyEmbedding.model_version == model_version)
            )
            result = await self.session.execute(del_stmt)
            existing = result.scalars().first()
            if existing:
                await self.session.delete(existing)

            new_emb = TerminologyEmbedding(
                entry_id=entry_id,
                entity_type=entity_type,
                embedding=emb,
                model_version=model_version,
                source_text=source_text,
            )
            self.session.add(new_emb)

        await self.session.flush()
