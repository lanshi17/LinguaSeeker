# Backend Config Single Source Implementation Plan

**Status:** completed
**Created:** 2026-06-06
**Completed:** 2026-06-06
**PR:** TBD

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `backend/config/` the only backend configuration data source while keeping Python code as typed loading and access layers.

**Architecture:** Add a shared backend config loader utility under `backend/src/core/` that reads only `backend/config/defaults`, `backend/config/environments`, and `backend/config/vault`, then flattens values into environment variables without overriding explicit environment variables. The main backend settings and the model-server settings both call this shared loader, so model-server no longer carries a copied YAML merge implementation. Documentation and tests should stop describing any legacy flat runtime file as a supported configuration source.

**Tech Stack:** Python 3.12, Pydantic Settings, PyYAML, pytest, Ruff.

---

### Task 1: Shared Loader Tests

**Files:**
- Create: `backend/tests/core/test_config_loader.py`
- Modify: `backend/services/model-server/tests/test_model_server_config.py`

**Step 1: Write the failing tests**

Create tests that prove:
- `load_backend_config_into_env()` loads layered YAML from `backend/config` style directories.
- A legacy flat runtime file is ignored even if present beside `config/`.
- Existing environment variables keep highest precedence.
- `app.config` reuses the shared loader function instead of defining its own YAML loader.

**Step 2: Run tests to verify they fail**

Run:

```bash
cd backend
uv run pytest tests/core/test_config_loader.py services/model-server/tests/test_model_server_config.py::test_model_server_reuses_backend_config_loader -q
```

Expected: FAIL because the shared loader module/function does not exist and model-server does not expose the shared loader.

### Task 2: Shared Loader Implementation

**Files:**
- Create: `backend/src/core/config_loader.py`
- Modify: `backend/src/core/config.py`
- Modify: `backend/services/model-server/app/config.py`

**Step 1: Implement minimal shared loader**

Create `src.core.config_loader.load_backend_config_into_env(backend_root: Path, environ: MutableMapping[str, str] | None = None) -> None`.

Implementation rules:
- Read only `backend_root/config/defaults/main.yaml`.
- Overlay `backend_root/config/environments/<ENVIRONMENT>.yaml`.
- Overlay `backend_root/config/vault/<ENVIRONMENT>.yaml`.
- Flatten nested YAML keys to uppercase underscore environment names.
- Do not overwrite keys already in `environ`.
- Do not read or fall back to a legacy flat runtime file.

**Step 2: Wire backend settings**

Replace the local loader functions in `backend/src/core/config.py` with:

```python
from src.core.config_loader import load_backend_config_into_env

load_backend_config_into_env(BACKEND_ROOT)
```

**Step 3: Wire model-server settings**

In `backend/services/model-server/app/config.py`, add the backend root to `sys.path`, import `load_backend_config_into_env`, and call it with `_BACKEND_ROOT`. Remove the duplicated YAML merge and flatten helpers.

**Step 4: Run tests to verify they pass**

Run:

```bash
cd backend
uv run pytest tests/core/test_config_loader.py services/model-server/tests/test_model_server_config.py -q
```

Expected: PASS.

### Task 3: Documentation Cleanup

**Files:**
- Modify: `AGENTS.md`
- Modify: `backend/config/README.md`
- Modify: `backend/config/templates/config.yaml.j2`
- Modify: `backend/scripts/render_config.py`
- Modify: `backend/tests/core/test_config.py`
- Modify: `backend/services/model-server/tests/test_model_server_config.py`
- Delete: `backend/src/core/config.py.jinja`

**Step 1: Remove stale configuration-source wording**

Update docs and comments so they say:
- Configuration data lives in `backend/config/`.
- Secret values live in `backend/config/vault/<env>.yaml` or environment variables.
- Rendered config is optional debugging output only and must not be treated as a runtime source.

**Step 2: Remove obsolete template**

Delete `backend/src/core/config.py.jinja`; it points to the removed legacy source.

**Step 3: Run text audit**

Run:

```bash
rg -n "legacy flat runtime file|legacy runtime config" AGENTS.md backend docs
```

Expected: no current-source references claiming runtime support.

### Task 4: Verification and Project Records

**Files:**
- Modify: `progress.txt`
- Modify: `docs/README.md` if doc organization changes it
- Move: this plan to `docs/archive/plans/` after implementation is complete

**Step 1: Run focused verification**

Run:

```bash
cd backend
uv run pytest tests/core/test_config_loader.py tests/core/test_config.py services/model-server/tests/test_model_server_config.py -q
uv run ruff check src/core/config.py src/core/config_loader.py services/model-server/app/config.py tests/core/test_config_loader.py services/model-server/tests/test_model_server_config.py
```

**Step 2: Run document organization**

Apply `doc-organize` for the docs touched in this task, archive the completed plan, and update the docs index if needed.

**Step 3: Record progress**

Append:

```text
[2026-06-06] Unified backend configuration source under backend/config [done]
```

to root `progress.txt`.
