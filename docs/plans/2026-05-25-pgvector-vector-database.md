# pgvector Vector Database Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add pgvector vector database for Phase 3 entity standardization — semantic similarity search as optional fallback when deterministic terminology matching fails.

**Architecture:** `terminology_embeddings` table with `vector(1536)`, HNSW index. `VectorRepository` in DAO for similarity search. `EmbeddingProvider` calling model-server `POST /v1/embeddings` (port 8001). `VectorFallbackMatcher` in Phase 3 matchers as optional second-pass. Guarded by `config.pgvector_enabled`.

**Tech Stack:** pgvector 0.8+ (PG extension), pgvector 0.3+ (Python), SQLAlchemy 2.0, httpx, Alembic, pytest-asyncio.

**Config (already exists):** `PostgreSQLConfig.pgvector_enabled: bool = True`, `EmbeddingConfig(base_url, model, dimension=1536, batch_size=10)`.

---

## Phase A: Audit Existing Integration

### Task A1: Verify Phase 3 ↔ DAO ↔ Migration parity

**Files:**
- Read: `backend/src/dao/models.py` (all)
- Read: `database/migrations/versions/2026-05-25_add_terminology_reference_tables.py` (all)
- Read: `backend/src/core/standardize_entities_and_align_knowledge/repositories.py` (all)

**Step 1: Run DAO model tests**

Run: `cd backend && uv run pytest tests/dao/test_models.py -v -k "terminology"`
Expected: PASS (6 tests: table_exists, unique_source_external_id, lookup_index, relationship_object_nullable, entity_type_normalized_name_index, source_db_index).

**Step 2: Run repository tests**

Run: `cd backend && uv run pytest tests/core/standardize_entities_and_align_knowledge/test_repositories.py -v`
Expected: All PASS.

**Step 3: Verify migration chain**

Run: `cd backend && uv run alembic -c database/alembic.ini history`
Expected: `4a82b5793055` → `add_terminology_20260525` (head).

**Step 4: Manual verify** — models.py TerminologyEntry/TerminologyAlias/TerminologyRelationship columns match migration create_table columns.

**Step 5: No commit** (verification only — gaps unlikely per progress.txt lines 98-110).

---

## Phase B: pgvector Foundation

### Task B1: Add pgvector Python dependency + register type

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/src/dao/connection.py`

**Step 1: Add pgvector to pyproject.toml**

Add `"pgvector>=0.3.0"` to `[project] dependencies` in `backend/pyproject.toml:34` (before `"socks>=0"`).

**Step 2: Install**

Run: `cd backend && uv pip install -e ".[dev]"`

**Step 3: Verify import**

Run: `cd backend && uv run python -c "from pgvector.sqlalchemy import Vector; print('OK')"`
Expected: prints OK.

**Step 4: Register Vector type in connection.py**

Add after line 9 in `backend/src/dao/connection.py` (after existing imports):

```python
# ── pgvector type registration ────────────────────────────────────────────
# Register the pgvector Vector type at module load so it's available
# for raw-SQL similarity operators (<->, <=>) in repository queries.
try:
    from pgvector.sqlalchemy import Vector  # noqa: F401
except ImportError:
    Vector = None  # type: ignore[assignment]
```

**Step 5: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/src/dao/connection.py
git commit -m "chore: add pgvector dependency and register Vector type"
```

---

### Task B2: Create pgvector extension + embedding table migration

**Files:**
- Create: `database/migrations/versions/2026-05-25_enable_pgvector_and_embeddings.py`
- Create: `backend/tests/dao/test_pgvector_migration.py`

**Step 1: Write the failing migration test**

Create `backend/tests/dao/test_pgvector_migration.py`:

```python
"""Tests for pgvector migration."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
VERSIONS = ROOT / "database" / "migrations" / "versions"


def _load_pgvector_revision():
    for path in sorted(VERSIONS.glob("*_enable_pgvector*.py")):
        spec = importlib.util.spec_from_file_location("pgv", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    pytest.fail("pgvector migration not found")


def test_pgvector_chains_from_terminology():
    mod = _load_pgvector_revision()
    assert mod.down_revision == "add_terminology_20260525"


def test_pgvector_creates_extension(monkeypatch):
    sqls = []
    monkeypatch.setattr("alembic.op.execute", lambda s: sqls.append(str(s)))
    monkeypatch.setattr("alembic.op.create_table", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.create_index", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_table", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_index", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_constraint", lambda *a, **kw: None)
    mod = _load_pgvector_revision()
    mod.upgrade()
    assert any("CREATE EXTENSION" in s.upper() and "vector" in s.lower() for s in sqls)


def test_pgvector_creates_embeddings_table(monkeypatch):
    tables = []
    monkeypatch.setattr("alembic.op.execute", lambda s: None)
    monkeypatch.setattr("alembic.op.create_index", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_table", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_index", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_constraint", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.create_table", lambda name, *a, **kw: tables.append(name))
    mod = _load_pgvector_revision()
    mod.upgrade()
    assert "terminology_embeddings" in tables


def test_pgvector_downgrade_drops(monkeypatch):
    dropped = []
    monkeypatch.setattr("alembic.op.execute", lambda s: None)
    monkeypatch.setattr("alembic.op.create_table", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.create_index", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_index", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_constraint", lambda *a, **kw: None)
    monkeypatch.setattr("alembic.op.drop_table", lambda name, **kw: dropped.append(name))
    mod = _load_pgvector_revision()
    mod.downgrade()
    assert "terminology_embeddings" in dropped
```

**Step 2: Run test — verify it FAILS**

```bash
cd backend
uv run pytest tests/dao/test_pgvector_migration.py -v
```
Expected: FAIL — migration file not found.

**Step 3: Create migration**

```bash
cd backend
uv run alembic -c database/alembic.ini revision -m "enable pgvector and embeddings"
```

Rename the generated file to `2026-05-25_enable_pgvector_and_embeddings.py`.
Fix `down_revision = "add_terminology_20260525"`.

Replace `upgrade()` / `downgrade()`:

```python
"""enable pgvector and embeddings

Revision ID: <auto>
Revises: add_terminology_20260525
Create Date: 2026-05-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "<auto>"
down_revision: Union[str, None] = "add_terminology_20260525"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "terminology_embeddings",
        sa.Column("embedding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("terminology_entries.entry_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("embedding", sa.ARRAY(sa.Float), nullable=False),
        sa.Column("model_version", sa.String(128), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("embedding_id", name=op.f("pk_terminology_embeddings")),
        sa.UniqueConstraint("entry_id", "model_version", name=op.f("uq_terminology_embeddings_entry_model")),
    )

    op.create_index(
        "ix_terminology_embeddings_hnsw",
        "terminology_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 200},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_terminology_embeddings_entity_type",
        "terminology_embeddings",
        ["entity_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_terminology_embeddings_entity_type", table_name="terminology_embeddings")
    op.drop_index("ix_terminology_embeddings_hnsw", table_name="terminology_embeddings")
    op.drop_constraint("uq_terminology_embeddings_entry_model", "terminology_embeddings")
    op.drop_table("terminology_embeddings")
```

**Step 4: Run test — verify it PASSES**

```bash
cd backend
uv run pytest tests/dao/test_pgvector_migration.py -v
```
Expected: PASS (4 tests).

**Step 5: Commit**

```bash
git add database/migrations/versions/2026-05-25_enable_pgvector_and_embeddings.py \
        backend/tests/dao/test_pgvector_migration.py
git commit -m "feat: add pgvector extension + terminology_embeddings migration"
```

---

### Task B3: Add TerminologyEmbedding model to DAO

**Files:**
- Modify: `backend/src/dao/models.py`
- Modify: `backend/tests/dao/test_models.py`

**Step 1: Write the failing model test**

Add to `backend/tests/dao/test_models.py` (after `test_terminology_relationship_object_is_nullable`):

```python
def test_terminology_embeddings_table_in_metadata() -> None:
    """ORM metadata includes the terminology_embeddings table."""
    assert "terminology_embeddings" in Base.metadata.tables


def test_terminology_embeddings_has_embedding_column() -> None:
    """Terminology embeddings table has an embedding column."""
    table = _table("terminology_embeddings")
    assert "embedding" in table.columns


def test_terminology_embeddings_entry_model_unique() -> None:
    """Each entry has at most one embedding per model version."""
    assert ("entry_id", "model_version") in _unique_constraint_columns(
        _table("terminology_embeddings")
    )


def test_terminology_embeddings_cascade_delete() -> None:
    """Embedding is deleted when the parent entry is deleted (CASCADE)."""
    table = _table("terminology_embeddings")
    fk = next(c for c in table.foreign_key_constraints if "entry_id" in [p.name for p in c.columns])
    assert fk.ondelete == "CASCADE"
```

**Step 2: Run test — verify it FAILS**

```bash
cd backend
uv run pytest tests/dao/test_models.py::test_terminology_embeddings_table_in_metadata -v
```
Expected: FAIL — table not in metadata.

**Step 3: Add TerminologyEmbedding model**

Add to `backend/src/dao/models.py`, after `TerminologyRelationship` and before end of file:

```python
class TerminologyEmbedding(Base):
    """Vector embedding for terminology entries used in semantic similarity search."""

    __tablename__ = "terminology_embeddings"
    __table_args__ = (
        UniqueConstraint("entry_id", "model_version", name="uq_terminology_embeddings_entry_model"),
        Index("ix_terminology_embeddings_entity_type", "entity_type"),
    )

    embedding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terminology_entries.entry_id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        ARRAY(Float), nullable=False
    )
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

Note: Need to add `from sqlalchemy import Float` to the existing imports in models.py (Float is already imported via `Numeric`? No — check: currently imports `Numeric` but not `Float`; need to add `Float` to the sqlalchemy import line).

**Step 4: Add Float import to models.py**

Modify the sqlalchemy import line to include `Float`:

```python
from sqlalchemy import (
    ...
    Float,
    ForeignKey,
    ...
)
```

**Step 5: Run model tests**

```bash
cd backend
uv run pytest tests/dao/test_models.py -v -k "terminology_embedding"
```
Expected: PASS (4 tests).

**Step 6: Run all existing model tests to verify no regressions**

```bash
cd backend
uv run pytest tests/dao/test_models.py -v
```
Expected: All PASS.

**Step 7: Commit**

```bash
git add backend/src/dao/models.py backend/tests/dao/test_models.py
git commit -m "feat: add TerminologyEmbedding ORM model"
```

---

## Phase C: Vector Repository

### Task C1: Create VectorRepository with similarity search

**Files:**
- Create: `backend/src/dao/vector_repo.py`
- Create: `backend/tests/dao/test_vector_repo.py`

**Step 1: Write the failing repository test**

Create `backend/tests/dao/test_vector_repo.py`:

```python
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

    async def execute(self, statement):
        self.statements.append(statement)
        stmt_str = str(statement.compile(compile_kwargs={"literal_binds": True}))
        class FakeResult:
            @staticmethod
            def mappings():
                class FakeMappings:
                    @staticmethod
                    def all():
                        return [
                            {"entry_id": r["entry_id"], "entity_type": r["entity_type"],
                             "source_db": r["source_db"], "external_id": r["external_id"],
                             "display_name": r["display_name"], "source_text": r["source_text"],
                             "distance": r.get("distance", 0.0)}
                            for r in self.search_rows
                        ]
                return FakeMappings()
        return FakeResult()

    def add(self, obj):
        self.added.append(obj)

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
         "external_id": "HGNC:1100", "display_name": "BRCA1", "source_text": "BRCA1",
         "distance": 0.12},
    ])
    repo = VectorRepository(session)
    rows = await repo.search_similar(
        entity_type="gene",
        embedding=[0.1] * 1536,
        limit=5,
    )
    assert len(rows) == 1
    assert rows[0]["entity_type"] == "gene"
    assert rows[0]["external_id"] == "HGNC:1100"


@pytest.mark.asyncio
async def test_search_similar_uses_cosine_operator():
    """search_similar uses the <=> cosine distance operator."""
    session = FakeSession()
    repo = VectorRepository(session)
    await repo.search_similar(
        entity_type="gene",
        embedding=[0.1] * 1536,
        limit=5,
    )
    stmt = str(session.statements[0].compile(compile_kwargs={"literal_binds": True}))
    assert "terminology_embeddings" in stmt.lower()
    assert "cosine" in stmt.lower() or "<=>" in stmt


@pytest.mark.asyncio
async def test_upsert_embeddings_inserts_new_rows():
    """upsert_embeddings inserts embeddings for entries that don't have them."""
    session = FakeSession()
    repo = VectorRepository(session)
    await repo.upsert_embeddings(
        entry_ids=[uuid.uuid4()],
        entity_type="gene",
        model_version="test-v1",
        embeddings=[[0.1] * 1536],
        source_texts=["BRCA1"],
    )
    assert len(session.added) == 1
    assert session.added[0].entity_type == "gene"
```

**Step 2: Run test — verify it FAILS**

```bash
cd backend
uv run pytest tests/dao/test_vector_repo.py -v
```
Expected: FAIL — module not found.

**Step 3: Implement VectorRepository**

Create `backend/src/dao/vector_repo.py`:

```python
"""Vector similarity search repository backed by pgvector."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, text

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
                text(f"embedding <=> '{embedding_str}'::vector").label("distance"),
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
```

**Step 4: Run tests — verify they PASS**

```bash
cd backend
uv run pytest tests/dao/test_vector_repo.py -v
```
Expected: PASS (3 tests).

**Step 5: Commit**

```bash
git add backend/src/dao/vector_repo.py backend/tests/dao/test_vector_repo.py
git commit -m "feat: add VectorRepository with cosine similarity search"
```

---

## Phase D: Embedding Provider

### Task D1: Create EmbeddingProvider for model-server

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/providers.py`
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_providers.py`

**Step 1: Write the failing provider test**

Create `backend/tests/core/standardize_entities_and_align_knowledge/test_providers.py`:

```python
"""Tests for the embedding provider."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from src.core.standardize_entities_and_align_knowledge.providers import EmbeddingProvider


@pytest.mark.asyncio
async def test_generate_embeddings_calls_model_server():
    """generate_embeddings POSTs to model-server and returns embeddings."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.json = lambda: {
        "data": [
            {"index": 0, "embedding": [0.1, 0.2, 0.3]},
            {"index": 1, "embedding": [0.4, 0.5, 0.6]},
        ],
        "usage": {"prompt_tokens": 10, "total_tokens": 10},
    }

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        provider = EmbeddingProvider(base_url="http://localhost:8001", model="test-model")
        result = await provider.generate_embeddings(["BRCA1", "TP53"])

    assert len(result) == 2
    assert result[0] == [0.1, 0.2, 0.3]
    assert result[1] == [0.4, 0.5, 0.6]
    mock_post.assert_called_once()
    call_args = mock_post.call_args[1]
    assert call_args["json"]["input"] == ["BRCA1", "TP53"]


@pytest.mark.asyncio
async def test_generate_embeddings_batches_large_inputs():
    """generate_embeddings splits large inputs into batches."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock()
    mock_response.json = lambda: {
        "data": [{"index": 0, "embedding": [0.1]}],
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    }

    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        provider = EmbeddingProvider(
            base_url="http://localhost:8001", model="test", batch_size=2
        )
        result = await provider.generate_embeddings(["a", "b", "c", "d", "e"])

    assert len(result) == 5
    assert mock_post.call_count == 3  # 2 + 2 + 1


@pytest.mark.asyncio
async def test_provider_raises_on_http_error():
    """generate_embeddings raises on non-2xx response."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = AsyncMock(
        side_effect=Exception("HTTP 500")
    )

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        provider = EmbeddingProvider(base_url="http://localhost:8001", model="test")
        with pytest.raises(Exception, match="HTTP 500"):
            await provider.generate_embeddings(["text"])
```

**Step 2: Run test — verify it FAILS**

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_providers.py -v
```
Expected: FAIL — module not found.

**Step 3: Implement EmbeddingProvider**

Create `backend/src/core/standardize_entities_and_align_knowledge/providers.py`:

```python
"""External service providers for Phase 3 — embedding generation via model-server."""
from __future__ import annotations

from typing import Any

import httpx


class EmbeddingProvider:
    """Calls the model-server /v1/embeddings API to generate text embeddings."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str = "",
        batch_size: int = 10,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.batch_size = max(1, batch_size)
        self.timeout = timeout

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of text strings via model-server.

        Args:
            texts: Input text strings.

        Returns:
            List of embedding vectors, each a list of floats.

        Raises:
            httpx.HTTPError: On HTTP failure.
        """
        all_embeddings: list[list[float]] = []
        url = f"{self.base_url}/v1/embeddings"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                payload: dict[str, Any] = {"input": batch}
                if self.model:
                    payload["model"] = self.model

                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

                # Sort by index to maintain order
                items = sorted(data["data"], key=lambda x: x["index"])
                for item in items:
                    all_embeddings.append(item["embedding"])

        return all_embeddings
```

**Step 4: Run tests — verify they PASS**

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_providers.py -v
```
Expected: PASS (3 tests).

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/providers.py \
        backend/tests/core/standardize_entities_and_align_knowledge/test_providers.py
git commit -m "feat: add EmbeddingProvider for model-server embedding generation"
```

---

## Phase E: Terminology Embedding Service

### Task E1: Create TerminologyEmbeddingService

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/embedding_service.py`
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_embedding_service.py`

**Step 1: Write the failing service test**

Create `backend/tests/core/standardize_entities_and_align_knowledge/test_embedding_service.py`:

```python
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
    mock_result = MagicMock()
    mock_result.mappings = lambda: type("M", (), {
        "all": lambda: [
            {"entry_id": uuid.uuid4(), "entity_type": "gene", "display_name": "BRCA1"},
            {"entry_id": uuid.uuid4(), "entity_type": "gene", "display_name": "TP53"},
        ],
    })()
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
```

**Step 2: Run test — verify it FAILS**

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_embedding_service.py -v
```
Expected: FAIL — module not found.

**Step 3: Implement TerminologyEmbeddingService**

Create `backend/src/core/standardize_entities_and_align_knowledge/embedding_service.py`:

```python
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
```

**Step 4: Run tests — verify they PASS**

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_embedding_service.py -v
```
Expected: PASS (3 tests).

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/embedding_service.py \
        backend/tests/core/standardize_entities_and_align_knowledge/test_embedding_service.py
git commit -m "feat: add TerminologyEmbeddingService for embedding generation and search"
```

---

## Phase F: Vector Fallback Matcher

### Task F1: Add VectorFallbackMatcher + integrate into Phase 3

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/matchers.py`
- Modify: `backend/tests/core/standardize_entities_and_align_knowledge/test_matchers.py`

**Step 1: Write the failing test**

Add to `backend/tests/core/standardize_entities_and_align_knowledge/test_matchers.py`:

```python
@pytest.mark.asyncio
async def test_vector_fallback_matcher_returns_candidates():
    """VectorFallbackMatcher returns candidates when embedding service returns results."""
    mock_embedding_svc = MagicMock()
    mock_embedding_svc.search_similar = AsyncMock(return_value=[
        {"external_id": "HGNC:1100", "display_name": "BRCA1", "source_db": "HGNC",
         "entity_type": "gene", "distance": 0.05, "entry_id": str(uuid.uuid4())},
    ])

    from src.core.standardize_entities_and_align_knowledge.matchers import VectorFallbackMatcher
    matcher = VectorFallbackMatcher(embedding_service=mock_embedding_svc, min_distance=0.3)
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        raw_text="BRAC1",
        normalized_text="brac1",
        role=BindingRole.SUBJECT,
        track="original",
        chain_id="chain-1",
    )
    results = await matcher.search(candidate)
    assert len(results) > 0
    assert results[0].external_id == "HGNC:1100"


@pytest.mark.asyncio
async def test_vector_fallback_matcher_filters_by_distance():
    """VectorFallbackMatcher filters out results beyond min_distance."""
    mock_embedding_svc = MagicMock()
    mock_embedding_svc.search_similar = AsyncMock(return_value=[
        {"external_id": "FAR", "display_name": "far", "source_db": "X",
         "entity_type": "gene", "distance": 0.9, "entry_id": str(uuid.uuid4())},
    ])

    from src.core.standardize_entities_and_align_knowledge.matchers import VectorFallbackMatcher
    matcher = VectorFallbackMatcher(embedding_service=mock_embedding_svc, min_distance=0.3)
    candidate = StandardizationCandidate(
        candidate_id="c1", entity_type=EntityType.GENE, raw_text="BRCA1",
        normalized_text="brca1", role=BindingRole.SUBJECT, track="original",
        chain_id="chain-1",
    )
    results = await matcher.search(candidate)
    assert len(results) == 0  # 0.9 > 0.3 threshold


@pytest.mark.asyncio
async def test_terminology_matcher_uses_vector_fallback():
    """TerminologyMatcher falls back to vector when deterministic returns nothing."""
    from src.core.standardize_entities_and_align_knowledge.matchers import TerminologyMatcher

    mock_repo = MagicMock()
    mock_repo.find_alias_candidates = AsyncMock(return_value=[])

    mock_vector = MagicMock()
    mock_vector.search = AsyncMock(return_value=[])
    matcher = TerminologyMatcher(repository=mock_repo, vector_fallback=mock_vector)
    candidate = StandardizationCandidate(
        candidate_id="c1", entity_type=EntityType.GENE, raw_text="unknown_gene",
        normalized_text="unknown_gene", role=BindingRole.SUBJECT, track="original",
        chain_id="chain-1",
    )
    match = await matcher.match(candidate)
    assert match.status == MatchStatus.UNMAPPED  # deterministic fails, vector has nothing
    mock_vector.search.assert_called_once_with(candidate)
```

**Step 2: Run test — verify it FAILS**

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_matchers.py -v -k "vector"
```
Expected: FAIL — VectorFallbackMatcher not defined.

**Step 3: Implement VectorFallbackMatcher**

Add to `backend/src/core/standardize_entities_and_align_knowledge/matchers.py`, after `TerminologyMatcher`:

```python
class VectorFallbackMatcher:
    """Semantic similarity fallback matcher using pgvector embeddings.

    Only invoked when the deterministic TerminologyMatcher returns zero matches
    or all-ambiguous results. Not used during normal operation.
    """

    def __init__(
        self,
        *,
        embedding_service: Any,  # TerminologyEmbeddingService
        min_distance: float = 0.3,
    ) -> None:
        self.embedding_service = embedding_service
        self.min_distance = min_distance

    async def search(
        self,
        candidate: StandardizationCandidate,
    ) -> list[TerminologyCandidate]:
        """Search for similar terminology entries by semantic similarity.

        Returns empty list when embedding service is unavailable or returns
        no results within the distance threshold.
        """
        if self.embedding_service is None:
            return []

        try:
            results = await self.embedding_service.search_similar(
                entity_type=candidate.entity_type,
                query_text=candidate.normalized_text,
                limit=5,
                min_distance=self.min_distance,
            )
        except Exception:
            return []

        return [
            TerminologyCandidate(
                entry_id=str(r["entry_id"]),
                entity_type=EntityType(r["entity_type"]),
                source_db=str(r["source_db"]),
                external_id=str(r["external_id"]),
                display_name=str(r["display_name"]),
                normalized_alias=str(r["source_text"]),
                alias_type="vector_similarity",
                raw_payload={"distance": float(r["distance"])},
            )
            for r in results
        ]
```

**Step 4: Add optional vector_fallback parameter to TerminologyMatcher**

Modify `TerminologyMatcher.__init__` in `matchers.py`:

```python
class TerminologyMatcher:
    """Apply deterministic source-priority matching against terminology candidates."""

    def __init__(
        self,
        repository: StandardizationRepository,
        vector_fallback: VectorFallbackMatcher | None = None,
    ) -> None:
        self.repository = repository
        self.vector_fallback = vector_fallback
```

Modify `TerminologyMatcher.match()` to use fallback when no deterministic candidates:

In the `match` method, after getting `candidates` from `find_alias_candidates`:

```python
# If deterministic matching found nothing, try vector fallback
if not candidates and self.vector_fallback is not None:
    candidates = await self.vector_fallback.search(candidate)
```

**Step 5: Run all matcher tests**

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_matchers.py -v
```
Expected: All PASS (existing + 3 new vector tests).

**Step 6: Run all Phase 3 tests for regressions**

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/ -v
```
Expected: All PASS.

**Step 7: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/matchers.py \
        backend/tests/core/standardize_entities_and_align_knowledge/test_matchers.py
git commit -m "feat: add VectorFallbackMatcher with optional semantic similarity fallback"
```

---

## Phase G: CLI, Docs, Final Verification

### Task G1: Add CLI entry for embedding generation

**Files:**
- Modify: `scripts/import_terminology.py` (or create new script)

**Step 1: Add `--generate-embeddings` flag to import_terminology.py**

Modify `scripts/import_terminology.py` to add:

```python
parser.add_argument("--generate-embeddings", action="store_true",
                    help="Generate pgvector embeddings after import")
```

In `main()`, after importing terminology, when `--generate-embeddings` is set:

```python
if args.generate_embeddings:
    from src.core.standardize_entities_and_align_knowledge.embedding_service import (
        TerminologyEmbeddingService,
    )
    from src.core.standardize_entities_and_align_knowledge.providers import EmbeddingProvider
    from src.dao.vector_repo import VectorRepository
    from src.core.standardize_entities_and_align_knowledge.contracts import EntityType
    from src.core.config import get_config

    cfg = get_config()
    if not cfg.postgresql.pgvector_enabled:
        logger.warning("pgvector is disabled in config; skipping embedding generation")
        return

    from src.dao.connection import async_session_factory, build_async_engine
    engine = build_async_engine(cfg)
    session_factory = async_session_factory(engine)

    provider = EmbeddingProvider(
        base_url=cfg.embedding.base_url,
        model=cfg.embedding.model,
        batch_size=cfg.embedding.batch_size,
    )

    async with session_factory() as session:
        repo = VectorRepository(session)
        svc = TerminologyEmbeddingService(
            session=session,
            repository=repo,
            provider=provider,
            model_version=cfg.embedding.model or "default",
        )
        for entity_type in EntityType:
            count = await svc.generate_and_store(entity_type)
            logger.info("Generated %d embeddings for %s", count, entity_type.value)

    await engine.dispose()
```

**Step 2: Verify script parses correctly**

```bash
cd backend
uv run python ../scripts/import_terminology.py --help
```
Expected: `--generate-embeddings` flag shown.

**Step 3: Commit**

```bash
git add scripts/import_terminology.py
git commit -m "feat: add --generate-embeddings flag to terminology import CLI"
```

---

### Task G2: Update documentation

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/README.md`
- Modify: `backend/src/dao/README.md`
- Modify: `progress.txt`

**Step 1: Update Phase 3 README**

Add to `backend/src/core/standardize_entities_and_align_knowledge/README.md`, before "## Unsupported Next Iteration Features":

```markdown
## Vector Similarity Search (pgvector)

Phase 3 supports optional semantic similarity search via pgvector as a fallback
when deterministic matching returns no results.

### Architecture

```text
TerminologyMatcher (deterministic)
    │
    └── no results?
        └── VectorFallbackMatcher
            └── TerminologyEmbeddingService
                ├── EmbeddingProvider → model-server /v1/embeddings
                └── VectorRepository → pgvector <=> cosine distance
```

### Enabling

1. Ensure `pgvector_enabled: true` in PostgreSQL config
2. Run the pgvector migration: `uv run alembic upgrade head`
3. Start model-server on port 8001 with embedding model loaded
4. Generate embeddings: `uv run python scripts/import_terminology.py --generate-embeddings`

### Usage

```python
from src.core.standardize_entities_and_align_knowledge.matchers import (
    TerminologyMatcher,
    VectorFallbackMatcher,
)
from src.core.standardize_entities_and_align_knowledge.embedding_service import (
    TerminologyEmbeddingService,
)

# Wire vector fallback (optional — matcher works without it)
embedding_svc = TerminologyEmbeddingService(...)
vector_matcher = VectorFallbackMatcher(embedding_service=embedding_svc)
matcher = TerminologyMatcher(repository=repo, vector_fallback=vector_matcher)
```

### Tables

- `terminology_embeddings`: embedding vectors indexed by HNSW for cosine similarity search

### Performance

- HNSW index with m=16, ef_construction=200 provides fast approximate nearest neighbor search
- Embedding generation is batched (configurable batch_size, default 10)
- Consider running embedding generation during off-peak hours for large terminology databases
```

**Step 2: Update DAO README**

Add to `backend/src/dao/README.md` models table:

```
| `TerminologyEmbedding` | `terminology_embeddings` | Vector embeddings for terminology entries with HNSW index for cosine similarity search. |
```

Add to "Usage Patterns" section:

```markdown
### Vector Similarity Search

```python
from src.dao.vector_repo import VectorRepository

repo = VectorRepository(session)
results = await repo.search_similar(
    entity_type="gene",
    embedding=[0.1] * 1536,
    limit=10,
)
```
```

**Step 3: Update progress.txt**

```
[2026-05-25] pgvector vector database: extension, migration, model, VectorRepository, EmbeddingProvider, TerminologyEmbeddingService, VectorFallbackMatcher, CLI, docs [completed]
```

**Step 4: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/README.md \
        backend/src/dao/README.md \
        progress.txt
git commit -m "docs: add pgvector vector database documentation"
```

---

### Task G3: Final verification

**Step 1: Full lint check**

```bash
cd backend
uv run ruff check src/dao/ src/core/standardize_entities_and_align_knowledge/ tests/dao/ tests/core/standardize_entities_and_align_knowledge/
```
Expected: No errors.

**Step 2: Run all affected test suites**

```bash
cd backend
uv run pytest tests/dao/ tests/core/standardize_entities_and_align_knowledge/ \
    -v --tb=short
```
Expected: All PASS.

**Step 3: Verify migration chain completeness**

```bash
cd backend
uv run alembic -c database/alembic.ini history
```
Expected: `4a82b5793055` → `add_terminology_20260525` → `<pgvector_revision>` (head).

**Step 4: Commit**

```bash
git add -A
git commit -m "test: final verification of pgvector implementation passes"
```

---

## Summary of All Deliverables

| Phase | Files Created | Files Modified |
|-------|-------------|---------------|
| A — Audit | — | (read-only verification) |
| B1 — Dependency | — | `pyproject.toml`, `connection.py` |
| B2 — Migration | `test_pgvector_migration.py`, migration `.py` | — |
| B3 — Model | — | `models.py`, `test_models.py` |
| C1 — Repo | `vector_repo.py`, `test_vector_repo.py` | — |
| D1 — Provider | `providers.py`, `test_providers.py` | — |
| E1 — Service | `embedding_service.py`, `test_embedding_service.py` | — |
| F1 — Matcher | — | `matchers.py`, `test_matchers.py` |
| G1 — CLI | — | `import_terminology.py` |
| G2 — Docs | — | Phase 3 `README.md`, DAO `README.md`, `progress.txt` |

**9 new files, 8 modified files. 7 commits.**
