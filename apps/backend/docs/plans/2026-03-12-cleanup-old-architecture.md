# Cleanup Old Architecture — Consolidate Shim Layers (方案 B)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move real code from old naming (`src/database/`, `src/presentation/`, `src/service/`) into new naming (`src/infrastructure/`, `src/api/`, `src/services/`), remove shim layers and migration tests.

**Architecture:** The project has a dual-naming problem. Real code lives in `src/database/`, `src/presentation/`, `src/service/` while shim layers in `src/infrastructure/`, `src/api/`, `src/services/` just re-export from the real locations. We consolidate by moving real code to the new names, updating all imports, and deleting old directories + migration tests.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Pydantic, pytest

---

## Migration Order (CRITICAL)

Execute tasks in this exact order — each migration is independent at the module level but we verify after each one:

1. **Task 1**: Migrate `src/database/` → `src/infrastructure/` (largest, most references)
2. **Task 2**: Migrate `src/service/` → `src/services/` (business logic layer)
3. **Task 3**: Migrate `src/presentation/` → `src/api/` (API routes layer)
4. **Task 4**: Delete shim migration tests
5. **Task 5**: Final verification — all tests pass, no stale imports

---

### Task 1: Migrate `src/database/` → `src/infrastructure/`

**Summary:** Move the real client code from `src/database/` into `src/infrastructure/`, update ALL imports project-wide.

**Current state:**
- `src/database/` has the real code: `redis_client.py`, `minio_client.py`, `postgre_client.py`, `neo4j_client.py`, `qdrant_client.py`, `dtos.py`, `enum.py`, `models.py`
- `src/infrastructure/` has shims: `minio.py`, `postgres.py`, `redis.py`, `neo4j.py`, `qdrant.py` — each just re-exports from `src.database.*`
- `src/infrastructure/__init__.py` re-exports all client classes

**Step 1: Replace each shim file with the real code**

For each pair:
- `src/infrastructure/minio.py` ← content of `src/database/minio_client.py`
- `src/infrastructure/postgres.py` ← content of `src/database/postgre_client.py`
- `src/infrastructure/redis.py` ← content of `src/database/redis_client.py`
- `src/infrastructure/neo4j.py` ← content of `src/database/neo4j_client.py`
- `src/infrastructure/qdrant.py` ← content of `src/database/qdrant_client.py`

Also move supporting files:
- `src/database/dtos.py` → `src/infrastructure/dtos.py`
- `src/database/enum.py` → `src/infrastructure/enum.py`
- `src/database/models.py` → `src/infrastructure/models.py`

**Step 2: Fix internal cross-references within moved files**

The moved files import from each other using `src.database.*` paths. Update these:
- `src.database.enum` → `src.infrastructure.enum`
- `src.database.models` → `src.infrastructure.models`
- `src.database.dtos` → `src.infrastructure.dtos`
- `src.database.minio_client` → `src.infrastructure.minio`
- `src.database.postgre_client` → `src.infrastructure.postgres`
- `src.database.neo4j_client` → `src.infrastructure.neo4j`
- `src.database.qdrant_client` → `src.infrastructure.qdrant`
- `src.database.redis_client` → `src.infrastructure.redis`

**Step 3: Update `src/infrastructure/__init__.py`**

Update to import from local files (e.g., `from .minio import MinIOClient`) instead of from `src.database.*`.

**Step 4: Update all external imports from `src.database.*`**

Files that import directly from `src.database` (must change to `src.infrastructure`):

| File | Old Import | New Import |
|---|---|---|
| `src/domain/graph/association_service.py` | `src.database.neo4j_client`, `src.database.postgre_client` | `src.infrastructure.neo4j`, `src.infrastructure.postgres` |
| `src/domain/graph/sync.py` | `src.database.neo4j_client`, `src.database.postgre_client` | same |
| `src/domain/graph/search.py` | `src.database.neo4j_client`, `src.database.postgre_client` | same |
| `src/domain/evidence/aggregator.py` | `src.database.postgre_client` | `src.infrastructure.postgres` |
| `src/domain/agent/rag.py` | `src.database.qdrant_client` | `src.infrastructure.qdrant` |
| `src/domain/variant/service.py` | `src.database.postgre_client`, `src.database.models` | `src.infrastructure.postgres`, `src.infrastructure.models` |
| `src/agents/reasoning/node.py` | `src.database.neo4j_client` | `src.infrastructure.neo4j` |
| `src/presentation/api.py` | `src.database.enum`, `src.database.models` | `src.infrastructure.enum`, `src.infrastructure.models` |
| `src/presentation/task_api.py` | `src.database.enum` | `src.infrastructure.enum` |
| `src/tools/db/qdrant_tool.py` | `src.database.qdrant_client` | `src.infrastructure.qdrant` |
| `src/tools/file/minio_tool.py` | `src.database.minio_client` | `src.infrastructure.minio` |
| `scripts/clean_redis_cache.py` | `src.database.redis_client` | `src.infrastructure.redis` |
| `scripts/cleanup_orphan_resources.py` | `src.database.*` | `src.infrastructure.*` |
| `scripts/reconcile_graph_sync.py` | `src.database.*` | `src.infrastructure.*` |
| `scripts/seed_knowledge_base.py` | `src.database.*` | `src.infrastructure.*` |
| `alembic/env.py` | `src.database.models`, `src.database.postgre_client` | `src.infrastructure.models`, `src.infrastructure.postgres` |
| ALL test files referencing `src.database.*` | Update to `src.infrastructure.*` |

**Step 5: Delete `src/database/` directory entirely**

```bash
rm -rf src/database/
```

**Step 6: Verify**

```bash
# Check no stale imports remain
grep -r "from src\.database" src/ scripts/ alembic/ tests/ --include="*.py"
grep -r "import src\.database" src/ scripts/ alembic/ tests/ --include="*.py"
# Run tests
pytest tests/ -x --timeout=30 -q
```

---

### Task 2: Migrate `src/service/` → `src/services/`

**Summary:** Move real business logic from `src/service/` into `src/services/`, update all imports.

**Current state:**
- `src/service/` has real code: `tasks.py` (Celery tasks), `dtos.py` (Pydantic models), `enum.py` (status enums)
- `src/services/` has shims: `task_manager.py` (re-exports from `src.service.tasks`), `report_generator.py` (re-exports from `src.domain.*`)

**Step 1: Move real files into `src/services/`**

- Move `src/service/tasks.py` → `src/services/tasks.py`
- Move `src/service/dtos.py` → `src/services/dtos.py`
- Move `src/service/enum.py` → `src/services/enum.py`

**Step 2: Delete the old shim `src/services/task_manager.py`**

Its re-exports are no longer needed; callers will import directly from `src.services.tasks`.

**Step 3: Keep `src/services/report_generator.py` as-is** (it re-exports from `src.domain.*`, not from `src.service`, so it's a convenience module, not a shim)

**Step 4: Fix internal cross-references in moved files**

- In `src/services/tasks.py`: `from src.service.enum import` → `from src.services.enum import`
- In `src/services/dtos.py`: `from src.service.enum import` → `from src.services.enum import`

**Step 5: Update all external imports**

Files that import from `src.service.*` (must change to `src.services.*`):

| File | Old Import | New Import |
|---|---|---|
| `src/presentation/task_api.py` | `src.service.dtos`, `src.service.enum` | `src.services.dtos`, `src.services.enum` |
| `src/api/routes/stream.py` | `src.service.enum` | `src.services.enum` |
| `src/agents/acquisition/node.py` | `src.service.enum` | `src.services.enum` |
| `src/agents/extraction/validator_tool.py` | `src.service.tasks` | `src.services.tasks` |
| `src/agents/parsing/node.py` | `src.service.enum` | `src.services.enum` |
| `src/celery_app.py` | `src.services.task_manager` | `src.services.tasks` (direct import) |
| `src/presentation/api.py` | `src.services.task_manager` | `src.services.tasks` |
| `src/presentation/task_api.py` | `src.services.task_manager` | `src.services.tasks` |
| ALL test files referencing `src.service.*` | Update to `src.services.*` |

**Step 6: Update `src/services/__init__.py`**

Import from local files instead of the old shim path.

**Step 7: Delete `src/service/` directory entirely**

```bash
rm -rf src/service/
```

**Step 8: Verify**

```bash
grep -r "from src\.service\b" src/ tests/ --include="*.py"
grep -r "import src\.service\b" src/ tests/ --include="*.py"
pytest tests/ -x --timeout=30 -q
```

---

### Task 3: Migrate `src/presentation/` → `src/api/`

**Summary:** Move real API route code from `src/presentation/` into `src/api/`, update all imports.

**Current state:**
- `src/presentation/` has real code: `api.py`, `task_api.py`, `graph_api.py`, `error_contract.py`
- `src/api/routes/` has shims: `core.py`, `task.py`, `evidence.py` (each re-exports router from presentation)
- `src/api/dependencies.py` is a shim re-exporting from `src.presentation.error_contract`
- `src/api/routes/stream.py` has REAL WebSocket code + imports from presentation

**Step 1: Replace shim files with real code**

- `src/api/routes/core.py` ← content of `src/presentation/api.py`
- `src/api/routes/task.py` ← content of `src/presentation/task_api.py`
- `src/api/routes/evidence.py` ← content of `src/presentation/graph_api.py`
- `src/api/dependencies.py` ← content of `src/presentation/error_contract.py`

**Step 2: Fix circular reference**

`src/presentation/api.py` and `src/presentation/task_api.py` import from `src.api.dependencies`. After inlining, these become `src/api/routes/core.py` and `src/api/routes/task.py` importing from `src.api.dependencies` — which is now the REAL code. No circular issue.

**Step 3: Fix imports in `src/api/routes/stream.py`**

Update from:
```python
from src.presentation.task_api import get_task_request_status, get_task_status
```
to:
```python
from src.api.routes.task import get_task_request_status, get_task_status
```

Also update `src.service.enum` → `src.services.enum` (if not already done in Task 2).

**Step 4: Fix imports within moved files**

The moved files reference `src.presentation.*` internally — update to `src.api.*`.

**Step 5: Update all external imports from `src.presentation.*`**

| File | Old Import | New Import |
|---|---|---|
| `tests/integration/test_graph_api.py` | `src.presentation.graph_api` | `src.api.routes.evidence` |
| `tests/integration/test_error_contract.py` | `src.presentation.error_contract` | `src.api.dependencies` |
| `tests/integration/test_task_api.py` | `src.presentation.task_api` | `src.api.routes.task` |
| `tests/unit/test_logging_smoke.py` | `src.presentation.error_contract` | `src.api.dependencies` |
| `tests/unit/test_error_mapping.py` | `src.presentation.error_contract` | `src.api.dependencies` |
| Any other test files | Update accordingly |

**Step 6: Delete `src/presentation/` directory entirely**

```bash
rm -rf src/presentation/
```

**Step 7: Verify**

```bash
grep -r "from src\.presentation" src/ tests/ --include="*.py"
grep -r "import src\.presentation" src/ tests/ --include="*.py"
pytest tests/ -x --timeout=30 -q
```

---

### Task 4: Delete Shim Migration Tests

**Files to delete:**
```bash
rm tests/test_domain_shim_adoption.py
rm tests/test_health_shim_adoption.py
rm tests/test_internal_shim_adoption.py
rm tests/test_tasks_shim_adoption.py
rm tests/test_namespace_compatibility.py
rm tests/test_scaffolding_modules.py
```

**Keep:** `tests/test_feature_flags.py` (tests active config behavior, NOT shim)

---

### Task 5: Final Verification

**Step 1: Check for ANY remaining stale imports**

```bash
grep -r "from src\.database" . --include="*.py" --exclude-dir=.git
grep -r "from src\.service\b" . --include="*.py" --exclude-dir=.git
grep -r "from src\.presentation" . --include="*.py" --exclude-dir=.git
```

All should return empty.

**Step 2: Run full test suite**

```bash
pytest tests/ -v --timeout=30
```

**Step 3: Check LSP diagnostics for import errors**

Run lsp_diagnostics on all modified files.

**Step 4: Verify app starts**

```bash
python -c "from main import app; print('OK')"
```
