# Log Analysis Fixes — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the top 7 most frequent errors and warnings found in production logs (2026-06-01 ~ 2026-06-12, ~11,000 error/warning lines).

**Architecture:** Surgical fixes to 6 files. Each task is independently testable and deployable. Ordered by dependency: DB migration first (unblocks startup), then startup fixes, then runtime fixes.

**Tech Stack:** Python 3.12, SQLAlchemy async, Alembic, Pydantic, FastAPI, loguru

---

## Summary of Issues

| # | Issue | Frequency | Severity | Root Cause |
|---|---|---|---|---|
| 1 | Orphan recovery fails: `source_key` column missing | Every startup | P0 | Migration `pipeline_run_leases_20260611` not applied |
| 2 | Redis connection refused | Every startup | P0 | Redis not running; startup logs spam |
| 3 | Connection pool leak in `_try_startup_lock` | Intermittent | P1 | `raw_conn` not closed on exception path |
| 4 | `context_type` Literal rejects `results`/`discussion`/`methods`/`background` | ~37 occurrences | P1 | Enum missing common academic section types |
| 5 | `OPENAI_API_KEY` missing / LLM 404 | Multiple | P1 | Config wiring gap or wrong endpoint |
| 6 | LLM formatter receives HTML instead of markdown | ~20 occurrences | P2 | No input validation in formatter |
| 7 | Phase 2 file-not-found after Phase 1 temp cleanup | ~10 occurrences | P2 | Temp file lifecycle race |

---

### Task 1: Apply Pending Database Migration

**Problem:** The migration `pipeline_run_leases_20260611` adds `source_key`, `owner_worker_id`, `heartbeat_at` columns to `pipeline_run_states`. It was never applied. Every startup crashes with `column pipeline_run_states.source_key does not exist`.

**Files:**
- Verify: `database/migrations/versions/2026-06-11_add_pipeline_run_leases.py`
- Verify: `backend/src/agents/state_persistence.py:189-229`
- Verify: `backend/src/dao/postgresql/models.py:670-678`

**Step 1: Check current migration status**

```bash
cd backend
uv run alembic -c ../database/alembic.ini current
```

Expected: shows a revision older than `pipeline_run_leases_20260611`.

**Step 2: Apply the migration**

```bash
uv run alembic -c ../database/alembic.ini upgrade head
```

Expected: `Running upgrade ... -> pipeline_run_leases_20260611`

**Step 3: Verify columns exist**

```bash
uv run python -c "
import asyncio
from sqlalchemy import text
from src.core.config import get_config
from sqlalchemy.ext.asyncio import create_async_engine

async def check():
    cfg = get_config()
    engine = create_async_engine(cfg.postgresql.url)
    async with engine.connect() as conn:
        result = await conn.execute(text(
            \"SELECT column_name FROM information_schema.columns \"
            \"WHERE table_name='pipeline_run_states' AND column_name IN ('source_key','owner_worker_id','heartbeat_at')\"
        ))
        rows = result.fetchall()
        print(f'Found columns: {[r[0] for r in rows]}')
        assert len(rows) == 3, f'Expected 3 columns, got {len(rows)}'
    await engine.dispose()

asyncio.run(check())
```

Expected: `Found columns: ['source_key', 'owner_worker_id', 'heartbeat_at']`

**Step 4: Commit**

```bash
git add database/migrations/versions/2026-06-11_add_pipeline_run_leases.py
git commit -m "chore: ensure pipeline_run_leases migration is applied"
```

---

### Task 2: Fix Connection Leak in `_try_startup_lock`

**Problem:** `backend/app/main.py:79-93` — if `exec_driver_sql()` or `fetchone()` raises after `raw_connection()` succeeds, the `except Exception` handler returns `True` without closing `raw_conn`. The leaked connection triggers SQLAlchemy's GC warning: "garbage collector is trying to clean up non-checked-in connection".

**Files:**
- Modify: `backend/app/main.py:79-93`
- Test: `backend/tests/test_startup_lock.py` (new)

**Step 1: Write the failing test**

```python
# backend/tests/test_startup_lock.py
"""Tests for _try_startup_lock connection lifecycle."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_startup_lock_closes_connection_on_sql_error():
    """raw_conn must be closed even when SQL execution fails."""
    from app.main import _try_startup_lock

    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.exec_driver_sql.side_effect = RuntimeError("SQL failed")
    mock_engine.raw_connection.return_value = mock_conn

    result = await _try_startup_lock(mock_engine)

    # Should return True (non-PostgreSQL fallback behavior)
    assert result is True
    # Connection MUST be closed on the error path
    mock_conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_startup_lock_closes_connection_when_not_acquired():
    """raw_conn must be closed when advisory lock is not acquired."""
    from app.main import _try_startup_lock

    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchone.return_value = (False,)
    mock_conn.exec_driver_sql.return_value = mock_result
    mock_engine.raw_connection.return_value = mock_conn

    result = await _try_startup_lock(mock_engine)

    assert result is False
    mock_conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_startup_lock_keeps_connection_when_acquired():
    """raw_conn must NOT be closed when advisory lock is acquired."""
    from app.main import _try_startup_lock

    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchone.return_value = (True,)
    mock_conn.exec_driver_sql.return_value = mock_result
    mock_engine.raw_connection.return_value = mock_conn

    result = await _try_startup_lock(mock_engine)

    assert result is True
    mock_conn.close.assert_not_awaited()
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/test_startup_lock.py::test_startup_lock_closes_connection_on_sql_error -v
```

Expected: FAIL — `mock_conn.close` was never called because the except handler returns without closing.

**Step 3: Fix the code**

In `backend/app/main.py:79-93`, replace:

```python
    try:
        raw_conn = await engine.raw_connection()
        result = await raw_conn.exec_driver_sql(
            "SELECT pg_try_advisory_lock(hashtext('cross_evidence_backend_startup'))"
        )
        row = result.fetchone()
        acquired = bool(row[0]) if row else False
        if acquired:
            _startup_lock_raw_conn = raw_conn
        else:
            await raw_conn.close()
        return acquired
    except Exception:
        # Non-PostgreSQL engines (SQLite in tests) don't have advisory locks
        return True
```

With:

```python
    try:
        raw_conn = await engine.raw_connection()
        try:
            result = await raw_conn.exec_driver_sql(
                "SELECT pg_try_advisory_lock(hashtext('cross_evidence_backend_startup'))"
            )
            row = result.fetchone()
            acquired = bool(row[0]) if row else False
        except Exception:
            # SQL failed — close the connection before re-raising
            await raw_conn.close()
            # Non-PostgreSQL engines (SQLite in tests) don't have advisory locks
            return True

        if acquired:
            _startup_lock_raw_conn = raw_conn
        else:
            await raw_conn.close()
        return acquired
    except Exception:
        return True
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_startup_lock.py -v
```

Expected: All 3 tests PASS.

**Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_startup_lock.py
git commit -m "fix: close raw_conn on SQL error in _try_startup_lock"
```

---

### Task 3: Make Redis Health Check Graceful

**Problem:** When Redis is not running, every startup logs `Redis health check failed: Error 111 connecting to localhost:6379` + `Startup connectivity check failed: redis`. This is noise — Redis is optional for many operations.

**Files:**
- Modify: `backend/src/utils/health.py:71-86`
- Modify: `backend/app/main.py:165-174`
- Test: `backend/tests/test_health.py` (new)

**Step 1: Write the failing test**

```python
# backend/tests/test_health.py
"""Tests for health check graceful degradation."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_redis_health_check_returns_false_on_connection_refused():
    """Redis check should return False, not raise."""
    from src.utils.health import _check_redis

    with patch("src.api.wiring.get_redis_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.ping.side_effect = ConnectionError("Error 111")
        mock_get.return_value = mock_client

        result = await _check_redis()

        assert result is False


@pytest.mark.asyncio
async def test_redis_health_check_skips_when_client_none():
    """Redis check should skip gracefully when client is None."""
    from src.utils.health import _check_redis

    with patch("src.api.wiring.get_redis_client", return_value=None):
        result = await _check_redis()
        assert result is False
```

**Step 2: Run test to verify current behavior**

```bash
cd backend
uv run pytest tests/test_health.py -v
```

Expected: PASS (existing code already returns False; this validates the behavior).

**Step 3: Downgrade startup log from WARNING to DEBUG for non-critical services**

In `backend/app/main.py`, find the health check section (around line 165-174). The startup currently logs every failed service as WARNING. Change Redis failures to DEBUG since it's non-blocking:

```python
# In the lifespan function, after check_all_connections() call:
# Find the section that logs failed services and adjust:
for svc, ok in results.items():
    if not ok:
        level = "debug" if svc == "redis" else "warning"
        getattr(logger, level)("Startup connectivity check failed: {}", svc)
```

**Step 4: Run tests**

```bash
uv run pytest tests/test_health.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/utils/health.py backend/app/main.py backend/tests/test_health.py
git commit -m "fix: downgrade Redis startup failure to debug level"
```

---

### Task 4: Extend `context_type` Literal to Accept Academic Section Types

**Problem:** `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py:115` — `context_type` is `Literal["text", "table", "figure", "supplementary", "caption"]`. OCR/MinerU returns `"results"`, `"discussion"`, `"methods"`, `"background"` — all rejected with Pydantic `literal_error`. ~37 occurrences.

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py:115`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py:782` (the `_map_block_type` helper)
- Test: `backend/tests/core/test_contracts.py` (new)

**Step 1: Write the failing test**

```python
# backend/tests/core/test_contracts.py
"""Tests for SourceLocation context_type validation."""

import pytest
from pydantic import ValidationError


def test_source_location_accepts_academic_section_types():
    """context_type must accept common academic paper section names."""
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import SourceLocation

    for section in ("results", "discussion", "methods", "background",
                    "introduction", "conclusion", "abstract"):
        loc = SourceLocation(
            context_type=section,
            context_ref="test",
            text_snippet="test snippet",
        )
        assert loc.context_type == section


def test_source_location_rejects_unknown_type():
    """context_type must reject truly unknown values."""
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import SourceLocation

    with pytest.raises(ValidationError):
        SourceLocation(
            context_type="nonexistent_type",
            context_ref="test",
            text_snippet="test snippet",
        )
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/core/test_contracts.py -v
```

Expected: FAIL — `Input should be 'text', 'table', 'figure', 'supplementary' or 'caption'`

**Step 3: Extend the Literal**

In `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py:115`, change:

```python
    context_type: Literal["text", "table", "figure", "supplementary", "caption"]
```

To:

```python
    context_type: Literal[
        "text", "table", "figure", "supplementary", "caption",
        "abstract", "introduction", "methods", "results", "discussion", "conclusion",
        "background",
    ]
```

**Step 4: Also update `_map_block_type` in core.py**

In `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py:782`, find the `_map_block_type` function. Ensure it maps unknown MinerU block types to `"text"` rather than passing through raw values:

```python
# If the function currently passes through raw MinerU types, add a fallback:
_KNOWN_CONTEXT_TYPES = frozenset({
    "text", "table", "figure", "supplementary", "caption",
    "abstract", "introduction", "methods", "results", "discussion",
    "conclusion", "background",
})

def _map_block_type(mineru_type: str) -> str:
    """Map MinerU block type to SourceLocation context_type."""
    mapping = {
        "chart": "figure",
        "image": "figure",
        "table": "table",
    }
    mapped = mapping.get(mineru_type, mineru_type)
    return mapped if mapped in _KNOWN_CONTEXT_TYPES else "text"
```

**Step 5: Run test to verify it passes**

```bash
uv run pytest tests/core/test_contracts.py -v
```

Expected: All PASS

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py \
       backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py \
       backend/tests/core/test_contracts.py
git commit -m "feat: extend context_type to accept academic section types"
```

---

### Task 5: Add HTML Detection in LLM Formatter

**Problem:** `_apply_llm_formatting()` in `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/format/formatter.py:240` receives HTML error pages from LLM API and tries to process them as markdown. Should detect HTML and fail fast with a clear message.

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/format/formatter.py:240-290`
- Test: `backend/tests/core/test_formatter.py` (new)

**Step 1: Write the failing test**

```python
# backend/tests/core/test_formatter.py
"""Tests for MarkdownFormatter HTML detection."""

import pytest


def test_apply_llm_formatting_detects_html_response():
    """Formatter must detect HTML in LLM output and skip formatting."""
    from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.formatter import MarkdownFormatter

    formatter = MarkdownFormatter()

    # Simulate LLM returning HTML error page
    html_response = "<html><head><title>404 Not Found</title></head><body><h1>Not Found</h1></body></html>"
    original = "Some original markdown text"

    # The method should return original text, not the HTML
    result = formatter._apply_llm_formatting(html_response, original)
    assert result == original
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/core/test_formatter.py::test_apply_llm_formatting_detects_html_response -v
```

Expected: FAIL — method doesn't exist or doesn't detect HTML.

**Step 3: Add HTML detection**

In `formatter.py`, add a helper and integrate it into `_apply_llm_formatting`:

```python
import re

_HTML_DETECT_RE = re.compile(r"^\s*<(!DOCTYPE|html|head|body|title)\b", re.IGNORECASE | re.DOTALL)

def _is_html(text: str) -> bool:
    """Return True if text looks like an HTML document (not markdown with inline HTML)."""
    return bool(_HTML_DETECT_RE.match(text[:500]))
```

In `_apply_llm_formatting`, add early return after receiving LLM output:

```python
    # After getting llm_output from LLM:
    if _is_html(llm_output):
        logger.warning("LLM format output is HTML (likely error page), keeping original")
        return original_text
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/core/test_formatter.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/format/formatter.py \
       backend/tests/core/test_formatter.py
git commit -m "fix: detect HTML responses in LLM formatter and fallback to original"
```

---

### Task 6: Verify LLM Config Wiring (No-Code Diagnostic)

**Problem:** Logs show `Missing credentials. Please pass an api_key` from OpenAI SDK and `404 Not Found` for `api.xiaomimimo.com`. This is a config issue, not a code bug.

**Files:**
- Verify: `backend/config/vault/dev.yaml` (or active env)
- Verify: `backend/src/core/config.py:86,326`
- Verify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/evidence_map.py:17-96`

**Step 1: Check active config**

```bash
cd backend
uv run python -c "
from src.core.config import get_config
cfg = get_config()
print(f'FAST_LLM base_url: {cfg.llm.base_url}')
print(f'FAST_LLM api_key set: {bool(cfg.llm.api_key)}')
print(f'FAST_LLM model: {cfg.llm.model}')
"
```

Expected: base_url, api_key, and model all populated.

**Step 2: If api_key is empty, check vault file**

```bash
cat backend/config/vault/dev.yaml | grep -A5 'fast_llm'
```

Expected: `api_key` field present and non-empty.

**Step 3: If 404 persists, test the endpoint directly**

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$(grep base_url backend/config/vault/dev.yaml | head -1 | awk '{print $2}')/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(grep api_key backend/config/vault/dev.yaml | head -1 | awk '{print $2}')" \
  -d '{"model":"test","messages":[{"role":"user","content":"hi"}]}'
```

Expected: 200 or 401 (not 404). If 404, the base_url is wrong.

**Step 4: Fix config if needed**

Edit `backend/config/vault/dev.yaml` to correct `fast_llm.base_url` and `fast_llm.api_key`.

**Step 5: Commit (only if config files changed)**

```bash
git add backend/config/vault/dev.yaml
git commit -m "fix: correct LLM endpoint and API key in dev config"
```

---

### Task 7: Add Graceful Fallback for Missing Phase 1 Files in Phase 2

**Problem:** Phase 2 retries after timeout, but Phase 1's temp files have been cleaned up. `FileNotFoundError` on `phase_1/metadata.json` or `phase_2/extraction_result.json`.

**Files:**
- Modify: `backend/src/agents/runner.py` or `backend/src/agents/phase_2_adapter.py` (retry logic)
- Modify: `backend/src/agents/concurrency.py:59` (retry error handler)
- Test: `backend/tests/agents/test_phase2_retry.py` (new)

**Step 1: Write the failing test**

```python
# backend/tests/agents/test_phase2_retry.py
"""Tests for Phase 2 retry with missing Phase 1 files."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_phase2_raises_permanent_error_on_missing_phase1_files():
    """Phase 2 should fail permanently (not retry) when Phase 1 files are missing."""
    from src.agents.concurrency import execute_with_retry

    call_count = 0

    async def failing_phase():
        nonlocal call_count
        call_count += 1
        raise FileNotFoundError("No such file or directory: '.../phase_1/metadata.json'")

    # Should NOT retry FileNotFoundError — it's permanent, not transient
    with pytest.raises(FileNotFoundError):
        await execute_with_retry(
            phase_name="phase_2",
            fn=failing_phase,
            max_retries=2,
        )

    # FileNotFoundError should not trigger retries
    assert call_count == 1
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/agents/test_phase2_retry.py -v
```

Expected: FAIL — `execute_with_retry` retries FileNotFoundError because it's a generic `Exception`.

**Step 3: Fix retry logic**

In `backend/src/agents/concurrency.py`, modify the retry handler to distinguish transient vs permanent errors:

```python
# Add near the top of the file:
_PERMANENT_ERRORS = (FileNotFoundError, PermissionError, IsADirectoryError)

# In execute_with_retry, change the except clause:
# FROM:
#     except Exception as exc:
# TO:
#     except _PERMANENT_ERRORS:
#         raise  # Don't retry permanent file-system errors
#     except Exception as exc:
#         # existing retry logic
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/agents/test_phase2_retry.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/agents/concurrency.py backend/tests/agents/test_phase2_retry.py
git commit -m "fix: don't retry FileNotFoundError in phase execution"
```

---

## Verification

After all tasks, run the full test suite:

```bash
cd backend
uv run pytest tests/ -v --timeout=60
```

Start the backend and verify startup is clean:

```bash
cd backend
uv run uvicorn app.main:app --reload 2>&1 | head -50
```

Expected: No `source_key does not exist` errors. Redis failure logged at DEBUG level (if Redis not running). No connection leak warnings.

---

## Post-Plan Cleanup

- Update `lesson.md` with root causes and fixes
- Update `progress.txt` with completion status
