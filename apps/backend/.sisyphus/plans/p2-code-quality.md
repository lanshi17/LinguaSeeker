# P2 Code Quality Plan — ACMG Backend

**Scope**: Code quality + runtime correctness improvements across type safety, exception handling, config management, and test organization.

**Important dependency**: User previously indicated “P1 完成之后执行 P2”（P1 to address async route handlers calling sync Postgres). This plan is written so tasks can be executed after P1, but most tasks are independent and can be run once environment/tooling is ready.

**Approach**: Runtime correctness/observability first (config + exceptions), then safety net (tests), then type hotspot reductions (not “remove all Any”).

**Verification baseline** (per task unless stated otherwise):
- `python -m py_compile <touched files>`
- `basedpyright` (or `pyright`) should not introduce NEW errors
- `pytest -q` (if runnable in repo environment)

---

## Phase 0: Tooling / Repo Hygiene (Enabler)

### Task 0.1: Define canonical verification commands for this repo
- **Goal**: Ensure we can run lint/typecheck/tests in this environment.
- **Files**: None (documentation in notepad)
- **Steps**:
  - [x] Identify package manager in use (uv/pip/poetry) and install dev deps.
  - [x] Confirm commands:
    - `ruff check src/`
    - `basedpyright` (or `pyright`)
    - `pytest -q`
- **Verify**: commands execute (even if they report findings).

---

## Phase 1: Config Management (Fail-fast + remove unsafe defaults)

### Task 1.1: Remove placeholder MinIO credential defaults + add startup validation
- **Files**:
  - Modify: `src/config.py`
  - Modify (or add): `main.py` startup validation hook (lifespan)
- **Requirements**:
  - [x] Replace `minio_access_key="your-minio-access-key"` / `minio_secret_key="your-minio-secret-key"` with safer defaults (empty / missing) and validate at startup.
  - [x] Validation error must be actionable (which var missing, where to set).
  - [x] Avoid leaking secrets in logs.
- **Verify**:
  - [x] `uv run python -m py_compile src/config.py main.py`
  - [x] `uv run pytest -q tests/test_minio_config_validation.py`
  - [x] `uv run basedpyright src/config.py` (no new errors)

### Task 1.2: Reduce duplicated LLM triplets via schema + resolver
- **Files**:
  - Modify: `src/config.py`
  - Create/Modify: `src/config_llm.py` (or similar)
  - Update call sites that read `*_api_key/base_url/model`
- **Requirements**:
  - [x] Keep existing env var names working.
  - [x] Provide single resolved config object per agent use.
  - [x] Document mapping.
- **Verify**:
  - Typecheck: fewer `type: ignore` around Settings
  - Tests: resolver returns expected values for representative env var sets.

---

## Phase 2: Exception Handling (API correctness + consistent error contract)

### Task 2.1: Route handlers: remove catch-log-swallow; use `ACMGException` hierarchy consistently
- **Files**:
  - Modify: `src/api/routes/core.py`, `src/api/routes/task.py`, `src/api/routes/evidence.py` (prioritize top offenders)
  - Reference: `src/utils/exceptions.py`
  - Reference: `src/api/dependencies.py` (error contract helpers)
- **Requirements**:
  - [x] Only catch exceptions you can handle; otherwise raise typed exceptions.
  - [x] Ensure FastAPI returns consistent error payload via existing exception handlers.
- **Verify**:
  - [x] Add/extend tests for at least one endpoint per file verifying status code + error_code.

### Task 2.2: Pipeline exceptions: make task_manager policy explicit and structured
- **Files**:
  - Modify: `src/services/task_manager.py`
- **Requirements**:
  - [x] Replace broad catch-and-continue with explicit per-step outcomes.
  - [x] Accumulate errors; return structured result so API can surface failures.
- **Verify**:
  - [x] Unit tests on task_manager step behavior (`uv run pytest -q tests/unit/test_tasks.py`).

---

## Phase 3: Tests Organization (Reduce chaos; make refactors safe)

### Task 3.1: Clean up tests/ directory: move non-test artifacts out; single toolchain
- **Steps**:
  - [x] Unblock pytest collection by ignoring non-test artifacts (at least `tests/src/` and `tests/test_qdrant_fix.py`) via root `pyproject.toml` `[tool.pytest.ini_options]`.
  - [x] Fix test imports for config dataclasses in failing tests (`config.*` / `src.config.*` -> `configs.*`) so `pytest` collection can proceed.
  - [x] Forward-fix committed secrets in `database/podman-compose.yml` (use `${REDIS_PASSWORD}` / `${NEO4J_PASSWORD}`; do not commit plaintext).
  - [x] Forward-fix committed secrets in `database/scripts/setup/verify_services.sh` (use `${REDIS_PASSWORD}` / `${NEO4J_PASSWORD}`; **do not echo secret values**).
  - [x] Move files out of `tests/` that are not tests (md/json/scripts) into `docs/` or `tools/` (keep repo conventions).
    - [x] `tests/TEST_PIPELINE_README.md` -> `docs/test-artifacts/TEST_PIPELINE_README.md` (git mv)
    - [x] `tests/README.md` -> `docs/test-artifacts/tests-README.md` (git mv)
    - [x] `tests/main.py` -> `tools/qdrant/test_pipeline_main.py` (git mv)
    - [x] `tests/docker-compose.yml` -> `tools/qdrant/docker-compose.yml` (git mv)
    - [x] `tests/.python-version` -> `.python-version` (git mv)
  - [x] Remove duplicate venv dirs from version control if tracked.
  - [x] Decide whether `tests/pyproject.toml` is needed; consolidate to root tooling if possible. (Decision: not needed; keep single root toolchain.)
- **Verify**:
  - `pytest -q` still discovers and runs unit/integration suites.

---

## Phase 4: Type Safety Hotspots (Targeted reduction)

### Task 4.1: Hotspot pass: reduce `Any` and double-casts in top files
- **Files**:
  - Modify: `src/services/task_manager.py`
  - Modify: `src/api/routes/task.py`
  - Modify: `src/infrastructure/postgres.py`
  - Optionally: `src/infrastructure/neo4j.py`, `src/domain/graph/sync.py`
- **Requirements**:
  - [x] Replace high-risk dynamic update/write hotspots with guarded assignment paths in touched modules where feasible for this batch.
  - [x] Reduce `cast(T, cast(object, value))` by typing at boundary/helper functions in `src/api/routes/task.py`.
  - [x] Do not attempt to deeply type raw LLM JSON outputs; validate/normalize at boundaries.
- **Verify**:
  - [x] `uv run python -m py_compile src/services/task_manager.py src/api/routes/task.py src/infrastructure/postgres.py tests/unit/test_tasks.py tests/test_task_route_helpers.py tests/test_postgres_update_task_request.py tests/test_postgres_update_paper_task.py tests/test_postgres_update_evidence_record.py`
  - [x] `uv run pytest -q tests/unit/test_tasks.py tests/test_task_route_helpers.py tests/test_postgres_update_task_request.py tests/test_postgres_update_paper_task.py tests/test_postgres_update_evidence_record.py` (`43 passed`)
  - [x] `uv run basedpyright src/services/task_manager.py src/api/routes/task.py src/infrastructure/postgres.py` (`0 errors, 0 warnings, 0 notes`)
  - [x] `uv run ruff check src/services/task_manager.py src/api/routes/task.py src/infrastructure/postgres.py tests/unit/test_tasks.py tests/test_task_route_helpers.py tests/test_postgres_update_task_request.py tests/test_postgres_update_paper_task.py tests/test_postgres_update_evidence_record.py` (`All checks passed!`)

---

## Final Wave (Gates)

### F1: Typecheck gate
- [ ] `uv run basedpyright src/` passes with no NEW errors *(current blocker: large existing warning/error set across `src/`; see `/home/lanshi/.local/share/opencode/tool-output/tool_d0ec2c9be001WGyjqYfzLrdcnJ`)*

### F2: Lint gate
- [ ] `uv run ruff check src/ tests/` passes *(current blocker: Ruff is now runnable, but the full repo still has many lint violations; see `/home/lanshi/.local/share/opencode/tool-output/tool_d0fbe3dff0015J6xmoIF4YDrcz`)*

### F3: Test gate
- [ ] `uv run pytest -q` passes *(current blocker: import-time settings bootstrap is fixed, but full collection still stops on 3 remaining import errors: `tests/integration/test_cyberleninka.py` (`ModuleNotFoundError: cyberleninka`), `tests/integration/test_hans_publishers.py` (`cannot import name Subject from pubscholar_enums`), and `tests/integration/test_pubscholar_scraper.py` (`ModuleNotFoundError: locators`))*

### F4: Smoke import gate
- [x] `uv run python -c "import src.config; import main"` succeeds (`smoke-ok`)
