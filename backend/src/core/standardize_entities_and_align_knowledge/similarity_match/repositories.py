"""pgvector repository for terminology semantic retrieval."""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from src.core.standardize_entities_and_align_knowledge.contracts import (
    EntityType,
    SimilarityCandidate,
    TerminologyCandidate,
)
from src.dao.postgresql.models import TerminologyEmbedding, TerminologyEntry


class PgvectorTerminologyRepository:
    """Retrieve terminology candidates by vector similarity."""

    def __init__(self, session) -> None:
        self._session = session

    async def find_nearest(
        self,
        *,
        entity_type: EntityType,
        query_vector: Sequence[float],
        embedding_model: str,
        limit: int,
    ) -> tuple[SimilarityCandidate, ...]:
        """Find nearest terminology embeddings by cosine distance."""
        distance = TerminologyEmbedding.embedding.cosine_distance(list(query_vector)).label("vector_distance")
        statement = (
            select(
                TerminologyEntry.entry_id,
                TerminologyEntry.entity_type,
                TerminologyEntry.source_db,
                TerminologyEntry.external_id,
                TerminologyEntry.display_name,
                TerminologyEntry.normalized_name,
                TerminologyEntry.raw_payload,
                TerminologyEmbedding.embedding_text,
                distance,
            )
            .join(TerminologyEntry, TerminologyEntry.entry_id == TerminologyEmbedding.entry_id)
            .where(TerminologyEmbedding.entity_type == entity_type.value)
            .where(TerminologyEmbedding.embedding_model == embedding_model)
            .order_by(distance)
            .limit(limit)
        )
        result = await self._session.execute(statement)
        rows = result.mappings().all()
        return tuple(
            SimilarityCandidate(
                terminology=TerminologyCandidate(
                    entry_id=str(row["entry_id"]),
                    entity_type=EntityType(row["entity_type"]),
                    source_db=str(row["source_db"]),
                    external_id=str(row["external_id"]),
                    display_name=str(row["display_name"]),
                    normalized_alias=str(row["normalized_name"]),
                    alias_type="semantic",
                    raw_payload=dict(row["raw_payload"] or {}),
                ),
                embedding_text=str(row["embedding_text"]),
                vector_distance=float(row["vector_distance"]),
            )
            for row in rows
        )
