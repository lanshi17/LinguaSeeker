"""Tests for pgvector similarity search repository."""
from __future__ import annotations

import uuid

import pytest

from src.dao.vector_repo import VectorRepository


class FakeSession:
    """Minimal async session for testing VectorRepository."""

    def __init__(self, search_rows=None):
        self.search_rows = search_rows or []
        self.statements = []
        self.added = []
        self.deleted = []

    async def execute(self, statement):
        self.statements.append(statement)
        parent = self

        class FakeScalars:
            def first(self_):
                return None

        class FakeResult:
            def scalars(self_):
                return FakeScalars()

            @staticmethod
            def mappings():
                class FakeMappings:
                    @staticmethod
                    def all():
                        return [
                            {"entry_id": r["entry_id"], "entity_type": r["entity_type"],
                             "source_db": r["source_db"], "external_id": r["external_id"],
                             "display_name": r["display_name"], "embedding_text": r["embedding_text"],
                             "distance": r.get("distance", 0.0)}
                            for r in parent.search_rows
                        ]
                return FakeMappings()
        return FakeResult()

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        pass


@pytest.mark.asyncio
async def test_search_similar_returns_ranked_results():
    """search_similar returns results ordered by cosine distance."""
    entry_id = uuid.uuid4()
    session = FakeSession(search_rows=[
        {"entry_id": entry_id, "entity_type": "gene", "source_db": "HGNC",
         "external_id": "HGNC:1100", "display_name": "BRCA1", "embedding_text": "BRCA1",
         "distance": 0.12},
    ])
    repo = VectorRepository(session)
    rows = await repo.search_similar(
        entity_type="gene",
        embedding=[0.1] * 1024,
        limit=5,
    )
    assert len(rows) == 1
    assert rows[0]["entity_type"] == "gene"
    assert rows[0]["external_id"] == "HGNC:1100"
    assert rows[0]["embedding_text"] == "BRCA1"


@pytest.mark.asyncio
async def test_search_similar_uses_cosine_distance():
    """search_similar uses the <=> cosine distance operator via Vector.cosine_distance()."""
    session = FakeSession()
    repo = VectorRepository(session)
    await repo.search_similar(
        entity_type="gene",
        embedding=[0.1] * 1024,
        limit=5,
    )
    stmt = str(session.statements[0].compile(compile_kwargs={"literal_binds": True}))
    assert "terminology_embeddings" in stmt.lower()
    assert "cosine" in stmt.lower() or "<=>" in stmt


@pytest.mark.asyncio
async def test_search_similar_filters_by_embedding_model():
    """search_similar filters by embedding_model when provided."""
    session = FakeSession()
    repo = VectorRepository(session)
    await repo.search_similar(
        entity_type="gene",
        embedding=[0.1] * 1024,
        limit=5,
        embedding_model="v1",
    )
    stmt = str(session.statements[0].compile(compile_kwargs={"literal_binds": True}))
    assert "embedding_model" in stmt.lower()


@pytest.mark.asyncio
async def test_upsert_embeddings_inserts_new_rows():
    """upsert_embeddings deletes existing and inserts new embeddings."""
    session = FakeSession()
    repo = VectorRepository(session)
    await repo.upsert_embeddings(
        entry_ids=[uuid.uuid4()],
        entity_type="gene",
        source_db="HGNC",
        external_ids=["HGNC:1100"],
        embedding_model="test-v1",
        embeddings=[[0.1] * 1024],
        embedding_texts=["BRCA1"],
    )
    assert len(session.added) == 1
    assert session.added[0].entity_type == "gene"
    assert session.added[0].source_db == "HGNC"
    assert session.added[0].external_id == "HGNC:1100"
    assert session.added[0].embedding_model == "test-v1"
    assert session.added[0].embedding_text == "BRCA1"
    assert len(session.added[0].embedding_text_hash) == 64


@pytest.mark.asyncio
async def test_upsert_embeddings_rejects_mismatched_input_lengths():
    """upsert_embeddings rejects mismatched parallel input lists instead of truncating rows."""
    session = FakeSession()
    repo = VectorRepository(session)

    with pytest.raises(ValueError, match="same length"):
        await repo.upsert_embeddings(
            entry_ids=[uuid.uuid4(), uuid.uuid4()],
            entity_type="gene",
            source_db="HGNC",
            external_ids=["HGNC:1100"],
            embedding_model="test-v1",
            embeddings=[[0.1] * 1024, [0.2] * 1024],
            embedding_texts=["BRCA1", "BRCA1 alias"],
        )
