# DAO Submodule Restructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reorganize `backend/src/dao/` into storage-specific subdirectories (`postgresql/`, `redis/`, `neo4j/`, `minio/`) for clearer separation of concerns and future extensibility.

**Architecture:** Each storage backend gets its own sub-package. PostgreSQL files (connection, contracts, models, vector_repo, search_index_repo) move into `dao/postgresql/`. Redis files (cache_repo) move into `dao/redis/`. `dao/neo4j/` and `dao/minio/` are created as empty placeholders for future graph database and S3-compatible object storage integration. The root `dao/__init__.py` documents sub-package organization. All call sites are updated to canonical new paths.

**Tech Stack:** Python, SQLAlchemy, Alembic (migration env.py import path), pytest

---

## Current Structure

```
backend/src/dao/
├── __init__.py           # """Data access layer package."""
├── connection.py         # PostgreSQL async engine/session
├── contracts.py          # AsyncpgConnectArgs TypedDict
├── models.py             # All SQLAlchemy ORM models
├── vector_repo.py        # pgvector terminology repository
├── search_index_repo.py  # JSONB read projection
├── cache_repo.py         # Redis cache repository
└── README.md
```

## Target Structure

```
backend/src/dao/
├── __init__.py              # Package docstring with sub-package map
├── postgresql/
│   ├── __init__.py          # Re-exports all PostgreSQL public API
│   ├── connection.py        # Async engine/session (moved)
│   ├── contracts.py         # AsyncpgConnectArgs (moved)
│   ├── models.py            # All ORM models (moved)
│   ├── vector_repo.py       # VectorRepository (moved)
│   └── search_index_repo.py # SearchIndexRepository (moved)
├── redis/
│   ├── __init__.py          # Re-exports CacheRepository
│   └── cache_repo.py        # CacheRepository (moved)
├── neo4j/
│   └── __init__.py          # Placeholder: """Neo4j data access (placeholder)."""
├── minio/
│   └── __init__.py          # Placeholder: """MinIO / S3-compatible object storage (placeholder)."""
└── README.md                # Updated
```

## Import Migration Map

| Old Path | New Canonical Path |
|---|---|
| `src.dao.connection` | `src.dao.postgresql.connection` |
| `src.dao.contracts` | `src.dao.postgresql.contracts` |
| `src.dao.models` | `src.dao.postgresql.models` |
| `src.dao.vector_repo` | `src.dao.postgresql.vector_repo` |
| `src.dao.search_index_repo` | `src.dao.postgresql.search_index_repo` |
| `src.dao.cache_repo` | `src.dao.redis.cache_repo` |

---

### Task 1: Create Subdirectory Structure and Move Files

**Files:**
- Create: `backend/src/dao/postgresql/__init__.py`
- Create: `backend/src/dao/redis/__init__.py`
- Create: `backend/src/dao/neo4j/__init__.py`
- Create: `backend/src/dao/minio/__init__.py`
- Move: `connection.py`, `contracts.py`, `models.py`, `vector_repo.py`, `search_index_repo.py` → `postgresql/`
- Move: `cache_repo.py` → `redis/`

**Step 1: Create subdirectories**

```bash
cd backend/src/dao
mkdir -p postgresql redis neo4j minio
```

**Step 2: Move PostgreSQL files**

```bash
git mv connection.py postgresql/connection.py
git mv contracts.py postgresql/contracts.py
git mv models.py postgresql/models.py
git mv vector_repo.py postgresql/vector_repo.py
git mv search_index_repo.py postgresql/search_index_repo.py
```

**Step 3: Move Redis files**

```bash
git mv cache_repo.py redis/cache_repo.py
```

**Step 4: Create placeholder `__init__.py` files**

```python
# backend/src/dao/neo4j/__init__.py
"""Neo4j data access layer (placeholder)."""
```

```python
# backend/src/dao/minio/__init__.py
"""MinIO / S3-compatible object storage data access layer (placeholder)."""
```

**Step 5: Create postgresql `__init__.py` with re-exports**

```python
# backend/src/dao/postgresql/__init__.py
"""PostgreSQL data access layer."""

from src.dao.postgresql.connection import (
    async_session_factory,
    build_async_engine,
    build_asyncpg_connect_args,
    get_async_session,
)
from src.dao.postgresql.contracts import AsyncpgConnectArgs
from src.dao.postgresql.models import (
    Base,
    CanonicalEvidenceItem,
    EntityMergeEvent,
    EvidenceEntityBinding,
    NormalizedEntity,
    PipelineRunState,
    ProcessingRun,
    ReviewAuditEvent,
    RunEvidenceItem,
    SourceDocument,
    SourceDocumentIdentifier,
    TerminologyAlias,
    TerminologyEmbedding,
    TerminologyEntry,
    TerminologyRelationship,
    User,
)
from src.dao.postgresql.search_index_repo import SearchIndexRepository, frontend_search_index
from src.dao.postgresql.vector_repo import VectorRepository
```

**Step 6: Create redis `__init__.py` with re-exports**

```python
# backend/src/dao/redis/__init__.py
"""Redis data access layer."""

from src.dao.redis.cache_repo import CACHE_PREFIX, CacheRepository
```

**Step 7: Clean up stale pycache**

```bash
find backend/src/dao -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
```

**Step 8: Commit**

```bash
git add backend/src/dao/
git commit -m "refactor: reorganize dao into postgresql/redis/neo4j/minio subdirectories"
```

---

### Task 2: Fix Internal Imports Within Moved Files

**Files:**
- Modify: `backend/src/dao/postgresql/connection.py`
- Modify: `backend/src/dao/postgresql/vector_repo.py`
- Modify: `backend/src/dao/postgresql/search_index_repo.py`

**Step 1: Update `postgresql/connection.py` internal import**

Change line 10:
```python
# Before:
from src.dao.contracts import AsyncpgConnectArgs
# After:
from src.dao.postgresql.contracts import AsyncpgConnectArgs
```

**Step 2: Update `postgresql/vector_repo.py` internal import**

Change line 10:
```python
# Before:
from src.dao.models import TerminologyEmbedding, TerminologyEntry
# After:
from src.dao.postgresql.models import TerminologyEmbedding, TerminologyEntry
```

**Step 3: `postgresql/search_index_repo.py` has no internal dao imports — verify only**

```bash
grep -n 'from src.dao' backend/src/dao/postgresql/search_index_repo.py
```

Expected: no results (this file has no internal dao imports).

**Step 4: Commit**

```bash
git add backend/src/dao/postgresql/
git commit -m "refactor: update internal imports in moved postgresql modules"
```

---

### Task 3: Update Root `dao/__init__.py`

**Files:**
- Modify: `backend/src/dao/__init__.py`

**Step 1: Keep root `__init__.py` minimal**

The root `__init__.py` stays as a simple package marker. All re-exports live in sub-package `__init__.py` files. This keeps the import graph explicit.

```python
# backend/src/dao/__init__.py
"""Data access layer — organized by storage backend.

Sub-packages:
    postgresql: SQLAlchemy ORM models, connection, and query repositories.
    redis: Async Redis cache operations.
    neo4j: Graph database access (placeholder).
    minio: MinIO / S3-compatible object storage (placeholder).
"""
```

**Step 2: Commit**

```bash
git add backend/src/dao/__init__.py
git commit -m "refactor: update dao root __init__.py with sub-package documentation"
```

---

### Task 4: Update Backend Source Imports to Canonical Paths

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/src/api/deps.py`
- Modify: `backend/src/agents/state_persistence.py`
- Modify: `backend/src/agents/state_persistence_factory.py`
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/chat_service.py`
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/source_linker.py`
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/feedback_service.py`
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/delta_audit_service.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/repositories.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/api.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/similarity_match/indexer.py`
- Modify: `backend/src/core/standardize_entities_and_align_knowledge/similarity_match/repositories.py`
- Modify: `backend/src/api/v1/delta_audit.py`

**Step 1: Update `connection` imports (6 files)**

Use `sed` for batch replacement:

```bash
cd backend
# connection imports
rg -l 'from src\.dao\.connection' --type py -g '!tests/' | \
  xargs sed -i 's|from src\.dao\.connection|from src.dao.postgresql.connection|g'
```

**Step 2: Update `models` imports (9 files)**

```bash
rg -l 'from src\.dao\.models' --type py -g '!tests/' | \
  xargs sed -i 's|from src\.dao\.models|from src.dao.postgresql.models|g'
```

**Step 3: Update `vector_repo` imports (2 files)**

```bash
rg -l 'from src\.dao\.vector_repo' --type py -g '!tests/' | \
  xargs sed -i 's|from src\.dao\.vector_repo|from src.dao.postgresql.vector_repo|g'
```

**Step 4: Verify no stale imports remain in source files**

```bash
rg 'from src\.dao\.(connection|contracts|models|vector_repo|search_index_repo|cache_repo)' \
  --type py -g '!tests/' -g '!dao/'
```

Expected: no results (all imports updated to new paths).

**Step 5: Commit**

```bash
git add backend/app/ backend/src/
git commit -m "refactor: update backend source imports to dao.postgresql/redis paths"
```

---

### Task 5: Update Alembic Migration `env.py`

**Files:**
- Modify: `database/migrations/env.py`

**Step 1: Update the Base import**

Change line 31:
```python
# Before:
from src.dao.models import Base  # noqa: E402
# After:
from src.dao.postgresql.models import Base  # noqa: E402
```

**Step 2: Verify no other stale imports in `database/`**

```bash
rg 'from src\.dao\.' database/
```

Expected: only `from src.dao.postgresql.models import Base`.

**Step 3: Commit**

```bash
git add database/migrations/env.py
git commit -m "refactor: update alembic env.py to import Base from dao.postgresql.models"
```

---

### Task 6: Update Script Imports

**Files:**
- Modify: `backend/scripts/e2e_standardize_entities.py`
- Modify: `backend/scripts/e2e_full.py`
- Modify: `backend/scripts/e2e_visualize_feedback.py`
- Modify: `scripts/import_terminology.py`

**Step 1: Batch update all script imports**

```bash
# connection imports
rg -l 'from src\.dao\.connection' --type py scripts/ backend/scripts/ | \
  xargs sed -i 's|from src\.dao\.connection|from src.dao.postgresql.connection|g'

# models imports
rg -l 'from src\.dao\.models' --type py scripts/ backend/scripts/ | \
  xargs sed -i 's|from src\.dao\.models|from src.dao.postgresql.models|g'

# vector_repo imports
rg -l 'from src\.dao\.vector_repo' --type py scripts/ backend/scripts/ | \
  xargs sed -i 's|from src\.dao\.vector_repo|from src.dao.postgresql.vector_repo|g'
```

**Step 2: Verify**

```bash
rg 'from src\.dao\.(connection|models|vector_repo|cache_repo)' --type py scripts/ backend/scripts/
```

Expected: no results.

**Step 3: Commit**

```bash
git add scripts/ backend/scripts/
git commit -m "refactor: update script imports to dao.postgresql paths"
```

---

### Task 7: Update Test Imports and Reorganize Test Structure

**Files:**
- Create: `backend/tests/dao/postgresql/` directory
- Create: `backend/tests/dao/redis/` directory
- Move: test files into matching subdirectories
- Modify: all test import statements

**Step 1: Create test subdirectories**

```bash
mkdir -p backend/tests/dao/postgresql backend/tests/dao/redis
```

**Step 2: Move PostgreSQL test files**

```bash
cd backend/tests/dao
git mv test_connection.py postgresql/test_connection.py
git mv test_models.py postgresql/test_models.py
git mv test_vector_repo.py postgresql/test_vector_repo.py
git mv test_search_index_repo.py postgresql/test_search_index_repo.py
git mv test_alembic_migration.py postgresql/test_alembic_migration.py
git mv test_pgvector_migration.py postgresql/test_pgvector_migration.py
git mv test_type_contract_compliance.py postgresql/test_type_contract_compliance.py
```

**Step 3: Move Redis test files**

```bash
git mv test_cache_repo.py redis/test_cache_repo.py
```

**Step 4: Batch update all test imports**

```bash
cd backend
# All dao submodule imports → postgresql or redis
rg -l 'from src\.dao\.connection' tests/ | xargs sed -i 's|from src\.dao\.connection|from src.dao.postgresql.connection|g'
rg -l 'from src\.dao\.models' tests/ | xargs sed -i 's|from src\.dao\.models|from src.dao.postgresql.models|g'
rg -l 'from src\.dao\.vector_repo' tests/ | xargs sed -i 's|from src\.dao\.vector_repo|from src.dao.postgresql.vector_repo|g'
rg -l 'from src\.dao\.search_index_repo' tests/ | xargs sed -i 's|from src\.dao\.search_index_repo|from src.dao.postgresql.search_index_repo|g'
rg -l 'from src\.dao\.cache_repo' tests/ | xargs sed -i 's|from src\.dao\.cache_repo|from src.dao.redis.cache_repo|g'
```

**Step 5: Update string assertions in test_alembic_migration.py**

This file checks the import path as a string literal. Update:

```python
# Before:
assert "from src.dao.models import Base" in source
# After:
assert "from src.dao.postgresql.models import Base" in source
```

**Step 6: Verify no stale test imports**

```bash
rg 'from src\.dao\.(connection|contracts|models|vector_repo|search_index_repo|cache_repo)' tests/
```

Expected: no results.

**Step 7: Commit**

```bash
git add backend/tests/dao/
git commit -m "refactor: reorganize dao tests into postgresql/redis subdirectories"
```

---

### Task 8: Update conftest.py and Shared Test Fixtures

**Files:**
- Modify: `backend/tests/conftest.py`

**Step 1: Update Base import in conftest**

```python
# Before:
from src.dao.models import Base
# After:
from src.dao.postgresql.models import Base
```

**Step 2: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "refactor: update conftest.py import for dao restructure"
```

---

### Task 9: Run Lint and Tests

**Step 1: Run Ruff lint**

```bash
cd backend
uv run --extra dev ruff check src/dao tests/dao tests/conftest.py database/migrations/env.py
```

Expected: no errors.

**Step 2: Run all dao tests**

```bash
uv run pytest tests/dao -v
```

Expected: all tests pass.

**Step 3: Run broader test suite to catch import regressions**

```bash
uv run pytest tests/ -v --timeout=60
```

Expected: all tests pass (no import errors).

**Step 4: Run import smoke test**

```bash
uv run python -c "
from src.dao.postgresql.connection import build_async_engine, async_session_factory, get_async_session
from src.dao.postgresql.models import Base, SourceDocument, ProcessingRun
from src.dao.postgresql.vector_repo import VectorRepository
from src.dao.postgresql.search_index_repo import SearchIndexRepository
from src.dao.redis.cache_repo import CacheRepository
import src.dao.neo4j
import src.dao.minio
print('All imports resolved successfully')
"
```

Expected: `All imports resolved successfully`

**Step 5: Commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: resolve lint/test issues from dao restructure"
```

---

### Task 10: Update README and Progress

**Files:**
- Modify: `backend/src/dao/README.md`
- Modify: `progress.txt`

**Step 1: Update README.md**

Update the architecture diagram, import paths examples, and extension guide to reflect new `dao/postgresql/`, `dao/redis/`, `dao/neo4j/`, `dao/minio/` structure. Key changes:

- Architecture diagram: show sub-packages including `neo4j/` and `minio/` placeholders
- Quick Start code: update import paths
- Extension Guide: reference `dao/postgresql/models.py` instead of `dao/models.py`
- Add a "Sub-package Organization" section explaining the structure and placeholder convention

**Step 2: Update progress.txt**

```
[2026-05-29] DAO 子目录重构：PostgreSQL/Redis/Neo4j/MinIO 子模块分离 [完成]
```

**Step 3: Commit**

```bash
git add backend/src/dao/README.md progress.txt
git commit -m "docs: update dao README and progress for submodule restructure"
```
