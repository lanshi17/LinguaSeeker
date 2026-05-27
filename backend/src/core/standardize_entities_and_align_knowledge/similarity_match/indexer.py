"""Build pgvector embeddings for imported terminology entries."""
from __future__ import annotations

import hashlib
from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.core.standardize_entities_and_align_knowledge.contracts import EntityType
from src.dao.models import TerminologyEmbedding, TerminologyEntry


def build_embedding_text(entry: TerminologyEntry) -> str:
    """Build deterministic text used for terminology semantic embedding."""
    aliases = entry.aliases if isinstance(entry.aliases, list) else []
    parts = [entry.display_name, *[str(alias) for alias in aliases], entry.external_id, entry.source_db]
    deduped = []
    seen = set()
    for part in parts:
        text = str(part or "").strip()
        if text and text not in seen:
            seen.add(text)
            deduped.append(text)
    return "\n".join(deduped)


def make_embedding_text_hash(text: str) -> str:
    """Hash embedding text for idempotent embedding upsert."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TerminologyEmbeddingIndexer:
    """Build and persist terminology embeddings through model-server."""

    def __init__(self, session, embedding_provider) -> None:
        self._session = session
        self._embedding_provider = embedding_provider

    async def build(
        self,
        *,
        embedding_model: str,
        batch_size: int,
        entity_types: set[EntityType] | None = None,
        source_dbs: set[str] | None = None,
    ) -> int:
        """Embed terminology entries, cleaning stale rows and upserting current ones."""
        statement = select(TerminologyEntry)
        if entity_types:
            statement = statement.where(TerminologyEntry.entity_type.in_([entity_type.value for entity_type in entity_types]))
        if source_dbs:
            statement = statement.where(TerminologyEntry.source_db.in_(source_dbs))
        result = await self._session.execute(statement.order_by(TerminologyEntry.entry_id))
        entries = tuple(
            entry
            for entry in result.scalars().all()
            if (not entity_types or EntityType(entry.entity_type) in entity_types)
            and (not source_dbs or entry.source_db in source_dbs)
        )

        # Delete stale embeddings for entries that will be re-embedded.
        entry_ids = [entry.entry_id for entry in entries]
        if entry_ids:
            for entry_id_batch in _batched_values(entry_ids, 5000):
                await self._session.execute(
                    delete(TerminologyEmbedding.__table__).where(
                        TerminologyEmbedding.entry_id.in_(entry_id_batch),
                        TerminologyEmbedding.embedding_model == embedding_model,
                    ),
                )

        written = 0
        for batch in _batched(entries, batch_size):
            texts = tuple(build_embedding_text(entry) for entry in batch)
            vectors = (await self._embedding_provider.embed_texts(texts)).vectors
            for entry, text, vector in zip(batch, texts, vectors, strict=True):
                text_hash = make_embedding_text_hash(text)
                stmt = pg_insert(TerminologyEmbedding.__table__).values(
                    entry_id=entry.entry_id,
                    entity_type=entry.entity_type,
                    source_db=entry.source_db,
                    external_id=entry.external_id,
                    embedding_text=text,
                    embedding_text_hash=text_hash,
                    embedding_model=embedding_model,
                    embedding=list(vector),
                )
                await self._session.execute(stmt)
                written += 1
            await self._session.flush()
            if hasattr(self._session, "commit"):
                await self._session.commit()
        return written


def _batched(entries: Iterable[TerminologyEntry], batch_size: int) -> Iterable[tuple[TerminologyEntry, ...]]:
    """Yield fixed-size entry batches."""
    batch = []
    for entry in entries:
        batch.append(entry)
        if len(batch) == batch_size:
            yield tuple(batch)
            batch = []
    if batch:
        yield tuple(batch)


def _batched_values(values: list[object], batch_size: int) -> Iterable[list[object]]:
    """Yield fixed-size batches for non-ORM value lists such as UUIDs."""
    for start in range(0, len(values), batch_size):
        yield values[start : start + batch_size]
