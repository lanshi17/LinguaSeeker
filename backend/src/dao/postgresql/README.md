# PostgreSQL DAO

> SQLAlchemy 2.0 async ORM models, connection helpers, and query repositories for the LinguaSeeker persistence layer.

## Architecture

```text
connection.py                    contracts.py
  build_async_engine()             AsyncpgConnectArgs (TypedDict)
  async_session_factory()          AsyncpgServerSettings (TypedDict)
  get_async_session()              CanonicalEvidencePayload (Pydantic)
        │
        │                       ┌──────────────────────────────────────────┐
        │                       │  models.py -- Base (Alembic target)      │
        │                       │  TimestampMixin (created_at, updated_at) │
        │                       │                                          │
        │                       │  Document lifecycle:                     │
        │                       │    SourceDocument                        │
        │                       │    SourceDocumentIdentifier              │
        │                       │    ProcessingRun                         │
        │                       │    PipelineRunState                      │
        │                       │                                          │
        │                       │  Evidence:                               │
        │                       │    RunEvidenceItem                       │
        │                       │    CanonicalEvidenceItem                 │
        │                       │    EvidenceEntityBinding                 │
        │                       │                                          │
        │                       │  Entity/terminology:                     │
        │                       │    NormalizedEntity                      │
        │                       │    EntityMergeEvent                      │
        │                       │    TerminologyEntry                      │
        │                       │    TerminologyAlias                      │
        │                       │    TerminologyRelationship               │
        │                       │    TerminologyEmbedding (pgvector)       │
        │                       │                                          │
        │                       │  Phase 4:                                │
        │                       │    User                                  │
        │                       │    LiteratureProfile                     │
        │                       │    ReviewAuditEvent                      │
        │                       │    ChatSession, ChatMessage              │
        │                       └──────────────────────────────────────────┘
        │
        ├──> search_index_repo.py       SearchIndexRepository (read projection)
        └──> literature_profile_repo.py LiteratureProfileRepository (evidence aggregation)
```

The write model (`models.py`) uses `Base.metadata` -- Alembic autogenerate tracks it. The read projection (`search_index_repo.py`) uses a standalone `MetaData()` so Alembic does not treat the flattened table as core schema drift.

The `__init__.py` uses lazy imports via `__getattr__` to avoid loading pgvector and other heavy dependencies at import time. Prefer importing specific submodules directly (e.g. `from src.dao.postgresql.models import Base`).

## Modules

### connection.py -- Engine and Session Lifecycle

| Function | Description |
|---|---|
| `build_asyncpg_connect_args` | Builds `server_settings` with `search_path` set to `{schema_},public` |
| `build_async_engine` | Creates an async engine from DSN, pool config (`pool_size`, `max_overflow`), and connect args |
| `async_session_factory` | Binds sessions with `expire_on_commit=False` |
| `get_async_session` | Context-managed session that closes on exit; requires an explicit factory |

pgvector registration: `connection.py` imports `pgvector.sqlalchemy.Vector` at module load. If absent, `Vector` is silently set to `None`.

### contracts.py -- Typed Infrastructure Contracts

| Symbol | Type | Description |
|---|---|---|
| `AsyncpgServerSettings` | `TypedDict` | asyncpg server settings (search_path) |
| `AsyncpgConnectArgs` | `TypedDict` | SQLAlchemy asyncpg connection arguments |
| `CanonicalEvidencePayload` | `Pydantic BaseModel` | Field-level JSONB contract for `CanonicalEvidenceItem.active_payload`. Uses `extra="allow"` to preserve unknown keys from extraction providers. |

### models.py -- ORM Models

All models use SQLAlchemy 2.0 declarative style with `Mapped[]` annotations. `TimestampMixin` provides `created_at`/`updated_at` with server defaults. Key groups:

**Document lifecycle:**
- `SourceDocument` -- Stable source document root across processing runs. Has `raw_metadata` JSONB and `latest_processing_run_id` FK.
- `SourceDocumentIdentifier` -- External identifier registry (PMID, DOI, etc.) for deduplication. Unique on `(identifier_type, identifier_value)`.
- `ProcessingRun` -- Reproducibility boundary for one pipeline execution. Stores version hashes (parser, translation, extraction, standardization, fusion, prompt, model, config).
- `PipelineRunState` -- Checkpoint persistence for pipeline orchestrator state. Stores full `PipelineGraphState` as JSONB. Includes durable worker lease fields (`owner_worker_id`, `heartbeat_at`, `source_key`) with a partial unique index on active source keys.

**Evidence:**
- `RunEvidenceItem` -- Versioned evidence item produced by one processing run. Confidence constrained to [0, 1]. Has `position_hash`, `text_hash`, `entity_scope_hash` for identity.
- `CanonicalEvidenceItem` -- Current-best canonical evidence record grouped across runs. Unique on `(source_document_id, field_id, position_hash, entity_scope_hash)`. GIN index on `active_payload ->> 'group_id'`.
- `EvidenceEntityBinding` -- Hyperedge-style relation between run evidence and normalized entities.

**Entity/terminology:**
- `NormalizedEntity` -- Shared dictionary for standardized and unmapped biomedical entities. Uses dual partial unique indexes: one for standardized rows (`entity_type, external_id`) and one for unmapped rows (`entity_type, normalized_raw_text`). Self-referential `merged_into_entity_id` FK for merge chains.
- `EntityMergeEvent` -- Audit trail for entity merge decisions.
- `TerminologyEntry` -- Unified reference entity imported from terminology databases. Unique on `(source_db, external_id)`.
- `TerminologyAlias` -- Indexed lookup alias for terminology matching. Unique on `(entry_id, normalized_alias, alias_type)`.
- `TerminologyRelationship` -- Structured relationship between entries or scalar assertions. Uses `NULLS NOT DISTINCT` to prevent duplicate scalar assertions.
- `TerminologyEmbedding` -- pgvector embedding for semantic retrieval. Vector dimension: 1024. Unique on `(entry_id, embedding_text_hash, embedding_model)`.

**Phase 4:**
- `User` -- Minimal auth user. Unique on `email`.
- `LiteratureProfile` -- Aggregated literature profile summarizing evidence extraction results. GIN index on `evidence_groups` JSONB. Indexes on `pmid`, `doi`, `review_status`.
- `ReviewAuditEvent` -- Audit trail for evidence review operations. Indexes on `(canonical_evidence_id, created_at DESC)` and `(reviewer_id, created_at DESC)`.
- `ChatSession` -- Chat session optionally bound to a processing run.
- `ChatMessage` -- Chat message in a session. Optional FK to `canonical_evidence_items` and `normalized_entities`.

### search_index_repo.py -- Read Projection

Physical `frontend_search_index` table for fast front-end lookup. Unique index on `canonical_evidence_id` (materialized-view-compatible).

| Method | Description |
|---|---|
| `search` | OR-combined query against `frontend_search_index`. Uses JSONB `?|` overlap for array columns (`gene_ids`, `variant_ids`). Text search via `ilike` on `active_payload` keys. Returns all rows when no filters supplied. |
| `refresh` | `DELETE` + `INSERT ... SELECT` from `canonical_evidence_items` joined with `source_document_identifiers`. Gracefully handles missing table in SQLite test environments. |

### literature_profile_repo.py -- Evidence Group Aggregation

Builds and maintains the `literature_profiles` table, which stores a per-document aggregated view of `canonical_evidence_items` grouped into `evidence_groups` JSONB.

| Method | Description |
|---|---|
| `_build_evidence_groups` | Pure function that groups canonical evidence rows into the `evidence_groups` structure. First-match-wins summary extraction per category (gene, variant, disease, classification). Worst-case review status aggregation. |
| `refresh_for_document` | Rebuild the profile row for a given `source_document_id`. Upserts via `ON CONFLICT DO UPDATE`. |
| `get_by_document` | Retrieve a single profile by `source_document_id` as a dict. |
| `search` | Search profiles with optional OR-combined filters (`gene`, `variant`, `disease`, `pmid`, `doi`). Paginated. |

## Entity Dual Unique Indexes

`NormalizedEntity` uses two partial unique indexes: one for standardized rows (keyed by `entity_type, external_id`) and one for unmapped rows (keyed by `entity_type, normalized_raw_text`). A third partial index covers `reviewed_unmappable` status. This prevents collisions across statuses.

## Testing

```bash
cd backend
uv run pytest tests/dao/postgresql -v
```
