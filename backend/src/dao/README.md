# DAO

> Async PostgreSQL, Redis cache, and read-side search-index helpers for the backend persistence layer.

## Sub-package Organization

```
src/dao/
├── postgresql/    # SQLAlchemy ORM models, connection, and query repositories
├── redis/         # Async Redis cache operations
├── neo4j/         # Graph database access (placeholder)
└── minio/         # MinIO / S3-compatible object storage (placeholder)
```

## Quick Start

```python
from src.dao.postgresql.connection import async_session_factory, build_async_engine, get_async_session
from src.dao.postgresql.search_index_repo import SearchIndexRepository

engine = build_async_engine()
session_factory = async_session_factory(engine)

async with get_async_session(session_factory) as session:
    repo = SearchIndexRepository(session)
    rows = await repo.search(gene_ids=["BRCA1"], limit=20)
```

The application owns the engine lifecycle. Call `await engine.dispose()` during shutdown.

## Architecture

```text
src.core.config.Settings
        |
        v
postgresql/connection.py  ->  AsyncEngine / async_sessionmaker / session context
        |
        +--> postgresql/models.py              normalized write-model metadata
        +--> postgresql/search_index_repo.py   flattened read projection queries
        +--> postgresql/vector_repo.py         pgvector cosine similarity search
        +--> postgresql/contracts.py           typed infrastructure contracts
        +--> redis/cache_repo.py               Redis read-cache and invalidation
```

The normalized PostgreSQL write model is migration-managed through `Base.metadata` in `postgresql/models.py`. The `frontend_search_index` table in `postgresql/search_index_repo.py` uses standalone `MetaData` so Alembic autogenerate does not treat the manual read projection as core write-model drift.

## Public API

### postgresql/connection.py

| Function | Signature | Description |
|---|---|---|
| `build_asyncpg_connect_args` | `build_asyncpg_connect_args(settings: Settings \| None = None) -> AsyncpgConnectArgs` | Builds asyncpg `server_settings` with the configured schema search path. |
| `build_async_engine` | `build_async_engine(settings: Settings \| None = None) -> AsyncEngine` | Creates a SQLAlchemy async engine from `Settings.postgresql_dsn`, pool size, overflow, and search path. |
| `async_session_factory` | `async_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]` | Binds `AsyncSession` instances to an engine with `expire_on_commit=False`. |
| `get_async_session` | `get_async_session(session_factory: SessionFactory) -> AsyncIterator[AsyncSession]` | Context-managed session helper. It requires an explicit factory to avoid hidden engine creation. |

`connection.py` also registers the pgvector `Vector` type at module load so cosine distance operators (`<=>`) are available in raw-SQL queries. If `pgvector` is not installed, the import is silently skipped.

### postgresql/models.py

`Base` is the Alembic target metadata for the normalized schema.

#### Core domain models

| Model | Table | Purpose |
|---|---|---|
| `SourceDocument` | `source_documents` | Stable document identity across retries and reprocessing. |
| `SourceDocumentIdentifier` | `source_document_identifiers` | DOI, PMID, PMCID, file hash, and other dedupe identifiers. |
| `ProcessingRun` | `processing_runs` | Version snapshot and artifact references for one pipeline run. |
| `RunEvidenceItem` | `run_evidence_items` | Versioned run-level evidence with location, confidence, and raw payload. |
| `CanonicalEvidenceItem` | `canonical_evidence_items` | Current-best canonical evidence keyed by source, field, position, and entity scope. |

#### Entity and terminology models

| Model | Table | Purpose |
|---|---|---|
| `NormalizedEntity` | `normalized_entities` | Entity dictionary for standardized and unmapped biomedical entities. |
| `EvidenceEntityBinding` | `evidence_entity_bindings` | Hyperedge-style evidence-to-entity roles. |
| `EntityMergeEvent` | `entity_merge_events` | Audit history for entity merges. |
| `TerminologyEntry` | `terminology_entries` | Unified reference entity imported from terminology databases. |
| `TerminologyAlias` | `terminology_aliases` | Indexed lookup alias for terminology matching. |
| `TerminologyRelationship` | `terminology_relationships` | Structured relationship between terminology entries. |
| `TerminologyEmbedding` | `terminology_embeddings` | Vector embeddings for terminology entries with HNSW index for cosine similarity search. |

#### Phase 4 — review, feedback, and chat models

| Model | Table | Purpose |
|---|---|---|
| `User` | `users` | Minimal auth and review ownership table. |
| `ReviewAuditEvent` | `review_audit_events` | Audit trail for evidence review operations (status changes, field edits). |
| `ChatSession` | `chat_sessions` | Chat session bound to a processing run and optional user. |
| `ChatMessage` | `chat_messages` | Individual chat message with role, content, and optional evidence/entity links. |
| `PipelineRunState` | `pipeline_run_states` | Checkpoint persistence for the pipeline orchestrator — stores full `PipelineGraphState` as JSONB for crash recovery. |

### postgresql/vector_repo.py

| Method | Signature | Description |
|---|---|---|
| `search_similar` | `search_similar(*, entity_type: str, embedding: list[float], limit: int = 10, min_distance: float \| None = None, embedding_model: str \| None = None) -> list[VectorSearchRow]` | Cosine similarity search against `terminology_embeddings`. Returns rows with `entry_id`, `entity_type`, `source_db`, `external_id`, `display_name`, `embedding_text`, and `distance`. |
| `upsert_embeddings` | `upsert_embeddings(*, entry_ids: list[UUID], entity_type: str, source_db: str, external_ids: list[str], embedding_model: str, embeddings: list[list[float]], embedding_texts: list[str]) -> None` | Delete-then-insert strategy for existing `(entry_id, embedding_model)` pairs. Validates that all input lists have equal length. |

### postgresql/search_index_repo.py

| Method | Signature | Description |
|---|---|---|
| `search` | `search(gene_ids: list[str] \| None = None, variant_ids: list[str] \| None = None, doi: str \| None = None, pmid: str \| None = None, field_id: str \| None = None, limit: int = 50) -> list[dict[str, object]]` | Queries `frontend_search_index` with OR-combined filters. Uses JSONB `?|` overlap operator for array columns. Returns empty list when no filters are supplied. |
| `refresh` | `refresh() -> None` | Truncates and rebuilds the read projection from canonical evidence and source identifiers. |

`refresh()` depends on `active_payload` keys defined by `GENE_IDS_PAYLOAD_KEY`, `VARIANT_IDS_PAYLOAD_KEY`, `ENTITY_IDS_PAYLOAD_KEY`, and `SEARCH_TEXT_PAYLOAD_KEY`.

### redis/cache_repo.py

| Method | Signature | Description |
|---|---|---|
| `get_document` | `get_document(document_id: str) -> dict[str, object] \| None` | Reads an unstructured document cache payload. |
| `set_document` | `set_document(document_id: str, value: dict[str, object], ttl: int = 3600) -> None` | Stores a document payload under `doc:<id>`. |
| `get_canonical_evidence` | `get_canonical_evidence(canonical_evidence_id: str) -> dict[str, object] \| None` | Reads an unstructured canonical evidence cache payload. |
| `set_canonical_evidence` | `set_canonical_evidence(canonical_evidence_id: str, value: dict[str, object], ttl: int = 3600) -> None` | Stores a canonical evidence payload. |
| `get_entity` | `get_entity(entity_id: str) -> dict[str, object] \| None` | Reads an unstructured entity cache payload. |
| `set_entity` | `set_entity(entity_id: str, value: dict[str, object], ttl: int = 3600) -> None` | Stores an entity payload. |
| `invalidate_document` | `invalidate_document(document_id: str) -> None` | Removes cached document by ID using a transactional pipeline. |
| `invalidate_canonical_evidence` | `invalidate_canonical_evidence(canonical_evidence_id: str) -> None` | Removes cached canonical evidence by ID using a transactional pipeline. |
| `invalidate_entity` | `invalidate_entity(entity_id: str) -> None` | Removes cached entity by ID using a transactional pipeline. |
| `invalidate_all` | `invalidate_all(document_ids: list[str] \| None = None, canonical_evidence_ids: list[str] \| None = None, entity_ids: list[str] \| None = None) -> None` | Deletes all affected cache keys in one transactional Redis pipeline. No-op when all ID lists are empty or `None`. |

The `dict` return annotations are intentional because cached JSON payloads are unstructured read-cache values, not stable module contracts.

## Internal Design

### JSONB as plain storage

`postgresql/models.py` keeps JSONB as plain storage. Pydantic/FastAPI boundaries must validate JSON payload shapes before DAO writes. This avoids ORM-level schema coupling and keeps database migrations focused on durable relational structure.

### Entity model dual unique indexes

The entity model uses two partial unique indexes:

- `uq_normalized_entities_standardized_external_id` for standardized rows with external IDs.
- `uq_normalized_entities_unmapped_raw_text` for unmapped rows keyed by raw text.

### Terminology relationships with NULLS NOT DISTINCT

`TerminologyRelationship` uses `postgresql_nulls_not_distinct=True` on its unique constraint so that `NULL` `object_entry_id` values (scalar assertions) are treated as equal, preventing duplicate entries.

### Transactional cache invalidation

`CacheRepository.invalidate_all()` derives all affected keys before opening one Redis `pipeline(transaction=True)`. This prevents partial invalidation if the network fails between separate delete commands.

### Lazy imports

Both `postgresql/__init__.py` and `redis/__init__.py` use `__getattr__`-based lazy imports. This avoids eagerly loading the `pgvector` and `redis.asyncio` dependencies when only the models or connection helpers are needed.

### pgvector type registration

`connection.py` attempts to import `pgvector.sqlalchemy.Vector` at module load. If the pgvector Python package is installed, the import registers the type with SQLAlchemy so that `.cosine_distance()` operators work in repository queries. If the package is absent, the import is silently skipped and `Vector` is set to `None`.

## Usage Patterns

### Create a session factory at startup

The application wiring in `src/api/wiring.py` uses a lazy-init singleton pattern:

```python
from src.dao.postgresql.connection import async_session_factory, build_async_engine

engine = build_async_engine()
session_factory = async_session_factory(engine)
```

Keep both objects in application state. Dispose the engine on shutdown via `await engine.dispose()`.

In production, `src/api/wiring.py` manages this lifecycle through `get_session_factory()` and `dispose_engine()`.

### Use the search projection

```python
from src.dao.postgresql.connection import get_async_session
from src.dao.postgresql.search_index_repo import SearchIndexRepository

async with get_async_session(session_factory) as session:
    rows = await SearchIndexRepository(session).search(
        gene_ids=["BRCA1"],
        variant_ids=["rs80357906"],
        limit=25,
    )
```

### Vector similarity search

```python
from src.dao.postgresql.vector_repo import VectorRepository

repo = VectorRepository(session)
results = await repo.search_similar(
    entity_type="gene",
    embedding=[0.1] * 1024,  # must match the Vector(1024) dimension in TerminologyEmbedding
    limit=10,
)
```

### Upsert terminology embeddings

```python
import uuid
from src.dao.postgresql.vector_repo import VectorRepository

repo = VectorRepository(session)
await repo.upsert_embeddings(
    entry_ids=[uuid.uuid4(), uuid.uuid4()],
    entity_type="gene",
    source_db="HGNC",
    external_ids=["HGNC:1100", "HGNC:1101"],
    embedding_model="bge-m3",
    embeddings=[[0.1] * 1024, [0.2] * 1024],
    embedding_texts=["BRCA1 DNA repair associated", "BRCA2 DNA repair associated"],
)
```

### Invalidate cache after a run completes

```python
from src.dao.redis.cache_repo import CacheRepository

cache = CacheRepository(redis_client)
await cache.invalidate_all(
    document_ids=[source_document_id],
    canonical_evidence_ids=changed_canonical_ids,
    entity_ids=changed_entity_ids,
)
```

### Store a pipeline checkpoint

```python
from src.dao.postgresql.models import PipelineRunState

checkpoint = PipelineRunState(
    processing_run_id=run_id,
    source_document_id=doc_id,
    state_json=pipeline_state.model_dump(),
)
session.add(checkpoint)
await session.flush()
```

## Extension Guide

### Adding a write-model table

1. Add a SQLAlchemy 2.0 declarative model to `postgresql/models.py`.
2. Add metadata tests in `backend/tests/dao/postgresql/test_models.py`.
3. Generate an Alembic migration: `cd backend && uv run alembic revision --autogenerate -m "description"`.
4. Add a migration test that guards critical columns, constraints, or indexes.

### Adding a read-side projection

1. Prefer standalone `MetaData()` unless the projection is intentionally migration-managed through `Base.metadata`.
2. Keep refresh SQL in a repository method.
3. Add tests for table shape and query behavior.

### Adding a new storage backend

1. Create a new sub-package under `src/dao/` (e.g., `src/dao/neo4j/`).
2. Implement connection, models, and repository modules within the sub-package.
3. Add tests under `backend/tests/dao/<backend>/`.
4. Update this README with the new sub-package documentation.

## Performance Notes

- `async_session_factory()` uses `expire_on_commit=False`, which avoids unnecessary refreshes in request handlers.
- PostgreSQL search path is set through asyncpg `server_settings` so table names resolve to the configured app schema.
- Redis invalidation uses one transactional pipeline for related keys.
- `frontend_search_index.refresh()` currently truncates and rebuilds a physical table. If refresh cost grows, the repository interface can stay stable while the implementation moves to a materialized view or incremental table refresh.
- `VectorRepository.upsert_embeddings()` uses a delete-then-insert strategy per entry. For bulk loads of thousands of entries, consider batching with explicit transaction boundaries.

## Dependencies

| Dependency | Version | Purpose |
|---|---|---|
| SQLAlchemy 2.0 | `>=2.0` | Async ORM, metadata, table definitions, SQL expressions. |
| asyncpg | `>=0.29` | PostgreSQL async driver behind SQLAlchemy. |
| pgvector | `>=0.3` | Vector type and cosine distance operators for `TerminologyEmbedding`. |
| Alembic | `>=1.13` | Migration environment under `database/migrations/`. |
| redis.asyncio | `>=5.0` | Async Redis cache client. |
| pydantic-settings | `>=2.0` | Loads PostgreSQL and Redis settings through `src.core.config`. |

## Testing

```bash
cd backend

# Run all DAO tests
uv run pytest tests/dao -v

# Run specific sub-package tests
uv run pytest tests/dao/postgresql -v
uv run pytest tests/dao/redis -v

# Lint DAO module
uv run ruff check src/dao tests/dao
```

| Test file | Covers |
|---|---|
| `test_models.py` | ORM model metadata: table names, columns, constraints, indexes. |
| `test_connection.py` | Engine builder, session factory, connect args. |
| `test_search_index_repo.py` | Search query construction and refresh SQL. |
| `test_vector_repo.py` | Vector similarity search and upsert logic. |
| `test_cache_repo.py` | Redis cache get/set/invalidation. |
| `test_alembic_migration.py` | Migration up/down correctness. |
| `test_pgvector_migration.py` | pgvector extension and embedding column migration. |
| `test_type_contract_compliance.py` | Verifies DAO exports follow typed contract rules (no bare `dict` returns in public API). |

Integration tests that require live PostgreSQL or Redis are marked skipped by default.
