"""Build pgvector embeddings for imported terminology entries."""
from __future__ import annotations

import hashlib
from collections.abc import Iterable

from sqlalchemy import select

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

    async def build(self, *, embedding_model: str, batch_size: int) -> int:
        """Embed terminology entries that do not yet have current model embeddings."""
        result = await self._session.execute(select(TerminologyEntry).order_by(TerminologyEntry.entry_id))
        entries = tuple(result.scalars().all())
        written = 0
        for batch in _batched(entries, batch_size):
            texts = tuple(build_embedding_text(entry) for entry in batch)
            vectors = (await self._embedding_provider.embed_texts(texts)).vectors
            for entry, text, vector in zip(batch, texts, vectors, strict=True):
                embedding = TerminologyEmbedding(
                    entry_id=entry.entry_id,
                    entity_type=entry.entity_type,
                    source_db=entry.source_db,
                    external_id=entry.external_id,
                    embedding_text=text,
                    embedding_text_hash=make_embedding_text_hash(text),
                    embedding_model=embedding_model,
                    embedding=list(vector),
                )
                self._session.add(embedding)
                written += 1
            await self._session.flush()
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
