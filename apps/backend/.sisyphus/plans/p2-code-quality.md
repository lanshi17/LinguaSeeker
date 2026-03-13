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
  - [ ] Move files out of `tests/` that are not tests (md/json/scripts) into `docs/` or `tools/` (keep repo conventions).
  - [ ] Remove duplicate venv dirs from version control if tracked.
  - [ ] Decide whether `tests/pyproject.toml` is needed; consolidate to root tooling if possible.
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
  - [ ] Replace `**fields: Any` with allowed-key validation + `Unpack[TypedDict]` where feasible (Python>=3.11).
  - [ ] Reduce `cast(T, cast(object, value))` by typing at boundary functions.
  - [ ] Do not attempt to deeply type raw LLM JSON outputs; validate/normalize at boundaries.
- **Verify**:
  - basedpyright shows reduction in Any-related warnings for touched modules.
  - Unit tests cover updated validation paths.

---

## Final Wave (Gates)

### F1: Typecheck gate
- [ ] `basedpyright` (or `pyright`) passes with no NEW errors

### F2: Lint gate
- [ ] `ruff check src/` passes (or no new violations)

### F3: Test gate
- [ ] `pytest -q` passes

### F4: Smoke import gate
- [ ] `python -c "import src.config; import main"` succeeds
