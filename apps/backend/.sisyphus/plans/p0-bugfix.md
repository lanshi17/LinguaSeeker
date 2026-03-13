# P0 Bug Fix Plan — ACMG Backend

**Scope**: 4 critical bugs with runtime impact  
**Approach**: Minimal, surgical fixes only — no architecture refactoring  
**Verification**: Each fix verified via lsp_diagnostics + existing tests  

---

## Phase 1: Configuration Bugs (Independent — Parallelizable)

### Task 1.1: Fix config.py duplicate embedding field declarations
- **File**: `src/config.py`
- **Bug**: `embedding_provider`, `embedding_base_url`, `embedding_api_key`, `embedding_model`, `embedding_dimension`, `embedding_batch_size` are declared TWICE — first at lines ~78-84 (no defaults), then at lines ~137-143 (with defaults). Pydantic silently uses the second declaration, making the first group dead code. This is confusing and could cause subtle bugs if someone modifies the first group thinking it's the active one.
- **Fix**: 
  - [x] Remove the first duplicate block (lines ~78-84 and its `# Embedding配置` section header)
  - [x] Keep the second block (lines ~137-143 with defaults) as the single source of truth
  - [x] Also fix `app_version` from `'2.0.0'` to `'2.1.0'` to match `pyproject.toml`
- **Verify**: `python -c "from src.config import settings; print(settings.embedding_provider, settings.app_version)"` runs without error
- **Parallelizable**: Yes (independent file)

### Task 1.2: Fix main.py CORS origins parsing  
- **File**: `main.py`
- **Bug**: `cors_origins` is a `str` field with default value `'["http://localhost:3000", "http://localhost:8080"]'` (JSON array as string). But `_parse_cors_origins()` on line ~96 splits by comma and strips whitespace. This produces broken values like `'["http://localhost:3000"'` with brackets and quotes included, causing CORS to silently fail.
- **Fix**:
  - [x] Modify `_parse_cors_origins()` to first try `json.loads(cfg.cors_origins)` for JSON array format
  - [x] Fall back to comma-split only if JSON parsing fails (for backward compat with plain CSV format)
  - [x] Strip any surrounding whitespace/quotes from each origin in both paths
  - [x] Remove unused `import asyncio` (line 7) while editing
- **Verify**: `python -c "from main import app; print('CORS OK')"` starts without error; check middleware origins are correct
- **Parallelizable**: Yes (independent file)

---

## Phase 2: Resource Safety (Independent — Parallelizable with Phase 1)

### Task 2.1: Fix core.py temp file leak in upload_pdf()
- **File**: `src/api/routes/core.py`
- **Bug**: At line ~348, `NamedTemporaryFile(delete=False)` creates a temp file. If the Celery `apply_async()` call on line ~352 raises an exception, the temp file path is never cleaned up — the `except` block raises HTTPException without removing the file. Note: on SUCCESS, the file must NOT be deleted because the Celery worker needs it.
- **Fix**:
  - [x] In the `except Exception` block (around line ~358), add `os.unlink(tmp_file_path)` BEFORE raising HTTPException
  - [x] Ensure `import os` is present at the top of the file (it likely already is)
  - [x] Verify the fix doesn't affect the success path (Celery worker still gets the file)
- **Verify**: Read the modified code to confirm: (1) success path leaves file intact, (2) error path cleans up
- **Parallelizable**: Yes (independent file)

### Task 2.2: Fix postgres.py sync blocking in async FastAPI
- **File**: `src/infrastructure/postgres.py` + callers in route handlers
- **Bug**: All 40+ PostgresClient methods use synchronous SQLAlchemy (`create_engine` + `sessionmaker` + sync `Session`). These are called from `async def` route handlers in FastAPI, which blocks the event loop. Under concurrent load, this causes request stacking and potential timeouts.
- **Fix** (MINIMAL — full async migration belongs in architecture refactor):
  - [x] ~~Create async wrapper~~ → Analysis showed only 2 handlers (upload_pdf, create_task_request_by_upload) mix async+sync; cannot simply convert. Added TODO(P1) comments to both handlers for architecture refactor.
  - [x] ~~Apply wrapper to route handlers~~ → Deferred to architecture refactor (mixed async/sync patterns require deeper changes)
  - [x] ~~Change handlers to def~~ → Not possible: both affected handlers use `await` for MinIO calls
  - [x] Document with a `# TODO: migrate to AsyncSession in architecture refactor` comment
- **Verify**: `python -c "from src.api.routes.core import router; print('routes OK')"` loads without error; `ruff check src/api/routes/` passes
- **Parallelizable**: Yes (but verify after all other fixes applied)

---

## Phase 3: Integration Verification

### Task 3.1: Full integration check
- [x] Run `uv run ruff check main.py src/config.py src/api/routes/core.py src/api/routes/task.py` — zero errors (scoped to P0-touched files; repo-wide `ruff check src/` still has baseline findings)
- [x] Run `python -c "from main import app"` — app loads successfully
- [x] Run existing tests if any cover modified files: `pytest tests/ -x --timeout=30 -q` (skip if no relevant tests)
- [x] Verify no import errors across the codebase

---

## Dependency Graph

```
Task 1.1 (config.py)     ──┐
Task 1.2 (main.py)        ──┤── All independent ──→ Task 3.1 (verification)
Task 2.1 (core.py)        ──┤
Task 2.2 (postgres.py)    ──┘
```

**All 4 fix tasks are fully independent and can run in parallel.**
Task 3.1 depends on all fixes being complete.

---

## Files Modified

| Task | Files |
|------|-------|
| 1.1 | `src/config.py` |
| 1.2 | `main.py` |
| 2.1 | `src/api/routes/core.py` |
| 2.2 | `src/infrastructure/postgres.py` OR `src/api/routes/*.py` |
| 3.1 | (verification only) |
