# DAO

> Async PostgreSQL persistence, Redis read-cache, and read-side search-index helpers for the backend data access layer.

## Sub-package Organization

```
src/dao/
├── postgresql/    # SQLAlchemy ORM models, connection, and query repositories
├── redis/         # Async Redis cache operations
├── neo4j/         # Graph database access (placeholder)
└── minio/         # MinIO / S3-compatible object storage (placeholder)
```

## Architecture

```text
src.core.config.Settings
        |
        v
postgresql/connection.py  ->  AsyncEngine / async_sessionmaker / session context
        |
        +--> postgresql/models.py                    ORM models (Alembic-managed)
        +--> postgresql/contracts.py                 Typed infrastructure contracts
        +--> postgresql/search_index_repo.py         Flattened read projection queries
        +--> postgresql/literature_profile_repo.py   Per-document evidence group aggregation
        +--> postgresql/document_annotation_repo.py  Document annotation CRUD
        +--> redis/connection.py                   Async Redis client builder
        +--> redis/cache_repo.py                     Redis read-cache and invalidation
```

Singleton lifecycle is managed by `src.api.wiring`: `wire_dependencies()` creates engine, session factory, and Redis client on startup; `dispose_engine()` and `dispose_redis()` release resources on shutdown.

The normalized PostgreSQL write model is migration-managed through `Base.metadata` in `postgresql/models.py`. The `frontend_search_index` table in `postgresql/search_index_repo.py` uses standalone `MetaData` so Alembic autogenerate does not treat the manual read projection as core write-model drift.

## Public API

### postgresql/connection.py

| Function | Description |
|---|---|
| `build_asyncpg_connect_args` | Builds asyncpg `server_settings` with the configured schema search path |
| `build_async_engine` | Creates a SQLAlchemy async engine from config (DSN, pool size, overflow, search path) |
| `async_session_factory` | Binds `AsyncSession` instances to an engine with `expire_on_commit=False` |
| `get_async_session` | Context-managed session helper requiring an explicit factory |

### postgresql/models.py

`Base` is the Alembic target metadata for the normalized schema. Key model groups:

- **Document lifecycle:** `SourceDocument`, `SourceDocumentIdentifier`, `ProcessingRun`, `PipelineRunState`, `DocumentProcessingCache`
- **Evidence:** `RunEvidenceItem`, `CanonicalEvidenceItem`, `EvidenceEntityBinding`
- **Entity and terminology:** `NormalizedEntity`, `EntityMergeEvent`, `TerminologyEntry`, `TerminologyAlias`, `TerminologyRelationship`, `TerminologyEmbedding`
- **Phase 4:** `User`, `ReviewAuditEvent`, `LiteratureProfile`, `ChatSession`, `ChatMessage`, `DocumentAnnotation`

### postgresql/literature_profile_repo.py

| Method | Description |
|---|---|
| `refresh_for_document` | Rebuild the `literature_profiles` row for a given `source_document_id` from canonical evidence |
| `get_by_document` | Retrieve a single literature profile by `source_document_id` |
| `search` | Search literature profiles with optional filters (gene, variant, disease, pmid, doi), paginated |

### postgresql/search_index_repo.py

| Method | Description |
|---|---|
| `search` | Queries `frontend_search_index` with OR-combined filters (gene, variant, disease, gene_ids, variant_ids, doi, pmid, field_id) |
| `refresh` | Truncates and rebuilds the read projection from canonical evidence and source identifiers |

### postgresql/document_annotation_repo.py

| Function | Description |
|---|---|
| `list_annotations` | Return annotations for a document, optionally filtered by track |
| `get_annotation` | Fetch a single annotation by UUID |
| `create_annotation` | Insert a new annotation and return the persisted row |
| `update_annotation` | Patch mutable fields (color, note) of an annotation |
| `delete_annotation` | Delete an annotation by UUID |

### redis/connection.py

| Function | Description |
|---|---|
| `build_redis_client` | Creates an async Redis client from config (host, port, db, password, max_connections) |

### redis/cache_repo.py

| Method | Description |
|---|---|
| `get_document` / `set_document` | Read/write unstructured document cache payload |
| `get_canonical_evidence` / `set_canonical_evidence` | Read/write canonical evidence cache payload |
| `get_entity` / `set_entity` | Read/write entity cache payload |
| `invalidate_document` / `invalidate_canonical_evidence` / `invalidate_entity` | Remove individual cached entries |
| `invalidate_all` | Transactional bulk invalidation across all key types |

## Usage Patterns

### Create a session factory at startup

```python
from src.dao.postgresql.connection import async_session_factory, build_async_engine

engine = build_async_engine()
session_factory = async_session_factory(engine)
# In production, src/api/wiring.py manages this lifecycle
```

### Use the search projection

```python
from src.dao.postgresql.connection import get_async_session
from src.dao.postgresql.search_index_repo import SearchIndexRepository

async with get_async_session(session_factory) as session:
    repo = SearchIndexRepository(session)
    rows = await repo.search(gene_ids=["BRCA1"], limit=20)
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

## Dependencies

| Dependency | Purpose |
|---|---|
| SQLAlchemy 2.0 | Async ORM, metadata, table definitions, SQL expressions |
| asyncpg | PostgreSQL async driver behind SQLAlchemy |
| pgvector | Vector type and cosine distance operators for `TerminologyEmbedding` |
| Alembic | Migration environment under `database/migrations/` |
| redis.asyncio | Async Redis cache client |

## Testing

```bash
cd backend
uv run pytest tests/dao -v
```

Integration tests that require live PostgreSQL or Redis are marked skipped by default.
