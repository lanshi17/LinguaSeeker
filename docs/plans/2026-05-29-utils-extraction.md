# Backend Utils Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract duplicated and cross-cutting utilities into backend/src/utils/ to eliminate code duplication and establish a stable home for reusable helpers.

**Architecture:** Flat module structure under backend/src/utils/ with empty __init__.py. Extract three utilities: sanitize_filename (deduplicate 3 copies → 1), _strip_json_fences (generic JSON parsing), and traced_node (cross-cutting observability). Move + update imports strategy (no re-exports). Tests move to tests/utils/ mirroring source structure.

**Tech Stack:** Python 3.12, pytest, LangSmith, loguru

---

## Task 1: Create utils directory structure

**Files:**
- Create: `backend/src/utils/__init__.py`
- Create: `backend/tests/utils/__init__.py`

**Step 1: Create directory structure**

```bash
mkdir -p backend/src/utils
mkdir -p backend/tests/utils
touch backend/src/utils/__init__.py
touch backend/tests/utils/__init__.py
```

**Step 2: Verify directories exist**

Run: `ls -la backend/src/utils/ backend/tests/utils/`
Expected: Both directories exist with __init__.py files

**Step 3: Commit**

```bash
git add backend/src/utils/__init__.py backend/tests/utils/__init__.py
git commit -m "chore: create utils directory structure"
```

---

## Task 2: Extract sanitize_filename to utils/text.py

**Files:**
- Create: `backend/src/utils/text.py`

**Step 1: Write utils/text.py with unified strict version**

```python
"""Text processing utilities."""
from __future__ import annotations

import re


def sanitize_filename(name: str) -> str:
    """Sanitize filename by removing invalid characters.
    
    Removes Windows-unsafe characters and caps length at 120 chars.
    Returns "paper" if result is empty.
    
    Args:
        name: Raw filename to sanitize.
    
    Returns:
        Sanitized filename safe for all platforms.
    """
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", str(name or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned or "paper")[:120]
```

**Step 2: Verify file created**

Run: `cat backend/src/utils/text.py`
Expected: File contains sanitize_filename function

**Step 3: Commit**

```bash
git add backend/src/utils/text.py
git commit -m "feat(utils): add sanitize_filename to utils/text.py"
```

---

## Task 3: Write tests for sanitize_filename

**Files:**
- Create: `backend/tests/utils/test_text.py`

**Step 1: Write test file**

```python
"""Tests for utils/text.py."""
from __future__ import annotations

from src.utils.text import sanitize_filename


class TestSanitizeFilename:
    def test_basic_sanitize(self):
        assert sanitize_filename('test: file? name') == 'test_ file_ name'

    def test_empty_string(self):
        assert sanitize_filename("") == "paper"

    def test_none_value(self):
        assert sanitize_filename(None) == "paper"

    def test_only_invalid_chars(self):
        assert sanitize_filename(':::') == 'paper'

    def test_length_cap(self):
        long_name = "a" * 200
        result = sanitize_filename(long_name)
        assert len(result) == 120

    def test_windows_unsafe_chars(self):
        assert sanitize_filename('file<>name*.txt') == 'file_name_.txt'

    def test_multiple_spaces(self):
        assert sanitize_filename('file   name') == 'file name'
```

**Step 2: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/utils/test_text.py::TestSanitizeFilename -v`
Expected: All 7 tests PASS

**Step 3: Commit**

```bash
git add backend/tests/utils/test_text.py
git commit -m "test(utils): add tests for sanitize_filename"
```

---

## Task 4: Update gateway.py to use utils sanitize_filename

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/gateway.py`

**Step 1: Remove local _sanitize_filename function**

Delete lines 33-36:
```python
def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "_", str(name or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned or "paper")[:120]
```

**Step 2: Add import at top of file**

Add after existing imports (around line 15):
```python
from src.utils.text import sanitize_filename
```

**Step 3: Update call site**

Change line 90:
```python
# Before:
target = Path(download_path) / f"{_sanitize_filename(filename_stem)}.pdf"

# After:
target = Path(download_path) / f"{sanitize_filename(filename_stem)}.pdf"
```

**Step 4: Run targeted tests**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/document_acquisition/online_acquisition/ -k "not integration" -v`
Expected: All existing tests still PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/gateway.py
git commit -m "refactor(acquisition): use utils sanitize_filename in gateway.py"
```

---

## Task 5: Update doi_fallback.py to use utils sanitize_filename

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/doi_fallback.py`

**Step 1: Remove local _sanitize_filename function**

Delete lines 54-55:
```python
def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\-.]", "_", name)
```

**Step 2: Add import at top of file**

Add after existing imports (around line 10):
```python
from src.utils.text import sanitize_filename
```

**Step 3: Update call site**

Change line 148:
```python
# Before:
filename = _sanitize_filename(doi.replace("/", "_")) + ".pdf"

# After:
filename = sanitize_filename(doi.replace("/", "_")) + ".pdf"
```

**Step 4: Run targeted tests**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/document_acquisition/online_acquisition/ -k "not integration" -v`
Expected: All existing tests still PASS

**Step 5: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/doi_fallback.py
git commit -m "refactor(acquisition): use utils sanitize_filename in doi_fallback.py"
```

---

## Task 6: Update web/base.py to use utils sanitize_filename

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web/base.py`

**Step 1: Remove local sanitize_filename function**

Delete lines 28-32:
```python
def sanitize_filename(name: str) -> str:
    """Sanitize filename by removing invalid characters."""
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return (name or "paper")[:120]
```

**Step 2: Add import at top of file**

Add after existing imports (around line 12):
```python
from src.utils.text import sanitize_filename
```

**Step 3: Update call site**

Change line 104:
```python
# Before:
filename = sanitize_filename(filename_stem) + ".pdf"

# After (no change needed, already uses sanitize_filename):
filename = sanitize_filename(filename_stem) + ".pdf"
```

**Step 4: Update test_web_providers.py imports**

Modify `backend/tests/core/ingest_and_digitize_data/document_acquisition/online_acquisition/test_web_providers.py`:

Change lines 13-14:
```python
# Before:
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web.base import (
    safe_json_loads,
    sanitize_filename,
    extract_pdf_links_from_html,
    scrape_html_elements,
    choose_item,
    build_js_helpers,
    resolve_llm_config,
)

# After:
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web.base import (
    safe_json_loads,
    extract_pdf_links_from_html,
    scrape_html_elements,
    choose_item,
    build_js_helpers,
    resolve_llm_config,
)
from src.utils.text import sanitize_filename
```

**Step 5: Run targeted tests**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/document_acquisition/online_acquisition/test_web_providers.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web/base.py
git add backend/tests/core/ingest_and_digitize_data/document_acquisition/online_acquisition/test_web_providers.py
git commit -m "refactor(acquisition): use utils sanitize_filename in web/base.py"
```

---

## Task 7: Move sanitize_filename tests from test_web_providers.py to test_text.py

**Files:**
- Modify: `backend/tests/core/ingest_and_digitize_data/document_acquisition/online_acquisition/test_web_providers.py`
- Modify: `backend/tests/utils/test_text.py`

**Step 1: Remove duplicate tests from test_web_providers.py**

Delete lines 33-37:
```python
def test_sanitize_filename(self):
    assert sanitize_filename('test: file? name') == 'test_ file_ name'

def test_sanitize_filename_empty(self):
    assert sanitize_filename("") == "paper"
```

Note: These tests are already covered by Task 3's test_text.py (test_basic_sanitize and test_empty_string).

**Step 2: Run tests to verify no regressions**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/document_acquisition/online_acquisition/test_web_providers.py tests/utils/test_text.py -v`
Expected: All tests PASS, no duplicates

**Step 3: Commit**

```bash
git add backend/tests/core/ingest_and_digitize_data/document_acquisition/online_acquisition/test_web_providers.py
git commit -m "refactor(tests): remove duplicate sanitize_filename tests"
```

---

## Task 8: Add strip_json_fences to utils/text.py

**Files:**
- Modify: `backend/src/utils/text.py`

**Step 1: Add strip_json_fences function**

Append to backend/src/utils/text.py:
```python
def strip_json_fences(content: str) -> str:
    """Strip Markdown code fences from LLM JSON output.
    
    LLMs often wrap JSON responses in ```json ... ``` blocks.
    This function removes those fences while preserving the JSON content.
    
    Args:
        content: Raw LLM output potentially containing code fences.
    
    Returns:
        Cleaned JSON string without fences.
    """
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text
```

**Step 2: Verify function added**

Run: `grep -A 15 "def strip_json_fences" backend/src/utils/text.py`
Expected: Function definition visible

**Step 3: Commit**

```bash
git add backend/src/utils/text.py
git commit -m "feat(utils): add strip_json_fences to utils/text.py"
```

---

## Task 9: Write tests for strip_json_fences

**Files:**
- Modify: `backend/tests/utils/test_text.py`

**Step 1: Add test class**

Append to backend/tests/utils/test_text.py:
```python
from src.utils.text import sanitize_filename, strip_json_fences


class TestStripJsonFences:
    def test_strip_fences(self):
        content = '```json\n{"key": "value"}\n```'
        assert strip_json_fences(content) == '{"key": "value"}'

    def test_no_fences(self):
        content = '{"key": "value"}'
        assert strip_json_fences(content) == '{"key": "value"}'

    def test_fences_without_language(self):
        content = '```\n{"key": "value"}\n```'
        assert strip_json_fences(content) == '{"key": "value"}'

    def test_empty_string(self):
        assert strip_json_fences("") == ""

    def test_only_fences(self):
        content = '```\n```'
        assert strip_json_fences(content) == ""

    def test_multiline_json(self):
        content = '```json\n{\n  "key": "value"\n}\n```'
        result = strip_json_fences(content)
        assert result == '{\n  "key": "value"\n}'
```

**Step 2: Update import statement**

Change line 4 in test_text.py:
```python
# Before:
from src.utils.text import sanitize_filename

# After:
from src.utils.text import sanitize_filename, strip_json_fences
```

**Step 3: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/utils/test_text.py::TestStripJsonFences -v`
Expected: All 6 tests PASS

**Step 4: Commit**

```bash
git add backend/tests/utils/test_text.py
git commit -m "test(utils): add tests for strip_json_fences"
```

---

## Task 10: Update providers.py to use utils strip_json_fences

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/providers.py`

**Step 1: Remove local _strip_json_fences function**

Delete lines 160-168:
```python
def _strip_json_fences(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text
```

**Step 2: Add import at top of file**

Add after existing imports (around line 15):
```python
from src.utils.text import strip_json_fences
```

**Step 3: Update call sites**

Change line 126:
```python
# Before:
json_text = _strip_json_fences(content)

# After:
json_text = strip_json_fences(content)
```

Change line 157:
```python
# Before:
return _strip_json_fences(content)

# After:
return strip_json_fences(content)
```

**Step 4: Run targeted tests**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/extract_evidence/ -k "not integration" -v`
Expected: All existing tests still PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/providers.py
git commit -m "refactor(extract_evidence): use utils strip_json_fences in providers.py"
```

---

## Task 11: Extract traced_node to utils/observability.py

**Files:**
- Create: `backend/src/utils/observability.py`

**Step 1: Write observability.py**

```python
"""Observability utilities — LangSmith tracing + structured logging."""
from __future__ import annotations

import functools
from typing import Any, Callable

from langsmith import traceable
from loguru import logger


def traced_node(name: str) -> Callable:
    """Decorator that adds LangSmith tracing + loguru logging to a pipeline node.
    
    Usage:
        @traced_node("my_node")
        def my_node(state: State) -> State:
            # node logic
            return state
    
    Args:
        name: Node name for tracing and logging.
    
    Returns:
        Decorated function with tracing and logging.
    """
    def decorator(fn: Callable) -> Callable:
        @traceable(name=name, run_type="chain")
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.info("Node [{}] start", name)
            try:
                result = fn(*args, **kwargs)
                logger.info("Node [{}] done", name)
                return result
            except Exception as e:
                logger.error("Node [{}] failed: {}", name, e)
                raise
        return wrapper
    return decorator
```

**Step 2: Verify file created**

Run: `cat backend/src/utils/observability.py`
Expected: File contains traced_node decorator

**Step 3: Commit**

```bash
git add backend/src/utils/observability.py
git commit -m "feat(utils): add traced_node to utils/observability.py"
```

---

## Task 12: Write tests for traced_node

**Files:**
- Create: `backend/tests/utils/test_observability.py`

**Step 1: Write test file**

```python
"""Tests for utils/observability.py."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.utils.observability import traced_node


class TestTracedNode:
    def test_basic_execution(self):
        @traced_node("test_node")
        def my_node(state: dict) -> dict:
            return {"result": state["input"] + 1}

        result = my_node({"input": 5})
        assert result == {"result": 6}

    def test_logging_on_success(self):
        @traced_node("success_node")
        def my_node(state: dict) -> dict:
            return state

        with patch("src.utils.observability.logger") as mock_logger:
            my_node({"data": "test"})
            mock_logger.info.assert_any_call("Node [{}] start", "success_node")
            mock_logger.info.assert_any_call("Node [{}] done", "success_node")

    def test_logging_on_failure(self):
        @traced_node("fail_node")
        def my_node(state: dict) -> dict:
            raise ValueError("test error")

        with patch("src.utils.observability.logger") as mock_logger:
            with pytest.raises(ValueError, match="test error"):
                my_node({})
            mock_logger.info.assert_any_call("Node [{}] start", "fail_node")
            mock_logger.error.assert_called_once()

    def test_preserves_function_name(self):
        @traced_node("named_node")
        def my_custom_node(state: dict) -> dict:
            return state

        assert my_custom_node.__name__ == "my_custom_node"

    def test_kwargs_passthrough(self):
        @traced_node("kwargs_node")
        def my_node(state: dict, multiplier: int = 1) -> dict:
            return {"result": state["value"] * multiplier}

        result = my_node({"value": 3}, multiplier=2)
        assert result == {"result": 6}
```

**Step 2: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/utils/test_observability.py -v`
Expected: All 5 tests PASS

**Step 3: Commit**

```bash
git add backend/tests/utils/test_observability.py
git commit -m "test(utils): add tests for traced_node"
```

---

## Task 13: Update workflow.py to use utils traced_node

**Files:**
- Modify: `backend/src/core/cross_lingual_process_and_extract_evidence/workflow.py`
- Delete: `backend/src/core/cross_lingual_process_and_extract_evidence/middleware.py`

**Step 1: Update import in workflow.py**

Change line 15:
```python
# Before:
from .middleware import traced_node

# After:
from src.utils.observability import traced_node
```

**Step 2: Verify no other imports of middleware.traced_node**

Run: `cd backend && grep -r "from.*middleware import traced_node" src/ --include="*.py"`
Expected: No matches (only workflow.py imported it)

**Step 3: Remove middleware.py**

```bash
rm backend/src/core/cross_lingual_process_and_extract_evidence/middleware.py
```

**Step 4: Run targeted tests**

Run: `cd backend && uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -k "not integration" -v`
Expected: All existing tests still PASS

**Step 5: Commit**

```bash
git add backend/src/core/cross_lingual_process_and_extract_evidence/workflow.py
git add backend/src/core/cross_lingual_process_and_extract_evidence/middleware.py
git commit -m "refactor(cross_lingual): use utils traced_node, remove middleware.py"
```

---

## Task 14: Run full test suite for utils

**Files:**
- None (verification only)

**Step 1: Run all utils tests**

Run: `cd backend && uv run pytest tests/utils/ -v`
Expected: All tests PASS (18 tests total: 7 sanitize + 6 strip + 5 traced)

**Step 2: Run affected feature tests**

Run: `cd backend && uv run pytest tests/core/ingest_and_digitize_data/document_acquisition/online_acquisition/ tests/core/cross_lingual_process_and_extract_evidence/ -k "not integration" -v`
Expected: All existing tests still PASS

**Step 3: Commit (if any test fixes needed)**

```bash
# Only if fixes were needed
git add -A
git commit -m "fix(utils): address test failures from extraction"
```

---

## Task 15: Run Phase 3 E2E (optional verification)

**Files:**
- None (verification only)

**Step 1: Run Phase 3 E2E script**

Run: `cd backend && uv run python scripts/e2e_standardize_entities.py`
Expected: E2E completes without import errors

Note: This step is optional if local model-server and PostgreSQL are available. If not, skip and rely on unit tests.

**Step 2: Verify no import errors in logs**

Check output for any `ImportError` or `ModuleNotFoundError`.
Expected: Clean execution

---

## Task 16: Final commit and summary

**Files:**
- None (documentation)

**Step 1: Review all changes**

Run: `git log --oneline -20`
Expected: See commits for each extraction task

**Step 2: Verify no leftover references**

Run: `cd backend && grep -r "_sanitize_filename\|_strip_json_fences" src/ --include="*.py" | grep -v "def _"`
Expected: No matches (all private functions removed)

**Step 3: Create summary commit**

```bash
git add docs/plans/2026-05-29-utils-extraction.md
git commit -m "docs: add utils extraction implementation plan"
```

---

## Success Criteria Verification

**Criterion 1: No more duplicated code**
- ✅ sanitize_filename: 3 copies → 1
- ✅ _strip_json_fences: 1 copy → 1 (but now reusable)
- ✅ traced_node: 1 copy → 1 (but now reusable)

**Criterion 2: New features can import from utils/ without reaching into other features**
- ✅ traced_node now in utils/observability.py
- ✅ Any future LangGraph workflow can import it

**Criterion 3: Generic utilities live in utils/**
- ✅ sanitize_filename → utils/text.py
- ✅ strip_json_fences → utils/text.py
- ✅ traced_node → utils/observability.py

---

## Risk Mitigation

**Risk 1: Import breakage**
- Mitigation: Targeted unit tests after each task
- Mitigation: Full test suite run at end

**Risk 2: Behavioral change in sanitize_filename**
- Mitigation: Unify to strict version (safer)
- Mitigation: DOI strings are short and non-empty, so length cap and fallback won't trigger

**Risk 3: Test coverage gaps**
- Mitigation: Added comprehensive tests for extracted utilities
- Mitigation: Moved existing sanitize_filename tests to new location

---

## Deferred Items

**SSRF Protection (_is_private_ip, _validate_url_safe)**
- Reason: Single-use in parse_document/orchestrator.py
- Action: Extract when second consumer appears

**web/base.py helpers**
- safe_json_loads, choose_item, etc.
- Reason: Feature-specific to web providers
- Action: Leave in place

---

## Appendix: File Change Summary

| File | Action | Reason |
|------|--------|--------|
| `backend/src/utils/__init__.py` | Create | Empty package marker |
| `backend/src/utils/text.py` | Create | sanitize_filename + strip_json_fences |
| `backend/src/utils/observability.py` | Create | traced_node |
| `backend/tests/utils/__init__.py` | Create | Empty package marker |
| `backend/tests/utils/test_text.py` | Create | Tests for text utilities |
| `backend/tests/utils/test_observability.py` | Create | Tests for observability |
| `backend/src/.../gateway.py` | Modify | Remove _sanitize_filename, import from utils |
| `backend/src/.../doi_fallback.py` | Modify | Remove _sanitize_filename, import from utils |
| `backend/src/.../web/base.py` | Modify | Remove sanitize_filename, import from utils |
| `backend/src/.../providers.py` | Modify | Remove _strip_json_fences, import from utils |
| `backend/src/.../workflow.py` | Modify | Import traced_node from utils |
| `backend/src/.../middleware.py` | Delete | Content moved to utils/observability.py |
| `backend/tests/.../test_web_providers.py` | Modify | Remove duplicate tests, update import |

