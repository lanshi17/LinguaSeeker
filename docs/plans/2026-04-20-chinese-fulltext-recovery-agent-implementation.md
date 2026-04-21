# Chinese Fulltext Recovery Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Chinese Fulltext Recovery Agent that can recover usable normalized markdown from Chinese article detail pages when PDF acquisition fails, so the two Chinese target samples can continue through the existing extraction pipeline without requiring a standard PDF.

**Architecture:** Keep the change scoped to the Chinese recovery path only. Add a standalone LangGraph agent with deterministic extraction first and format-LLM normalization only as a fallback, then integrate it into `apps/backend/src/services/task_manager.py` as the final Chinese fallback after primary download, COAJ, and Unpaywall all fail. Reuse the existing markdown-based extraction flow already exercised by the web-page path rather than duplicating translation/extraction/graph code.

**Tech Stack:** Python 3.12, LangGraph, httpx, BeautifulSoup, existing `normalize_document_body(...)`, existing backend format-model configuration, existing `process_literature_identifier_task` / markdown extraction pipeline, pytest.

---

### Task 1: Add Chinese fulltext recovery tools

**Files:**
- Create: `apps/backend/src/agents/chinese_fulltext_recovery/tools.py`
- Test: `apps/backend/tests/unit/test_chinese_fulltext_recovery.py`

**Step 1: Write the failing test**

```python
from src.agents.chinese_fulltext_recovery.tools import extract_readable_body


def test_extract_readable_body_prefers_article_text_from_chinese_html() -> None:
    html = """
    <html><body>
      <nav>导航</nav>
      <article>
        <h1>DNAJB2复合杂合突变相关腓骨肌萎缩症2型家系病例1例</h1>
        <p>摘要：这里是摘要。</p>
        <p>正文第一段。</p>
        <p>正文第二段。</p>
      </article>
    </body></html>
    """

    result = extract_readable_body(html)

    assert result["success"] is True
    assert "DNAJB2复合杂合突变相关腓骨肌萎缩症2型家系病例1例" in result["body"]
    assert "正文第一段" in result["body"]
    assert result["body_selector"] == "article"
```

Add a second failing test for the quality gate:

```python
def test_validate_body_rejects_navigation_shell() -> None:
    assert validate_normalized_body("登录 注册 搜索 首页") is False
```

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_chinese_fulltext_recovery.py -q`
Expected: FAIL with `ModuleNotFoundError`.

**Step 3: Write minimal implementation**

Create `tools.py` with only deterministic extraction and validation helpers.

```python
def extract_readable_body(html: str) -> dict[str, Any]:
    normalized = normalize_document_body(html)
    return {
        "success": bool(normalized.text),
        "body": normalized.text,
        "body_selector": normalized.body_selector,
        "warnings": [],
    }


def validate_normalized_body(text: str, min_length: int = 200) -> bool:
    cleaned = str(text or "").strip()
    if len(cleaned) < min_length:
        return False
    boilerplate_tokens = ["登录", "注册", "首页", "搜索"]
    if all(token in cleaned for token in boilerplate_tokens):
        return False
    return True
```

Do not add the LangGraph agent yet. This task is just the tool layer.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_chinese_fulltext_recovery.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/agents/chinese_fulltext_recovery/tools.py apps/backend/tests/unit/test_chinese_fulltext_recovery.py
git commit -m "feat: add chinese fulltext recovery tools"
```

### Task 2: Add the standalone LangGraph recovery agent

**Files:**
- Create: `apps/backend/src/agents/chinese_fulltext_recovery/agent.py`
- Modify: `apps/backend/src/agents/chinese_fulltext_recovery/tools.py`
- Modify: `apps/backend/tests/unit/test_chinese_fulltext_recovery.py`

**Step 1: Write the failing test**

```python
from src.agents.chinese_fulltext_recovery.agent import run_chinese_fulltext_recovery


def test_recovery_agent_skips_llm_when_body_is_already_good(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.agents.chinese_fulltext_recovery.tools.fetch_detail_html",
        lambda url: {"success": True, "html": "<article><p>足够长的正文 ...</p></article>"},
    )
    monkeypatch.setattr(
        "src.agents.chinese_fulltext_recovery.tools.extract_readable_body",
        lambda html: {"success": True, "body": "足够长的正文" * 100, "body_selector": "article", "warnings": []},
    )

    result = run_chinese_fulltext_recovery("https://example.cn/paper")

    assert result["success"] is True
    assert result["provider"] == "chinese_fulltext_recovery"
    assert result["normalized_markdown"]
    assert "fallback:html_body" in result["warnings"]
```

Add a second failing test where extraction returns poor content and the agent must call the format-LLM normalization helper.

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_chinese_fulltext_recovery.py -q -k recovery_agent`
Expected: FAIL with `ModuleNotFoundError` or missing symbol error.

**Step 3: Write minimal implementation**

Create `agent.py` using a small `StateGraph`.

```python
class ChineseFulltextRecoveryState(TypedDict, total=False):
    source_url: str
    html: str
    extracted_body: str
    normalized_markdown: str
    body_selector: str | None
    warnings: list[str]
    status: str
```

Nodes:
1. `fetch_html`
2. `extract_body`
3. `maybe_normalize`
4. `finalize`

Keep the LLM call behind a helper like `normalize_body_with_format_llm(...)` in `tools.py`. For this task, a thin wrapper that returns the input body unchanged is acceptable if tests only assert routing, not model quality.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_chinese_fulltext_recovery.py -q -k recovery_agent`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/agents/chinese_fulltext_recovery/agent.py apps/backend/src/agents/chinese_fulltext_recovery/tools.py apps/backend/tests/unit/test_chinese_fulltext_recovery.py
git commit -m "feat: add chinese fulltext recovery agent"
```

### Task 3: Integrate Chinese recovery into the download layer

**Files:**
- Modify: `apps/backend/src/services/task_manager.py`
- Modify: `apps/backend/tests/unit/test_tasks.py`

**Step 1: Write the failing test**

Add a failing test proving `_try_download_and_store_literature_pdf(...)` returns normalized markdown after all PDF fallbacks fail.

```python
@pytest.mark.asyncio
async def test_try_download_returns_normalized_markdown_when_chinese_pdf_fallbacks_fail(monkeypatch):
    async def fake_unified_workflow(_):
        return {"success": False, "downloads": [], "warnings": [], "route": {"used": "web", "web_provider": "pubscholar"}, "raw": {"web": {"source_trace": []}}}

    async def fake_coaj_lookup(_):
        return {"success": True, "pdf_url": None, "raw": {}}

    async def fake_unpaywall(**_):
        class Result:
            downloads = []
        return Result()

    monkeypatch.setattr(...)
    monkeypatch.setattr(...)
    monkeypatch.setattr(...)
    monkeypatch.setattr(...run_chinese_fulltext_recovery..., lambda url: {
        "success": True,
        "normalized_markdown": "# 标题\n\n正文",
        "provider": "chinese_fulltext_recovery",
        "warnings": ["fallback:html_body"],
    })

    result = await _try_download_and_store_literature_pdf(...)
    assert result["normalized_markdown"] == "# 标题\n\n正文"
```

Also add a sibling test proving non-Chinese samples do not trigger the recovery agent.

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_tasks.py -q -k chinese_fulltext_recovery`
Expected: FAIL because `_try_download_and_store_literature_pdf(...)` cannot yet return normalized markdown.

**Step 3: Write minimal implementation**

In `task_manager.py`, after COAJ and Unpaywall fail:

```python
if file_path is None and language_hint and language_hint.startswith("zh") and detail_link:
    recovery = run_chinese_fulltext_recovery(detail_link)
    warnings.extend(recovery.get("warnings") or [])
    if recovery.get("success") and recovery.get("normalized_markdown"):
        return {
            "downloaded": False,
            "provider": recovery.get("provider"),
            "normalized_markdown": recovery.get("normalized_markdown"),
            "warnings": warnings,
            "reason": "html_fallback",
        }
```

Do not force this into non-Chinese paths.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_tasks.py -q -k chinese_fulltext_recovery`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/services/task_manager.py apps/backend/tests/unit/test_tasks.py
git commit -m "fix: add chinese html fallback after pdf failures"
```

### Task 4: Reuse the markdown processing path in `process_literature_identifier_task`

**Files:**
- Modify: `apps/backend/src/services/task_manager.py`
- Modify: `apps/backend/tests/unit/test_tasks.py`

**Step 1: Write the failing test**

```python
def test_process_literature_identifier_task_continues_when_recovery_returns_markdown(monkeypatch):
    async def fake_download(**kwargs):
        return {
            "downloaded": False,
            "normalized_markdown": "# 标题\n\n中文正文",
            "provider": "chinese_fulltext_recovery",
            "reason": "html_fallback",
        }
```

Stub the downstream markdown path and assert the worker does **not** return `FULLTEXT_UNAVAILABLE`.

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_tasks.py -q -k recovery_returns_markdown`
Expected: FAIL because the identifier worker still only accepts `local_file_path`.

**Step 3: Write minimal implementation**

Extract or reuse the existing markdown flow from `process_web_page_task(...)` into a helper, for example:

```python
def _process_markdown_direct(...):
    ...
```

Then in `process_literature_identifier_task(...)`:

```python
markdown = str(download.get("normalized_markdown") or "").strip()
if markdown:
    return _process_markdown_direct(
        markdown_content=markdown,
        document_id=document_id,
        paper_task_id=paper_task_id,
        request_id=request_id,
        source="web",
        title=selected_title or query,
        source_url=detail_link,
    )
```

Only return `FULLTEXT_UNAVAILABLE` if there is neither a reusable PDF path nor normalized markdown.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_tasks.py -q -k recovery_returns_markdown`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/services/task_manager.py apps/backend/tests/unit/test_tasks.py
git commit -m "fix: let literature identifier worker continue with recovered markdown"
```

### Task 5: Validate the two Chinese samples only

**Files:**
- No committed code required unless validation exposes another bug
- Runtime report only: `/tmp/acmg_chinese_body_fallback_report.json`

**Step 1: Start the isolated backend**

Run the backend from this worktree on a dedicated port.

Run: `uv run uvicorn main:app --host 127.0.0.1 --port 8010`
Expected: server starts with the worktree code.

**Step 2: Run the DNAJB2 Chinese sample**

Use the known Yiigle URL directly and submit it as a Chinese literature candidate.

Expected:
- no final `FULLTEXT_UNAVAILABLE`
- either `paper_status=success` or downstream extraction-specific failure

**Step 3: Run the ANK1 Chinese sample**

Use the known Hans URL directly and submit it as a Chinese literature candidate.

Expected:
- no final `FULLTEXT_UNAVAILABLE`
- either `paper_status=success` or downstream extraction-specific failure

**Step 4: Save runtime report**

Write a runtime-only acceptance report like:

```json
[
  {
    "name": "pubscholar-zh-dnajb2",
    "used_html_fallback": true,
    "paper_status": "success",
    "document_text_nonempty": true,
    "expected_gene_in_text": true
  }
]
```

Save to `/tmp/acmg_chinese_body_fallback_report.json`.

**Step 5: Commit only if code changed during validation**

If validation requires no additional code changes, do not commit.
If validation reveals one more focused code fix, commit only that fix.

## Final verification

Run:

```bash
uv run --project apps/backend pytest \
  apps/backend/tests/unit/test_coaj_service.py \
  apps/backend/tests/unit/test_chinese_fulltext_recovery.py \
  apps/backend/tests/unit/test_tasks.py -q
```

Expected: all recovery-agent and fallback tests PASS.

Then validate the two Chinese real samples only.

## Definition of done

This slice is done when:
1. Chinese PDF fallback can escalate to HTML body recovery
2. recovered markdown can continue through the existing processing pipeline
3. the two Chinese target samples no longer fail purely because no PDF could be acquired
