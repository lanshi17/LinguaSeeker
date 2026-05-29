# Standardization Precise And Similarity Matching Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split Phase 3 entity standardization into precise matching and similarity matching submodules, with semantic matching backed by model-server embeddings/rerank and PostgreSQL pgvector.

**Architecture:** Keep `backend/src/core/standardize_entities_and_align_knowledge/` as the Phase 3 vertical slice. Move deterministic alias matching into `precise_match/`, add `similarity_match/` for model-server inference plus pgvector candidate retrieval, and wire an exact-first hybrid matcher through the existing facade. The orchestrator-facing API remains stable: callers still use `EntityStandardizationService.run_dual_result()`.

**Tech Stack:** Python 3.12, dataclasses, Pydantic settings, SQLAlchemy 2 async ORM, Alembic, PostgreSQL pgvector, httpx, model-server `/v1/embeddings` and `/v1/rerank`, pytest, uv, Ruff

---

**Status:** planned
**Created:** 2026-05-25
**Completed:** N/A
**PR:** N/A

## Prerequisites

- Use a dedicated worktree before implementation because this is a medium backend refactor.
- Use @test-driven-development for each task.
- Use @systematic-debugging for unexpected failures.
- Use @verification-before-completion before claiming completion.
- Use @module-guide after implementation and tests pass.
- Use @doc-organize after documentation updates.
- Do not stage or modify unrelated dirty worktree files. Current known unrelated file: `backend/tests/scripts/test_e2e_standardize_entities.py`.
- All Python dependency changes must use `uv`; do not use system `pip`.

## Context From Current Code

- Existing deterministic Phase 3 code lives in `backend/src/core/standardize_entities_and_align_knowledge/`.
- `matchers.py` currently owns deterministic alias matching and should become a compatibility wrapper plus hybrid matcher entry point.
- `repositories.py::find_alias_candidates()` is the precise lookup boundary and should stay available for exact matching.
- `backend/services/model-server` already exposes `POST /v1/embeddings` and `POST /v1/rerank`.
- Backend config already has `cfg.embedding`, `cfg.rerank`, `cfg.model_server_url`, and `cfg.postgresql.pgvector_enabled`.
- Existing Phase 3 MVP intentionally excluded vectors; this plan extends that completed MVP rather than replacing it.
- Old-version search found RAG-style vector usage under `backend/.old_version/src/domain/agent/workflow.py`, but no reusable typed Phase 3 standardization module.

## Confirmed Decisions

- Vector database: PostgreSQL + pgvector.
- Semantic inference provider: `backend/services/model-server`.
- Embedding endpoint: `POST {base_url}/v1/embeddings`.
- Rerank endpoint: `POST {base_url}/v1/rerank`.
- Default embedding model/dimension should align with model-server defaults: `Qwen/Qwen3-Embedding-0.6B`, dimension `1024`.
- Default rerank model should align with model-server default: `BAAI/bge-reranker-v2-m3`.
- Precise matching remains authoritative. Similarity matching only runs when precise matching returns `unmapped`.
- Deterministic `ambiguous` matches are not auto-resolved by semantic matching in this iteration.
- Similarity matches persist as existing `MatchStatus.STANDARDIZED` when accepted, with `match_method="similarity"` and score metadata in `raw_payload`.
- If semantic retrieval or model-server inference fails for one candidate, return the precise `unmapped` result with a semantic-failure rationale; do not abort the document run.

## Target Module Layout

```text
backend/src/core/standardize_entities_and_align_knowledge/
├── precise_match/
│   ├── __init__.py
│   └── core.py
├── similarity_match/
│   ├── __init__.py
│   ├── contracts.py
│   ├── core.py
│   ├── indexer.py
│   ├── providers.py
│   └── repositories.py
├── api.py
├── contracts.py
├── core.py
├── matchers.py
└── repositories.py
```

## Task 1: Align Model Config And Add pgvector Dependency

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock`
- Modify: `backend/src/core/config.py`
- Modify: `backend/tests/core/test_config.py`

**Step 1: Write the failing config test**

Append to `backend/tests/core/test_config.py`:

```python
def test_standardization_similarity_model_defaults_match_model_server() -> None:
    """Backend semantic matching defaults align with model-server defaults."""
    from src.core.config import Settings

    settings = Settings()

    assert settings.embedding.base_url == ""
    assert settings.embedding.model == "Qwen/Qwen3-Embedding-0.6B"
    assert settings.embedding.dimension == 1024
    assert settings.rerank.model == "BAAI/bge-reranker-v2-m3"
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/test_config.py::test_standardization_similarity_model_defaults_match_model_server -v
```

Expected: FAIL because backend embedding/rerank defaults are currently empty or dimension `1536`.

**Step 3: Add the dependency with uv**

Run:

```bash
cd backend
uv add pgvector
```

Expected: `backend/pyproject.toml` and `backend/uv.lock` update. Do not manually install with `pip`.

**Step 4: Update config defaults**

In `backend/src/core/config.py`, update only embedding/rerank defaults:

```python
class EmbeddingConfig(BaseModel):
    """Embedding model."""

    base_url: str = ""
    model: str = "Qwen/Qwen3-Embedding-0.6B"
    dimension: int = 1024
    batch_size: int = 10


class RerankConfig(BaseModel):
    """Rerank model."""

    base_url: str = ""
    model: str = "BAAI/bge-reranker-v2-m3"
    top_k: int = 10
    score_threshold: float = 0.7
```

Also update the flat fields:

```python
embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
embedding_dimension: int = 1024
rerank_model: str = "BAAI/bge-reranker-v2-m3"
```

**Step 5: Run test to verify it passes**

Run:

```bash
cd backend
uv run pytest tests/core/test_config.py::test_standardization_similarity_model_defaults_match_model_server -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/src/core/config.py backend/tests/core/test_config.py
git commit -m "chore(standardization): add pgvector dependency"
```

## Task 2: Add pgvector ORM Model And Migration

**Files:**
- Modify: `backend/src/dao/models.py`
- Modify: `backend/tests/dao/test_models.py`
- Create: `database/migrations/versions/2026-05-25_add_terminology_embeddings_pgvector.py`
- Modify: `backend/tests/dao/test_alembic_migration.py`

**Step 1: Write failing ORM tests**

Update `EXPECTED_TABLES` in `backend/tests/dao/test_models.py` to include:

```python
"terminology_embeddings",
```

Append:

```python
def test_terminology_embeddings_table_exists() -> None:
    """Terminology embeddings are stored separately from source aliases."""
    table = _table("terminology_embeddings")

    assert table.c.entry_id.nullable is False
    assert table.c.embedding_text_hash.nullable is False
    assert table.c.embedding_model.nullable is False


def test_terminology_embeddings_unique_text_per_model() -> None:
    """One embedding row exists per terminology entry/text/model tuple."""
    table = _table("terminology_embeddings")

    assert (
        "entry_id",
        "embedding_text_hash",
        "embedding_model",
    ) in _unique_constraint_columns(table)
```

**Step 2: Run ORM tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/dao/test_models.py::test_terminology_embeddings_table_exists tests/dao/test_models.py::test_terminology_embeddings_unique_text_per_model -v
```

Expected: FAIL because the ORM model does not exist.

**Step 3: Add the ORM model**

In `backend/src/dao/models.py`, import pgvector:

```python
from pgvector.sqlalchemy import Vector
```

Add after `TerminologyRelationship`:

```python
class TerminologyEmbedding(Base, TimestampMixin):
    """pgvector embedding for terminology semantic retrieval."""

    __tablename__ = "terminology_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "entry_id",
            "embedding_text_hash",
            "embedding_model",
            name="uq_terminology_embeddings_entry_text_model",
        ),
        Index("ix_terminology_embeddings_entity_type_model", "entity_type", "embedding_model"),
        Index("ix_terminology_embeddings_entry_id", "entry_id"),
    )

    embedding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("terminology_entries.entry_id"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_db: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
```

**Step 4: Run ORM tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/dao/test_models.py -v
```

Expected: PASS.

**Step 5: Write failing migration tests**

In `backend/tests/dao/test_alembic_migration.py`, add a loader:

```python
def _load_embedding_revision_module():
    """Load the terminology embedding migration revision as a Python module."""
    import importlib.util

    revision_paths = list(VERSIONS_DIR.glob("*add_terminology_embeddings_pgvector.py"))
    assert len(revision_paths) == 1
    revision_path = revision_paths[0]
    spec = importlib.util.spec_from_file_location("add_terminology_embeddings_pgvector", revision_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```

Add tests:

```python
def test_head_revision_points_to_pgvector_embeddings() -> None:
    """The Alembic head includes pgvector terminology embeddings."""
    backend_str = str(BACKEND_DIR)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    script = ScriptDirectory.from_config(config)

    head = script.get_revision("head")

    assert head is not None
    assert head.revision == "add_terminology_embeddings_20260525"
    assert head.down_revision == "add_terminology_20260525"


def test_embedding_migration_creates_pgvector_extension(monkeypatch) -> None:
    """The embedding migration enables pgvector before creating vector columns."""
    module = _load_embedding_revision_module()
    statements: list[str] = []

    monkeypatch.setattr(module.op, "execute", lambda statement: statements.append(str(statement)))
    monkeypatch.setattr(module.op, "create_table", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.op, "create_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.op, "f", lambda name: name)

    module.upgrade()

    assert "CREATE EXTENSION IF NOT EXISTS vector" in statements
```

Update the existing `test_head_revision_points_to_terminology_schema()` so it verifies the revision chain rather than the final head, or rename it to `test_terminology_revision_extends_initial_schema()` and assert the terminology revision still has down revision `4a82b5793055`.

**Step 6: Run migration tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/dao/test_alembic_migration.py::test_head_revision_points_to_pgvector_embeddings tests/dao/test_alembic_migration.py::test_embedding_migration_creates_pgvector_extension -v
```

Expected: FAIL because the migration file does not exist.

**Step 7: Add the migration**

Create `database/migrations/versions/2026-05-25_add_terminology_embeddings_pgvector.py`:

```python
"""add terminology embeddings pgvector table

Revision ID: add_terminology_embeddings_20260525
Revises: add_terminology_20260525
Create Date: 2026-05-25
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "add_terminology_embeddings_20260525"
down_revision: Union[str, None] = "add_terminology_20260525"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "terminology_embeddings",
        sa.Column("embedding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("source_db", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("embedding_text", sa.Text(), nullable=False),
        sa.Column("embedding_text_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["terminology_entries.entry_id"],
            name=op.f("fk_terminology_embeddings_entry_id"),
        ),
        sa.PrimaryKeyConstraint("embedding_id", name=op.f("pk_terminology_embeddings")),
        sa.UniqueConstraint(
            "entry_id",
            "embedding_text_hash",
            "embedding_model",
            name=op.f("uq_terminology_embeddings_entry_text_model"),
        ),
    )
    op.create_index(
        "ix_terminology_embeddings_entity_type_model",
        "terminology_embeddings",
        ["entity_type", "embedding_model"],
        unique=False,
    )
    op.create_index(
        "ix_terminology_embeddings_entry_id",
        "terminology_embeddings",
        ["entry_id"],
        unique=False,
    )
    op.create_index(
        "ix_terminology_embeddings_embedding_hnsw",
        "terminology_embeddings",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_terminology_embeddings_embedding_hnsw", table_name="terminology_embeddings")
    op.drop_index("ix_terminology_embeddings_entry_id", table_name="terminology_embeddings")
    op.drop_index("ix_terminology_embeddings_entity_type_model", table_name="terminology_embeddings")
    op.drop_table("terminology_embeddings")
```

**Step 8: Run migration tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/dao/test_alembic_migration.py tests/dao/test_models.py -v
```

Expected: PASS.

**Step 9: Commit**

```bash
git add backend/src/dao/models.py backend/tests/dao/test_models.py backend/tests/dao/test_alembic_migration.py database/migrations/versions/2026-05-25_add_terminology_embeddings_pgvector.py
git commit -m "feat(standardization): add terminology embedding table"
```

## Task 3: Extend Typed Match Contracts

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/contracts.py`
- Modify: `backend/tests/core/standardize_entities_and_align_knowledge/test_contracts.py`

**Step 1: Write failing contract tests**

Append to `backend/tests/core/standardize_entities_and_align_knowledge/test_contracts.py`:

```python
def test_entity_match_defaults_to_precise_method() -> None:
    """Existing exact matches keep precise matching as the default method."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain-1",
        track="original",
    )

    match = EntityMatch(
        candidate=candidate,
        status=MatchStatus.UNMAPPED,
        external_id=None,
        display_name="BRCA1",
    )

    assert match.match_method == MatchMethod.PRECISE
    assert match.similarity_score is None


def test_similarity_candidate_contract_is_typed() -> None:
    """Similarity retrieval returns typed candidates, not raw dictionaries."""
    candidate = SimilarityCandidate(
        terminology=TerminologyCandidate(
            entry_id="entry-1",
            entity_type=EntityType.GENE,
            source_db="HGNC",
            external_id="HGNC:1100",
            display_name="BRCA1",
            normalized_alias="brca1",
            alias_type="semantic",
        ),
        embedding_text="BRCA1 BRCA1 DNA repair associated",
        vector_distance=0.12,
        rerank_score=None,
    )

    assert candidate.terminology.external_id == "HGNC:1100"
    assert candidate.vector_distance == 0.12
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_contracts.py::test_entity_match_defaults_to_precise_method tests/core/standardize_entities_and_align_knowledge/test_contracts.py::test_similarity_candidate_contract_is_typed -v
```

Expected: FAIL because the new contract types do not exist.

**Step 3: Add contract types**

In `contracts.py`, add:

```python
class MatchMethod(str, Enum):
    """How an entity match was produced."""

    PRECISE = "precise"
    SIMILARITY = "similarity"
```

Add:

```python
@dataclass(frozen=True)
class SimilarityCandidate:
    """Semantic retrieval candidate returned from pgvector and rerank."""

    terminology: TerminologyCandidate
    embedding_text: str
    vector_distance: float
    rerank_score: float | None = None
```

Extend `EntityMatch` by adding defaulted fields at the end:

```python
    match_method: MatchMethod = MatchMethod.PRECISE
    similarity_score: float | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
```

**Step 4: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_contracts.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/contracts.py backend/tests/core/standardize_entities_and_align_knowledge/test_contracts.py
git commit -m "feat(standardization): add semantic match contracts"
```

## Task 4: Move Deterministic Matcher Into precise_match

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/precise_match/__init__.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/precise_match/core.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/matchers.py`
- Modify: `backend/tests/core/standardize_entities_and_align_knowledge/test_matchers.py`
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_precise_match.py`

**Step 1: Write failing direct-import test**

Create `backend/tests/core/standardize_entities_and_align_knowledge/test_precise_match.py`:

```python
"""Tests for precise deterministic terminology matching."""
from __future__ import annotations

import pytest

from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityType,
    MatchMethod,
    MatchStatus,
    StandardizationCandidate,
    TerminologyCandidate,
)
from src.core.standardize_entities_and_align_knowledge.precise_match.core import PreciseTerminologyMatcher


class FakeRepository:
    """Repository stub returning predefined terminology candidates."""

    def __init__(self, candidates):
        self.candidates = tuple(candidates)

    async def find_alias_candidates(self, entity_type, raw_text):
        return self.candidates


@pytest.mark.asyncio
async def test_precise_matcher_standardizes_unique_hgnc_alias() -> None:
    """Precise matcher preserves existing deterministic matching semantics."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain-1",
        track="original",
    )
    terminology = TerminologyCandidate(
        entry_id="entry-1",
        entity_type=EntityType.GENE,
        source_db="HGNC",
        external_id="HGNC:1100",
        display_name="BRCA1",
        normalized_alias="BRCA1",
        alias_type="primary",
    )

    match = await PreciseTerminologyMatcher(FakeRepository([terminology])).match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "HGNC:1100"
    assert match.match_method == MatchMethod.PRECISE
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_precise_match.py -v
```

Expected: FAIL because `precise_match.core` does not exist.

**Step 3: Move matcher code**

Create `backend/src/core/standardize_entities_and_align_knowledge/precise_match/__init__.py`:

```python
"""Precise deterministic terminology matching."""

from src.core.standardize_entities_and_align_knowledge.precise_match.core import PreciseTerminologyMatcher

__all__ = ["PreciseTerminologyMatcher"]
```

Create `backend/src/core/standardize_entities_and_align_knowledge/precise_match/core.py` by moving the existing `TerminologyMatcher` implementation from `matchers.py` and renaming the class:

```python
"""Precise deterministic terminology matching rules for Phase 3."""
from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.contracts import (
    EntityMatch,
    EntityType,
    MatchMethod,
    MatchStatus,
    StandardizationCandidate,
    TerminologyCandidate,
)
from src.core.standardize_entities_and_align_knowledge.repositories import StandardizationRepository


ALIAS_TYPE_PRIORITY = {
    "primary": 0,
    "alias": 1,
    "previous_symbol": 2,
    "name": 3,
    "rsid": 4,
}


class PreciseTerminologyMatcher:
    """Apply deterministic source-priority matching against terminology candidates."""

    def __init__(self, repository: StandardizationRepository):
        self._repository = repository

    async def match(self, candidate: StandardizationCandidate) -> EntityMatch:
        """Match one candidate to zero, one, or many deterministic terminology entries."""
        choices = await self._repository.find_alias_candidates(candidate.entity_type, candidate.raw_text)
        ranked = self._rank(candidate.entity_type, choices)

        if len(ranked) == 1:
            selected = ranked[0]
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.STANDARDIZED,
                external_id=selected.external_id,
                display_name=selected.display_name,
                terminology_candidates=(selected,),
                rationale=f"unique {selected.source_db} {selected.alias_type} match",
                match_method=MatchMethod.PRECISE,
            )
        if len(ranked) > 1:
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.AMBIGUOUS,
                external_id=None,
                display_name=candidate.raw_text,
                terminology_candidates=tuple(ranked),
                rationale="multiple deterministic terminology candidates",
                match_method=MatchMethod.PRECISE,
            )
        return EntityMatch(
            candidate=candidate,
            status=MatchStatus.UNMAPPED,
            external_id=None,
            display_name=candidate.raw_text,
            rationale="no deterministic terminology candidate",
            match_method=MatchMethod.PRECISE,
        )

    def _rank(
        self,
        entity_type: EntityType,
        choices: tuple[TerminologyCandidate, ...],
    ) -> tuple[TerminologyCandidate, ...]:
        """Apply deterministic source ranking by entity type."""
        if entity_type == EntityType.GENE:
            return self._apply_alias_type_priority(
                tuple(candidate for candidate in choices if candidate.source_db == "HGNC"),
            )
        if entity_type == EntityType.DISEASE:
            omim = tuple(candidate for candidate in choices if candidate.source_db == "OMIM")
            if omim:
                return self._apply_alias_type_priority(omim)
            return self._apply_alias_type_priority(
                tuple(candidate for candidate in choices if candidate.source_db in {"HPO", "MONDO"}),
            )
        if entity_type == EntityType.PHENOTYPE:
            return self._apply_alias_type_priority(
                tuple(candidate for candidate in choices if candidate.source_db == "HPO"),
            )
        if entity_type == EntityType.VARIANT:
            return self._apply_alias_type_priority(
                tuple(candidate for candidate in choices if candidate.source_db == "ClinVar"),
            )
        raise ValueError(f"Unsupported entity type: {entity_type}")

    def _apply_alias_type_priority(
        self,
        choices: tuple[TerminologyCandidate, ...],
    ) -> tuple[TerminologyCandidate, ...]:
        """Keep only candidates at the best alias-type priority level."""
        if not choices:
            return ()
        best_priority = min(ALIAS_TYPE_PRIORITY.get(candidate.alias_type, 99) for candidate in choices)
        return tuple(
            candidate
            for candidate in choices
            if ALIAS_TYPE_PRIORITY.get(candidate.alias_type, 99) == best_priority
        )
```

Replace `backend/src/core/standardize_entities_and_align_knowledge/matchers.py` with compatibility exports for now:

```python
"""Matcher facade exports for Phase 3 standardization."""
from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.precise_match.core import (
    ALIAS_TYPE_PRIORITY,
    PreciseTerminologyMatcher,
)

TerminologyMatcher = PreciseTerminologyMatcher

__all__ = ["ALIAS_TYPE_PRIORITY", "PreciseTerminologyMatcher", "TerminologyMatcher"]
```

**Step 4: Run matcher tests**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_matchers.py tests/core/standardize_entities_and_align_knowledge/test_precise_match.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/matchers.py backend/src/core/standardize_entities_and_align_knowledge/precise_match backend/tests/core/standardize_entities_and_align_knowledge/test_matchers.py backend/tests/core/standardize_entities_and_align_knowledge/test_precise_match.py
git commit -m "refactor(standardization): split precise matcher"
```

## Task 5: Add Model-Server Embedding And Rerank Providers

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/similarity_match/__init__.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/similarity_match/contracts.py`
- Create: `backend/src/core/standardize_entities_and_align_knowledge/similarity_match/providers.py`
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_similarity_providers.py`

**Step 1: Write failing provider tests**

Create `backend/tests/core/standardize_entities_and_align_knowledge/test_similarity_providers.py`:

```python
"""Tests for model-server semantic matching providers."""
from __future__ import annotations

import httpx
import pytest

from src.core.standardize_entities_and_align_knowledge.similarity_match.providers import (
    ModelServerEmbeddingProvider,
    ModelServerRerankProvider,
)


@pytest.mark.asyncio
async def test_embedding_provider_calls_model_server_embeddings() -> None:
    """Embedding provider maps OpenAI-style model-server responses into vectors."""
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "object": "list",
                "model": "Qwen/Qwen3-Embedding-0.6B",
                "data": [
                    {"object": "embedding", "embedding": [0.1, 0.2], "index": 0},
                    {"object": "embedding", "embedding": [0.3, 0.4], "index": 1},
                ],
                "usage": {"prompt_tokens": 2, "total_tokens": 2},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ModelServerEmbeddingProvider(
            base_url="http://model-server",
            model="Qwen/Qwen3-Embedding-0.6B",
            client=client,
        )
        result = await provider.embed_texts(("BRCA1", "Fabry disease"))

    assert requests[0].url.path == "/v1/embeddings"
    assert result.model == "Qwen/Qwen3-Embedding-0.6B"
    assert result.vectors == ((0.1, 0.2), (0.3, 0.4))


@pytest.mark.asyncio
async def test_rerank_provider_returns_ranked_scores() -> None:
    """Rerank provider maps model-server rerank results into typed scores."""
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "BAAI/bge-reranker-v2-m3",
                "results": [
                    {"index": 1, "document": "candidate-b", "relevance_score": 0.91},
                    {"index": 0, "document": "candidate-a", "relevance_score": 0.44},
                ],
                "usage": {"prompt_tokens": 3, "total_tokens": 3},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = ModelServerRerankProvider(
            base_url="http://model-server",
            model="BAAI/bge-reranker-v2-m3",
            client=client,
        )
        result = await provider.rerank("query", ("candidate-a", "candidate-b"), top_k=2)

    assert result.model == "BAAI/bge-reranker-v2-m3"
    assert result.results[0].index == 1
    assert result.results[0].relevance_score == 0.91
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_similarity_providers.py -v
```

Expected: FAIL because `similarity_match.providers` does not exist.

**Step 3: Add typed provider contracts**

Create `backend/src/core/standardize_entities_and_align_knowledge/similarity_match/__init__.py`:

```python
"""Semantic similarity matching for Phase 3 entity standardization."""
```

Create `backend/src/core/standardize_entities_and_align_knowledge/similarity_match/contracts.py`:

```python
"""Typed contracts for semantic similarity matching providers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingBatchResult:
    """Embedding provider response for a batch of texts."""

    model: str
    vectors: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class RerankItem:
    """One reranked document score."""

    index: int
    document: str
    relevance_score: float


@dataclass(frozen=True)
class RerankBatchResult:
    """Rerank provider response for candidate texts."""

    model: str
    results: tuple[RerankItem, ...]
```

**Step 4: Add model-server providers**

Create `backend/src/core/standardize_entities_and_align_knowledge/similarity_match/providers.py`:

```python
"""Model-server providers for semantic standardization matching."""
from __future__ import annotations

from collections.abc import Sequence

import httpx

from src.core.standardize_entities_and_align_knowledge.similarity_match.contracts import (
    EmbeddingBatchResult,
    RerankBatchResult,
    RerankItem,
)


class ModelServerEmbeddingProvider:
    """Client for model-server OpenAI-compatible embeddings."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client
        self._timeout = timeout

    async def embed_texts(self, texts: Sequence[str]) -> EmbeddingBatchResult:
        """Embed texts through model-server `/v1/embeddings`."""
        payload = {"input": list(texts), "model": self._model}
        if self._client is not None:
            return await self._post_embeddings(self._client, payload)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await self._post_embeddings(client, payload)

    async def _post_embeddings(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, object],
    ) -> EmbeddingBatchResult:
        response = await client.post(f"{self._base_url}/v1/embeddings", json=payload)
        response.raise_for_status()
        body = response.json()
        data = sorted(body.get("data", []), key=lambda item: item.get("index", 0))
        vectors = tuple(tuple(float(value) for value in item["embedding"]) for item in data)
        return EmbeddingBatchResult(model=str(body.get("model") or self._model), vectors=vectors)


class ModelServerRerankProvider:
    """Client for model-server rerank scoring."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client
        self._timeout = timeout

    async def rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_k: int | None,
    ) -> RerankBatchResult:
        """Rerank documents through model-server `/v1/rerank`."""
        payload = {"query": query, "documents": list(documents), "model": self._model, "top_k": top_k}
        if self._client is not None:
            return await self._post_rerank(self._client, payload)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await self._post_rerank(client, payload)

    async def _post_rerank(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, object],
    ) -> RerankBatchResult:
        response = await client.post(f"{self._base_url}/v1/rerank", json=payload)
        response.raise_for_status()
        body = response.json()
        results = tuple(
            RerankItem(
                index=int(item["index"]),
                document=str(item["document"]),
                relevance_score=float(item["relevance_score"]),
            )
            for item in body.get("results", [])
        )
        return RerankBatchResult(model=str(body.get("model") or self._model), results=results)
```

**Step 5: Run provider tests**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_similarity_providers.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/similarity_match backend/tests/core/standardize_entities_and_align_knowledge/test_similarity_providers.py
git commit -m "feat(standardization): add semantic model providers"
```

## Task 6: Add pgvector Similarity Repository

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/similarity_match/repositories.py`
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_similarity_repositories.py`

**Step 1: Write failing repository tests**

Create `backend/tests/core/standardize_entities_and_align_knowledge/test_similarity_repositories.py`:

```python
"""Tests for pgvector terminology similarity repository."""
from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.contracts import EntityType
from src.core.standardize_entities_and_align_knowledge.similarity_match.repositories import (
    PgvectorTerminologyRepository,
)


class FakeSession:
    """Minimal session that captures SQLAlchemy statements."""

    def __init__(self) -> None:
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return FakeResult()


class FakeResult:
    """Empty SQLAlchemy result stand-in."""

    def mappings(self):
        return self

    def all(self):
        return []


async def test_find_nearest_builds_pgvector_similarity_query() -> None:
    """Nearest-neighbor search filters by entity type and model."""
    session = FakeSession()
    repository = PgvectorTerminologyRepository(session)

    result = await repository.find_nearest(
        entity_type=EntityType.GENE,
        query_vector=(0.1, 0.2),
        embedding_model="Qwen/Qwen3-Embedding-0.6B",
        limit=5,
    )

    assert result == ()
    statement_text = str(session.statements[0])
    assert "terminology_embeddings" in statement_text
    assert "terminology_entries" in statement_text
    assert "embedding_model" in statement_text
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_similarity_repositories.py -v
```

Expected: FAIL because repository does not exist.

**Step 3: Add repository implementation**

Create `backend/src/core/standardize_entities_and_align_knowledge/similarity_match/repositories.py`:

```python
"""pgvector repository for terminology semantic retrieval."""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from src.core.standardize_entities_and_align_knowledge.contracts import (
    EntityType,
    SimilarityCandidate,
    TerminologyCandidate,
)
from src.dao.models import TerminologyEmbedding, TerminologyEntry


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
```

**Step 4: Run repository tests**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_similarity_repositories.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/similarity_match/repositories.py backend/tests/core/standardize_entities_and_align_knowledge/test_similarity_repositories.py
git commit -m "feat(standardization): add pgvector candidate retrieval"
```

## Task 7: Add Terminology Embedding Index Builder

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/similarity_match/indexer.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/api.py`
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_similarity_indexer.py`
- Create: `scripts/build_terminology_embeddings.py`

**Step 1: Write failing indexer tests**

Create `backend/tests/core/standardize_entities_and_align_knowledge/test_similarity_indexer.py`:

```python
"""Tests for terminology embedding index building."""
from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.similarity_match.indexer import (
    build_embedding_text,
    make_embedding_text_hash,
)


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
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_similarity_indexer.py -v
```

Expected: FAIL because `similarity_match.indexer` does not exist.

**Step 3: Add indexer helpers and service skeleton**

Create `backend/src/core/standardize_entities_and_align_knowledge/similarity_match/indexer.py`:

```python
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
```

Implementation note for the engineer: after this skeleton passes helper tests, add one follow-up test that `TerminologyEmbeddingIndexer.build()` stages embeddings with a fake session/provider. If unique conflicts appear in integration testing, change this to PostgreSQL `INSERT ... ON CONFLICT DO UPDATE`; do not add that complexity before a test requires it.

**Step 4: Add public API helper**

In `backend/src/core/standardize_entities_and_align_knowledge/api.py`, add:

```python
async def build_terminology_embeddings(*, cfg: Any) -> int:
    """Build pgvector embeddings for imported terminology entries."""
    from src.core.standardize_entities_and_align_knowledge.similarity_match.indexer import (
        TerminologyEmbeddingIndexer,
    )
    from src.core.standardize_entities_and_align_knowledge.similarity_match.providers import (
        ModelServerEmbeddingProvider,
    )

    engine = build_async_engine(cfg)
    session_factory = async_session_factory(engine)
    try:
        async with get_async_session(session_factory) as session:
            provider = ModelServerEmbeddingProvider(
                base_url=(cfg.embedding.base_url or cfg.model_server_url),
                model=cfg.embedding.model,
            )
            count = await TerminologyEmbeddingIndexer(session, provider).build(
                embedding_model=cfg.embedding.model,
                batch_size=cfg.embedding.batch_size,
            )
            await session.commit()
            return count
    finally:
        await engine.dispose()
```

**Step 5: Add CLI wrapper**

Create `scripts/build_terminology_embeddings.py`:

```python
"""Build pgvector embeddings for imported terminology entries."""
from __future__ import annotations

import asyncio

from src.core.config import get_config
from src.core.standardize_entities_and_align_knowledge.api import build_terminology_embeddings


async def main() -> None:
    """Run terminology embedding index build."""
    count = await build_terminology_embeddings(cfg=get_config())
    print(f"Built {count} terminology embeddings")


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 6: Run indexer tests**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_similarity_indexer.py tests/core/standardize_entities_and_align_knowledge/test_api.py -v
```

Expected: PASS after adding or adjusting API tests for `build_terminology_embeddings()`.

**Step 7: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/api.py backend/src/core/standardize_entities_and_align_knowledge/similarity_match/indexer.py backend/tests/core/standardize_entities_and_align_knowledge/test_similarity_indexer.py backend/tests/core/standardize_entities_and_align_knowledge/test_api.py scripts/build_terminology_embeddings.py
git commit -m "feat(standardization): add terminology embedding indexer"
```

## Task 8: Add Similarity Matcher

**Files:**
- Create: `backend/src/core/standardize_entities_and_align_knowledge/similarity_match/core.py`
- Create: `backend/tests/core/standardize_entities_and_align_knowledge/test_similarity_match.py`

**Step 1: Write failing similarity matcher tests**

Create `backend/tests/core/standardize_entities_and_align_knowledge/test_similarity_match.py`:

```python
"""Tests for semantic similarity terminology matching."""
from __future__ import annotations

import pytest

from src.core.standardize_entities_and_align_knowledge.contracts import (
    BindingRole,
    EntityType,
    MatchMethod,
    MatchStatus,
    SimilarityCandidate,
    StandardizationCandidate,
    TerminologyCandidate,
)
from src.core.standardize_entities_and_align_knowledge.similarity_match.core import (
    SimilarityMatchConfig,
    SimilarityTerminologyMatcher,
)


class FakeEmbeddingProvider:
    async def embed_texts(self, texts):
        return type("EmbeddingResult", (), {"model": "model-a", "vectors": ((0.1, 0.2),)})()


class FakeRerankProvider:
    async def rerank(self, query, documents, *, top_k):
        return type(
            "RerankResult",
            (),
            {
                "model": "rerank-a",
                "results": (
                    type("RerankItem", (), {"index": 0, "document": documents[0], "relevance_score": 0.91})(),
                ),
            },
        )()


class FakeSimilarityRepository:
    async def find_nearest(self, *, entity_type, query_vector, embedding_model, limit):
        return (
            SimilarityCandidate(
                terminology=TerminologyCandidate(
                    entry_id="entry-1",
                    entity_type=EntityType.GENE,
                    source_db="HGNC",
                    external_id="HGNC:1100",
                    display_name="BRCA1",
                    normalized_alias="BRCA1",
                    alias_type="semantic",
                ),
                embedding_text="BRCA1\nBRCC1\nHGNC:1100\nHGNC",
                vector_distance=0.08,
            ),
        )


@pytest.mark.asyncio
async def test_similarity_matcher_accepts_high_rerank_score() -> None:
    """A high-confidence semantic candidate becomes a standardized match."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA one",
        chain_id="chain-1",
        track="original",
    )
    matcher = SimilarityTerminologyMatcher(
        embedding_provider=FakeEmbeddingProvider(),
        rerank_provider=FakeRerankProvider(),
        repository=FakeSimilarityRepository(),
        config=SimilarityMatchConfig(
            embedding_model="model-a",
            rerank_top_k=10,
            rerank_score_threshold=0.7,
        ),
    )

    match = await matcher.match(candidate)

    assert match.status == MatchStatus.STANDARDIZED
    assert match.external_id == "HGNC:1100"
    assert match.match_method == MatchMethod.SIMILARITY
    assert match.similarity_score == 0.91
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_similarity_match.py -v
```

Expected: FAIL because `similarity_match.core` does not exist.

**Step 3: Implement similarity matcher**

Create `backend/src/core/standardize_entities_and_align_knowledge/similarity_match/core.py`:

```python
"""Semantic similarity matcher for Phase 3 standardization."""
from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from src.core.standardize_entities_and_align_knowledge.contracts import (
    EntityMatch,
    MatchMethod,
    MatchStatus,
    SimilarityCandidate,
    StandardizationCandidate,
)


@dataclass(frozen=True)
class SimilarityMatchConfig:
    """Configuration for semantic terminology matching."""

    embedding_model: str
    rerank_top_k: int
    rerank_score_threshold: float
    min_rerank_margin: float = 0.05


class SimilarityTerminologyMatcher:
    """Match one candidate by embedding retrieval and rerank scoring."""

    def __init__(self, *, embedding_provider, rerank_provider, repository, config: SimilarityMatchConfig) -> None:
        self._embedding_provider = embedding_provider
        self._rerank_provider = rerank_provider
        self._repository = repository
        self._config = config

    async def match(self, candidate: StandardizationCandidate) -> EntityMatch:
        """Run semantic matching for one candidate."""
        try:
            embedding_result = await self._embedding_provider.embed_texts((candidate.raw_text,))
            query_vector = embedding_result.vectors[0]
            nearest = await self._repository.find_nearest(
                entity_type=candidate.entity_type,
                query_vector=query_vector,
                embedding_model=self._config.embedding_model,
                limit=self._config.rerank_top_k,
            )
            if not nearest:
                return self._unmapped(candidate, "no semantic terminology candidate")

            rerank_result = await self._rerank_provider.rerank(
                candidate.raw_text,
                tuple(item.embedding_text for item in nearest),
                top_k=self._config.rerank_top_k,
            )
            ranked = self._merge_rerank_scores(nearest, rerank_result.results)
            if not ranked:
                return self._unmapped(candidate, "semantic rerank returned no candidates")

            top = ranked[0]
            second_score = ranked[1].rerank_score if len(ranked) > 1 else None
            top_score = top.rerank_score or 0.0
            if top_score < self._config.rerank_score_threshold:
                return self._unmapped(candidate, "semantic rerank score below threshold")
            if second_score is not None and top_score - second_score < self._config.min_rerank_margin:
                return EntityMatch(
                    candidate=candidate,
                    status=MatchStatus.AMBIGUOUS,
                    external_id=None,
                    display_name=candidate.raw_text,
                    terminology_candidates=tuple(item.terminology for item in ranked[:2]),
                    rationale="semantic rerank candidates are too close",
                    match_method=MatchMethod.SIMILARITY,
                    similarity_score=top_score,
                    raw_payload={"semantic_candidates": _candidate_payloads(ranked[:2])},
                )

            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.STANDARDIZED,
                external_id=top.terminology.external_id,
                display_name=top.terminology.display_name,
                terminology_candidates=(top.terminology,),
                rationale="semantic pgvector retrieval plus rerank match",
                match_method=MatchMethod.SIMILARITY,
                similarity_score=top_score,
                raw_payload={"semantic_candidates": _candidate_payloads(ranked[:3])},
            )
        except Exception as exc:
            logger.warning("Semantic matching failed for candidate {}: {}", candidate.candidate_id, exc)
            return self._unmapped(candidate, f"semantic matching unavailable: {exc.__class__.__name__}")

    def _merge_rerank_scores(self, nearest, rerank_items) -> tuple[SimilarityCandidate, ...]:
        """Attach rerank scores back to nearest-neighbor candidates."""
        ranked = []
        for item in rerank_items:
            if item.index < 0 or item.index >= len(nearest):
                continue
            source = nearest[item.index]
            ranked.append(
                SimilarityCandidate(
                    terminology=source.terminology,
                    embedding_text=source.embedding_text,
                    vector_distance=source.vector_distance,
                    rerank_score=item.relevance_score,
                ),
            )
        return tuple(sorted(ranked, key=lambda candidate: candidate.rerank_score or 0.0, reverse=True))

    def _unmapped(self, candidate: StandardizationCandidate, rationale: str) -> EntityMatch:
        """Build an unmapped semantic result."""
        return EntityMatch(
            candidate=candidate,
            status=MatchStatus.UNMAPPED,
            external_id=None,
            display_name=candidate.raw_text,
            rationale=rationale,
            match_method=MatchMethod.SIMILARITY,
        )


def _candidate_payloads(candidates: tuple[SimilarityCandidate, ...]) -> list[dict[str, object]]:
    """Serialize semantic candidate rationale for audit payloads."""
    return [
        {
            "entry_id": candidate.terminology.entry_id,
            "external_id": candidate.terminology.external_id,
            "display_name": candidate.terminology.display_name,
            "vector_distance": candidate.vector_distance,
            "rerank_score": candidate.rerank_score,
        }
        for candidate in candidates
    ]
```

This helper returns `list[dict[str, object]]`, not a function-level bare `dict` return. That satisfies the project rule against `-> dict` return annotations.

**Step 4: Run tests**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_similarity_match.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/similarity_match/core.py backend/tests/core/standardize_entities_and_align_knowledge/test_similarity_match.py
git commit -m "feat(standardization): add semantic similarity matcher"
```

## Task 9: Add Hybrid Matcher And Facade Wiring

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/matchers.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/api.py`
- Modify: `backend/tests/core/standardize_entities_and_align_knowledge/test_matchers.py`
- Modify: `backend/tests/core/standardize_entities_and_align_knowledge/test_api.py`

**Step 1: Write failing hybrid matcher tests**

Append to `backend/tests/core/standardize_entities_and_align_knowledge/test_matchers.py`:

```python
class FakePreciseMatcher:
    """Precise matcher test double."""

    def __init__(self, match):
        self.match_result = match
        self.calls = 0

    async def match(self, candidate):
        self.calls += 1
        return self.match_result


class FakeSimilarityMatcher:
    """Similarity matcher test double."""

    def __init__(self, match):
        self.match_result = match
        self.calls = 0

    async def match(self, candidate):
        self.calls += 1
        return self.match_result


@pytest.mark.asyncio
async def test_hybrid_matcher_uses_similarity_for_unmapped_precise_result() -> None:
    """Similarity matching is a fallback for precise unmapped candidates."""
    candidate = StandardizationCandidate(
        candidate_id="c-semantic",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA one",
        chain_id="chain-1",
        track="original",
    )
    precise = EntityMatch(candidate, MatchStatus.UNMAPPED, None, "BRCA one")
    semantic = EntityMatch(
        candidate,
        MatchStatus.STANDARDIZED,
        "HGNC:1100",
        "BRCA1",
        match_method=MatchMethod.SIMILARITY,
    )
    semantic_matcher = FakeSimilarityMatcher(semantic)

    match = await HybridTerminologyMatcher(FakePreciseMatcher(precise), semantic_matcher).match(candidate)

    assert match.external_id == "HGNC:1100"
    assert match.match_method == MatchMethod.SIMILARITY
    assert semantic_matcher.calls == 1


@pytest.mark.asyncio
async def test_hybrid_matcher_does_not_override_precise_standardized_result() -> None:
    """Precise standardized results are authoritative."""
    candidate = StandardizationCandidate(
        candidate_id="c-precise",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA1",
        chain_id="chain-1",
        track="original",
    )
    precise = EntityMatch(candidate, MatchStatus.STANDARDIZED, "HGNC:1100", "BRCA1")
    semantic = EntityMatch(
        candidate,
        MatchStatus.STANDARDIZED,
        "HGNC:9999",
        "Wrong",
        match_method=MatchMethod.SIMILARITY,
    )
    semantic_matcher = FakeSimilarityMatcher(semantic)

    match = await HybridTerminologyMatcher(FakePreciseMatcher(precise), semantic_matcher).match(candidate)

    assert match.external_id == "HGNC:1100"
    assert match.match_method == MatchMethod.PRECISE
    assert semantic_matcher.calls == 0
```

Add imports:

```python
from src.core.standardize_entities_and_align_knowledge.contracts import EntityMatch, MatchMethod
from src.core.standardize_entities_and_align_knowledge.matchers import HybridTerminologyMatcher
```

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_matchers.py::test_hybrid_matcher_uses_similarity_for_unmapped_precise_result tests/core/standardize_entities_and_align_knowledge/test_matchers.py::test_hybrid_matcher_does_not_override_precise_standardized_result -v
```

Expected: FAIL because `HybridTerminologyMatcher` does not exist.

**Step 3: Implement hybrid matcher**

Update `backend/src/core/standardize_entities_and_align_knowledge/matchers.py`:

```python
"""Matcher facade exports for Phase 3 standardization."""
from __future__ import annotations

from src.core.standardize_entities_and_align_knowledge.contracts import (
    MatchStatus,
    StandardizationCandidate,
)
from src.core.standardize_entities_and_align_knowledge.precise_match.core import (
    ALIAS_TYPE_PRIORITY,
    PreciseTerminologyMatcher,
)


class HybridTerminologyMatcher:
    """Run precise matching first, then semantic matching for unmapped mentions."""

    def __init__(self, precise_matcher, similarity_matcher) -> None:
        self._precise_matcher = precise_matcher
        self._similarity_matcher = similarity_matcher

    async def match(self, candidate: StandardizationCandidate):
        """Return precise result unless it is unmapped."""
        precise_match = await self._precise_matcher.match(candidate)
        if precise_match.status != MatchStatus.UNMAPPED:
            return precise_match
        return await self._similarity_matcher.match(candidate)


TerminologyMatcher = PreciseTerminologyMatcher

__all__ = [
    "ALIAS_TYPE_PRIORITY",
    "HybridTerminologyMatcher",
    "PreciseTerminologyMatcher",
    "TerminologyMatcher",
]
```

**Step 4: Wire facade to hybrid matcher**

In `backend/src/core/standardize_entities_and_align_knowledge/api.py`, change imports:

```python
from src.core.standardize_entities_and_align_knowledge.matchers import HybridTerminologyMatcher
from src.core.standardize_entities_and_align_knowledge.precise_match.core import PreciseTerminologyMatcher
from src.core.standardize_entities_and_align_knowledge.similarity_match.core import (
    SimilarityMatchConfig,
    SimilarityTerminologyMatcher,
)
from src.core.standardize_entities_and_align_knowledge.similarity_match.providers import (
    ModelServerEmbeddingProvider,
    ModelServerRerankProvider,
)
from src.core.standardize_entities_and_align_knowledge.similarity_match.repositories import (
    PgvectorTerminologyRepository,
)
```

In `run_dual_result()`, replace matcher construction:

```python
repository = StandardizationRepository(self._session)
precise_matcher = PreciseTerminologyMatcher(repository)
semantic_base_url = self._cfg.embedding.base_url or self._cfg.model_server_url
similarity_matcher = SimilarityTerminologyMatcher(
    embedding_provider=ModelServerEmbeddingProvider(
        base_url=semantic_base_url,
        model=self._cfg.embedding.model,
    ),
    rerank_provider=ModelServerRerankProvider(
        base_url=self._cfg.rerank.base_url or self._cfg.model_server_url,
        model=self._cfg.rerank.model,
    ),
    repository=PgvectorTerminologyRepository(self._session),
    config=SimilarityMatchConfig(
        embedding_model=self._cfg.embedding.model,
        rerank_top_k=self._cfg.rerank.top_k,
        rerank_score_threshold=self._cfg.rerank.score_threshold,
    ),
)
matcher = HybridTerminologyMatcher(precise_matcher, similarity_matcher)
adapter = DualResultAdapter()
input_data = adapter.to_standardization_input(
    result,
    source_document_id=source_document_id,
    processing_run_id=processing_run_id,
)
return await StandardizationService(matcher, repository).run(input_data)
```

**Step 5: Add/adjust API wiring test**

In `backend/tests/core/standardize_entities_and_align_knowledge/test_api.py`, add a test that monkeypatches `HybridTerminologyMatcher`, `PreciseTerminologyMatcher`, and `SimilarityTerminologyMatcher` and verifies the facade constructs the hybrid matcher. Keep the test isolated from live model-server.

**Step 6: Run tests**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_matchers.py tests/core/standardize_entities_and_align_knowledge/test_api.py -v
```

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/matchers.py backend/src/core/standardize_entities_and_align_knowledge/api.py backend/tests/core/standardize_entities_and_align_knowledge/test_matchers.py backend/tests/core/standardize_entities_and_align_knowledge/test_api.py
git commit -m "feat(standardization): wire hybrid terminology matcher"
```

## Task 10: Persist Match Method And Semantic Rationale

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/repositories.py`
- Modify: `backend/tests/core/standardize_entities_and_align_knowledge/test_repositories.py`

**Step 1: Write failing persistence test**

Append to `backend/tests/core/standardize_entities_and_align_knowledge/test_repositories.py`:

```python
@pytest.mark.asyncio
async def test_upsert_normalized_entity_persists_similarity_rationale() -> None:
    """Semantic match metadata is preserved for audit and review."""
    session = FakeSession()
    repo = StandardizationRepository(session)
    match = EntityMatch(
        candidate=StandardizationCandidate(
            candidate_id="chain-1:gene",
            entity_type=EntityType.GENE,
            role=BindingRole.SUBJECT,
            raw_text="BRCA one",
            chain_id="chain-1",
            track="original",
        ),
        status=MatchStatus.STANDARDIZED,
        external_id="HGNC:1100",
        display_name="BRCA1",
        rationale="semantic pgvector retrieval plus rerank match",
        match_method=MatchMethod.SIMILARITY,
        similarity_score=0.91,
        raw_payload={"semantic_candidates": [{"external_id": "HGNC:1100"}]},
    )

    await repo.upsert_normalized_entity(match)

    normalized_entity = session.added[0]
    assert normalized_entity.raw_payload["match_method"] == "similarity"
    assert normalized_entity.raw_payload["similarity_score"] == 0.91
    assert normalized_entity.raw_payload["semantic_candidates"][0]["external_id"] == "HGNC:1100"
```

Add import:

```python
from src.core.standardize_entities_and_align_knowledge.contracts import MatchMethod
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_repositories.py::test_upsert_normalized_entity_persists_similarity_rationale -v
```

Expected: FAIL because repository raw payload does not include match method and similarity metadata.

**Step 3: Update repository payload**

In `upsert_normalized_entity()`, build a shared payload:

```python
payload = {
    "candidate_id": match.candidate.candidate_id,
    "rationale": match.rationale,
    "match_method": match.match_method.value,
    "similarity_score": match.similarity_score,
    "terminology_candidate_ids": [candidate.entry_id for candidate in match.terminology_candidates],
    **match.raw_payload,
}
```

Use `payload` when creating and updating `NormalizedEntity.raw_payload`.

**Step 4: Run repository tests**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_repositories.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/repositories.py backend/tests/core/standardize_entities_and_align_knowledge/test_repositories.py
git commit -m "feat(standardization): persist semantic match rationale"
```

## Task 11: Add End-To-End Semantic Fallback Coverage

**Files:**
- Modify: `backend/tests/core/standardize_entities_and_align_knowledge/test_integration.py`
- Modify: `backend/tests/core/standardize_entities_and_align_knowledge/test_core.py`

**Step 1: Write failing service-level integration test**

Add an integration-style test using fake matchers/repository so no live model-server or PostgreSQL instance is required:

```python
@pytest.mark.asyncio
async def test_standardization_service_counts_similarity_standardized_match() -> None:
    """Service summary treats accepted similarity matches as standardized."""
    candidate = StandardizationCandidate(
        candidate_id="c1",
        entity_type=EntityType.GENE,
        role=BindingRole.SUBJECT,
        raw_text="BRCA one",
        chain_id="chain-1",
        track="original",
    )
    input_data = StandardizationInput(
        document_id="doc-1",
        source_document_id="source-1",
        processing_run_id="run-1",
        candidates=(candidate,),
        evidence_items=(),
    )

    class SimilarityOnlyMatcher:
        async def match(self, candidate):
            return EntityMatch(
                candidate=candidate,
                status=MatchStatus.STANDARDIZED,
                external_id="HGNC:1100",
                display_name="BRCA1",
                match_method=MatchMethod.SIMILARITY,
                similarity_score=0.91,
            )

    repo = FakeRepository()
    result = await StandardizationService(SimilarityOnlyMatcher(), repo).run(input_data)

    assert result.standardized_count == 1
    assert repo.normalized[0].match_method == MatchMethod.SIMILARITY
```

**Step 2: Run test to verify current behavior**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge/test_core.py::test_standardization_service_counts_similarity_standardized_match -v
```

Expected: PASS if previous tasks are correct. If it fails, fix the minimal service incompatibility.

**Step 3: Add a facade-level semantic wiring test**

In `test_integration.py`, add a test that monkeypatches the similarity matcher to return a semantic match and verifies `EntityStandardizationService.run_dual_result()` returns `standardized_count == 1`. Reuse the existing dual-result fixture helpers in that file; do not call live model-server.

**Step 4: Run Phase 3 tests**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/tests/core/standardize_entities_and_align_knowledge/test_core.py backend/tests/core/standardize_entities_and_align_knowledge/test_integration.py
git commit -m "test(standardization): cover semantic fallback flow"
```

## Task 12: Update Module Documentation And Progress

**Files:**
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/README.md`
- Modify: `progress.txt`
- Optional after implementation: create/update `docs/active/<module-guide-name>.md` through @module-guide if that skill chooses an external docs path.

**Step 1: Update README**

Revise the architecture section to show:

```text
StandardizationService
  -> HybridTerminologyMatcher
     -> precise_match.PreciseTerminologyMatcher
     -> similarity_match.SimilarityTerminologyMatcher
        -> model-server /v1/embeddings
        -> terminology_embeddings pgvector retrieval
        -> model-server /v1/rerank
```

Add usage docs:

```bash
cd backend
uv run ../scripts/build_terminology_embeddings.py
```

Document operational prerequisites:

- `database/migrations` must be upgraded through `add_terminology_embeddings_20260525`.
- PostgreSQL must have pgvector available.
- model-server must be reachable at `EMBEDDING_BASE_URL` or `MODEL_SERVER_URL`.
- `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`, and the pgvector column dimension must match.

**Step 2: Add progress entry**

Append:

```text
[2026-05-25] [Phase 3 precise/similarity matching split with pgvector semantic fallback implemented] [done]
```

**Step 3: Run doc and code verification**

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge tests/dao/test_models.py tests/dao/test_alembic_migration.py tests/core/test_config.py -v
uv run ruff check src tests
```

Expected: all targeted tests pass and Ruff reports no errors.

**Step 4: Use module-guide and doc-organize**

After tests pass:

- Use @module-guide for `backend/src/core/standardize_entities_and_align_knowledge`.
- Use @doc-organize because docs changed.

**Step 5: Commit**

```bash
git add backend/src/core/standardize_entities_and_align_knowledge/README.md progress.txt
git commit -m "docs(standardization): document semantic matching split"
```

## Final Verification

Run:

```bash
cd backend
uv run pytest tests/core/standardize_entities_and_align_knowledge tests/dao/test_models.py tests/dao/test_alembic_migration.py tests/core/test_config.py -v
uv run ruff check src tests
```

Expected:

- Phase 3 standardization tests pass.
- DAO model and migration tests pass.
- Config tests pass.
- Ruff has zero violations.

Optional live smoke test when PostgreSQL and model-server are running:

```bash
cd backend
uv run ../scripts/build_terminology_embeddings.py
```

Expected:

- CLI prints `Built <N> terminology embeddings`.
- No model-server or pgvector errors.

## Rollback Notes

- The new pgvector table is additive; rollback drops only `terminology_embeddings`.
- Compatibility alias `TerminologyMatcher = PreciseTerminologyMatcher` preserves existing imports while the hybrid matcher is introduced.
- If model-server is unavailable, semantic matching should degrade to precise `unmapped` behavior rather than breaking the run.

