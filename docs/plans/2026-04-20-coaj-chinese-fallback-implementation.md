# COAJ Chinese Fulltext Fallback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add COAJ as a Chinese DOI fulltext fallback and Unpaywall as the all-language DOI fallback after primary download failure so the two Chinese target papers can progress beyond `FULLTEXT_UNAVAILABLE` into the existing parsing and extraction pipeline.

**Architecture:** Keep the change scoped to the download layer. Add one minimal COAJ DOI metadata helper under the backend literature API folder, then extend `apps/backend/src/services/task_manager.py` so `_try_download_and_store_literature_pdf(...)` tries the current primary provider first, then COAJ for Chinese DOI samples, then Unpaywall for any DOI sample. Do not modify literature candidate search, provider matrices, or frontend behavior in this slice.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, httpx, existing literature unified workflow, existing `process_pdf_task` pipeline, pytest.

---

### Task 1: Add COAJ DOI helper

**Files:**
- Create: `apps/backend/src/domain/literature/api/coaj/service.py`
- Test: `apps/backend/tests/unit/test_coaj_service.py`

**Step 1: Write the failing test**

```python
from src.domain.literature.api.coaj.service import extract_coaj_pdf_url


def test_extract_coaj_pdf_url_builds_absolute_url_from_relative_pdf_path() -> None:
    response = {
        "success": True,
        "data": {
            "article": {
                "doi": "10.12114/j.issn.1007-9572.2022.0859",
                "title": "中文文章",
                "pdfPath": "/1007-9572/3CDB12E30F6E4BBA9A6771699A85F3D8.pdf",
            }
        },
    }

    result = extract_coaj_pdf_url(response)

    assert result == "https://coaj.cn/1007-9572/3CDB12E30F6E4BBA9A6771699A85F3D8.pdf"
```

Add a second test for the HTTP helper:

```python
@pytest.mark.asyncio
async def test_lookup_article_basic_returns_pdf_url(monkeypatch):
    ...
```

Stub `httpx.AsyncClient.get(...)` to return a COAJ-style JSON payload and assert the helper returns:
- `success=True`
- `doi`
- `title`
- `pdf_url`
- `raw`

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_coaj_service.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.domain.literature.api.coaj.service'`

**Step 3: Write minimal implementation**

Create `apps/backend/src/domain/literature/api/coaj/service.py` with only the DOI lookup and URL normalization logic.

```python
from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urljoin

import httpx

COAJ_BASE_URL = "https://coaj.cn"
COAJ_ARTICLE_BASIC_URL = f"{COAJ_BASE_URL}/api/v1/open/article/basic"


def extract_coaj_pdf_url(payload: Dict[str, Any]) -> Optional[str]:
    article = (payload.get("data") or {}).get("article") or {}
    pdf_path = str(article.get("pdfPath") or "").strip()
    if not pdf_path:
        return None
    return urljoin(COAJ_BASE_URL + "/", pdf_path)


async def lookup_coaj_article_basic(doi: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.get(COAJ_ARTICLE_BASIC_URL, params={"doi": doi})
        response.raise_for_status()
        payload = response.json()

    article = (payload.get("data") or {}).get("article") or {}
    return {
        "success": bool(payload.get("success")) and bool(extract_coaj_pdf_url(payload)),
        "doi": str(article.get("doi") or doi),
        "title": article.get("title"),
        "pdf_url": extract_coaj_pdf_url(payload),
        "journal": ((payload.get("data") or {}).get("journal") or {}).get("titleZh"),
        "publisher": ((payload.get("data") or {}).get("journal") or {}).get("publisherZh"),
        "raw": payload,
    }
```

Do not add search behavior. This helper is download fallback only.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_coaj_service.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/domain/literature/api/coaj/service.py apps/backend/tests/unit/test_coaj_service.py
git commit -m "feat: add coaj doi fulltext lookup helper"
```

### Task 2: Add fallback-order tests around literature PDF download

**Files:**
- Modify: `apps/backend/tests/unit/test_tasks.py`
- Modify: `apps/backend/src/services/task_manager.py`

**Step 1: Write the failing test**

Add these four targeted tests to `apps/backend/tests/unit/test_tasks.py`.

```python
@pytest.mark.asyncio
async def test_try_download_prefers_coaj_for_chinese_doi_when_primary_fails(monkeypatch):
    ...
```

Arrange:
- stub `literature_unified_workflow(...)` to return no downloads
- stub new COAJ helper to return a PDF URL
- stub `_download_url_to_file(...)` to write a valid PDF
- stub `MinIOClient` upload calls

Assert:
- result `downloaded is True`
- result `provider == "coaj"`
- warnings contain a marker like `fallback:coaj`

Add three siblings:
1. Chinese DOI primary fail + COAJ fail + Unpaywall success
2. Non-Chinese DOI primary fail + Unpaywall success
3. No DOI primary fail -> no COAJ/Unpaywall call -> `pdf_not_found`

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_tasks.py -q -k "coaj or unpaywall_fallback or no_doi"`
Expected: FAIL because no COAJ fallback exists and fallback order is not implemented yet.

**Step 3: Write minimal implementation**

In `apps/backend/src/services/task_manager.py`, add a small internal helper to compute fallback URLs.

```python
async def _resolve_fallback_download_url(
    *,
    source: str,
    identifiers: List[str],
    query: str,
) -> tuple[Optional[str], Optional[str], List[str]]:
    warnings: List[str] = []
    doi = next((item for item in identifiers if str(item).lower().startswith("10.")), None)
    if not doi:
        return None, None, warnings

    if source == "pubscholar" or source == "hans_publishers" or any("zh" in str(item).lower() for item in identifiers):
        coaj_result = await lookup_coaj_article_basic(doi)
        if coaj_result.get("pdf_url"):
            warnings.append("fallback:coaj")
            return str(coaj_result["pdf_url"]), "coaj", warnings
        warnings.append("fallback:coaj_miss")

    unpaywall_result = await call_unpaywall(query=query, doi=doi, limit=1, raw=True)
    if unpaywall_result.downloads:
        fallback_url = _resolve_download_url(unpaywall_result.downloads)
        if fallback_url:
            warnings.append("fallback:unpaywall")
            return fallback_url, "unpaywall", warnings
    warnings.append("fallback:unpaywall_miss")
    return None, None, warnings
```

Then extend `_try_download_and_store_literature_pdf(...)` only after primary download resolution fails:

```python
if file_path is None:
    fallback_url, fallback_provider, fallback_warnings = await _resolve_fallback_download_url(...)
    warnings.extend(fallback_warnings)
    if fallback_url:
        candidate = download_dir / _safe_pdf_filename(fallback_provider or source, selected_title or document_id)
        ok, error = await _download_url_to_file(fallback_url, candidate)
        if ok and candidate.is_file():
            file_path = candidate
            provider = fallback_provider
        elif error:
            warnings.append(f"download_url_failed:{error}")
```

YAGNI rule: keep the language detection simple. For this slice, pass a new optional `language_hint` string into `_try_download_and_store_literature_pdf(...)` and use `language_hint.startswith("zh")` to decide whether COAJ should run first.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_tasks.py -q -k "coaj or unpaywall_fallback or no_doi"`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/services/task_manager.py apps/backend/tests/unit/test_tasks.py
git commit -m "fix: add coaj and unpaywall download fallbacks"
```

### Task 3: Thread Chinese language hint through DOI download calls

**Files:**
- Modify: `apps/backend/src/services/task_manager.py`
- Test: `apps/backend/tests/unit/test_tasks.py`

**Step 1: Write the failing test**

Add one focused test proving the Chinese DOI helper path passes `language_hint="zh"` from a Chinese literature candidate into `_try_download_and_store_literature_pdf(...)`.

```python
def test_process_literature_identifier_task_passes_language_hint_to_download(monkeypatch):
    captured = {}

    async def fake_download(**kwargs):
        captured.update(kwargs)
        return {"downloaded": False, "reason": "pdf_not_found"}
```

Assert `captured["language_hint"] == "zh"` when the candidate language is Chinese.

**Step 2: Run test to verify it fails**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_tasks.py -q -k language_hint`
Expected: FAIL because no language hint is passed yet.

**Step 3: Write minimal implementation**

Update `process_literature_identifier_task(...)`:

```python
language_hint = str(candidate.get("language") or candidate.get("lang") or "").strip().lower() or None
```

Pass that into `_try_download_and_store_literature_pdf(...)`.

Also update the helper signature:

```python
async def _try_download_and_store_literature_pdf(..., language_hint: Optional[str] = None)
```

Use the hint only to decide whether COAJ should be tried before Unpaywall.

**Step 4: Run test to verify it passes**

Run: `uv run --project apps/backend pytest apps/backend/tests/unit/test_tasks.py -q -k language_hint`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/backend/src/services/task_manager.py apps/backend/tests/unit/test_tasks.py
git commit -m "fix: pass chinese language hint into download fallbacks"
```

### Task 4: Validate the two Chinese real samples only

**Files:**
- No code changes required unless this validation reveals a new bug
- Output artifact: `/tmp/acmg_chinese_acceptance_report.json` (generated at runtime only, do not commit)

**Step 1: Run the first Chinese real sample**

Run a direct real validation for:
- DNAJB2 / `https://rs.yiigle.com/CN119999202201/1360483.htm`

Use the existing submit + direct processing pattern already exercised in prior validation work.

Expected success criteria:
- no `FULLTEXT_UNAVAILABLE`
- `paper_status` reaches `success` or at minimum document text becomes non-empty

**Step 2: Run the second Chinese real sample**

Run a direct real validation for:
- ANK1 / `https://image.hanspub.org/Html/77-1577845_75032.htm`

Expected success criteria:
- no `FULLTEXT_UNAVAILABLE`
- pipeline reaches parsing/extraction instead of stopping at download

**Step 3: Save runtime acceptance summary**

Create a runtime-only JSON summary like:

```json
[
  {
    "name": "pubscholar-zh-dnajb2",
    "download_stage": "coaj|unpaywall|primary",
    "paper_status": "success",
    "document_text_nonempty": true,
    "expected_gene_in_text": true
  }
]
```

Write it to `/tmp/acmg_chinese_acceptance_report.json`.

**Step 4: Verify both Chinese samples improved**

Run the validation script and inspect the output.
Expected:
- neither Chinese sample ends with `FULLTEXT_UNAVAILABLE`
- if still failing, the failure is now downstream and documented precisely

**Step 5: Commit only if code changed**

If validation required no extra code changes, do not create a commit.
If you needed one more code fix, make a focused commit for that fix only.

## Final verification

Run:

```bash
uv run --project apps/backend pytest \
  apps/backend/tests/unit/test_coaj_service.py \
  apps/backend/tests/unit/test_tasks.py \
  apps/backend/tests/integration/test_multilingual_literature_api.py -q
```

Expected: all COAJ / Unpaywall fallback and literature submit regression tests PASS.

Then run the two Chinese real validations only and confirm:
- the pipeline gets a usable fulltext input
- the failure mode, if any, has moved beyond fulltext acquisition

## Definition of done

This implementation slice is done when:
1. COAJ DOI lookup exists and returns usable PDF URLs when available
2. `_try_download_and_store_literature_pdf(...)` tries COAJ first for Chinese DOI samples after primary failure
3. `_try_download_and_store_literature_pdf(...)` tries Unpaywall after COAJ or directly for non-Chinese DOI samples
4. the two Chinese target papers no longer fail purely because of `FULLTEXT_UNAVAILABLE`
