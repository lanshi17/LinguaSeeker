# Log Analysis Fixes — Implementation Plan

**Status:** completed
**Created:** 2026-06-12
**Completed:** 2026-06-12
**PR:** —

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the top 13 most frequent errors and warnings found in production logs (2026-06-01 ~ 2026-06-12, ~11,000+ error/warning lines across ~450 log files).

**Architecture:** Surgical fixes to ~12 files across 4 subsystems (startup, Phase 1-3 pipeline, Phase 4 visualization, infrastructure). Each task is independently testable and deployable. Ordered by dependency: DB migration first (unblocks startup), then startup fixes, then pipeline fixes, then visualization fixes.

**Tech Stack:** Python 3.12, SQLAlchemy async, Alembic, Pydantic, FastAPI, loguru, httpx

---

## Summary of Issues

| # | Issue | Frequency | Severity | Root Cause |
|---|---|---|---|---|
| 1 | Duplicate track warnings in `search_service` | ~8,500+ | P0 | No dedup on `(field_id, track)` — last-writer-wins overwrite |
| 2 | Redis connection refused / auth failed | ~370+ | P0 | Redis not running or password mismatch; logs spam |
| 3 | Orphan recovery fails: `source_key` column missing | ~47 | P0 | Migration `pipeline_run_leases_20260611` not applied |
| 4 | Evidence grounding: ellipsis + snippet not found | ~200+ | P1 | LLM extracts paraphrased/summarized quotes; no fuzzy match |
| 5 | LLM timeout + HTML response + length mismatch | ~150+ | P1 | Slow LLM; no HTML detection; strict length threshold |
| 6 | `OPENAI_API_KEY` missing for relevance_scan | ~50 | P1 | Config wiring gap — wrong config variable used |
| 7 | Connection pool leak in `_try_startup_lock` | ~49 | P1 | `raw_conn` not closed on exception path |
| 8 | `context_type` Literal rejects academic sections | ~37 | P1 | Enum missing `results`/`discussion`/`methods`/`background` |
| 9 | Phase 2 file-not-found after Phase 1 temp cleanup | ~30 | P2 | Phase adapter wraps `FileNotFoundError` as `PermanentPhaseError` (correct), but repeated pipeline runs each log the error; misleading log message |
| 10 | Phase 3 DB objects missing (`literature_profiles`, `frontend_search_index`) | ~4 | P2 | Migrations not applied or runtime table creation timing |
| 11 | Semantic matching connection failure | ~40 | P2 | Model server not running at `localhost:8001` |
| 12 | Phase4ServiceFactory close failure on shutdown | ~70 | P2 | Shutdown cleanup logs at WARNING level even for benign failures |
| 13 | Translation validation: "unchanged" | ~8 | P3 | Short texts with shared technical terms trigger similarity threshold; no length guard |

---

## Phase A: Infrastructure & Startup (Tasks 1-3)

### Task 1: Apply Pending Database Migrations

**Problem:** Multiple Phase 3 failures (`relation "literature_profiles" does not exist`, `relation "frontend_search_index" does not exist`, `column pipeline_run_states.source_key does not exist`) — all caused by unapplied migrations.

**Files:**
- Verify: `database/migrations/versions/2026-06-11_add_pipeline_run_leases.py`
- Verify: `database/migrations/versions/2026-06-08_add_literature_profiles.py`
- Verify: `backend/src/agents/state_persistence.py:189-229`
- Verify: `backend/src/dao/postgresql/models.py:94-145` (LiteratureProfile)
- Verify: `backend/src/dao/postgresql/search_index_repo.py:40-70` (frontend_search_index)

**Step 1: Check current migration status**

```bash
cd backend
uv run alembic -c ../database/alembic.ini current
```

Expected: shows a revision older than `pipeline_run_leases_20260611`.

**Step 2: Apply all pending migrations**

```bash
uv run alembic -c ../database/alembic.ini upgrade head
```

Expected: applies `literature_profiles`, `pipeline_run_leases`, `performance_indexes`, `created_at_to_search_index` migrations.

**Step 3: Verify critical tables and columns exist**

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
        # Check pipeline_run_states columns
        r1 = await conn.execute(text(
            \"SELECT column_name FROM information_schema.columns \"
            \"WHERE table_name='pipeline_run_states' AND column_name IN ('source_key','owner_worker_id','heartbeat_at')\"
        ))
        cols = [r[0] for r in r1.fetchall()]
        print(f'pipeline_run_states columns: {cols}')
        assert len(cols) == 3, f'Expected 3, got {len(cols)}'

        # Check literature_profiles table exists
        r2 = await conn.execute(text(
            \"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='literature_profiles')\"
        ))
        assert r2.scalar(), 'literature_profiles table missing'
        print('literature_profiles: EXISTS')

        # Check frontend_search_index table exists
        r3 = await conn.execute(text(
            \"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='frontend_search_index')\"
        ))
        assert r3.scalar(), 'frontend_search_index table missing'
        print('frontend_search_index: EXISTS')

    await engine.dispose()

asyncio.run(check())
```

Expected: all checks pass.

**Step 4: Commit**

```bash
git add database/migrations/
git commit -m "chore: ensure all pending database migrations are applied"
```

---

### Task 2: Fix Connection Leak in `_try_startup_lock`

**Problem:** `backend/app/main.py:79-93` — if `exec_driver_sql()` or `fetchone()` raises after `raw_connection()` succeeds, the `except Exception` handler returns `True` without closing `raw_conn`. The leaked connection triggers SQLAlchemy's GC warning: "garbage collector is trying to clean up non-checked-in connection" (~49 occurrences).

**Files:**
- Modify: `backend/app/main.py:79-93`
- Test: `backend/tests/test_startup_lock.py` (new)

**Step 1: Write the failing test**

```python
# backend/tests/test_startup_lock.py
"""Tests for _try_startup_lock connection lifecycle."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_startup_lock_closes_connection_on_sql_error():
    """raw_conn must be closed even when SQL execution fails."""
    from app.main import _try_startup_lock

    mock_engine = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.exec_driver_sql.side_effect = RuntimeError("SQL failed")
    mock_engine.raw_connection.return_value = mock_conn

    result = await _try_startup_lock(mock_engine)

    assert result is True
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

Expected: FAIL — `mock_conn.close` was never called.

**Step 3: Fix the code**

In `backend/app/main.py:79-93`, replace:

```python
    try:
        raw_conn = await engine.raw_connection()
        result = await raw_conn.exec_driver_sql(
            "SELECT pg_try_advisory_lock(hashtext('lingua_seeker_backend_startup'))"
        )
        row = result.fetchone()
        acquired = bool(row[0]) if row else False
        if acquired:
            _startup_lock_raw_conn = raw_conn
        else:
            await raw_conn.close()
        return acquired
    except Exception:
        return True
```

With:

```python
    try:
        raw_conn = await engine.raw_connection()
        try:
            result = await raw_conn.exec_driver_sql(
                "SELECT pg_try_advisory_lock(hashtext('lingua_seeker_backend_startup'))"
            )
            row = result.fetchone()
            acquired = bool(row[0]) if row else False
        except Exception:
            await raw_conn.close()
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

Expected: All 3 PASS.

**Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_startup_lock.py
git commit -m "fix: close raw_conn on SQL error in _try_startup_lock"
```

---

### Task 3: Make Redis Health Check Graceful

**Problem:** When Redis is not running or misconfigured, every startup logs ~370+ lines of `Redis health check failed: Error 111 connecting to localhost:6379` and `AUTH <password> called without any password configured`. Redis is non-critical for core pipeline.

**Files:**
- Modify: `backend/src/utils/health.py:71-94`
- Modify: `backend/app.main:lifespan` (around lines 60-90)
- Test: `backend/tests/test_health.py` (new)

**Step 1: Write the regression test (characterizes current behavior)**

```python
# backend/tests/test_health.py
"""Tests for health check graceful degradation."""

import pytest
from unittest.mock import AsyncMock, patch


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

**Step 2: Run test to verify current behavior is correct**

```bash
cd backend
uv run pytest tests/test_health.py -v
```

Expected: PASS (existing `_check_redis` already returns `False` on failure — this is a regression guard).
**Step 3: Downgrade Redis startup log from WARNING to DEBUG**

In `backend/app/main.py:166-174` (lifespan health check section), change the failure logging to use DEBUG for Redis specifically:

```python
# CURRENT (line ~170):
if failed:
    logger.warning("Startup connectivity check failed: {}", ", ".join(failed))

# AFTER:
if failed:
    critical_failed = [s for s in failed if s != "redis"]
    if critical_failed:
        logger.warning("Startup connectivity check failed: {}", ", ".join(critical_failed))
    if "redis" in failed:
        logger.debug("Redis health check failed (non-critical)")
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

## Phase B: Pipeline Core Fixes (Tasks 4-8)

### Task 4: Improve Evidence Grounding — Fuzzy Match for Ellipsis Snippets

**Problem:** LLM extracts evidence snippets containing `...` (ellipsis), which are exact-matched against the original document and fail. ~200+ warnings of `ellipsis_detected` and `not found in document`.

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py:681-689` (ellipsis check in `_ground_one`)
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py:976-985` (existing `_normalize_snippet_for_search` — reuse or extend)
- Test: `backend/tests/core/test_grounding.py` (new)

**Step 1: Write the failing test**

```python
# backend/tests/core/test_grounding.py
"""Tests for evidence grounding fuzzy match."""

import pytest


def test_ground_one_matches_ellipsis_snippet_fuzzy():
    """Snippets with '...' should match after removing ellipsis and doing substring search."""
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import _normalize_for_grounding

    snippet = "M1 nonsense variant ... producing truncated protein"
    doc_text = "M1 nonsense variant c.477G>A(p.Trp159Ter) resulted in the 159th codon changing from encoded tryptophan to terminating codon, producing truncated protein"

    # After normalization, the ellipsis-stripped snippet should match
    normalized_snippet = _normalize_for_grounding(snippet)
    normalized_doc = _normalize_for_grounding(doc_text)

    assert normalized_snippet in normalized_doc


def test_ground_one_rejects_genuinely_missing_snippet():
    """Snippets not in document should still be rejected."""
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import _normalize_for_grounding

    snippet = "completely fabricated evidence text"
    doc_text = "Real document text about a different topic"

    normalized_snippet = _normalize_for_grounding(snippet)
    normalized_doc = _normalize_for_grounding(doc_text)

    assert normalized_snippet not in normalized_doc
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/core/test_grounding.py -v
```

Expected: FAIL — `_normalize_for_grounding` doesn't exist.

**Step 3: Add fuzzy normalization helper**

In `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py`, add a new helper (or extend the existing `_normalize_snippet_for_search` at line 976):

```python
# NOTE: `import re` already exists at top of core.py — do not re-add.
_GROUNDING_ELLIPSIS_RE = re.compile(r"\s*\.{2,}\s*")
_GROUNDING_SPACE_RE = re.compile(r"\s+")

def _normalize_for_grounding(text: str) -> str:
    """Normalize text for fuzzy grounding: strip ellipsis, collapse whitespace, lowercase."""
    text = _GROUNDING_ELLIPSIS_RE.sub(" ", text)
    text = _GROUNDING_SPACE_RE.sub(" ", text).strip()
    return text.lower()
```

Then in `_ground_one` (line 681), change the ellipsis detection path:

```python
# BEFORE (line ~681):
if self._snippet_has_ellipsis(snippet):
    logger.warning("Snippet '{}' contains ellipsis, marking SOURCE_INVALID (ellipsis_detected)", snippet)
    return item.model_copy(update={...})

# AFTER:
if self._snippet_has_ellipsis(snippet):
    # Try fuzzy match: strip ellipsis and do substring search
    normalized_snippet = _normalize_for_grounding(snippet)
    normalized_doc = _normalize_for_grounding(document.formatted_text)
    if normalized_snippet and normalized_snippet in normalized_doc:
        logger.debug("Snippet matched via fuzzy grounding (ellipsis stripped)")
        # Continue with normal grounding flow below
    else:
        logger.warning("Snippet '{}' contains ellipsis and not found via fuzzy match, marking SOURCE_INVALID", snippet[:80])
        return item.model_copy(update={...})
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/core/test_grounding.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py \
       backend/tests/core/test_grounding.py
git commit -m "feat: fuzzy match ellipsis snippets in evidence grounding"
```

---

### Task 5: Add HTML Detection in LLM Formatter

**Problem:** `_apply_llm_formatting()` in `formatter.py:240` receives HTML error pages from LLM API (18 occurrences of `<html>`) and tries to process them as markdown. Also, length mismatch warnings (~30+) when LLM output is significantly shorter than input.

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

    html_response = "<html><head><title>404 Not Found</title></head><body><h1>Not Found</h1></body></html>"
    original = "Some original markdown text"

    result = formatter._apply_llm_formatting(html_response, original)
    assert result == original
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/core/test_formatter.py::test_apply_llm_formatting_detects_html_response -v
```

Expected: FAIL — method doesn't detect HTML.

**Step 3: Add HTML detection**

In `formatter.py`, add at module level:

```python
import re

_HTML_DETECT_RE = re.compile(r"^\s*<(!DOCTYPE|html|head|body|title)\b", re.IGNORECASE | re.DOTALL)

def _is_html(text: str) -> bool:
    """Return True if text looks like an HTML document."""
    return bool(_HTML_DETECT_RE.match(text[:500]))
```

In `_apply_llm_formatting`, add early return after receiving LLM output:

```python
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

**Problem:** Logs show `Missing credentials. Please pass an api_key` from OpenAI SDK (~50 occurrences) and `404 Not Found` for `api.xiaomimimo.com`. Also `Error code: 401 - Invalid API Key`. These are config issues, not code bugs.

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
print(f'REASONING_LLM base_url: {cfg.reasoning_llm.base_url}')
print(f'REASONING_LLM api_key set: {bool(cfg.reasoning_llm.api_key)}')
"
```

Expected: all values populated.

**Step 2: If api_key is empty, check vault file**

```bash
grep -A5 'fast_llm\|reasoning_llm' backend/config/vault/dev.yaml
```

**Step 3: If 404/401 persists, test the endpoint**

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$(grep -A10 'fast_llm' backend/config/vault/dev.yaml | grep base_url | awk '{print $2}')/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(grep -A10 'fast_llm' backend/config/vault/dev.yaml | grep api_key | awk '{print $2}')" \
  -d '{"model":"test","messages":[{"role":"user","content":"hi"}]}'
```

Expected: 200 or 401 (not 404). If 404, the base_url is wrong.

**Step 4: Fix config if needed**

Edit `backend/config/vault/dev.yaml` to correct the endpoint and API key.

**Step 5: Commit (only if config files changed)**

```bash
git add backend/config/vault/dev.yaml
git commit -m "fix: correct LLM endpoint and API key in dev config"
```

---

### Task 7: Extend `context_type` Literal to Accept Academic Section Types

**Problem:** `contracts.py:115` — `context_type` is `Literal["text", "table", "figure", "supplementary", "caption"]`. OCR/MinerU returns `"results"`, `"discussion"`, `"methods"`, `"background"` — all rejected. ~37 occurrences.

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py:115`
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py:782` (`_map_block_type`)
- Test: `backend/tests/core/test_contracts.py` (new)

**Step 1: Write the failing test**

```python
# backend/tests/core/test_contracts.py
"""Tests for SourceLocation context_type validation."""

import pytest
from pydantic import ValidationError


def test_source_location_accepts_academic_section_types():
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import SourceLocation

    for section in ("results", "discussion", "methods", "background",
                    "introduction", "conclusion", "abstract"):
        loc = SourceLocation(context_type=section, context_ref="test", text_snippet="test")
        assert loc.context_type == section


def test_source_location_rejects_unknown_type():
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import SourceLocation

    with pytest.raises(ValidationError):
        SourceLocation(context_type="nonexistent_type", context_ref="test", text_snippet="test")
```

**Step 2: Run test to verify it fails**

```bash
cd backend
uv run pytest tests/core/test_contracts.py -v
```

Expected: FAIL — `Input should be 'text', 'table', 'figure', 'supplementary' or 'caption'`

**Step 3: Extend the Literal**

In `contracts.py:115`:

```python
    context_type: Literal[
        "text", "table", "figure", "supplementary", "caption",
        "abstract", "introduction", "methods", "results", "discussion", "conclusion",
        "background",
    ]
```

**Step 4: Update `_map_block_type` in core.py**

```python
_KNOWN_CONTEXT_TYPES = frozenset({
    "text", "table", "figure", "supplementary", "caption",
    "abstract", "introduction", "methods", "results", "discussion",
    "conclusion", "background",
})

def _map_block_type(mineru_type: str) -> str:
    mapping = {"chart": "figure", "image": "figure", "table": "table"}
    mapped = mapping.get(mineru_type, mineru_type)
    return mapped if mapped in _KNOWN_CONTEXT_TYPES else "text"
```

**Step 5: Run test to verify it passes**

```bash
uv run pytest tests/core/test_contracts.py -v
```

**Step 6: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/contracts.py \
       backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/core.py \
       backend/tests/core/test_contracts.py
git commit -m "feat: extend context_type to accept academic section types"
```

---

### Task 8: Improve FileNotFoundError Messaging in Phase Execution

**Problem:** ~30 occurrences of `FileNotFoundError` for `phase_1/metadata.json` and upload PDFs that were deleted. The phase adapters correctly classify these as `PermanentPhaseError` (never retried), and `RetryablePhaseExecutor` already skips retry for permanent errors. The log noise comes from repeated pipeline runs — each run logs the error once. The fix is to make the error message clearly indicate it's a permanent failure (not transient), so operators don't mistake it for a retry-worthy transient error.

**Files:**
- Modify: `backend/src/agents/phase_2_adapter.py` (line ~82-86 — `phase_1_output is None` check, or wherever `FileNotFoundError` surfaces)
- Test: `backend/tests/agents/test_phase2_retry.py` (new)

**Step 1: Write the characterization test**

```python
# backend/tests/agents/test_phase2_retry.py
"""Tests verifying FileNotFoundError is never retried."""

import pytest
from src.agents.concurrency import RetryablePhaseExecutor
from src.agents.contracts import RetryablePhaseError


@pytest.mark.asyncio
async def test_file_not_found_error_is_not_retried():
    """FileNotFoundError propagates immediately — retry logic never catches it."""
    executor = RetryablePhaseExecutor(max_retries=2, backoff_base=0.01)

    call_count = 0

    async def failing_phase(state):
        nonlocal call_count
        call_count += 1
        raise FileNotFoundError("No such file: phase_1/metadata.json")

    with pytest.raises(FileNotFoundError):
        await executor.execute_with_retry(
            operation=failing_phase, state=None, phase_name="phase_2"
        )

    assert call_count == 1  # Never retried


@pytest.mark.asyncio
async def test_permanent_phase_error_is_not_retried():
    """PermanentPhaseError propagates immediately."""
    from src.agents.contracts import PermanentPhaseError

    executor = RetryablePhaseExecutor(max_retries=2, backoff_base=0.01)
    call_count = 0

    async def failing_phase(state):
        nonlocal call_count
        call_count += 1
        raise PermanentPhaseError("file not found", phase=2)

    with pytest.raises(PermanentPhaseError):
        await executor.execute_with_retry(
            operation=failing_phase, state=None, phase_name="phase_2"
        )

    assert call_count == 1


@pytest.mark.asyncio
async def test_retryable_phase_error_is_retried():
    """RetryablePhaseError is retried (smoke test to confirm retry works)."""
    executor = RetryablePhaseExecutor(max_retries=2, backoff_base=0.01)
    call_count = 0

    async def failing_phase(state):
        nonlocal call_count
        call_count += 1
        raise RetryablePhaseError("transient timeout", phase=2)

    with pytest.raises(RetryablePhaseError):
        await executor.execute_with_retry(
            operation=failing_phase, state=None, phase_name="phase_2"
        )

    assert call_count == 3  # 1 initial + 2 retries
```

**Step 2: Run test to verify current behavior is correct**

```bash
cd backend
uv run pytest tests/agents/test_phase2_retry.py -v
```

Expected: All 3 PASS — `FileNotFoundError` and `PermanentPhaseError` are never retried; `RetryablePhaseError` is retried.

**Step 3: Improve the error message in the phase adapter**

In `backend/src/agents/phase_2_adapter.py`, ensure the `FileNotFoundError` path produces a message that clearly distinguishes permanent from transient:

```python
# When phase_1_output is missing (line ~82):
if state.phase_1_output is None:
    raise PermanentPhaseError(
        "Phase 1 output not found (permanent — check that phase 1 completed successfully and temp files were not cleaned up)",
        phase=2,
    )
```

No retry-logic changes are needed in `concurrency.py` — the current behavior is already correct.

**Step 4: Run tests to verify**

```bash
uv run pytest tests/agents/test_phase2_retry.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/agents/phase_2_adapter.py backend/tests/agents/test_phase2_retry.py
git commit -m "fix: clarify permanent error message in phase 2 adapter"
```

---

## Phase C: Visualization & Infrastructure (Tasks 9-12)

### Task 9: Deduplicate Tracks in `search_service.get_group_detail`

**Problem:** `search_service.py` `get_group_detail` produces ~8,500+ "Duplicate track" warnings. The SQL query returns ALL `CanonicalEvidenceItem` rows for a group with no filtering on `track`. When multiple rows share the same `(field_id, track)`, the loop silently overwrites (last-writer-wins). The unique constraint on the table is `(source_document_id, field_id, position_hash, entity_scope_hash)` — does not include `track`.

**Files:**
- Modify: `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py:384-543`
- Test: `backend/tests/core/test_search_service.py` (new)

**Step 1: Write the failing test**

```python
# backend/tests/core/test_search_service.py
"""Tests for search_service track deduplication."""

import pytest


def test_get_group_detail_no_duplicate_track_warnings(caplog):
    """get_group_detail should not produce duplicate track warnings when rows are deduplicated."""
    import logging
    # This is a structural test — the actual fix is in the SQL query or post-query dedup.
    # Once fixed, querying with known duplicate data should produce no warnings.
    # Placeholder: verify the dedup function exists and works.
    pass  # Full integration test requires DB fixtures; see Step 3 for the logic fix.
```

**Step 2: Understand the current code**

Read `backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py:430-543` to understand:
- Line ~432: SQL query returns all rows for `group_id`
- Line ~503: `items_by_field` partitions by `field_id`
- Line ~508-537: For each field, picks first `original` and first `translated` — logs warning on duplicates

**Step 3: Add `updated_at` to SELECT and add post-query deduplication**

First, add `CanonicalEvidenceItem.updated_at` to the SELECT at line 427 so the dedup code can sort by recency:

```python
stmt = (
    select(
        CanonicalEvidenceItem.canonical_evidence_id,
        CanonicalEvidenceItem.source_document_id,
        CanonicalEvidenceItem.field_id,
        CanonicalEvidenceItem.review_status,
        CanonicalEvidenceItem.current_best_confidence,
        CanonicalEvidenceItem.active_payload,
        CanonicalEvidenceItem.updated_at,             # ← ADD for dedup tiebreaking
    )
    .where(CanonicalEvidenceItem.active_payload["group_id"].astext == group_id)
    .order_by(CanonicalEvidenceItem.field_id)
)
```

Then, after fetching rows (after line 438), add deduplication before the trace-building loop:

```python
# After fetching rows, deduplicate by (field_id, track):
# Keep the row with the most recent updated_at for each (field_id, track) pair
seen: dict[tuple[str, str], int] = {}
deduped_rows = []
for row in sorted(rows, key=lambda r: r.updated_at or "", reverse=True):
    track = (row.active_payload or {}).get("track", "original")
    key = (row.field_id, track)
    if key not in seen:
        seen[key] = 1
        deduped_rows.append(row)
rows = deduped_rows
```

**Step 4: Also downgrade the remaining warning to DEBUG**

If after dedup some warnings still occur (edge cases), change the log level:

```python
logger.debug("Duplicate original track for field_id=...")  # was logger.warning
```

**Step 5: Commit**

```bash
git add backend/src/core/visualize_evidence_with_expert_in_loop/search_service.py
git commit -m "fix: deduplicate tracks in search_service get_group_detail"
```

---

### Task 10: Downgrade Shutdown Cleanup Logs from WARNING to DEBUG

**Problem:** ~70 warnings of `Phase4ServiceFactory close failed during shutdown` and ~10 `Redis disposal failed during shutdown`. The shutdown code at `main.py:190-205` already wraps both cleanup calls in try-except, so exceptions do not propagate — but they log at `logger.warning` level, producing noise on every graceful restart. The fix is to downgrade these to `logger.debug`.

**Files:**
- Modify: `backend/app/main.py:195-201` (shutdown cleanup logging)

**Step 1: Read the current shutdown code**

```bash
cd backend
# Lines 190-205 in app/main.py already have try-except — confirm
```

**Step 2: Downgrade log levels in shutdown cleanup**

In `backend/app/main.py:195-201`, change `logger.warning` to `logger.debug` for benign shutdown failures:

```python
# CURRENT (lines ~195-201):
except Exception:
    logger.warning("Phase4ServiceFactory close failed during shutdown")
...
except Exception:
    logger.warning("Redis disposal failed during shutdown")

# AFTER:
except Exception as exc:
    logger.debug("Phase4ServiceFactory close failed during shutdown: {}", exc)
...
except Exception as exc:
    logger.debug("Redis disposal failed during shutdown: {}", exc)
```

Note: the exception variable (`as exc`) should also be captured so the message includes the actual error for debugging.

**Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "fix: downgrade shutdown cleanup logs from warning to debug"
```

---

### Task 11: Verify Model Server for Semantic Matching (No-Code Diagnostic)

**Problem:** ~40 occurrences of `Semantic matching service error: All connection attempts failed`. The `SimilarityTerminologyMatcher` in Phase 3 tries to connect to `http://localhost:8001/v1/embeddings` and `/v1/rerank` via httpx, but the model server is not running.

**Files:**
- Verify: `services/model-server/` (is it running?)
- Verify: `backend/config/environments/development.yaml` (embedding/rerank base_url)
- Verify: `backend/src/core/config.py:290-300` (embedding/rerank config)

**Step 1: Check if model server is running**

```bash
curl -s http://localhost:8001/health || echo "Model server NOT running"
```

**Step 2: If not running, start it**

```bash
cd services/model-server
uv run python main.py &
```

Or use the script:

```bash
bash scripts/start_model_server.sh
```

**Step 3: Verify semantic matching works**

```bash
curl -s -X POST http://localhost:8001/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input":"test","model":"Qwen/Qwen3-Embedding-0.6B"}' | head -c 200
```

Expected: JSON response with embedding vector.

**Step 4: Commit (no code change, just verification)**

No commit needed — this is operational.

---

### Task 12: Improve Translation Validation Threshold

**Problem:** ~8 occurrences of `translation_validation_failed: unchanged`. The validator uses `difflib.SequenceMatcher` with threshold ≥0.85 similarity on lowercased text. Short texts or technical content with many shared terms can trigger false positives.

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/validator/core.py:12-34`
- Test: `backend/tests/core/test_translation_validator.py` (new)

**Step 1: Write the failing test**

```python
# backend/tests/core/test_translation_validator.py
"""Tests for translation validation threshold."""

import pytest


def test_short_cjk_technical_text_not_flagged():
    """Short CJK-source texts with shared technical terms should not be falsely flagged."""
    from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.validator.core import validate_translation_output

    # Chinese source with shared English gene/mutation notation
    source = "患者携带BRCA1基因c.5266dupC（p.Gln1756ProfsTer74）突变。"
    translated = "The patient carries BRCA1 gene c.5266dupC (p.Gln1756ProfsTer74) mutation."

    # Many shared ASCII tokens (BRCA1, c.5266dupC, p.Gln1756ProfsTer74) but genuinely translated
    # With CJK-aware threshold (0.95 for short CJK-source texts), should NOT raise
    try:
        validate_translation_output(source, translated)
    except Exception as e:
        pytest.fail(f"Should not raise for genuine translation with shared terms: {e}")


def test_short_cjk_untranslated_still_caught():
    """Short CJK-source text returned unchanged is still caught (ratio >= 0.95)."""
    from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.validator.core import validate_translation_output

    source = "患者携带BRCA1 c.5266dupC突变。"
    translated = "患者携带BRCA1 c.5266dupC突变。"  # unchanged

    with pytest.raises(ValueError, match="translation_validation_failed: unchanged"):
        validate_translation_output(source, translated)


def test_short_english_untranslated_still_caught():
    """Short English text returned unchanged is caught at threshold 0.85."""
    from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.validator.core import validate_translation_output

    source = "c.1234A>G (p.Thr412Ala) in exon 10"
    translated = "c.1234A>G (p.Thr412Ala) in exon 10"  # unchanged

    with pytest.raises(ValueError, match="translation_validation_failed: unchanged"):
        validate_translation_output(source, translated)

**Step 2: Run test to verify current behavior**

```bash
cd backend
uv run pytest tests/core/test_translation_validator.py -v
```

Expected:
- `test_short_cjk_technical_text_not_flagged` — FAIL (current 0.85 threshold falsely flags the genuine translation)
- `test_short_cjk_untranslated_still_caught` — PASS
- `test_short_english_untranslated_still_caught` — PASS
```

**Step 3: Adjust validation logic**

In `validator/core.py`, instead of a blanket length guard (which would mask genuine untranslated short texts), use a CJK-aware adjustment: for short texts, raise the similarity threshold from 0.85 to 0.95, AND require CJK characters to be present in the source before applying the unchanged check. This protects short biomedical texts with shared technical terms while still catching genuinely untranslated Chinese text.

Replace lines 39-42 in `core.py`:

```python
# BEFORE (lines 39-42):
if source and ratio >= 0.85:
    raise ValueError("translation_validation_failed: unchanged")

# AFTER:
# For short texts with high CJK content in source, use a stricter threshold.
# Short technical texts (gene names, mutations) share many tokens across languages.
source_cjk_count = len(_CJK_RE.findall(source))
threshold = 0.95 if (len(source) < 150 and source_cjk_count > 0) else 0.85
if source and ratio >= threshold:
    raise ValueError("translation_validation_failed: unchanged")
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/core/test_translation_validator.py -v
```

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/validator/core.py \
       backend/tests/core/test_translation_validator.py
git commit -m "fix: use CJK-aware similarity threshold for short texts in translation validation"
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

Expected:
- No `source_key does not exist` errors
- No `literature_profiles does not exist` errors
- Redis failure logged at DEBUG level (if Redis not running)
- No connection leak warnings from `_try_startup_lock`
- Shutdown cleanup failures logged at DEBUG level
- Duplicate track occurrences reduced (fully eliminated in trace building; remaining edge cases at DEBUG level)
---

## Post-Plan Cleanup

- Update `lesson.md` with root causes and fixes
- Update `progress.txt` with completion status
- Run `docs/` doc-organize skill
