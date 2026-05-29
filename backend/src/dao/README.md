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
        +--> redis/cache_repo.py               Redis read-cache and invalidation
        +--> postgresql/contracts.py           typed infrastructure contracts
```

The normalized PostgreSQL write model is migration-managed through `Base.metadata` in `postgresql/models.py`. The `frontend_search_index` table in `postgresql/search_index_repo.py` uses standalone `MetaData` so Alembic autogenerate does not treat the manual read projection as core write-model drift.

## Public API

### postgresql/connection.py

| Function | Signature | Description |
|---|---|---|
| `build_asyncpg_connect_args` | `build_asyncpg_connect_args(settings: Settings | None = None) -> AsyncpgConnectArgs` | Builds asyncpg `server_settings` with the configured schema search path. |
| `build_async_engine` | `build_async_engine(settings: Settings | None = None) -> AsyncEngine` | Creates a SQLAlchemy async engine from `Settings.postgresql_dsn`, pool size, overflow, and search path. |
| `async_session_factory` | `async_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]` | Binds `AsyncSession` instances to an engine with `expire_on_commit=False`. |
| `get_async_session` | `get_async_session(session_factory: SessionFactory) -> AsyncIterator[AsyncSession]` | Context-managed session helper. It requires an explicit factory to avoid hidden engine creation. |

### postgresql/models.py

`Base` is the Alembic target metadata for the normalized schema.

| Model | Table | Purpose |
|---|---|---|
| `SourceDocument` | `source_documents` | Stable document identity across retries and reprocessing. |
| `SourceDocumentIdentifier` | `source_document_identifiers` | DOI, PMID, PMCID, file hash, and other dedupe identifiers. |
| `ProcessingRun` | `processing_runs` | Version snapshot and artifact references for one pipeline run. |
| `RunEvidenceItem` | `run_evidence_items` | Versioned run-level evidence with location, confidence, and raw payload. |
| `CanonicalEvidenceItem` | `canonical_evidence_items` | Current-best canonical evidence keyed by source, field, position, and entity scope. |
| `NormalizedEntity` | `normalized_entities` | Entity dictionary for standardized and unmapped biomedical entities. |
| `EvidenceEntityBinding` | `evidence_entity_bindings` | Hyperedge-style evidence-to-entity roles. |
| `EntityMergeEvent` | `entity_merge_events` | Audit history for entity merges. |
| `User` | `users` | Minimal auth and review ownership table. |
| `TerminologyEntry` | `terminology_entries` | Unified reference entity imported from terminology databases. |
| `TerminologyAlias` | `terminology_aliases` | Indexed lookup alias for terminology matching. |
| `TerminologyRelationship` | `terminology_relationships` | Structured relationship between terminology entries. |
| `TerminologyEmbedding` | `terminology_embeddings` | Vector embeddings for terminology entries with HNSW index for cosine similarity search. |

### redis/cache_repo.py

| Method | Signature | Description |
|---|---|---|
| `get_document` | `get_document(document_id: str) -> dict[str, object] | None` | Reads an unstructured document cache payload. |
| `set_document` | `set_document(document_id: str, value: dict[str, object], ttl: int = 3600) -> None` | Stores a document payload under `doc:<id>`. |
| `get_canonical_evidence` | `get_canonical_evidence(canonical_evidence_id: str) -> dict[str, object] | None` | Reads an unstructured canonical evidence cache payload. |
| `set_canonical_evidence` | `set_canonical_evidence(canonical_evidence_id: str, value: dict[str, object], ttl: int = 3600) -> None` | Stores a canonical evidence payload. |
| `get_entity` | `get_entity(entity_id: str) -> dict[str, object] | None` | Reads an unstructured entity cache payload. |
| `set_entity` | `set_entity(entity_id: str, value: dict[str, object], ttl: int = 3600) -> None` | Stores an entity payload. |
| `invalidate_all` | `invalidate_all(document_ids: list[str] | None = None, canonical_evidence_ids: list[str] | None = None, entity_ids: list[str] | None = None) -> None` | Deletes all affected cache keys in one transactional Redis pipeline. |

The `dict` return annotations are intentional because cached JSON payloads are unstructured read-cache values, not stable module contracts.

### postgresql/search_index_repo.py

| Method | Signature | Description |
|---|---|---|
| `search` | `search(gene_ids: list[str] | None = None, variant_ids: list[str] | None = None, doi: str | None = None, pmid: str | None = None, field_id: str | None = None, limit: int = 50) -> list[dict[str, object]]` | Queries `frontend_search_index` with OR-combined filters. |
| `refresh` | `refresh() -> None` | Truncates and rebuilds the read projection from canonical evidence and source identifiers. |

`refresh()` depends on `active_payload` keys defined by `GENE_IDS_PAYLOAD_KEY`, `VARIANT_IDS_PAYLOAD_KEY`, `ENTITY_IDS_PAYLOAD_KEY`, and `SEARCH_TEXT_PAYLOAD_KEY`.

## Internal Design

`postgresql/models.py` keeps JSONB as plain storage. Pydantic/FastAPI boundaries must validate JSON payload shapes before DAO writes. This avoids ORM-level schema coupling and keeps database migrations focused on durable relational structure.

The entity model uses two partial unique indexes:

- `uq_normalized_entities_standardized_external_id` for standardized rows with external IDs.
- `uq_normalized_entities_unmapped_raw_text` for unmapped rows keyed by raw text.

`CacheRepository.invalidate_all()` derives all affected keys before opening one Redis `pipeline(transaction=True)`. This prevents partial invalidation if the network fails between separate delete commands.

## Usage Patterns

### Create A Session Factory At Startup

```python
from src.dao.postgresql.connection import async_session_factory, build_async_engine

engine = build_async_engine()
session_factory = async_session_factory(engine)
```

Keep both objects in application state. Dispose the engine on shutdown.

### Use The Search Projection

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

### Vector Similarity Search

```python
from src.dao.postgresql.vector_repo import VectorRepository

repo = VectorRepository(session)
results = await repo.search_similar(
    entity_type="gene",
    embedding=[0.1] * 1536,
    limit=10,
)
```

### Invalidate Cache After A Run Completes

```python
from src.dao.redis.cache_repo import CacheRepository

cache = CacheRepository(redis_client)
await cache.invalidate_all(
    document_ids=[source_document_id],
    canonical_evidence_ids=changed_canonical_ids,
    entity_ids=changed_entity_ids,
)
```

## Extension Guide

When adding a write-model table:

1. Add a SQLAlchemy 2.0 declarative model to `postgresql/models.py`.
2. Add metadata tests in `backend/tests/dao/postgresql/test_models.py`.
3. Add or update an Alembic migration under `database/migrations/versions/`.
4. Add a migration test that guards critical columns, constraints, or indexes.

When adding a read-side projection:

1. Prefer standalone `MetaData()` unless the projection is intentionally migration-managed through `Base.metadata`.
2. Keep refresh SQL in a repository method.
3. Add tests for table shape and query behavior.

When adding a new storage backend:

1. Create a new sub-package under `src/dao/` (e.g., `src/dao/neo4j/`).
2. Implement connection, models, and repository modules within the sub-package.
3. Add tests under `backend/tests/dao/<backend>/`.
4. Update this README with the new sub-package documentation.

## Performance Notes

- `async_session_factory()` uses `expire_on_commit=False`, which avoids unnecessary refreshes in request handlers.
- PostgreSQL search path is set through asyncpg `server_settings` so table names resolve to the configured app schema.
- Redis invalidation uses one transactional pipeline for related keys.
- `frontend_search_index.refresh()` currently truncates and rebuilds a physical table. If refresh cost grows, the repository interface can stay stable while the implementation moves to a materialized view or incremental table refresh.

## Dependencies

| Dependency | Purpose |
|---|---|
| SQLAlchemy 2.0 | Async ORM, metadata, table definitions, SQL expressions. |
| asyncpg | PostgreSQL async driver behind SQLAlchemy. |
| Alembic | Migration environment under `database/migrations/`. |
| redis.asyncio | Async Redis cache client. |
| pydantic-settings | Loads PostgreSQL and Redis settings through `src.core.config`. |

## Testing

```bash
cd backend
uv run pytest tests/dao -v
uv run --extra dev ruff check src/dao tests/dao tests/conftest.py
```

Integration tests that require live PostgreSQL or Redis are marked skipped by default.
