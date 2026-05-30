# PostgreSQL DAO

> SQLAlchemy 2.0 async ORM models, connection helpers, and query repositories for the ACMG Lingua persistence layer.

## Quick Start

```python
from src.dao.postgresql.connection import async_session_factory, build_async_engine, get_async_session
from src.dao.postgresql.models import SourceDocument

engine = build_async_engine()
factory = async_session_factory(engine)

async with get_async_session(factory) as session:
    doc = SourceDocument(raw_metadata={"title": "BRCA1 study"})
    session.add(doc)
    await session.flush()
    # doc.source_document_id is now populated
```

## Architecture

```text
connection.py                 contracts.py
  build_async_engine()          AsyncpgConnectArgs (TypedDict)
  async_session_factory()
  get_async_session()           ┌──────────────────────────────────────┐
        │                       │  models.py — Base (Alembic target)   │
        │                       │                                      │
        ├──────────────────────>│  SourceDocument ──> SourceDocId       │
        │                       │  ProcessingRun                       │
        │                       │  RunEvidenceItem                     │
        │                       │  CanonicalEvidenceItem               │
        │                       │  NormalizedEntity                    │
        │                       │  EvidenceEntityBinding               │
        │                       │  TerminologyEntry ──> TerminologyAlias│
        │                       │                    ──> TerminologyRel │
        │                       │                    ──> TerminologyEmb │
        │                       │  User, ReviewAuditEvent              │
        │                       │  ChatSession ──> ChatMessage         │
        │                       │  PipelineRunState                    │
        │                       └──────────────────────────────────────┘
        │
        ├──> vector_repo.py       VectorRepository (pgvector cosine search)
        │
        └──> search_index_repo.py SearchIndexRepository (read projection)
                                   frontend_search_index (standalone MetaData)
```

The write model (`models.py`) uses `Base.metadata` — Alembic autogenerate tracks it. The read projection (`search_index_repo.py`) uses a standalone `MetaData()` so Alembic does not treat the flattened table as core schema drift.

## Public API

### connection.py — Engine and Session Lifecycle

| Function | Signature | Description |
|---|---|---|
| `build_asyncpg_connect_args` | `(settings: Settings \| None = None) -> AsyncpgConnectArgs` | Builds `server_settings` with `search_path` set to `{schema_},public`. |
| `build_async_engine` | `(settings: Settings \| None = None) -> AsyncEngine` | Creates an async engine from DSN, pool config, and connect args. |
| `async_session_factory` | `(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]` | Binds sessions with `expire_on_commit=False`. |
| `get_async_session` | `(session_factory: SessionFactory) -> AsyncIterator[AsyncSession]` | Context-managed session that closes on exit. Requires an explicit factory. |

`SessionFactory` is typed as `Callable[[], AsyncIterator[AsyncSession]] | async_sessionmaker[AsyncSession]`, accepting both the standard `async_sessionmaker` and custom context-manager factories used in tests.

pgvector registration: `connection.py` imports `pgvector.sqlalchemy.Vector` at module load. This registers the type with SQLAlchemy so `.cosine_distance()` is available in queries. If `pgvector` is absent, `Vector` is silently set to `None`.

### contracts.py — Typed Infrastructure Contracts

```python
class AsyncpgServerSettings(TypedDict):
    search_path: str

class AsyncpgConnectArgs(TypedDict):
    server_settings: AsyncpgServerSettings
```

These TypedDicts enforce the exact shape of asyncpg connection arguments at the type-checker level, preventing silent key mismatches.

### models.py — ORM Models

All models use SQLAlchemy 2.0 declarative style with `Mapped[]` annotations. Mutable tables inherit `TimestampMixin` for `created_at` / `updated_at` columns.

#### Document lifecycle

| Model | Table | Key columns | Relationships |
|---|---|---|---|
| `SourceDocument` | `source_documents` | `source_document_id` (PK), `raw_metadata` (JSONB), `latest_processing_run_id` (FK) | `identifiers` → `SourceDocumentIdentifier[]` |
| `SourceDocumentIdentifier` | `source_document_identifiers` | `identifier_type`, `identifier_value` (unique pair), `source_document_id` (FK) | `source_document` → `SourceDocument` |
| `ProcessingRun` | `processing_runs` | `processing_run_id` (PK), `source_document_id` (FK), version columns, `input_artifacts` / `output_artifacts` (JSONB), `run_status` | — |
| `PipelineRunState` | `pipeline_run_states` | `processing_run_id` (PK), `source_document_id` (FK), `state_json` (JSONB) | — |

#### Evidence

| Model | Table | Key columns | Constraints |
|---|---|---|---|
| `RunEvidenceItem` | `run_evidence_items` | `processing_run_id` (FK), `source_document_id` (FK), `track`, `field_id`, `status`, `value` (JSONB), `confidence`, `position_hash`, `text_hash`, `entity_scope_hash` | `CHECK confidence BETWEEN 0 AND 1` |
| `CanonicalEvidenceItem` | `canonical_evidence_items` | `source_document_id` (FK), `field_id`, `position_hash`, `text_hash`, `entity_scope_hash`, `current_best_run_evidence_id` (FK), `current_best_status`, `current_best_confidence`, `conflict_flag`, `review_status`, `active_payload` (JSONB) | `UNIQUE(source_document_id, field_id, position_hash, entity_scope_hash)`, `CHECK confidence BETWEEN 0 AND 1` |

#### Entity and terminology

| Model | Table | Key columns | Constraints |
|---|---|---|---|
| `NormalizedEntity` | `normalized_entities` | `entity_type`, `external_id`, `normalized_raw_text`, `display_name`, `aliases` (JSONB), `standardization_status`, `merged_into_entity_id` (self-FK) | Two partial unique indexes (see below) |
| `EvidenceEntityBinding` | `evidence_entity_bindings` | `run_evidence_item_id` (FK), `entity_id` (FK), `entity_type`, `role`, `binding_rank` | — |
| `EntityMergeEvent` | `entity_merge_events` | `from_entity_id` (FK), `to_entity_id` (FK), `merge_reason`, `merged_by_user_id` (FK) | — |
| `TerminologyEntry` | `terminology_entries` | `entity_type`, `source_db`, `external_id`, `display_name`, `normalized_name`, `aliases` (JSONB), `version` | `UNIQUE(source_db, external_id)` |
| `TerminologyAlias` | `terminology_aliases` | `entry_id` (FK), `entity_type`, `alias_text`, `normalized_alias`, `alias_type`, `source_db` | `UNIQUE(entry_id, normalized_alias, alias_type)` |
| `TerminologyRelationship` | `terminology_relationships` | `subject_entry_id` (FK), `object_entry_id` (FK, nullable), `relationship_type`, `source_db`, `evidence_level` | `UNIQUE(subject, object, type, source) NULLS NOT DISTINCT` |
| `TerminologyEmbedding` | `terminology_embeddings` | `entry_id` (FK, CASCADE), `entity_type`, `source_db`, `external_id`, `embedding_text`, `embedding_text_hash`, `embedding_model`, `embedding` (Vector(1024)) | `UNIQUE(entry_id, embedding_text_hash, embedding_model)` |

#### Phase 4 — review and chat

| Model | Table | Key columns | Relationships |
|---|---|---|---|
| `User` | `users` | `email` (unique), `password_hash`, `display_name`, `status` | — |
| `ReviewAuditEvent` | `review_audit_events` | `canonical_evidence_id` (FK), `reviewer_id` (FK), `target_type`, `old_status`, `new_status`, `field_deltas` (JSONB), `change_reason` | — |
| `ChatSession` | `chat_sessions` | `processing_run_id` (FK), `user_id` (FK, optional) | — |
| `ChatMessage` | `chat_messages` | `chat_session_id` (FK), `role`, `content`, `evidence_id` (optional), `entity_id` (optional) | — |

### vector_repo.py — Cosine Similarity Search

| Method | Signature | Description |
|---|---|---|
| `search_similar` | `(*, entity_type: str, embedding: list[float], limit: int = 10, min_distance: float \| None = None, embedding_model: str \| None = None) -> list[VectorSearchRow]` | Cosine distance search against `terminology_embeddings`. Joins to `terminology_entries` for display metadata. Orders by distance ascending. |
| `upsert_embeddings` | `(*, entry_ids: list[UUID], entity_type: str, source_db: str, external_ids: list[str], embedding_model: str, embeddings: list[list[float]], embedding_texts: list[str]) -> None` | Delete-then-insert per `(entry_id, embedding_model)`. Computes `embedding_text_hash` as SHA-256 of the text. Flushes after all inserts. |

`VectorSearchRow` is a `TypedDict` with fields: `entry_id`, `entity_type`, `source_db`, `external_id`, `display_name`, `embedding_text`, `distance`.

### search_index_repo.py — Read Projection

| Method | Signature | Description |
|---|---|---|
| `search` | `(*, gene_ids: list[str] \| None = None, variant_ids: list[str] \| None = None, doi: str \| None = None, pmid: str \| None = None, field_id: str \| None = None, limit: int = 50) -> list[dict[str, object]]` | OR-combined query against `frontend_search_index`. Uses JSONB `?|` overlap for array columns. Returns `[]` with no filters (no query executed). |
| `refresh` | `() -> None` | `TRUNCATE` + `INSERT ... SELECT` from `canonical_evidence_items` joined with `source_document_identifiers` for PMID/DOI. Commits after rebuild. |

The `frontend_search_index` table is defined with standalone `MetaData()`, not `Base.metadata`. This means Alembic does not autogenerate migrations for it — the table is created manually or via a dedicated migration.

## Internal Design

### Entity dual unique indexes

`NormalizedEntity` uses two partial unique indexes instead of one unconditional unique constraint:

```sql
-- Standardized rows: unique by (entity_type, external_id)
CREATE UNIQUE INDEX uq_normalized_entities_standardized_external_id
    ON normalized_entities (entity_type, external_id)
    WHERE external_id IS NOT NULL AND standardization_status = 'standardized';

-- Unmapped rows: unique by (entity_type, normalized_raw_text)
CREATE UNIQUE INDEX uq_normalized_entities_unmapped_raw_text
    ON normalized_entities (entity_type, normalized_raw_text)
    WHERE standardization_status = 'unmapped';
```

This allows standardized and unmapped entities to coexist without collision while preventing duplicates within each status.

### TerminologyRelationship NULLS NOT DISTINCT

The unique constraint on `terminology_relationships` uses `postgresql_nulls_not_distinct=True`. Standard SQL treats `NULL != NULL` in unique constraints, which would allow duplicate scalar assertions (where `object_entry_id` is NULL). The `NULLS NOT DISTINCT` modifier makes PostgreSQL treat NULLs as equal for uniqueness purposes.

### Vector dimension

`TerminologyEmbedding.embedding` is `Vector(1024)`. All embeddings passed to `VectorRepository` must have exactly 1024 dimensions. The embedding model used at search time must match the model used at indexing time — the `embedding_model` filter parameter allows disambiguation.

### Search index payload keys

`refresh()` extracts values from `canonical_evidence_items.active_payload` using four constants:

| Constant | JSONB key | Type |
|---|---|---|
| `GENE_IDS_PAYLOAD_KEY` | `gene_ids` | `list[str]` |
| `VARIANT_IDS_PAYLOAD_KEY` | `variant_ids` | `list[str]` |
| `ENTITY_IDS_PAYLOAD_KEY` | `entity_ids` | `list[str]` |
| `SEARCH_TEXT_PAYLOAD_KEY` | `search_text` | `str` |

If these keys are missing from `active_payload`, the SQL `COALESCE` provides empty defaults.

## Usage Patterns

### Create engine and session factory at startup

```python
from src.dao.postgresql.connection import async_session_factory, build_async_engine

engine = build_async_engine()          # reads from Settings singleton
session_factory = async_session_factory(engine)

# In production, src/api/wiring.py manages this as a lazy singleton:
#   get_session_factory()  — creates on first call
#   dispose_engine()       — called from FastAPI lifespan shutdown
```

### Query with a repository

```python
from src.dao.postgresql.connection import get_async_session
from src.dao.postgresql.search_index_repo import SearchIndexRepository

async with get_async_session(session_factory) as session:
    repo = SearchIndexRepository(session)
    rows = await repo.search(gene_ids=["BRCA1", "BRCA2"], limit=25)
    for row in rows:
        print(row["canonical_evidence_id"], row["pmid"], row["field_id"])
```

### Vector similarity search for entity matching

```python
from src.dao.postgresql.vector_repo import VectorRepository

async with get_async_session(session_factory) as session:
    repo = VectorRepository(session)
    candidates = await repo.search_similar(
        entity_type="gene",
        embedding=query_embedding,  # list[float] of length 1024
        limit=5,
        min_distance=0.3,           # skip low-similarity results
        embedding_model="bge-m3",
    )
    best = candidates[0] if candidates else None
    if best and best["distance"] < 0.15:
        print(f"Matched: {best['display_name']} ({best['external_id']})")
```

### Refresh the search index after a pipeline run

```python
async with get_async_session(session_factory) as session:
    repo = SearchIndexRepository(session)
    await repo.refresh()
    # Commits internally — no manual commit needed
```

### Store a pipeline checkpoint for crash recovery

```python
from src.dao.postgresql.models import PipelineRunState

async with get_async_session(session_factory) as session:
    checkpoint = PipelineRunState(
        processing_run_id=run_id,
        source_document_id=doc_id,
        state_json=graph_state.model_dump(),
    )
    session.add(checkpoint)
    await session.flush()
```

### Custom session factory for tests

`get_async_session` accepts any callable returning an `AsyncIterator[AsyncSession]`, making it easy to inject test doubles:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

@asynccontextmanager
async def test_session_factory() -> AsyncIterator[AsyncSession]:
    async with test_engine.begin() as conn:
        # Set up test data
        pass
    async with test_session_maker() as session:
        yield session

async with get_async_session(test_session_factory) as session:
    # Runs against the test database
    pass
```

## Extension Guide

### Adding a new write-model table

1. Add a declarative model to `models.py` using `Base` and `Mapped[]`.
2. Add the table name to `EXPECTED_TABLES` in `tests/dao/postgresql/test_models.py`.
3. Add constraint/index tests following the existing patterns.
4. Generate migration: `cd backend && uv run alembic revision --autogenerate -m "add <table>"`.
5. Add migration-specific tests in `test_alembic_migration.py`.

### Adding a new read-side projection

1. Define the `Table` with a standalone `MetaData()` (not `Base.metadata`).
2. Add a repository class with `__init__(self, session: Any)`.
3. Write query methods returning `list[dict[str, object]]` with `# noqa  # dict-return:` justification.
4. Add tests in a new `test_<name>_repo.py` file.

### Common pitfalls

- **Forgetting `expire_on_commit=False`**: Without this, accessing lazy-loaded attributes after commit triggers unexpected SQL. The `async_session_factory` sets this by default.
- **Wrong vector dimension**: `Vector(1024)` is hardcoded. Embeddings from models with different dimensions (e.g., 1536 for OpenAI `text-embedding-3-small`) will fail at insert time.
- **Partial unique index collisions**: When inserting `NormalizedEntity`, check `standardization_status` first. Inserting an entity with `external_id="HGNC:1100"` and `standardization_status="unmapped"` does not conflict with a standardized row having the same external ID.
- **Search index staleness**: `frontend_search_index` is not auto-refreshed. Call `refresh()` explicitly after pipeline runs that modify `canonical_evidence_items`.

## Dependencies

| Dependency | Purpose |
|---|---|
| SQLAlchemy 2.0 | Async ORM, declarative base, `Mapped[]`, table metadata. |
| asyncpg | PostgreSQL async driver (used via SQLAlchemy's `create_async_engine`). |
| pgvector | `Vector` type and `.cosine_distance()` operator for terminology embeddings. |
| Alembic | Migration management against `Base.metadata`. |

## Testing

```bash
cd backend

# Run all postgresql DAO tests
uv run pytest tests/dao/postgresql -v

# Run specific test files
uv run pytest tests/dao/postgresql/test_models.py -v
uv run pytest tests/dao/postgresql/test_vector_repo.py -v
uv run pytest tests/dao/postgresql/test_connection.py -v

# Lint
uv run ruff check src/dao/postgresql tests/dao/postgresql
```

| Test file | What it covers |
|---|---|
| `test_connection.py` | Engine creation, pool config, session factory, `get_async_session` lifecycle. |
| `test_models.py` | Table existence, unique constraints, partial unique indexes, check constraints, FK cascades, Vector type registration. |
| `test_vector_repo.py` | `search_similar` ranking, cosine distance operator, model filter; `upsert_embeddings` insert, delete-then-insert, length validation. |
| `test_search_index_repo.py` | Table shape, unique index, `search()` with various filters, no-filter no-op, `refresh()` truncate + commit. |
| `test_alembic_migration.py` | Migration up/down correctness. |
| `test_pgvector_migration.py` | pgvector extension creation and embedding column migration. |
| `test_type_contract_compliance.py` | Enforces `# noqa  # dict-return:` on all bare `dict` return annotations. |

Integration tests requiring a live PostgreSQL instance are `@pytest.mark.skip` by default.
