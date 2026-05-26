"""Tests for terminology embedding index building."""
from __future__ import annotations

import pytest

from src.core.standardize_entities_and_align_knowledge.similarity_match.indexer import (
    TerminologyEmbeddingIndexer,
    build_embedding_text,
    make_embedding_text_hash,
)
from src.core.standardize_entities_and_align_knowledge.contracts import EntityType


class Entry:
    """Simple entry stub for embedding text tests."""

    display_name = "BRCA1"
    aliases = ["BRCA1", "BRCC1"]
    external_id = "HGNC:1100"
    source_db = "HGNC"


def test_build_embedding_text_includes_display_name_aliases_and_source_identity() -> None:
    """Embedding text is deterministic and contains useful terminology context."""
    text = build_embedding_text(Entry())

    assert text == "BRCA1\nBRCC1\nHGNC:1100\nHGNC"


def test_make_embedding_text_hash_is_stable_sha256() -> None:
    """Embedding text hash is stable for upsert identity."""
    assert len(make_embedding_text_hash("BRCA1")) == 64
    assert make_embedding_text_hash("BRCA1") == make_embedding_text_hash("BRCA1")


class FakeEntry:
    def __init__(self, entry_id: str, entity_type: str, source_db: str, display_name: str, external_id: str) -> None:
        self.entry_id = entry_id
        self.entity_type = entity_type
        self.source_db = source_db
        self.display_name = display_name
        self.external_id = external_id
        self.aliases = [display_name]


class FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, rows) -> None:
        self.rows = rows
        self.statements: list[object] = []

    async def execute(self, statement):
        self.statements.append(statement)
        return FakeScalarResult(self.rows)

    async def flush(self) -> None:
        return None


class FakeEmbeddingProvider:
    async def embed_texts(self, texts):
        return type("EmbeddingResult", (), {"vectors": tuple((0.1, 0.2) for _ in texts)})()


@pytest.mark.asyncio
async def test_embedding_indexer_can_filter_entity_types_and_sources() -> None:
    """Embedding build should support narrowing to selected entity types/sources."""
    rows = [
        FakeEntry("e1", "gene", "HGNC", "GLA", "HGNC:4296"),
        FakeEntry("e2", "disease", "OMIM", "FABRY DISEASE", "OMIM:301500"),
        FakeEntry("e3", "variant", "ClinVar", "NM_000169.3(GLA):c.679C>T (p.Arg227Ter)", "ClinVarVariation:10733"),
    ]
    session = FakeSession(rows)
    indexer = TerminologyEmbeddingIndexer(session, FakeEmbeddingProvider())

    count = await indexer.build(
        embedding_model="test-model",
        batch_size=10,
        entity_types={EntityType.DISEASE},
        source_dbs={"OMIM"},
    )

    assert count == 1


@pytest.mark.asyncio
async def test_embedding_indexer_chunks_large_delete_sets() -> None:
    """Embedding rebuild should chunk stale-row deletes to stay under asyncpg argument limits."""
    rows = [
        FakeEntry(f"e{i}", "disease", "OMIM", f"Disease {i}", f"OMIM:{i}")
        for i in range(40000)
    ]
    session = FakeSession(rows)
    indexer = TerminologyEmbeddingIndexer(session, FakeEmbeddingProvider())

    await indexer.build(
        embedding_model="test-model",
        batch_size=1000,
        entity_types={EntityType.DISEASE},
        source_dbs={"OMIM"},
    )

    delete_statements = [statement for statement in session.statements if "DELETE FROM terminology_embeddings" in str(statement)]
    assert len(delete_statements) >= 2
