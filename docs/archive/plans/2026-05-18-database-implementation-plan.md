# Database Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the MVP database layer for CrossEvidence with normalized PostgreSQL persistence, Redis read caching, Alembic migrations, async SQLAlchemy access, and a flattened search index for fast front-end lookup.

**Architecture:** Keep the write side normalized and versioned: source documents, external identifiers, processing runs, run-level evidence, canonical evidence, normalized entities, and entity bindings remain separate tables. Expose a dedicated read model for front-end search so gene/variant/DOI/PMID queries do not pay the full join cost on every keystroke. Redis stays a DAO cache only, invalidated proactively when a run completes or review status changes.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async ORM, Alembic, asyncpg, Redis, Pydantic, pytest, loguru, uv

---

**Status:** completed
**Created:** 2026-05-18
**Completed:** 2026-05-18
**PR:** branch `database-mvp`

## Context

### Confirmed Schema Direction

- `source_documents` is the stable document root.
- `source_document_identifiers` stores DOI/PMID/PMCID/file hash and deduplicates on `(identifier_type, identifier_value)`.
- `processing_runs` stores version snapshots and input/output artifact references for each pipeline run.
- `run_evidence_items` stores run-level evidence with `position_hash`, `text_hash`, `entity_scope_hash`, and `raw_payload`.
- `canonical_evidence_items` stores the current best aggregated evidence, a minimal review status, and flattened `active_payload`.
- `normalized_entities` uses internal UUIDs plus `(entity_type, normalized_raw_text)` or `(entity_type, external_id)` uniqueness depending on status.
- `evidence_entity_bindings` stores hyperedge-style roles: `subject`, `target`, `context`, `comparator`, `mention`.
- `entity_merge_events` preserves merge audit history.
- Redis is only a cache layer for DAO reads.
- `frontend_search_index` is the read-optimized surface for front-end query paths.

### Existing Repo Facts

- `backend/src/dao/` exists but is empty.
- `backend/src/core/config.py` already has PostgreSQL and Redis settings, but no DAO connection helpers yet.
- `backend/pyproject.toml` already includes `sqlalchemy`, `asyncpg`, `alembic`, and `redis`.
- `database/migrations/` exists and is the intended Alembic home.
- `database/seeds/` exists and can hold initial seed data.

### Important Constraints

- Use SQLAlchemy 2.0 style only.
- Keep `raw_payload` JSONB validation in Pydantic, not in database CHECK constraints.
- Treat JSONB columns as plain storage at the SQLAlchemy layer. FastAPI/Pydantic contracts must validate `raw_payload`, `active_payload`, `source_span`, and other JSONB shapes before DAO writes; do not bind Pydantic models to ORM JSONB fields with `TypeDecorator`.
- Do not add pgvector or Neo4j implementation to MVP.
- Do not build a token/session Redis subsystem yet.
- Avoid bare `dict` return annotations in backend code.

---

## Task 1: Add database connection settings and helpers

**Files:**
- Modify: `backend/src/core/config.py`
- Create: `backend/tests/core/test_database_config.py`

**Step 1: Write the failing test**

Create a test that verifies:

- `Settings().postgresql` exposes host, port, db, schema, user, password, pool_size, max_overflow.
- `Settings().redis` exposes host, port, password, db, max_connections.
- A derived async SQLAlchemy DSN helper exists and uses the PostgreSQL settings.

Example:

```python
from src.core.config import Settings


def test_postgresql_and_redis_nested_config():
    settings = Settings()
    assert settings.postgresql.host == "127.0.0.1"
    assert settings.redis.host == "localhost"


def test_postgresql_dsn_helper():
    settings = Settings()
    assert settings.postgresql_dsn.startswith("postgresql+asyncpg://")
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/core/test_database_config.py -v
```

Expected: FAIL because the DSN helper is missing or incomplete.

**Step 3: Write minimal implementation**

Add a small helper in `backend/src/core/config.py` or a DAO config module that returns an async SQLAlchemy PostgreSQL DSN using the existing nested settings.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && uv run pytest tests/core/test_database_config.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/config.py backend/tests/core/test_database_config.py
git commit -m "feat: add database connection config helper"
```

---

## Task 2: Build async database connection and session helpers

**Files:**
- Create: `backend/src/dao/connection.py`
- Create: `backend/tests/dao/test_connection.py`

**Step 1: Write the failing test**

Add tests for:

- building an async engine from config
- creating an async session factory
- exporting a context-managed session helper
- preserving schema/search-path behavior for the configured app schema

Example:

```python
from src.dao.connection import build_async_engine, async_session_factory


def test_build_async_engine_uses_asyncpg():
    engine = build_async_engine()
    assert "asyncpg" in str(engine.url)
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/dao/test_connection.py -v
```

Expected: FAIL because the module does not exist yet.

**Step 3: Write minimal implementation**

Implement an async SQLAlchemy engine factory, an `async_sessionmaker`, and a lightweight helper for app-schema handling.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && uv run pytest tests/dao/test_connection.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/dao/connection.py backend/tests/dao/test_connection.py
git commit -m "feat: add async database connection helpers"
```

---

## Task 3: Define SQLAlchemy 2.0 ORM models for the MVP schema

**Files:**
- Create: `backend/src/dao/models.py`
- Create: `backend/tests/dao/test_models.py`

**Step 1: Write the failing test**

Add tests that verify the ORM metadata contains:

- `source_documents`
- `source_document_identifiers`
- `processing_runs`
- `normalized_entities`
- `entity_merge_events`
- `run_evidence_items`
- `evidence_entity_bindings`
- `canonical_evidence_items`
- `users`

Also assert the key constraints:

- unique `(identifier_type, identifier_value)`
- unique `(source_document_id, field_id, position_hash, entity_scope_hash)`
- unique `(entity_type, external_id)`
- unique `(entity_type, normalized_raw_text)` for unmapped rows

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/dao/test_models.py -v
```

Expected: FAIL because the ORM models are missing.

**Step 3: Write minimal implementation**

Add SQLAlchemy 2.0 declarative models with UUID primary keys, JSONB fields, timestamps, explicit indexes, and typed relationships only where they remove ambiguity.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && uv run pytest tests/dao/test_models.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/dao/models.py backend/tests/dao/test_models.py
git commit -m "feat: add MVP database ORM models"
```

---

## Task 4: Add Alembic environment and initial migration

**Files:**
- Create: `database/migrations/env.py`
- Create: `database/migrations/versions/<timestamp>_init_mvp_schema.py`
- Modify: `database/migrations/.gitkeep` or replace with real files
- Create: `database/migrations/script.py.mako`
- Create: `database/alembic.ini` only if the repo does not already have an equivalent Alembic config in the root database directory
- Create: `backend/tests/dao/test_alembic_migration.py`

**Step 1: Write the failing test**

Add a migration smoke test that:

- points Alembic at `database/migrations/`
- verifies the migration environment uses the async Alembic pattern, equivalent to `alembic init -t async`
- verifies `database/migrations/env.py` can import `backend/src/dao/models.py` metadata even when Alembic is launched from the repo root or the `database/` directory
- upgrades to head against a test database
- verifies the core tables exist

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/dao/test_alembic_migration.py -v
```

Expected: FAIL because Alembic is not wired yet.

**Step 3: Write minimal implementation**

Create the Alembic environment under `database/migrations/`, import `backend/src/dao/models.py` metadata, and add a first revision that creates the MVP schema.

Implementation constraints:

- Generate or mirror the async template from `alembic init -t async`; the generated `env.py` must use async SQLAlchemy migration flow with `asyncpg`, not the default synchronous engine.
- Because migrations live outside `backend/`, `env.py` must calculate the repo root from `__file__` and add the backend directory to `sys.path` before importing `src.dao.models`.
- Keep `target_metadata` wired to the SQLAlchemy 2.0 declarative metadata from `src.dao.models`.
- Do not hide path setup in local shell assumptions; `uv run alembic -c database/alembic.ini upgrade head` should work from the repo root.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && uv run pytest tests/dao/test_alembic_migration.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add database/migrations backend/tests/dao/test_alembic_migration.py
git commit -m "feat: add Alembic migration for MVP schema"
```

---

## Task 5: Add Redis cache repository helpers

**Files:**
- Create: `backend/src/dao/cache_repo.py`
- Create: `backend/tests/dao/test_cache_repo.py`

**Step 1: Write the failing test**

Add tests that verify:

- cache read helpers exist for source documents, canonical evidence, entities, and search results
- cache invalidation helpers accept affected IDs and delete the correct key namespaces
- invalidation uses a Redis pipeline or `MULTI`/`EXEC` transaction for batched deletes
- the implementation does not assume token/session caching yet

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/dao/test_cache_repo.py -v
```

Expected: FAIL because the repository is missing.

**Step 3: Write minimal implementation**

Implement a small Redis-backed helper that stores JSON payloads by namespace and invalidates by entity/document/canonical IDs.

Implementation constraints:

- Invalidation must derive all affected keys first, then delete them through a single Redis pipeline with transactional behavior where supported, for example `pipeline(transaction=True)` in redis-py.
- Do not issue separate awaited `DEL` calls for `doc:*`, `entity:*`, `canonical:*`, and `search:*` namespaces; a partial network failure between commands can leave stale cache behind.
- Keep token/session TTL namespaces out of this repository until authentication is implemented.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && uv run pytest tests/dao/test_cache_repo.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/dao/cache_repo.py backend/tests/dao/test_cache_repo.py
git commit -m "feat: add Redis cache repository helpers"
```

---

## Task 6: Add read-side search index projection

**Files:**
- Create: `backend/src/dao/search_index_repo.py`
- Create: `backend/tests/dao/test_search_index_repo.py`

**Step 1: Write the failing test**

Add tests for a helper that builds or refreshes `frontend_search_index` with:

- `canonical_evidence_id`
- `pmid`
- `doi`
- `gene_ids`
- `variant_ids`
- `entity_ids`
- `field_id`
- `review_status`
- `current_best_confidence`
- `search_text`
- `active_payload`

**Step 2: Run test to verify it fails**

Run:

```bash
cd backend && uv run pytest tests/dao/test_search_index_repo.py -v
```

Expected: FAIL because the repository is missing.

**Step 3: Write minimal implementation**

Implement a refresh helper and a query helper for the flattened search surface.

Implementation constraints:

- If `frontend_search_index` starts as a materialized view, create a unique index on `canonical_evidence_id`. PostgreSQL requires a unique index before `REFRESH MATERIALIZED VIEW CONCURRENTLY` can be used.
- Refresh materialized views with `REFRESH MATERIALIZED VIEW CONCURRENTLY frontend_search_index`, not plain `REFRESH MATERIALIZED VIEW`, so front-end searches do not block behind an exclusive refresh lock.
- If concurrent refresh cost or migration ergonomics become too high, switch the read side to a refreshable physical table, but keep the same repository interface.

**Step 4: Run test to verify it passes**

Run:

```bash
cd backend && uv run pytest tests/dao/test_search_index_repo.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/dao/search_index_repo.py backend/tests/dao/test_search_index_repo.py
git commit -m "feat: add flattened search index repository"
```

---

## Task 7: Wire database docs and operator scripts

**Files:**
- Modify: `docs/README.md`
- Modify: `database/config/.env.example`
- Create or modify: `database/scripts/dbctl.sh` only if it needs database init hooks for the new Alembic layout
- Modify: `database/seeds/` if seed data is needed for initial lookup tables

**Step 1: Write the failing check**

Add a docs/index assertion in a simple test or manual verification step that confirms the new database design plan exists and the docs index includes it.

**Step 2: Run verification**

Run:

```bash
git diff -- docs/README.md database/config/.env.example
```

Expected: shows the new database plan and the environment examples aligned with PostgreSQL/Redis/Alembic settings.

**Step 3: Write minimal implementation**

Update docs index entries, environment examples, and any small dbctl hooks needed to initialize the new Alembic layout.

**Step 4: Run verification**

Run:

```bash
git diff -- docs/README.md database/config/.env.example database/scripts/dbctl.sh
```

Expected: only the intended doc and bootstrap changes.

**Step 5: Commit**

```bash
git add docs/README.md database/config/.env.example database/scripts/dbctl.sh
git commit -m "docs: align database bootstrap and index with MVP schema"
```

---

## Risks

- The schema may still need minor field adjustments once the DAO layer starts consuming real extraction payloads.
- Alembic pathing can be annoying because this repo keeps database infrastructure at the root, not under `backend/`; using the synchronous Alembic template would also break asyncpg migrations.
- The first search index implementation may need to shift from materialized view to refreshable table if refresh cost becomes too high.
- A materialized-view search index can block front-end reads if refreshed without `CONCURRENTLY`, and `CONCURRENTLY` requires a unique index on `canonical_evidence_id`.
- Redis cache key design may need one extra pass once actual read endpoints are wired.
- Redis invalidation must be batched through a pipeline or transaction; partial invalidation can make the read model appear inconsistent after entity merges or completed runs.
- JSONB model binding in the ORM layer can create avoidable deserialization overhead and schema drift. Keep JSONB validation at the Pydantic boundary and DAO storage plain.
