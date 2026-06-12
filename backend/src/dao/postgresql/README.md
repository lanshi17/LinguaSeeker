# PostgreSQL DAO

> SQLAlchemy 2.0 async ORM models, connection helpers, and query repositories for the CrossEvidence persistence layer.

## Architecture

```text
connection.py                 contracts.py
  build_async_engine()          AsyncpgConnectArgs (TypedDict)
  async_session_factory()
  get_async_session()           ┌──────────────────────────────────────────┐
        │                       │  models.py -- Base (Alembic target)      │
        │                       │  SourceDocument, ProcessingRun           │
        │                       │  RunEvidenceItem, CanonicalEvidenceItem  │
        │                       │  NormalizedEntity, EvidenceEntityBinding │
        │                       │  TerminologyEntry/Alias/Relationship/Emb │
        │                       │  User, ReviewAuditEvent                  │
        │                       │  ChatSession, ChatMessage                │
        │                       │  PipelineRunState, LiteratureProfile     │
        │                       └──────────────────────────────────────────┘
        │
        ├──> search_index_repo.py       SearchIndexRepository (read projection)
        └──> literature_profile_repo.py LiteratureProfileRepository (evidence aggregation)
```

The write model (`models.py`) uses `Base.metadata` -- Alembic autogenerate tracks it. The read projection (`search_index_repo.py`) uses a standalone `MetaData()` so Alembic does not treat the flattened table as core schema drift.

## Modules

### connection.py -- Engine and Session Lifecycle

| Function | Description |
|---|---|
| `build_asyncpg_connect_args` | Builds `server_settings` with `search_path` set to `{schema_},public` |
| `build_async_engine` | Creates an async engine from DSN, pool config, and connect args |
| `async_session_factory` | Binds sessions with `expire_on_commit=False` |
| `get_async_session` | Context-managed session that closes on exit; requires an explicit factory |

pgvector registration: `connection.py` imports `pgvector.sqlalchemy.Vector` at module load. If absent, `Vector` is silently set to `None`.

### contracts.py -- Typed Infrastructure Contracts

Defines `AsyncpgServerSettings` and `AsyncpgConnectArgs` TypedDicts that enforce the exact shape of asyncpg connection arguments at the type-checker level.

### models.py -- ORM Models

All models use SQLAlchemy 2.0 declarative style with `Mapped[]` annotations. Key groups:

- **Document lifecycle:** `SourceDocument`, `SourceDocumentIdentifier`, `ProcessingRun`, `PipelineRunState`
- **Evidence:** `RunEvidenceItem`, `CanonicalEvidenceItem`
- **Entity/terminology:** `NormalizedEntity`, `EvidenceEntityBinding`, `EntityMergeEvent`, `TerminologyEntry`, `TerminologyAlias`, `TerminologyRelationship`, `TerminologyEmbedding`
- **Phase 4:** `User`, `ReviewAuditEvent`, `ChatSession`, `ChatMessage`, `LiteratureProfile`

### search_index_repo.py -- Read Projection

| Method | Description |
|---|---|
| `search` | OR-combined query against `frontend_search_index`. Uses JSONB `?|` overlap for array columns. Returns `[]` with no filters. |
| `refresh` | `TRUNCATE` + `INSERT ... SELECT` from `canonical_evidence_items` joined with `source_document_identifiers`. |

### literature_profile_repo.py -- Evidence Group Aggregation

Builds and maintains the `literature_profiles` table, which stores a per-document aggregated view of `canonical_evidence_items` grouped into `evidence_groups` JSONB.

| Method | Description |
|---|---|
| `_build_evidence_groups` | Pure function that groups canonical evidence rows into the `evidence_groups` structure |
| `refresh_for_document` | Rebuild the profile row for a given `source_document_id` |
| `get_by_document` | Retrieve a single profile by `source_document_id` |
| `search` | Search profiles with optional filters |

## Entity Dual Unique Indexes

`NormalizedEntity` uses two partial unique indexes: one for standardized rows (keyed by `entity_type, external_id`) and one for unmapped rows (keyed by `entity_type, normalized_raw_text`). This prevents collisions across statuses.

## Testing

```bash
cd backend
uv run pytest tests/dao/postgresql -v
```
