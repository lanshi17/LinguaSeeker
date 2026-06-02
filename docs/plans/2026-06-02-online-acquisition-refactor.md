# Online Acquisition Refactor: Separate Link Acquisition from Download

**Status:** planned
**Created:** 2026-06-02

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the online acquisition module to cleanly separate link acquisition (search + Firecrawl) from file download (API OA resolution + direct HTTP), replacing 7 web providers with a single Firecrawl adapter using the adapter pattern.

**Architecture:** Three-phase pipeline — (1) parallel link acquisition from API providers + Firecrawl web search, basic dedup; (2) download by candidate type: DOI/PMID → API OA resolution → download, direct URL → HTTP download; (3) LLM content gate on downloaded PDFs. Rust handles HTTP I/O, Python handles orchestration and business logic.

**Tech Stack:** Python (asyncio, Pydantic, firecrawl-py), Rust (PyO3, reqwest, tokio), existing net-io crate.

---

## File Map

### New Files
| File | Purpose |
|---|---|
| `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web_search/__init__.py` | Module exports |
| `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web_search/adapter.py` | Abstract WebSearchAdapter ABC |
| `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web_search/firecrawl_adapter.py` | Firecrawl implementation |
| `backend/tests/test_web_search_adapter.py` | Adapter + Firecrawl tests |
| `backend/tests/test_download_phase.py` | Download phase tests |
| `backend/tests/test_workflow_refactored.py` | Refactored workflow integration tests |

### Modified Files
| File | Change |
|---|---|
| `backend/libs/net-io/src/client.rs` | Add `get_bytes()` method |
| `backend/libs/net-io/src/py.rs` | Add `download_file()` PyO3 binding |
| `backend/src/core/config.py` | Add `WebSearchConfig` |
| `backend/src/core/.../online_acquisition/contracts.py` | Deprecate WebProvider, update request/response |
| `backend/src/core/.../online_acquisition/workflow.py` | Rewrite: 3-phase pipeline |
| `backend/src/core/.../online_acquisition/gateway.py` | Split: search-only + resolve_oa_url + download_file |
| `backend/src/core/.../online_acquisition/search_service.py` | Remove LANG_PROVIDER_MATRIX web entries, simplify |
| `backend/src/core/.../online_acquisition/web_providers.py` | Deprecate (keep for backward compat) |
| `backend/src/core/.../online_acquisition/__init__.py` | Update exports |
| `backend/src/core/.../online_acquisition/normalizers.py` | Add `normalize_firecrawl` |
| `backend/tests/.../test_online_acquisition_gateway.py` | Update for new gateway API |
| `backend/tests/.../test_online_acquisition_workflow.py` | Update for new workflow |

### Unchanged Files
| File | Reason |
|---|---|
| `literature_type_classifier.py` | Already implemented, applied post-download |
| `provider_health.py` | Still used for API providers |
| `doi_fallback.py` | Still used as last-resort probe |
| `web/base.py` | Kept for backward compat, not used in new flow |
| `web/*.py` (individual providers) | Deprecated, not deleted |

---

## Task 1: Add `WebSearchConfig` to config.py

**Files:**
- Modify: `backend/src/core/config.py:185-192` (after LiteratureConfig)
- Test: manual — verify config loads from .env

**Step 1: Add WebSearchConfig class after LiteratureConfig**

In `backend/src/core/config.py`, after the `LiteratureConfig` class (line 192), add:

```python
class WebSearchConfig(BaseModel):
    """Web search provider configuration (adapter-based, currently Firecrawl)."""

    api_key: str = ""
    base_url: str = "https://api.firecrawl.dev"
    timeout: int = 30
    max_results: int = 10
```

**Step 2: Add flat env var fields to Settings**

In the `Settings` class, after the existing `LITERATURE_*` fields (around line 350), add:

```python
    # --- Web Search (Firecrawl-compatible) ---
    WEB_SEARCH_API_KEY: str = ""
    WEB_SEARCH_BASE_URL: str = "https://api.firecrawl.dev"
    WEB_SEARCH_TIMEOUT: int = 30
    WEB_SEARCH_MAX_RESULTS: int = 10
```

**Step 3: Add nested field to Settings**

After the `literature` nested field (around line 405), add:

```python
    web_search: WebSearchConfig = Field(default_factory=WebSearchConfig, exclude=True)
```

**Step 4: Wire up in `_build_nested` validator**

In the `_build_nested` method (around line 530), add:

```python
        data["web_search"] = WebSearchConfig(
            api_key=data.get("WEB_SEARCH_API_KEY", ""),
            base_url=data.get("WEB_SEARCH_BASE_URL", "https://api.firecrawl.dev") or "https://api.firecrawl.dev",
            timeout=int(data.get("WEB_SEARCH_TIMEOUT", 30) or 30),
            max_results=int(data.get("WEB_SEARCH_MAX_RESULTS", 10) or 10),
        )
```

**Step 5: Add to .env.example**

Append to `backend/.env.example`:

```env
# --- Web Search (Firecrawl) ---
WEB_SEARCH_API_KEY=
WEB_SEARCH_BASE_URL=https://api.firecrawl.dev
WEB_SEARCH_TIMEOUT=30
WEB_SEARCH_MAX_RESULTS=10
```

**Step 6: Verify config loads**

```bash
cd backend && python -c "from src.core.config import get_config; c = get_config(); print(c.web_search.api_key, c.web_search.base_url)"
```

Expected: prints empty key and default base URL.

**Step 7: Commit**

```bash
git add backend/src/core/config.py backend/.env.example
git commit -m "feat(config): add WebSearchConfig for Firecrawl adapter"
```

---

## Task 2: Create WebSearch Adapter Interface

**Files:**
- Create: `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web_search/__init__.py`
- Create: `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web_search/adapter.py`
- Test: `backend/tests/test_web_search_adapter.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_web_search_adapter.py
"""Tests for web search adapter interface."""

import pytest
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search.adapter import (
    SearchLink,
    WebSearchAdapter,
    WebSearchResult,
)


class TestSearchLink:
    def test_search_link_creation(self):
        link = SearchLink(url="https://example.com/paper.pdf", source="test", title="Test Paper")
        assert link.url == "https://example.com/paper.pdf"
        assert link.source == "test"
        assert link.title == "Test Paper"

    def test_search_link_optional_fields(self):
        link = SearchLink(url="https://example.com/paper.pdf")
        assert link.source is None
        assert link.title is None


class TestWebSearchResult:
    def test_web_search_result_creation(self):
        links = [SearchLink(url="https://example.com/1.pdf")]
        result = WebSearchResult(links=links, query="test query", provider="test")
        assert len(result.links) == 1
        assert result.query == "test query"
        assert result.warnings == []


class TestWebSearchAdapter:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            WebSearchAdapter(api_key="test")

    def test_subclass_must_implement(self):
        class IncompleteAdapter(WebSearchAdapter):
            pass

        with pytest.raises(TypeError):
            IncompleteAdapter(api_key="test")
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_web_search_adapter.py -v
```

Expected: FAIL — module not found.

**Step 3: Create `web_search/__init__.py`**

```python
# backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web_search/__init__.py
"""Web search adapter package — adapter pattern for pluggable search backends."""

from .adapter import SearchLink, WebSearchAdapter, WebSearchResult

__all__ = ["SearchLink", "WebSearchAdapter", "WebSearchResult"]
```

**Step 4: Create `web_search/adapter.py`**

```python
# backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web_search/adapter.py
"""Abstract web search adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class SearchLink:
    """A single candidate download link discovered by web search."""

    url: str
    source: Optional[str] = None
    title: Optional[str] = None
    doi: Optional[str] = None


@dataclass
class WebSearchResult:
    """Result container from a web search adapter."""

    links: List[SearchLink] = field(default_factory=list)
    query: str = ""
    provider: str = ""
    warnings: List[str] = field(default_factory=list)


class WebSearchAdapter(ABC):
    """Abstract base for web search backends.

    Implementations must provide ``search`` to discover candidate download
    links from a query string.  The adapter pattern allows swapping the
    underlying search engine (Firecrawl, Serper, Tavily, etc.) without
    changing downstream orchestration.
    """

    def __init__(self, *, api_key: str, base_url: str = "", timeout: int = 30, max_results: int = 10) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_results = max_results

    @abstractmethod
    async def search(self, query: str, *, language: Optional[str] = None) -> WebSearchResult:
        """Search the web for candidate download links.

        Args:
            query: Search query (literature title, keywords, etc.).
            language: Optional language hint (ISO 639-1 code).

        Returns:
            WebSearchResult with candidate links.
        """

    @abstractmethod
    async def scrape_links(self, url: str) -> List[SearchLink]:
        """Scrape a page for PDF/download links.

        Args:
            url: The page URL to scrape.

        Returns:
            List of discovered download links.
        """
```

**Step 5: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_web_search_adapter.py -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/src/core/.../online_acquisition/web_search/ backend/tests/test_web_search_adapter.py
git commit -m "feat(web-search): add abstract WebSearchAdapter interface"
```

---

## Task 3: Implement Firecrawl Adapter

**Files:**
- Create: `backend/src/core/.../online_acquisition/web_search/firecrawl_adapter.py`
- Modify: `backend/tests/test_web_search_adapter.py` (add Firecrawl tests)

**Step 1: Write the failing test**

Append to `backend/tests/test_web_search_adapter.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search.firecrawl_adapter import (
    FirecrawlAdapter,
)


class TestFirecrawlAdapter:
    def test_init_requires_api_key(self):
        """Adapter stores config."""
        adapter = FirecrawlAdapter(api_key="fc-test-key", base_url="https://api.firecrawl.dev", timeout=10, max_results=5)
        assert adapter.api_key == "fc-test-key"
        assert adapter.max_results == 5

    @pytest.mark.asyncio
    async def test_search_returns_links(self):
        """search() calls Firecrawl.search and returns SearchLink list."""
        adapter = FirecrawlAdapter(api_key="fc-test-key")

        mock_search_result = {
            "web": [
                {"url": "https://journal.com/article/1", "title": "Paper One"},
                {"url": "https://journal.com/article/2", "title": "Paper Two"},
            ]
        }

        with patch.object(adapter, "_client", new_callable=MagicMock) as mock_client:
            mock_client.search = AsyncMock(return_value=mock_search_result)
            result = await adapter.search("BRCA1 case report")

        assert result.provider == "firecrawl"
        assert len(result.links) == 2
        assert result.links[0].url == "https://journal.com/article/1"

    @pytest.mark.asyncio
    async def test_search_handles_empty_results(self):
        adapter = FirecrawlAdapter(api_key="fc-test-key")

        with patch.object(adapter, "_client", new_callable=MagicMock) as mock_client:
            mock_client.search = AsyncMock(return_value={"web": []})
            result = await adapter.search("nonexistent query")

        assert result.links == []
        assert result.provider == "firecrawl"

    @pytest.mark.asyncio
    async def test_search_handles_api_error(self):
        adapter = FirecrawlAdapter(api_key="fc-bad-key")

        with patch.object(adapter, "_client", new_callable=MagicMock) as mock_client:
            mock_client.search = AsyncMock(side_effect=Exception("API Error"))
            result = await adapter.search("test query")

        assert result.links == []
        assert len(result.warnings) == 1
        assert "firecrawl" in result.warnings[0].lower()

    @pytest.mark.asyncio
    async def test_scrape_links_extracts_pdf_urls(self):
        adapter = FirecrawlAdapter(api_key="fc-test-key")

        mock_scrape_result = {
            "markdown": '[Download PDF](https://journal.com/paper.pdf)\n<a href="https://journal.com/full.pdf">Full text</a>',
            "metadata": {"source_url": "https://journal.com/article/1"},
        }

        with patch.object(adapter, "_client", new_callable=MagicMock) as mock_client:
            mock_client.scrape = AsyncMock(return_value=mock_scrape_result)
            links = await adapter.scrape_links("https://journal.com/article/1")

        assert len(links) >= 1
        assert any(".pdf" in link.url for link in links)
```

**Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_web_search_adapter.py::TestFirecrawlAdapter -v
```

Expected: FAIL — module not found.

**Step 3: Implement `firecrawl_adapter.py`**

```python
# backend/src/core/.../online_acquisition/web_search/firecrawl_adapter.py
"""Firecrawl-based web search adapter."""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from .adapter import SearchLink, WebSearchAdapter, WebSearchResult

logger = logging.getLogger(__name__)

# Regex patterns for extracting PDF links from scraped markdown/HTML
_PDF_URL_PATTERN = re.compile(
    r'https?://[^\s"\'<>]+\.pdf(?:[^\s"\'<>]*)',
    re.IGNORECASE,
)
_PDF_LINK_PATTERN = re.compile(
    r'\[([^\]]*)\]\((https?://[^\s"\'<>)]+\.pdf[^\s"\'<>)]*)\)',
    re.IGNORECASE,
)
_HREF_PDF_PATTERN = re.compile(
    r'href=["\']?(https?://[^\s"\'<>"\']+\.pdf[^\s"\'<>"\']*)',
    re.IGNORECASE,
)


class FirecrawlAdapter(WebSearchAdapter):
    """Web search adapter using Firecrawl's search + scrape APIs.

    Environment:
        ``WEB_SEARCH_API_KEY`` — Firecrawl API key (``fc-...``).
        ``WEB_SEARCH_BASE_URL`` — optional, defaults to ``https://api.firecrawl.dev``.
    """

    def __init__(self, *, api_key: str, base_url: str = "", timeout: int = 30, max_results: int = 10) -> None:
        super().__init__(api_key=api_key, base_url=base_url, timeout=timeout, max_results=max_results)
        self._client = None  # lazy-init

    def _get_client(self):
        """Lazy-init the AsyncFirecrawl client."""
        if self._client is None:
            from firecrawl import AsyncFirecrawl

            kwargs = {"api_key": self.api_key}
            if self.base_url and self.base_url != "https://api.firecrawl.dev":
                kwargs["api_url"] = self.base_url
            self._client = AsyncFirecrawl(**kwargs)
        return self._client

    async def search(self, query: str, *, language: Optional[str] = None) -> WebSearchResult:
        """Search via Firecrawl and scrape each result for PDF links."""
        warnings: list[str] = []
        all_links: list[SearchLink] = []

        try:
            client = self._get_client()
            result = await client.search(query, limit=self.max_results)

            web_results = result.get("web", []) if isinstance(result, dict) else []
            for item in web_results:
                url = item.get("url", "")
                title = item.get("title", "")
                if not url:
                    continue

                # Add the search result URL itself as a candidate
                all_links.append(SearchLink(url=url, source="firecrawl-search", title=title or None))

        except Exception as exc:
            msg = f"firecrawl search failed: {exc}"
            logger.warning(msg)
            warnings.append(msg)

        return WebSearchResult(
            links=all_links,
            query=query,
            provider="firecrawl",
            warnings=warnings,
        )

    async def scrape_links(self, url: str) -> List[SearchLink]:
        """Scrape a page for PDF download links using Firecrawl."""
        links: list[SearchLink] = []
        try:
            client = self._get_client()
            result = await client.scrape(url, formats=["markdown"])

            markdown = result.get("markdown", "") if isinstance(result, dict) else ""
            if not markdown:
                return links

            # Extract PDF URLs from markdown content
            seen: set[str] = set()

            # Match markdown links to PDFs
            for match in _PDF_LINK_PATTERN.finditer(markdown):
                pdf_url = match.group(2)
                if pdf_url not in seen:
                    seen.add(pdf_url)
                    links.append(SearchLink(url=pdf_url, source="firecrawl-scrape"))

            # Match href attributes to PDFs
            for match in _HREF_PDF_PATTERN.finditer(markdown):
                pdf_url = match.group(1)
                if pdf_url not in seen:
                    seen.add(pdf_url)
                    links.append(SearchLink(url=pdf_url, source="firecrawl-scrape"))

            # Fallback: bare PDF URLs
            for match in _PDF_URL_PATTERN.finditer(markdown):
                pdf_url = match.group(0)
                if pdf_url not in seen:
                    seen.add(pdf_url)
                    links.append(SearchLink(url=pdf_url, source="firecrawl-scrape"))

        except Exception as exc:
            logger.warning("firecrawl scrape failed for %s: %s", url, exc)

        return links
```

**Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_web_search_adapter.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/core/.../online_acquisition/web_search/firecrawl_adapter.py backend/tests/test_web_search_adapter.py
git commit -m "feat(web-search): implement Firecrawl adapter with search + scrape"
```

---

## Task 4: Add `get_bytes()` and `download_file()` to Rust net-io

**Files:**
- Modify: `backend/libs/net-io/src/client.rs:21-173`
- Modify: `backend/libs/net-io/src/py.rs:14-30, 264-330`

**Step 1: Add `get_bytes()` to HttpClient**

In `backend/libs/net-io/src/client.rs`, after `get_text()` (line 100), add:

```rust
    /// GET raw bytes with retry. Returns (bytes, final_url, status_code).
    pub async fn get_bytes(&self, url: &str) -> Result<(Vec<u8>, String, u16), GatewayError> {
        let mut last_err = None;
        for attempt in 1..=self.max_retries {
            match self.inner.get(url).send().await {
                Ok(resp) => {
                    let status = resp.status().as_u16();
                    let final_url = resp.url().to_string();
                    if resp.status().is_success() {
                        let bytes = resp.bytes().await
                            .map_err(|e| GatewayError::Other(format!("bytes read failed: {e}")))?;
                        return Ok((bytes.to_vec(), final_url, status));
                    }
                    last_err = Some(GatewayError::Other(format!("HTTP {status}")));
                }
                Err(e) => {
                    last_err = Some(GatewayError::Http(e.to_string()));
                }
            }
            if attempt < self.max_retries {
                tokio::time::sleep(retry_backoff(attempt)).await;
            }
        }
        Err(last_err.unwrap_or_else(|| GatewayError::Other("unknown error".into())))
    }
```

**Step 2: Add `download_file()` PyO3 function**

In `backend/libs/net-io/src/py.rs`, add a new function after `scrape_web` (around line 130):

```rust
/// Download a file from a URL. Returns dict with `bytes`, `final_url`, `status_code`.
#[pyfunction]
#[pyo3(signature = (url, timeout_ms=None, max_retries=None, proxy=None))]
fn download_file<'py>(
    url: String,
    timeout_ms: Option<u64>,
    max_retries: Option<u32>,
    proxy: Option<String>,
) -> PyResult<Bound<'py, PyAny>> {
    pyo3_async_runtimes::tokio::future_into_py(async move {
        let client = HttpClient::new(timeout_ms, max_retries, proxy)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let (bytes, final_url, status_code) = client
            .get_bytes(&url)
            .await
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))?;
        Ok(serde_json::json!({
            "bytes": bytes,
            "final_url": final_url,
            "status_code": status_code,
        }))
    })
}
```

**Step 3: Register `download_file` in PyModule**

In the `#[pymodule]` function (line 14), add after `scrape_web`:

```rust
    m.add_function(wrap_pyfunction!(download_file, m)?)?;
```

**Step 4: Build and test**

```bash
cd backend/libs/net-io && maturin develop --release
cd backend && python -c "
import asyncio
from src.utils.rust_io import net_io
async def test():
    # Test with a known PDF URL
    result = await net_io.download_file('https://arxiv.org/pdf/2301.00001v1')
    print(f'status={result[\"status_code\"]}, bytes_len={len(result[\"bytes\"])}')
asyncio.run(test())
"
```

Expected: status=200 (or 302 redirect handled), bytes starting with `%PDF`.

**Step 5: Commit**

```bash
git add backend/libs/net-io/src/client.rs backend/libs/net-io/src/py.rs
git commit -m "feat(rust-io): add get_bytes() and download_file() for direct PDF download"
```

---

## Task 5: Refactor gateway.py — Split into search-only + download helpers

**Files:**
- Modify: `backend/src/core/.../online_acquisition/gateway.py`

**Step 1: Add `download_file_from_url()` function**

After `_download_pdf_from_candidates` (line 125), add a new function that downloads a single URL directly:

```python
async def download_file_from_url(
    url: str,
    download_path: str,
    filename_stem: str,
) -> Tuple[Optional[str], Optional[str], List[str]]:
    """Download a file from a direct URL. Validates %PDF magic bytes.

    Args:
        url: Direct download URL.
        download_path: Directory to save the file.
        filename_stem: Base filename (without extension).

    Returns:
        (file_path, final_url, warnings) tuple.
    """
    warnings: List[str] = []
    try:
        if net_io is not None:
            result = await net_io.download_file(url, timeout_ms=30_000)
            status = result.get("status_code", 0)
            file_bytes = result.get("bytes", b"")
            final_url = result.get("final_url", url)

            if status < 200 or status >= 400:
                warnings.append(f"download_http_{status}")
                return None, final_url, warnings

            if not file_bytes or not file_bytes[:4] == b"%PDF":
                warnings.append("not_pdf_content")
                return None, final_url, warnings

            Path(download_path).mkdir(parents=True, exist_ok=True)
            file_path = str(Path(download_path) / f"{sanitize_filename(filename_stem)}.pdf")
            Path(file_path).write_bytes(file_bytes)
            return file_path, final_url, warnings
        else:
            # Fallback: httpx
            async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
                resp = await client.get(url)
                if resp.status_code >= 400:
                    warnings.append(f"download_http_{resp.status_code}")
                    return None, str(resp.url), warnings
                if not resp.content[:4] == b"%PDF":
                    warnings.append("not_pdf_content")
                    return None, str(resp.url), warnings
                Path(download_path).mkdir(parents=True, exist_ok=True)
                file_path = str(Path(download_path) / f"{sanitize_filename(filename_stem)}.pdf")
                Path(file_path).write_bytes(resp.content)
                return file_path, str(resp.url), warnings
    except Exception as exc:
        warnings.append(f"download_error: {exc}")
        return None, url, warnings
```

**Step 2: Add `resolve_oa_url()` function**

After the new `download_file_from_url`, add:

```python
def resolve_oa_url(result: OnlineAcquisitionGatewayResult) -> Optional[str]:
    """Extract OA download URL from a gateway result.

    Inspects result.downloads for pdf_url entries (returned by unpaywall, doaj, etc.)
    and result.items for embedded download links (e.g., europepmc fullTextUrlList).
    """
    # Check downloads first (unpaywall, doaj, jstage pattern)
    for dl in result.downloads:
        if isinstance(dl, dict):
            url = dl.get("pdf_url") or dl.get("url")
            if url:
                return url

    # Check items for embedded URLs (europepmc fullTextUrlList, crossref link)
    for item in result.items:
        if not isinstance(item, dict):
            continue
        # EuropePMC fullTextUrlList
        ftl = item.get("fullTextUrlList")
        if isinstance(ftl, dict):
            for ft in ftl.get("fullTextUrl", []):
                if isinstance(ft, dict) and ft.get("documentStyle") == "pdf":
                    return ft.get("url")
        # Crossref link array
        links = item.get("link")
        if isinstance(links, list):
            for link in links:
                if isinstance(link, dict) and link.get("content-type") == "application/pdf":
                    return link.get("URL")
        # PMC pmcid → construct URL
        pmcid = item.get("pmcid")
        if isinstance(pmcid, str) and pmcid.startswith("PMC"):
            return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"

    return None
```

**Step 3: Keep existing `search_provider()` unchanged**

The existing `search_provider()` (line 264) stays as-is — it calls `call_provider_with_retry` with `action="search"`.

**Step 4: Deprecate `download_from_provider()`**

Add a deprecation warning to `download_from_provider()` (line 285):

```python
import warnings as _warnings

def download_from_provider(...):
    _warnings.warn(
        "download_from_provider is deprecated; use search_provider + resolve_oa_url + download_file_from_url",
        DeprecationWarning,
        stacklevel=2,
    )
    # ... existing implementation unchanged ...
```

**Step 5: Commit**

```bash
git add backend/src/core/.../online_acquisition/gateway.py
git commit -m "refactor(gateway): split into search-only + resolve_oa_url + download_file_from_url"
```

---

## Task 6: Add `normalize_firecrawl` to normalizers.py

**Files:**
- Modify: `backend/src/core/.../online_acquisition/normalizers.py:644-670`

**Step 1: Add firecrawl normalizer function**

Before `NORMALIZER_MAP` (line 644), add:

```python
def normalize_firecrawl(item: Dict[str, Any]) -> OnlineAcquisitionItem:
    """Normalize a Firecrawl search result into an OnlineAcquisitionItem."""
    return OnlineAcquisitionItem(
        source="firecrawl",
        title=_clean_text(item.get("title")),
        authors=[],
        journal=None,
        year=None,
        doi=_clean_text(item.get("doi")),
        url=_clean_text(item.get("url")),
        links=[u for u in [item.get("url")] if u],
        language=None,
        publisher=None,
        issn=None,
        identifiers=[],
        keywords=[],
        literature_type=None,
    )
```

**Step 2: Register in NORMALIZER_MAP**

Add `"firecrawl": normalize_firecrawl` to the `NORMALIZER_MAP` dict (line 644).

**Step 3: Commit**

```bash
git add backend/src/core/.../online_acquisition/normalizers.py
git commit -m "feat(normalizers): add firecrawl normalizer"
```

---

## Task 7: Update contracts.py

**Files:**
- Modify: `backend/src/core/.../online_acquisition/contracts.py`

**Step 1: Deprecate WebProvider fields (keep for backward compat)**

Add deprecation comments to `WebProvider` (line 16), `web_provider` (line 39), and `web_params` (line 42). No code deletion — just mark as deprecated.

**Step 2: Add `candidate_links` field to OnlineAcquisitionResponse**

In `OnlineAcquisitionResponse` (line 111), add a new field:

```python
    candidate_links: List[Dict[str, Any]] = Field(default_factory=list, description="All candidate download links before download")
```

**Step 3: Commit**

```bash
git add backend/src/core/.../online_acquisition/contracts.py
git commit -m "refactor(contracts): deprecate WebProvider, add candidate_links to response"
```

---

## Task 8: Rewrite workflow.py — Three-phase pipeline

**Files:**
- Modify: `backend/src/core/.../online_acquisition/workflow.py`

This is the largest change. The new workflow has three distinct phases.

**Step 1: Update imports**

Replace the existing imports (lines 1-21) with:

```python
"""Online acquisition workflow — three-phase pipeline.

Phase 1 (Link Acquisition): Parallel search from API providers + Firecrawl.
Phase 2 (Download): Route candidates by type — DOI/PMID → OA API, direct URL → HTTP.
Phase 3 (Gate): LLM classification on downloaded PDF content.
"""

import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Optional

from .contracts import (
    OnlineAcquisitionGatewayResult,
    OnlineAcquisitionItem,
    OnlineAcquisitionRequest,
    OnlineAcquisitionResponse,
    OnlineAcquisitionRouteInfo,
    OnlineAcquisitionSourceTraceEntry,
)
from .gateway import (
    _normalize_doi,
    call_provider,
    download_file_from_url,
    resolve_oa_url,
    search_provider,
)
from .literature_type_classifier import LiteratureType, classify_item
from .normalizers import normalize_items
from .provider_health import get_health_tracker
from .web_search import SearchLink

logger = logging.getLogger(__name__)
```

**Step 2: Keep helper functions**

Keep `_extract_identifiers` (line 35), `_build_query` (line 78), `_build_gateway_identifiers` (line 84), `_resolve_language` (line 88). Remove `_select_initial_provider`, `_build_provider_chain` (replaced by parallel search).

**Step 3: Define `_acquire_links_api()` — parallel API provider search**

```python
# API providers to search (order matters for result priority)
_API_SEARCH_PROVIDERS = [
    "crossref", "unpaywall", "openalex", "europepmc", "pmc",
    "doaj", "jstage", "arxiv", "biorxiv", "medrxiv",
    "scielo", "base", "core", "openaire", "cinii",
]

# Identifier-specific provider overrides
_ID_PROVIDER_MAP: Dict[str, List[str]] = {
    "doi": ["crossref", "unpaywall", "openalex", "europepmc"],
    "pmid": ["pmc", "europepmc"],
    "pmcid": ["pmc"],
}


async def _acquire_links_api(
    *,
    query: str,
    identifiers: Dict[str, Optional[str]],
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Phase 1a: Search API providers in parallel, return raw items with metadata."""
    doi = identifiers.get("doi")
    pmid = identifiers.get("pmid")
    pmcid = identifiers.get("pmcid")

    # Select providers based on available identifiers
    if doi:
        providers = _ID_PROVIDER_MAP["doi"]
    elif pmid or pmcid:
        providers = _ID_PROVIDER_MAP.get("pmid" if pmid else "pmcid", ["pmc"])
    else:
        providers = _API_SEARCH_PROVIDERS

    # Build identifier params for Rust
    id_params = {k: v for k, v in identifiers.items() if v}

    async def _search_one(provider: str) -> Optional[OnlineAcquisitionGatewayResult]:
        try:
            return search_provider(
                provider=provider,
                query=query,
                identifiers=id_params,
                limit=limit,
                raw=False,
                params={},
            )
        except Exception as exc:
            logger.debug("api search %s failed: %s", provider, exc)
            return None

    # Parallel search across all providers
    results = await asyncio.gather(*[_search_one(p) for p in providers])

    # Collect all raw items with provider tag
    all_items: List[Dict[str, Any]] = []
    for result in results:
        if result and result.success:
            for item in result.items:
                if isinstance(item, dict):
                    item["_source_provider"] = result.provider
                    all_items.append(item)

    return all_items
```

**Step 4: Define `_acquire_links_firecrawl()` — web search**

```python
async def _acquire_links_firecrawl(
    *,
    query: str,
    language: Optional[str] = None,
) -> List[SearchLink]:
    """Phase 1b: Search via Firecrawl adapter."""
    from .web_search.firecrawl_adapter import FirecrawlAdapter

    from src.core.config import get_config
    cfg = get_config()
    if not cfg.web_search.api_key:
        logger.info("web search skipped: no WEB_SEARCH_API_KEY configured")
        return []

    adapter = FirecrawlAdapter(
        api_key=cfg.web_search.api_key,
        base_url=cfg.web_search.base_url,
        timeout=cfg.web_search.timeout,
        max_results=cfg.web_search.max_results,
    )

    result = await adapter.search(query, language=language)
    if result.warnings:
        for w in result.warnings:
            logger.warning("firecrawl: %s", w)

    # Scrape each result page for PDF links
    all_links = list(result.links)
    scrape_tasks = [adapter.scrape_links(link.url) for link in result.links[:5]]  # limit scrape concurrency
    scrape_results = await asyncio.gather(*scrape_tasks, return_exceptions=True)
    for sr in scrape_results:
        if isinstance(sr, list):
            all_links.extend(sr)

    return all_links
```

**Step 5: Define `_merge_and_dedupe()` — basic dedup**

```python
def _merge_and_dedupe(
    api_items: List[Dict[str, Any]],
    firecrawl_links: List[SearchLink],
) -> List[Dict[str, Any]]:
    """Merge API items and Firecrawl links, deduplicate by DOI/URL/title."""
    seen_dois: set[str] = set()
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    merged: List[Dict[str, Any]] = []

    def _norm_title(t: Optional[str]) -> str:
        if not t:
            return ""
        return re.sub(r"[^\w\s]", "", t.lower()).strip()

    # Process API items first (higher priority)
    for item in api_items:
        doi = (item.get("doi") or item.get("DOI") or "").strip().lower()
        url = (item.get("url") or item.get("URL") or item.get("link") or "").strip()
        title = _norm_title(item.get("title") or item.get("article_title"))

        if doi and doi in seen_dois:
            continue
        if url and url in seen_urls:
            continue
        if title and title in seen_titles:
            continue

        if doi:
            seen_dois.add(doi)
        if url:
            seen_urls.add(url)
        if title:
            seen_titles.add(title)

        item["_candidate_type"] = "api"
        merged.append(item)

    # Process Firecrawl links
    for link in firecrawl_links:
        url = link.url.strip()
        if url in seen_urls:
            continue
        seen_urls.add(url)

        merged.append({
            "url": url,
            "title": link.title or "",
            "doi": link.doi or "",
            "_source_provider": link.source or "firecrawl",
            "_candidate_type": "firecrawl",
        })

    return merged
```

**Step 6: Define `_download_candidates()` — Phase 2 download**

```python
async def _download_candidates(
    candidates: List[Dict[str, Any]],
    download_path: str,
) -> List[Dict[str, Any]]:
    """Phase 2: Download files from candidate links.

    Routing:
    - DOI present → call unpaywall to resolve OA URL → download
    - PMID present → call pmc to get pmcid → construct PMC PDF URL → download
    - Direct PDF URL → HTTP GET download
    - Other URL → skip (link acquisition already handled)
    """
    downloads: List[Dict[str, Any]] = []

    async def _download_one(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        doi = candidate.get("doi") or candidate.get("DOI")
        pmid = candidate.get("pmid") or candidate.get("identifiers", {}).get("pmid") if isinstance(candidate.get("identifiers"), dict) else None
        pmcid = candidate.get("pmcid")
        url = candidate.get("url") or candidate.get("URL")
        title = candidate.get("title", "untitled")
        filename_stem = re.sub(r"[^\w\-]", "_", title)[:80] if title else "untitled"

        # Route 1: DOI → unpaywall OA resolution
        if doi:
            try:
                id_params = {"doi": doi}
                result = search_provider(
                    provider="unpaywall",
                    query="",
                    identifiers=id_params,
                    limit=1,
                    raw=False,
                    params={},
                )
                oa_url = resolve_oa_url(result)
                if oa_url:
                    file_path, final_url, warns = await download_file_from_url(
                        oa_url, download_path, filename_stem
                    )
                    if file_path:
                        return {
                            "file_path": file_path,
                            "source": "unpaywall",
                            "doi": doi,
                            "url": final_url,
                            "warnings": warns,
                        }
            except Exception as exc:
                logger.debug("unpaywall download failed for %s: %s", doi, exc)

        # Route 2: PMCID → PMC direct PDF URL
        if pmcid:
            pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
            file_path, final_url, warns = await download_file_from_url(
                pdf_url, download_path, filename_stem
            )
            if file_path:
                return {
                    "file_path": file_path,
                    "source": "pmc",
                    "pmcid": pmcid,
                    "url": final_url,
                    "warnings": warns,
                }

        # Route 3: Direct URL (looks like PDF or is a known download URL)
        if url:
            file_path, final_url, warns = await download_file_from_url(
                url, download_path, filename_stem
            )
            if file_path:
                return {
                    "file_path": file_path,
                    "source": candidate.get("_source_provider", "direct"),
                    "url": final_url,
                    "warnings": warns,
                }

        return None

    # Download all candidates (parallel, no retry per user request)
    results = await asyncio.gather(*[_download_one(c) for c in candidates])
    downloads = [r for r in results if r is not None]

    # Hash dedup (if hash utils available)
    # Note: existing hash dedup from upload flow can be applied downstream

    return downloads
```

**Step 7: Rewrite `online_acquisition_workflow()`**

```python
async def online_acquisition_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Main entry point — three-phase online acquisition pipeline.

    Phase 1: Parallel link acquisition (API providers + Firecrawl).
    Phase 2: Download by candidate type (DOI→OA, PMCID→PMC, URL→direct).
    Phase 3: LLM content gate on downloaded PDFs.
    """
    # --- Validate request ---
    request = OnlineAcquisitionRequest(**payload)
    query = _build_query(request)
    identifiers = _extract_identifiers(request.identifiers + ([request.query] if request.query else []))
    language = _resolve_language(request, identifiers)

    route = OnlineAcquisitionRouteInfo(
        prefer=request.prefer,
        api_provider=request.api_provider,
        web_provider=request.web_provider,
        used="api",
        reason="parallel_acquisition",
        fallback_used=False,
    )
    warnings: List[str] = []
    traces: List[OnlineAcquisitionSourceTraceEntry] = []

    download_path = request.download_path
    if language:
        download_path = os.path.join(download_path, language)

    # === Phase 1: Link Acquisition (parallel) ===
    id_params = _build_gateway_identifiers(identifiers)

    # Run API + Firecrawl in parallel
    api_task = _acquire_links_api(query=query, identifiers=ident_params, limit=request.limit)
    firecrawl_task = _acquire_links_firecrawl(query=query, language=language)

    api_items, firecrawl_links = await asyncio.gather(api_task, firecrawl_task)

    # Merge and deduplicate
    candidates = _merge_and_dedupe(api_items, firecrawl_links)

    if not candidates:
        warnings.append("FETCH_NO_RESULT: no candidates from any source")
        return OnlineAcquisitionResponse(
            success=False,
            items=[],
            downloads=[],
            warnings=warnings,
            route=route,
            candidate_links=[],
        ).model_dump()

    # Normalize API items into OnlineAcquisitionItem for response
    normalized_items: List[OnlineAcquisitionItem] = []
    for item in candidates:
        provider = item.get("_source_provider", "unknown")
        try:
            normalized = normalize_items(provider, [item])
            normalized_items.extend(normalized)
        except Exception:
            # Firecrawl items go through firecrawl normalizer
            try:
                normalized = normalize_items("firecrawl", [item])
                normalized_items.extend(normalized)
            except Exception:
                pass

    # Apply literature type filter (metadata-level)
    if request.literature_types:
        typed_items = []
        for ni in normalized_items:
            lt = classify_item(ni)
            ni.literature_type = lt.value if lt else None
            if lt and lt.value in request.literature_types:
                typed_items.append(ni)
        normalized_items = typed_items

    # === Search-only mode: return metadata ===
    if request.action == "search":
        return OnlineAcquisitionResponse(
            success=bool(normalized_items),
            items=normalized_items,
            downloads=[],
            warnings=warnings,
            route=route,
            candidate_links=[{k: v for k, v in c.items() if not k.startswith("_")} for c in candidates],
        ).model_dump()

    # === Phase 2: Download ===
    downloads = await _download_candidates(candidates, download_path)

    if not downloads:
        warnings.append("FULLTEXT_UNAVAILABLE: no files downloaded")

    # === Phase 3: LLM Content Gate ===
    # Classification on downloaded PDF content (if needed)
    # Currently keyword-based on title/journal; PDF content classification
    # can be added as a future enhancement.

    return OnlineAcquisitionResponse(
        success=bool(downloads),
        items=normalized_items,
        downloads=downloads,
        warnings=warnings,
        route=route,
        candidate_links=[{k: v for k, v in c.items() if not k.startswith("_")} for c in candidates],
    ).model_dump()
```

**Step 8: Update `__init__.py` exports**

In `backend/src/core/.../online_acquisition/__init__.py`, add:
- `from .web_search import SearchLink, WebSearchAdapter, WebSearchResult`
- `from .gateway import download_file_from_url, resolve_oa_url`

**Step 9: Commit**

```bash
git add backend/src/core/.../online_acquisition/workflow.py backend/src/core/.../online_acquisition/__init__.py
git commit -m "refactor(workflow): three-phase pipeline — parallel link acquisition, download, LLM gate"
```

---

## Task 9: Update search_service.py — Remove web provider routing

**Files:**
- Modify: `backend/src/core/.../online_acquisition/search_service.py`

**Step 1: Remove web provider entries from LANG_PROVIDER_MATRIX**

In `LANG_PROVIDER_MATRIX` (lines 24-78), remove all `{"route": "web", "provider": ...}` entries. Keep only `{"route": "api", "provider": ...}` entries. The matrix now only controls API provider ordering by language.

Updated matrix:

```python
LANG_PROVIDER_MATRIX: Dict[str, List[ProviderPlanItem]] = {
    "zh": [
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
        {"route": "api", "provider": "pmc"},
    ],
    "ja": [
        {"route": "api", "provider": "jstage"},
        {"route": "api", "provider": "cinii"},
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
        {"route": "api", "provider": "pmc"},
    ],
    "ko": [
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
    ],
    "es": [
        {"route": "api", "provider": "scielo"},
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
    ],
    "pt": [
        {"route": "api", "provider": "scielo"},
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
    ],
    "en": [
        {"route": "api", "provider": "pmc"},
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "arxiv"},
        {"route": "api", "provider": "biorxiv"},
        {"route": "api", "provider": "medrxiv"},
        {"route": "api", "provider": "openaire"},
        {"route": "api", "provider": "base"},
        {"route": "api", "provider": "core"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
    ],
    "auto": [
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
        {"route": "api", "provider": "pmc"},
    ],
}
```

**Step 2: Update `search_multilingual` to remove web provider handling**

In `search_multilingual` (line 222), remove the branch that handles `route == "web"` (lines ~250-260). All providers in the matrix are now API-only.

**Step 3: Commit**

```bash
git add backend/src/core/.../online_acquisition/search_service.py
git commit -m "refactor(search-service): remove web provider routing from LANG_PROVIDER_MATRIX"
```

---

## Task 10: Deprecate web_providers.py

**Files:**
- Modify: `backend/src/core/.../online_acquisition/web_providers.py`

**Step 1: Add module-level deprecation warning**

At the top of `web_providers.py` (after imports), add:

```python
import warnings

warnings.warn(
    "web_providers is deprecated; use web_search.firecrawl_adapter.FirecrawlAdapter instead",
    DeprecationWarning,
    stacklevel=2,
)
```

**Step 2: Keep all existing code unchanged**

Do not delete any code — existing callers may still depend on it.

**Step 3: Commit**

```bash
git add backend/src/core/.../online_acquisition/web_providers.py
git commit -m "refactor(web-providers): deprecate in favor of Firecrawl adapter"
```

---

## Task 11: Write integration tests

**Files:**
- Create: `backend/tests/test_download_phase.py`
- Create: `backend/tests/test_workflow_refactored.py`

**Step 1: Write download phase tests**

```python
# backend/tests/test_download_phase.py
"""Tests for the download phase of the refactored workflow."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestResolveOaUrl:
    def test_resolve_from_unpaywall_downloads(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import resolve_oa_url
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
            OnlineAcquisitionGatewayResult,
        )

        result = OnlineAcquisitionGatewayResult(
            provider="unpaywall",
            success=True,
            items=[{"best_oa_location": {"url_for_pdf": "https://example.com/paper.pdf"}}],
            downloads=[{"pdf_url": "https://example.com/paper.pdf"}],
            warnings=[],
            raw=None,
            meta=None,
            source_trace=[],
        )
        url = resolve_oa_url(result)
        assert url == "https://example.com/paper.pdf"

    def test_resolve_from_pmcid(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import resolve_oa_url
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
            OnlineAcquisitionGatewayResult,
        )

        result = OnlineAcquisitionGatewayResult(
            provider="pmc",
            success=True,
            items=[{"pmcid": "PMC1234567", "title": "Test"}],
            downloads=[],
            warnings=[],
            raw=None,
            meta=None,
            source_trace=[],
        )
        url = resolve_oa_url(result)
        assert url == "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1234567/pdf/"

    def test_resolve_returns_none_when_no_url(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import resolve_oa_url
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
            OnlineAcquisitionGatewayResult,
        )

        result = OnlineAcquisitionGatewayResult(
            provider="crossref",
            success=True,
            items=[{"title": "No URL paper"}],
            downloads=[],
            warnings=[],
            raw=None,
            meta=None,
            source_trace=[],
        )
        url = resolve_oa_url(result)
        assert url is None


class TestDownloadFileFromUrl:
    @pytest.mark.asyncio
    async def test_download_validates_pdf_magic(self, tmp_path):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import download_file_from_url

        with patch("src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway.net_io") as mock_net:
            mock_net.download_file = AsyncMock(return_value={
                "bytes": b"%PDF-1.4 fake content",
                "final_url": "https://example.com/paper.pdf",
                "status_code": 200,
            })
            file_path, final_url, warnings = await download_file_from_url(
                "https://example.com/paper.pdf", str(tmp_path), "test_paper"
            )

        assert file_path is not None
        assert file_path.endswith(".pdf")
        assert warnings == []

    @pytest.mark.asyncio
    async def test_download_rejects_non_pdf(self, tmp_path):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import download_file_from_url

        with patch("src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway.net_io") as mock_net:
            mock_net.download_file = AsyncMock(return_value={
                "bytes": b"<html>Not a PDF</html>",
                "final_url": "https://example.com/page.html",
                "status_code": 200,
            })
            file_path, final_url, warnings = await download_file_from_url(
                "https://example.com/page.html", str(tmp_path), "test_paper"
            )

        assert file_path is None
        assert "not_pdf_content" in warnings
```

**Step 2: Write workflow integration tests**

```python
# backend/tests/test_workflow_refactored.py
"""Integration tests for the refactored three-phase workflow."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestMergeAndDedupe:
    def test_dedup_by_doi(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _merge_and_dedupe
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search import SearchLink

        api_items = [{"doi": "10.1234/test", "title": "Paper A", "_source_provider": "crossref"}]
        firecrawl_links = [SearchLink(url="https://example.com/paper", doi="10.1234/test")]

        merged = _merge_and_dedupe(api_items, firecrawl_links)
        assert len(merged) == 1
        assert merged[0]["_candidate_type"] == "api"

    def test_dedup_by_url(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _merge_and_dedupe
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search import SearchLink

        api_items = [{"url": "https://example.com/paper.pdf", "_source_provider": "crossref"}]
        firecrawl_links = [SearchLink(url="https://example.com/paper.pdf")]

        merged = _merge_and_dedupe(api_items, firecrawl_links)
        assert len(merged) == 1

    def test_merges_distinct_items(self):
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import _merge_and_dedupe
        from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.web_search import SearchLink

        api_items = [{"doi": "10.1234/a", "title": "Paper A", "_source_provider": "crossref"}]
        firecrawl_links = [SearchLink(url="https://example.com/different-paper.pdf")]

        merged = _merge_and_dedupe(api_items, firecrawl_links)
        assert len(merged) == 2
```

**Step 3: Run all tests**

```bash
cd backend && uv run pytest tests/test_download_phase.py tests/test_workflow_refactored.py tests/test_web_search_adapter.py -v
```

Expected: PASS.

**Step 4: Commit**

```bash
git add backend/tests/test_download_phase.py backend/tests/test_workflow_refactored.py
git commit -m "test: add download phase and workflow integration tests"
```

---

## Task 12: Run full test suite and fix regressions

**Step 1: Run existing tests**

```bash
cd backend && uv run pytest tests/ -v --tb=short 2>&1 | head -100
```

**Step 2: Fix any failing tests**

Key areas to check:
- `test_online_acquisition_gateway.py` — may need updates for new gateway API
- `test_online_acquisition_workflow.py` — needs rewrite for new workflow shape
- `test_online_acquisition_search_service.py` — LANG_PROVIDER_MATRIX changes

**Step 3: Commit fixes**

```bash
git add -A
git commit -m "fix(tests): update tests for refactored online acquisition module"
```

---

## Task 13: Documentation and cleanup

**Step 1: Update progress.txt**

```
[2026-06-02] [Online acquisition refactor: separate link acquisition from download, Firecrawl adapter] [IN_PROGRESS]
```

**Step 2: Record lesson in lesson.md**

Record any debugging or iteration notes.

**Step 3: Archive old docs if any**

Move any outdated architecture docs to `docs/archive/`.

**Step 4: Final commit**

```bash
git add -A
git commit -m "docs: update progress and lessons for online acquisition refactor"
```

---

## Execution Order Summary

| Order | Task | Dependencies | Estimated Size |
|---|---|---|---|
| 1 | WebSearchConfig in config.py | None | Small |
| 2 | WebSearch Adapter interface | None | Small |
| 3 | Firecrawl Adapter | Task 2 | Medium |
| 4 | Rust get_bytes + download_file | None | Medium |
| 5 | Refactor gateway.py | Task 4 | Medium |
| 6 | Add normalize_firecrawl | None | Small |
| 7 | Update contracts.py | None | Small |
| 8 | Rewrite workflow.py | Tasks 2,3,5,6,7 | Large |
| 9 | Update search_service.py | None | Small |
| 10 | Deprecate web_providers.py | None | Trivial |
| 11 | Integration tests | Tasks 2-8 | Medium |
| 12 | Fix regressions | Task 11 | Variable |
| 13 | Documentation | Task 12 | Small |

Tasks 1, 2, 4, 6, 7, 9, 10 can be done in parallel (no dependencies on each other).
