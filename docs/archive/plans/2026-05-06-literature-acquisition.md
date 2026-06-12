# Literature Acquisition Module Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a layered, modular literature acquisition module that delegates HTTP I/O to `rust_io.literature` and keeps business logic in Python.

**Architecture:** Three-layer design — Contracts (data types) → Gateway (I/O bridge + normalization) → Workflow (orchestration + fallback chains). The `rust_io` native extension handles all HTTP/network I/O (crossref, doaj, europepmc, jstage, openalex, pmc, unpaywall). Python handles routing logic, result normalization, DOI fallback probing, and multilingual search orchestration.

**Tech Stack:** Python 3.12, Pydantic v2, `rust_io` (PyO3 native extension), httpx (for DOI fallback HTML parsing only).

---

## Module Structure

```
src/core/ingest_and_digitize_data/literature_acquisition/
├── __init__.py              # Public API exports
├── contracts.py             # Request/Response/Item data types (Pydantic)
├── normalizers.py           # Per-provider result normalization
├── gateway.py               # Unified gateway wrapping rust_io.literature
├── doi_fallback.py          # DOI landing page probe + PDF download
├── pubmed_service.py        # PubMed esearch/esummary/efetch integration
├── search_service.py        # Multilingual provider planning + search
└── workflow.py              # Top-level entry point
```

## Layer Diagram

```
workflow.py (orchestration, fallback chains)
    ├── gateway.py (dispatches to rust_io.literature, normalizes)
    ├── doi_fallback.py (DOI probe, HTML PDF extraction)
    ├── pubmed_service.py (PubMed XML API)
    └── search_service.py (language-based provider planning)
        └── contracts.py + normalizers.py (data layer)
```

---

### Task 1: Contracts — Data Types

**Files:**
- Create: `src/core/ingest_and_digitize_data/literature_acquisition/__init__.py`
- Create: `src/core/ingest_and_digitize_data/literature_acquisition/contracts.py`

**Step 1: Create `__init__.py`**

```python
"""Literature acquisition module — layered architecture."""
```

**Step 2: Create `contracts.py` with all data types**

```python
"""Pure data types for literature acquisition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# --- Literal types ---

ApiProvider = Literal[
    "crossref", "unpaywall", "openalex", "europepmc", "pmc", "jstage", "doaj"
]
WebProvider = Literal["pubscholar", "cyberleninka", "hans_publishers"]
PreferStrategy = Literal["auto", "api", "web"]
ActionStrategy = Literal["search", "download"]

# --- Request ---

class LiteratureRequest(BaseModel):
    """Unified request for literature search/download."""

    action: ActionStrategy = "search"
    query: Optional[str] = None
    identifiers: List[str] = Field(default_factory=list)
    prefer: PreferStrategy = "auto"
    raw: bool = False
    limit: int = 20
    language: Optional[str] = "auto"

    api_provider: Optional[ApiProvider] = None
    web_provider: Optional[WebProvider] = None

    api_params: Dict[str, Any] = Field(default_factory=dict)
    web_params: Dict[str, Any] = Field(default_factory=dict)

    download_path: str = "./downloads"
    selected_index: int = 0
    selected_title: Optional[str] = None
    detail_link: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_input(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        if "identifier" in values and "identifiers" not in values:
            values["identifiers"] = values.get("identifier")
        if "text" in values and "query" not in values:
            values["query"] = values.get("text")
        return values

    @field_validator("identifiers", mode="before")
    @classmethod
    def _identifiers_to_list(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v) for v in value if v is not None]
        return [str(value)]

    @field_validator("limit")
    @classmethod
    def _limit_range(cls, value: int) -> int:
        return max(1, min(200, value))


# --- Unified Item ---

class LiteratureItem(BaseModel):
    """Standardized literature metadata item."""

    source: str
    title: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    journal: Optional[str] = None
    year: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    links: List[str] = Field(default_factory=list)
    language: Optional[str] = None
    publisher: Optional[str] = None
    issn: List[str] = Field(default_factory=list)
    identifiers: Dict[str, Any] = Field(default_factory=dict)
    keywords: List[str] = Field(default_factory=list)


# --- Route Info ---

class RouteInfo(BaseModel):
    """Routing decision summary."""

    prefer: PreferStrategy
    api_provider: Optional[str] = None
    web_provider: Optional[str] = None
    used: Optional[Literal["api", "web", "none"]] = None
    reason: Optional[str] = None
    fallback_used: bool = False


# --- Response ---

class LiteratureResponse(BaseModel):
    """Unified response for literature search/download."""

    success: bool
    items: List[LiteratureItem] = Field(default_factory=list)
    downloads: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    route: RouteInfo
    raw: Optional[Any] = None


# --- Gateway contracts (internal) ---

@dataclass
class GatewayRequest:
    """Internal request for a single provider call."""

    provider: str
    action: ActionStrategy = "search"
    query: Optional[str] = None
    identifiers: Dict[str, Optional[str]] = field(default_factory=dict)
    limit: int = 20
    raw: bool = False
    params: Dict[str, Any] = field(default_factory=dict)
    download_path: str = "./downloads"
    selected_index: int = 0
    selected_title: Optional[str] = None
    detail_link: Optional[str] = None


@dataclass
class GatewayResult:
    """Internal result from a single provider call."""

    provider: str
    success: bool
    items: List[Dict[str, Any]]
    warnings: List[str]
    downloads: List[Dict[str, Any]] = field(default_factory=list)
    raw: Any = None
    meta: Any = None
```

**Step 3: Verify import**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run python -c "from src.core.ingest_and_digitize_data.literature_acquisition.contracts import LiteratureRequest, LiteratureResponse; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add src/core/ingest_and_digitize_data/literature_acquisition/__init__.py src/core/ingest_and_digitize_data/literature_acquisition/contracts.py
git commit -m "feat(literature): add contracts module with request/response types"
```

---

### Task 2: Normalizers — Provider-Specific Result Normalization

**Files:**
- Create: `src/core/ingest_and_digitize_data/literature_acquisition/normalizers.py`

**Step 1: Create `normalizers.py`**

Port from `.old_version/src/domain/literature/unified/normalizers.py`. Each provider has a dedicated normalizer function that converts raw API response dicts into `LiteratureItem`.

```python
"""Per-provider normalization to LiteratureItem."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .contracts import LiteratureItem

DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
ISSN_PATTERN = re.compile(r"\b\d{4}-\d{3}[\dX]\b", re.IGNORECASE)


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return str(value).strip() or None


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _dedupe(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    output: List[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _first(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        for item in value:
            text = _clean_text(item)
            if text:
                return text
        return None
    return _clean_text(value)


def _normalize_authors(value: Any) -> List[str]:
    if value is None:
        return []
    authors: List[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                name = _clean_text(item.get("name"))
                if not name:
                    given = _clean_text(item.get("given") or item.get("first"))
                    family = _clean_text(item.get("family") or item.get("last"))
                    if given and family:
                        name = f"{given} {family}".strip()
                    else:
                        name = given or family
                if name:
                    authors.append(name)
            else:
                text = _clean_text(item)
                if text:
                    authors.append(text)
        return _dedupe(authors)
    if isinstance(value, str):
        if ";" in value:
            parts = [p.strip() for p in value.split(";") if p.strip()]
        elif " and " in value:
            parts = [p.strip() for p in value.split(" and ") if p.strip()]
        else:
            parts = [value.strip()]
        return _dedupe([p for p in parts if p])
    return []


def _extract_year(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        match = re.search(r"(19|20)\d{2}", value)
        return match.group(0) if match else _clean_text(value)
    if isinstance(value, dict):
        for key in ("date-parts", "date_parts", "dateparts"):
            parts = value.get(key)
            if parts and isinstance(parts, list):
                try:
                    year = parts[0][0]
                    if year:
                        return str(year)
                except (IndexError, TypeError):
                    continue
        for key in ("year", "published_year", "pubyear"):
            if key in value:
                return _extract_year(value.get(key))
    if isinstance(value, (list, tuple)):
        for item in value:
            year = _extract_year(item)
            if year:
                return year
    return None


def _extract_links(values: Sequence[Any]) -> List[str]:
    links: List[str] = []
    for value in values:
        if not value:
            continue
        if isinstance(value, str):
            links.append(value.strip())
            continue
        if isinstance(value, dict):
            for key in ("url", "URL", "link", "landing_page_url", "doi_url", "url_for_pdf"):
                if value.get(key):
                    links.append(str(value.get(key)).strip())
    return _dedupe([link for link in links if link])


def _collect_strings(value: Any, limit: int = 5000) -> List[str]:
    collected: List[str] = []
    queue: List[Any] = [value]
    while queue and len(collected) < limit:
        current = queue.pop(0)
        if isinstance(current, dict):
            queue.extend(current.values())
        elif isinstance(current, list):
            queue.extend(current)
        elif isinstance(current, tuple):
            queue.extend(list(current))
        else:
            text = _clean_text(current)
            if text:
                collected.append(text)
    return collected


def _find_first_match(pattern: re.Pattern[str], values: Iterable[str]) -> Optional[str]:
    for value in values:
        match = pattern.search(value)
        if match:
            return match.group(0)
    return None


# --- Per-provider normalizers ---


def normalize_crossref(item: Dict[str, Any]) -> LiteratureItem:
    title = _first(item.get("title"))
    authors = _normalize_authors(item.get("author") or item.get("authors"))
    journal = _first(item.get("container-title"))
    doi = _clean_text(item.get("DOI") or item.get("doi"))
    url = _clean_text(item.get("URL") or item.get("url"))
    year = _extract_year(
        item.get("issued")
        or item.get("published")
        or item.get("created")
        or item.get("published-online")
        or item.get("published-print")
    )
    language = _clean_text(item.get("language"))
    publisher = _clean_text(item.get("publisher"))
    issn = _dedupe([_clean_text(v) for v in _as_list(item.get("ISSN")) if _clean_text(v)])
    keywords = _dedupe([_clean_text(v) for v in _as_list(item.get("subject")) if _clean_text(v)])
    links = _extract_links([url, item.get("URL"), item.get("url")])
    return LiteratureItem(
        source="crossref",
        title=title,
        authors=authors,
        journal=journal,
        year=year,
        doi=doi,
        url=url,
        links=links,
        language=language,
        publisher=publisher,
        issn=issn,
        identifiers={"issn": issn} if issn else {},
        keywords=keywords,
    )


def normalize_unpaywall(item: Dict[str, Any]) -> LiteratureItem:
    title = _clean_text(item.get("title") or item.get("publication_title"))
    doi = _clean_text(item.get("doi") or item.get("DOI"))
    journal = _clean_text(item.get("journal_name") or item.get("journal"))
    publisher = _clean_text(item.get("publisher"))
    year = _extract_year(item.get("year") or item.get("published_date"))
    authors = _normalize_authors(item.get("authors") or item.get("author"))
    best_oa = item.get("best_oa_location") or {}
    url = _clean_text(
        item.get("url")
        or best_oa.get("url")
        or best_oa.get("landing_page_url")
        or item.get("doi_url")
    )
    links = _extract_links(
        [url, item.get("url"), item.get("doi_url"), best_oa.get("url"), best_oa.get("url_for_pdf")]
    )
    return LiteratureItem(
        source="unpaywall",
        title=title,
        authors=authors,
        journal=journal,
        year=year,
        doi=doi,
        url=url,
        links=links,
        language=_clean_text(item.get("language")),
        publisher=publisher,
        identifiers={"is_oa": item.get("is_oa")} if "is_oa" in item else {},
        keywords=_dedupe([_clean_text(v) for v in _as_list(item.get("keywords")) if _clean_text(v)]),
    )


def normalize_pmc(item: Dict[str, Any]) -> LiteratureItem:
    strings = _collect_strings(item)
    title = _first(item.get("title")) or _find_first_match(
        re.compile(r"<title>(.+?)</title>"), strings
    )
    doi = _find_first_match(DOI_PATTERN, strings)
    pmcid = _find_first_match(re.compile(r"\bPMC\d+\b", re.IGNORECASE), strings)
    journal = _first(item.get("journal_title")) or _first(item.get("journal"))
    year = _extract_year(item.get("year") or item.get("pubyear"))
    issn_matches: List[str] = []
    for s in strings:
        issn_matches.extend(ISSN_PATTERN.findall(s))
    issn = _dedupe([m.upper() for m in issn_matches])
    links = _extract_links([item.get("link"), item.get("url")])
    identifiers: Dict[str, Any] = {}
    if pmcid:
        identifiers["pmcid"] = pmcid
    return LiteratureItem(
        source="pmc",
        title=_clean_text(title) if isinstance(title, str) else _clean_text(title),
        authors=_normalize_authors(item.get("authors")),
        journal=_clean_text(journal),
        year=year,
        doi=_clean_text(doi),
        url=_first(links) if links else None,
        links=links,
        language=_clean_text(item.get("language")),
        issn=issn,
        identifiers=identifiers,
        keywords=_dedupe([_clean_text(v) for v in _as_list(item.get("keywords")) if _clean_text(v)]),
    )


def normalize_jstage(item: Dict[str, Any]) -> LiteratureItem:
    title = _clean_text(item.get("article_title_en") or item.get("article_title_ja"))
    journal = _clean_text(item.get("material_title_en") or item.get("material_title_ja"))
    doi = _clean_text(item.get("doi"))
    url = _clean_text(item.get("link"))
    issn = _dedupe([_clean_text(item.get("issn")), _clean_text(item.get("eissn"))])
    return LiteratureItem(
        source="jstage",
        title=title,
        authors=[],
        journal=journal,
        year=_extract_year(item.get("pubyear")),
        doi=doi,
        url=url,
        links=_extract_links([url]),
        language="ja" if item.get("article_title_ja") else None,
        issn=issn,
        identifiers={"issn": issn} if issn else {},
        keywords=[],
    )


def normalize_doaj(item: Dict[str, Any]) -> LiteratureItem:
    title = _clean_text(item.get("title"))
    journal = _clean_text(item.get("journal_title"))
    doi = _clean_text(item.get("doi"))
    url = _clean_text(_first(item.get("links")))
    issn = _dedupe([_clean_text(v) for v in _as_list(item.get("issns")) if _clean_text(v)])
    links = _extract_links([url] + _as_list(item.get("links")))
    return LiteratureItem(
        source="doaj",
        title=title,
        authors=[],
        journal=journal,
        year=_extract_year(item.get("year")),
        doi=doi,
        url=url,
        links=links,
        language=None,
        publisher=_clean_text(item.get("publisher")),
        issn=issn,
        identifiers={"issn": issn} if issn else {},
        keywords=_dedupe([_clean_text(v) for v in _as_list(item.get("keywords")) if _clean_text(v)]),
    )


def normalize_openalex(item: Dict[str, Any]) -> LiteratureItem:
    title = _clean_text(item.get("title"))
    authors = _normalize_authors(item.get("authorships") or item.get("authors"))
    journal = _clean_text(
        item.get("primary_location", {}).get("source", {}).get("display_name")
        if isinstance(item.get("primary_location"), dict)
        else None
    )
    doi = _clean_text(item.get("doi"))
    url = _clean_text(item.get("id"))
    year = _extract_year(item.get("publication_year") or item.get("year"))
    language = _clean_text(item.get("language"))
    keywords = _dedupe(
        [_clean_text(v.get("display_name")) for v in (item.get("keywords") or []) if isinstance(v, dict)]
    )
    return LiteratureItem(
        source="openalex",
        title=title,
        authors=authors,
        journal=journal,
        year=year,
        doi=doi,
        url=url,
        links=_extract_links([url, doi]),
        language=language,
        issn=[],
        identifiers={},
        keywords=keywords,
    )


def normalize_europepmc(item: Dict[str, Any]) -> LiteratureItem:
    title = _clean_text(item.get("title") or item.get("articleTitle"))
    authors = _normalize_authors(item.get("authorList", {}).get("author") if isinstance(item.get("authorList"), dict) else item.get("authors"))
    journal = _clean_text(item.get("journalTitle") or item.get("journal"))
    doi = _clean_text(item.get("doi"))
    pmcid = _clean_text(item.get("pmcid"))
    url = _clean_text(item.get("url") or item.get("fullTextUrlList", {}).get("fullTextUrl", [{}])[0].get("url") if isinstance(item.get("fullTextUrlList"), dict) else None)
    year = _extract_year(item.get("pubYear") or item.get("year"))
    return LiteratureItem(
        source="europepmc",
        title=title,
        authors=authors,
        journal=journal,
        year=year,
        doi=doi,
        url=url,
        links=_extract_links([url]),
        language=_clean_text(item.get("language")),
        issn=[],
        identifiers={"pmcid": pmcid} if pmcid else {},
        keywords=_dedupe([_clean_text(v) for v in _as_list(item.get("keywords")) if _clean_text(v)]),
    )


# --- Normalizer registry ---

NORMALIZER_MAP: Dict[str, Any] = {
    "crossref": normalize_crossref,
    "unpaywall": normalize_unpaywall,
    "pmc": normalize_pmc,
    "jstage": normalize_jstage,
    "doaj": normalize_doaj,
    "openalex": normalize_openalex,
    "europepmc": normalize_europepmc,
}


def normalize_items(provider: str, items: List[Dict[str, Any]]) -> List[LiteratureItem]:
    """Normalize raw provider items to LiteratureItem list."""
    normalizer = NORMALIZER_MAP.get(provider)
    if not normalizer:
        return []
    output: List[LiteratureItem] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        output.append(normalizer(item))
    return output
```

**Step 2: Verify import**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run python -c "from src.core.ingest_and_digitize_data.literature_acquisition.normalizers import normalize_items, NORMALIZER_MAP; print(f'{len(NORMALIZER_MAP)} normalizers loaded')"`
Expected: `7 normalizers loaded`

**Step 3: Commit**

```bash
git add src/core/ingest_and_digitize_data/literature_acquisition/normalizers.py
git commit -m "feat(literature): add per-provider normalizers for 7 API providers"
```

---

### Task 3: Gateway — Bridge rust_io.literature to Python

**Files:**
- Create: `src/core/ingest_and_digitize_data/literature_acquisition/gateway.py`

**Step 1: Create `gateway.py`**

This module wraps `rust_io.literature.fetch_one()` and normalizes results. It replaces the old version's `api_gateway.py` which used Python httpx for HTTP calls.

```python
"""Unified gateway — delegates HTTP I/O to rust_io.literature."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from .contracts import GatewayRequest, GatewayResult
from .normalizers import normalize_items


def _merge_params(base: Dict[str, Any], overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not overrides:
        return base
    merged = dict(base)
    for key, value in overrides.items():
        if key in ("params", "search_params") and isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def _build_fetch_params(request: GatewayRequest) -> Dict[str, Any]:
    """Convert GatewayRequest to rust_io.literature.fetch_one params dict."""
    params: Dict[str, Any] = {
        "query": request.query,
        "limit": request.limit,
        "raw": request.raw,
        "selected_index": request.selected_index,
        "selected_title": request.selected_title,
        "detail_link": request.detail_link,
    }
    if request.identifiers:
        params["identifiers"] = {k: v for k, v in request.identifiers.items() if v is not None}
    return params


def _rust_result_to_gateway(provider: str, result: Dict[str, Any]) -> GatewayResult:
    """Convert rust_io FetchResult dict to GatewayResult."""
    return GatewayResult(
        provider=provider,
        success=bool(result.get("success")),
        items=list(result.get("items") or []),
        downloads=list(result.get("downloads") or []),
        warnings=list(result.get("warnings") or []),
        raw=result.get("raw"),
        meta=result.get("meta"),
    )


def _failure_result(provider: str, error: Exception) -> GatewayResult:
    return GatewayResult(
        provider=provider,
        success=False,
        items=[],
        downloads=[],
        warnings=[f"{provider}_error:{error}"],
    )


async def call_provider(request: GatewayRequest) -> GatewayResult:
    """Call a single provider via rust_io.literature.fetch_one."""
    try:
        import rust_io.literature as rust_lit
    except ImportError:
        return _failure_result(request.provider, RuntimeError("rust_io.literature not available"))

    params = _build_fetch_params(request)
    try:
        raw_result = await rust_lit.fetch_one(
            provider=request.provider,
            action=request.action,
            params=params,
        )
        return _rust_result_to_gateway(request.provider, raw_result)
    except Exception as exc:
        return _failure_result(request.provider, exc)


async def call_provider_with_retry(
    request: GatewayRequest,
    max_attempts: int = 2,
) -> GatewayResult:
    """Call a provider with retry logic."""
    last_result: GatewayResult | None = None
    for attempt in range(1, max_attempts + 1):
        result = await call_provider(request)
        if result.success and (result.items or result.downloads):
            return result
        last_result = result
        if attempt < max_attempts:
            await asyncio.sleep(0.5 * attempt)
    return last_result or _failure_result(request.provider, RuntimeError("no result"))


async def search_provider(
    provider: str,
    query: Optional[str] = None,
    identifiers: Optional[Dict[str, Optional[str]]] = None,
    limit: int = 20,
    raw: bool = False,
    params: Optional[Dict[str, Any]] = None,
) -> GatewayResult:
    """Search a single provider and return normalized GatewayResult."""
    request = GatewayRequest(
        provider=provider,
        action="search",
        query=query,
        identifiers=identifiers or {},
        limit=limit,
        raw=raw,
        params=params or {},
    )
    return await call_provider_with_retry(request)


async def download_from_provider(
    provider: str,
    query: Optional[str] = None,
    identifiers: Optional[Dict[str, Optional[str]]] = None,
    limit: int = 20,
    raw: bool = False,
    download_path: str = "./downloads",
    selected_index: int = 0,
    selected_title: Optional[str] = None,
    detail_link: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> GatewayResult:
    """Download from a single provider."""
    request = GatewayRequest(
        provider=provider,
        action="download",
        query=query,
        identifiers=identifiers or {},
        limit=limit,
        raw=raw,
        params=params or {},
        download_path=download_path,
        selected_index=selected_index,
        selected_title=selected_title,
        detail_link=detail_link,
    )
    return await call_provider_with_retry(request)
```

**Step 2: Verify import**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run python -c "from src.core.ingest_and_digitize_data.literature_acquisition.gateway import call_provider, search_provider; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/core/ingest_and_digitize_data/literature_acquisition/gateway.py
git commit -m "feat(literature): add gateway module bridging rust_io to Python"
```

---

### Task 4: DOI Fallback — Landing Page Probe

**Files:**
- Create: `src/core/ingest_and_digitize_data/literature_acquisition/doi_fallback.py`

**Step 1: Create `doi_fallback.py`**

Port from `.old_version/src/domain/literature/doi_fallback.py`. Uses httpx for DOI resolution and HTML PDF link extraction — this is the one place where Python-side HTTP is acceptable (complex HTML parsing with BeautifulSoup).

```python
"""DOI landing page probe and PDF download fallback."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx

_PDF_LINK_PATTERNS = [
    re.compile(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', re.IGNORECASE),
    re.compile(r'href=["\']([^"\']*download[^"\']*pdf[^"\']*)["\']', re.IGNORECASE),
]

_CHINESE_DOMAINS = {"yiigle.com", "wanfangdata.com.cn", "cnki.net", "cqvip.com"}

_TIMEOUT = 60

_BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,ja;q=0.7",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 CrossEvidence/1.0",
}


def _normalize_proxy_url(proxy: Optional[str]) -> Optional[str]:
    value = str(proxy or "").strip()
    if value.lower() in {"", "none", "false", "off", "0"}:
        return None
    if "://" not in value:
        value = f"http://{value}"
    return value


def _extract_pdf_links(html: str, base_url: str) -> List[str]:
    links: List[str] = []
    for pattern in _PDF_LINK_PATTERNS:
        for match in pattern.finditer(html):
            href = match.group(1)
            absolute = urljoin(base_url, href)
            if absolute not in links:
                links.append(absolute)
    return links


def _is_chinese_domain(url: str) -> bool:
    lower = url.lower()
    return any(domain in lower for domain in _CHINESE_DOMAINS)


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\-.]", "_", name)


def probe_doi_landing_page(
    doi: str,
    *,
    timeout: int = _TIMEOUT,
    email: Optional[str] = None,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    """Probe a DOI landing page to find a direct PDF link."""
    ua = _BROWSER_HEADERS["User-Agent"]
    if email:
        ua = f"{ua} (+mailto:{email})"
    headers = {**_BROWSER_HEADERS, "User-Agent": ua}

    try:
        landing = httpx.get(
            f"https://doi.org/{doi}",
            timeout=timeout,
            follow_redirects=True,
            headers=headers,
            proxy=_normalize_proxy_url(proxy),
        )
    except Exception as exc:
        return {"success": False, "pdf_url": None, "error": str(exc), "warnings": [f"doi_probe_failed:{exc}"]}

    if not landing.is_success:
        return {
            "success": False,
            "pdf_url": None,
            "error": f"HTTP {landing.status_code}",
            "warnings": [f"doi_probe_http_{landing.status_code}"],
        }

    resolved_url = str(landing.url)

    if landing.content.startswith(b"%PDF"):
        return {"success": True, "pdf_url": resolved_url, "resolved_url": resolved_url, "warnings": []}

    if _is_chinese_domain(resolved_url):
        return {
            "success": False,
            "pdf_url": None,
            "resolved_url": resolved_url,
            "is_chinese": True,
            "warnings": ["doi_resolved_to_chinese_domain"],
        }

    pdf_links = _extract_pdf_links(landing.text or "", resolved_url)
    for link in pdf_links:
        try:
            probe = httpx.get(
                link,
                timeout=timeout,
                follow_redirects=True,
                headers=headers,
                proxy=_normalize_proxy_url(proxy),
            )
            if probe.is_success and probe.content.startswith(b"%PDF"):
                return {"success": True, "pdf_url": link, "resolved_url": resolved_url, "warnings": []}
        except Exception:
            continue

    return {"success": False, "pdf_url": None, "resolved_url": resolved_url, "warnings": ["doi_probe_no_pdf_found"]}


def doi_fallback_download(
    doi: str,
    *,
    download_path: str = "./downloads",
    email: Optional[str] = None,
    timeout: int = _TIMEOUT,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    """Try to download a PDF via DOI landing page probe."""
    warnings: List[str] = []

    probe = probe_doi_landing_page(doi, timeout=timeout, email=email, proxy=proxy)
    warnings.extend(probe.get("warnings") or [])

    if probe.get("is_chinese") and probe.get("resolved_url"):
        return {"success": False, "method": None, "is_chinese": True, "resolved_url": probe["resolved_url"], "warnings": warnings}

    if probe.get("success") and probe.get("pdf_url"):
        try:
            os.makedirs(download_path, exist_ok=True)
            filename = _sanitize_filename(doi.replace("/", "_")) + ".pdf"
            file_path = os.path.join(download_path, filename)
            resp = httpx.get(
                probe["pdf_url"],
                timeout=timeout,
                follow_redirects=True,
                headers=_BROWSER_HEADERS,
                proxy=_normalize_proxy_url(proxy),
            )
            if resp.is_success and resp.content.startswith(b"%PDF"):
                Path(file_path).write_bytes(resp.content)
                return {
                    "success": True,
                    "method": "doi_landing_probe",
                    "pdf_url": probe["pdf_url"],
                    "file_path": file_path,
                    "size_bytes": len(resp.content),
                    "warnings": warnings,
                }
        except Exception as exc:
            warnings.append(f"doi_download_failed:{exc}")

    return {"success": False, "method": None, "warnings": warnings}
```

**Step 2: Verify import**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run python -c "from src.core.ingest_and_digitize_data.literature_acquisition.doi_fallback import probe_doi_landing_page, doi_fallback_download; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/core/ingest_and_digitize_data/literature_acquisition/doi_fallback.py
git commit -m "feat(literature): add DOI fallback with landing page probe"
```

---

### Task 5: PubMed Service — XML API Integration

**Files:**
- Create: `src/core/ingest_and_digitize_data/literature_acquisition/pubmed_service.py`

**Step 1: Create `pubmed_service.py`**

Port from `.old_version/src/domain/literature/pubmed_service.py`. Uses httpx for PubMed's XML API (esearch, esummary, efetch) — this is complex XML parsing that stays in Python for now.

```python
"""PubMed esearch/esummary/efetch integration."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class PubMedCandidate:
    pmid: str
    title: str
    journal: str
    pub_date: str


@dataclass
class PubMedArticle:
    pmid: str
    title: str
    journal: str
    pub_date: str
    abstract: str


class PubMedService:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("PUBMED_BASE_URL", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils")).rstrip("/")
        self.api_key = api_key or os.getenv("PUBMED_API_KEY", "")

    async def search_candidates(
        self,
        query: str,
        candidate_limit: int = 15,
    ) -> List[PubMedCandidate]:
        """Search PubMed and return candidate list."""
        term = (query or "").strip()
        if not term:
            return []

        params: Dict[str, Any] = {
            "db": "pubmed",
            "term": term,
            "retmax": max(1, min(candidate_limit, 15)),
            "retmode": "json",
            "sort": "pub date",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        async with httpx.AsyncClient(timeout=15.0) as client:
            esearch_resp = await client.get(f"{self.base_url}/esearch.fcgi", params=params)
            esearch_resp.raise_for_status()
            esearch_payload = esearch_resp.json()

            pmids: List[str] = (
                esearch_payload.get("esearchresult", {}).get("idlist", []) or []
            )
            if not pmids:
                return []

            summary_params: Dict[str, Any] = {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "json",
            }
            if self.api_key:
                summary_params["api_key"] = self.api_key
            summary_resp = await client.get(f"{self.base_url}/esummary.fcgi", params=summary_params)
            summary_resp.raise_for_status()
            summary_payload = summary_resp.json()

        records = summary_payload.get("result", {})
        candidates: List[PubMedCandidate] = []
        for pmid in pmids:
            row = records.get(pmid, {})
            if not row:
                continue
            candidates.append(
                PubMedCandidate(
                    pmid=pmid,
                    title=str(row.get("title") or "").strip(),
                    journal=str(row.get("fulljournalname") or row.get("source") or "").strip(),
                    pub_date=str(row.get("pubdate") or "").strip(),
                )
            )
        return candidates

    async def fetch_article(self, pmid: str) -> Optional[PubMedArticle]:
        """Fetch full article metadata + abstract by PMID."""
        normalized_pmid = str(pmid or "").strip()
        if not normalized_pmid:
            return None

        summary_params: Dict[str, Any] = {
            "db": "pubmed",
            "id": normalized_pmid,
            "retmode": "json",
        }
        if self.api_key:
            summary_params["api_key"] = self.api_key

        fetch_params: Dict[str, Any] = {
            "db": "pubmed",
            "id": normalized_pmid,
            "retmode": "xml",
        }
        if self.api_key:
            fetch_params["api_key"] = self.api_key

        async with httpx.AsyncClient(timeout=15.0) as client:
            summary_resp = await client.get(f"{self.base_url}/esummary.fcgi", params=summary_params)
            summary_resp.raise_for_status()
            summary_payload = summary_resp.json()

            fetch_resp = await client.get(f"{self.base_url}/efetch.fcgi", params=fetch_params)
            fetch_resp.raise_for_status()
            fetch_xml = fetch_resp.text

        row = summary_payload.get("result", {}).get(normalized_pmid, {})
        if not row:
            return None

        abstract_fragments: List[str] = []
        try:
            root = ET.fromstring(fetch_xml)
            for node in root.findall(".//Abstract/AbstractText"):
                text = "".join(node.itertext()).strip()
                if text:
                    abstract_fragments.append(text)
        except ET.ParseError:
            abstract_fragments = []

        abstract_text = "\n\n".join(abstract_fragments).strip()
        return PubMedArticle(
            pmid=normalized_pmid,
            title=str(row.get("title") or "").strip(),
            journal=str(row.get("fulljournalname") or row.get("source") or "").strip(),
            pub_date=str(row.get("pubdate") or "").strip(),
            abstract=abstract_text,
        )


_pubmed_service: Optional[PubMedService] = None


def get_pubmed_service() -> PubMedService:
    global _pubmed_service
    if _pubmed_service is None:
        _pubmed_service = PubMedService()
    return _pubmed_service
```

**Step 2: Verify import**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run python -c "from src.core.ingest_and_digitize_data.literature_acquisition.pubmed_service import PubMedService, get_pubmed_service; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/core/ingest_and_digitize_data/literature_acquisition/pubmed_service.py
git commit -m "feat(literature): add PubMed service with esearch/efetch integration"
```

---

### Task 6: Search Service — Multilingual Provider Planning

**Files:**
- Create: `src/core/ingest_and_digitize_data/literature_acquisition/search_service.py`

**Step 1: Create `search_service.py`**

Port from `.old_version/src/domain/literature/unified/search_service.py`. Provides language-based provider routing and candidate deduplication.

```python
"""Multilingual provider planning and search orchestration."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Sequence, TypedDict

from .workflow import literature_workflow


class ProviderPlanItem(TypedDict):
    route: str
    provider: str


LANG_PROVIDER_MATRIX: Dict[str, List[ProviderPlanItem]] = {
    "zh": [
        {"route": "web", "provider": "pubscholar"},
        {"route": "web", "provider": "hans_publishers"},
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
        {"route": "api", "provider": "pmc"},
    ],
    "ja": [
        {"route": "api", "provider": "jstage"},
        {"route": "api", "provider": "crossref"},
        {"route": "api", "provider": "unpaywall"},
        {"route": "api", "provider": "doaj"},
        {"route": "api", "provider": "pmc"},
    ],
    "en": [
        {"route": "api", "provider": "pmc"},
        {"route": "api", "provider": "crossref"},
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

_TITLE_NORMALIZER = re.compile(r"[^\w一-鿿぀-ヿ가-힯]+", re.UNICODE)


def build_provider_plan(
    *,
    language: str = "auto",
    provider_hints: Optional[Sequence[str]] = None,
) -> List[ProviderPlanItem]:
    """Build a provider execution plan based on language and hints."""
    normalized_language = (language or "auto").strip().lower() or "auto"
    plan = list(LANG_PROVIDER_MATRIX.get(normalized_language, LANG_PROVIDER_MATRIX["auto"]))
    hints = [str(item).strip().lower() for item in (provider_hints or []) if str(item).strip()]
    if not hints:
        return plan
    hinted = [item for item in plan if item["provider"] in hints]
    remaining = [item for item in plan if item["provider"] not in hints]
    return hinted + remaining


def _normalize_title(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    normalized = _TITLE_NORMALIZER.sub("", str(title).casefold())
    return normalized or None


def _clean_identifier(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text.casefold() or None


def _candidate_keys(candidate: Dict[str, Any]) -> List[tuple[str, str]]:
    identifiers = candidate.get("identifiers") or {}
    keys: List[tuple[str, str]] = []
    doi = _clean_identifier(candidate.get("doi") or identifiers.get("doi"))
    if doi:
        keys.append(("doi", doi))
    url = _clean_identifier(
        candidate.get("url") or candidate.get("detail_link") or identifiers.get("url") or identifiers.get("detail_link")
    )
    if url:
        keys.append(("url", url))
    normalized_title = _normalize_title(candidate.get("title"))
    if normalized_title:
        keys.append(("title", normalized_title))
    return keys


def dedupe_candidates(candidates: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate candidates by DOI, URL, or title."""
    seen: set[tuple[str, str]] = set()
    deduped: List[Dict[str, Any]] = []
    for candidate in candidates:
        keys = _candidate_keys(candidate)
        if keys and any(key in seen for key in keys):
            continue
        deduped.append(candidate)
        for key in keys:
            seen.add(key)
    return deduped


def _build_candidate_id(candidate: Dict[str, Any]) -> str:
    identity = {
        "provider": candidate.get("provider"),
        "route": candidate.get("route"),
        "doi": candidate.get("doi"),
        "url": candidate.get("url"),
        "title": candidate.get("title"),
    }
    digest = hashlib.sha1(
        json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"cand-{digest[:12]}"


def _normalize_candidate(item: Dict[str, Any], plan_item: ProviderPlanItem) -> Dict[str, Any]:
    identifiers = dict(item.get("identifiers") or {})
    doi = item.get("doi") or identifiers.get("doi")
    url = item.get("url") or identifiers.get("url")
    links = item.get("links") if isinstance(item.get("links"), list) else []
    detail_link = item.get("url") or (links[0] if links else None)

    normalized = {
        "candidate_id": "",
        "provider": plan_item["provider"],
        "route": plan_item["route"],
        "title": str(item.get("title") or "").strip(),
        "journal": item.get("journal"),
        "year": item.get("year"),
        "language": item.get("language"),
        "doi": doi,
        "url": url,
        "identifiers": identifiers,
        "detail_link": detail_link,
    }
    if doi and not normalized["identifiers"].get("doi"):
        normalized["identifiers"]["doi"] = doi
    if url and not normalized["identifiers"].get("url"):
        normalized["identifiers"]["url"] = url
    normalized["candidate_id"] = _build_candidate_id(normalized)
    return normalized


def rank_candidates(
    candidates: Sequence[Dict[str, Any]],
    *,
    expected_title: Optional[str] = None,
    preferred_provider: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Rank candidates by title match, provider preference, and DOI presence."""
    normalized_expected_title = _normalize_title(expected_title)
    normalized_provider = str(preferred_provider or "").strip().lower() or None

    def _score(candidate: Dict[str, Any]) -> tuple[int, int, int]:
        normalized_title = _normalize_title(candidate.get("title"))
        exact_title = int(bool(normalized_expected_title and normalized_title == normalized_expected_title))
        provider_match = int(
            bool(normalized_provider and str(candidate.get("provider") or "").strip().lower() == normalized_provider)
        )
        has_doi = int(
            bool(_clean_identifier(candidate.get("doi") or (candidate.get("identifiers") or {}).get("doi")))
        )
        return (exact_title, provider_match, has_doi)

    return sorted(candidates, key=_score, reverse=True)


async def search_multilingual(
    *,
    target: str,
    disease: str,
    language: str = "auto",
    candidate_limit: int = 15,
    provider_hints: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Search across multiple providers with language-based routing."""
    query = f"{target} {disease} case report".strip()
    if not query:
        return []

    plan = build_provider_plan(language=language, provider_hints=provider_hints)
    collected: List[Dict[str, Any]] = []
    preferred_provider = plan[0]["provider"] if plan else None

    for plan_item in plan:
        payload: Dict[str, Any] = {
            "action": "search",
            "query": query,
            "prefer": plan_item["route"],
            "limit": candidate_limit,
            "language": language,
            "raw": False,
        }
        if plan_item["route"] == "api":
            payload["api_provider"] = plan_item["provider"]
        else:
            payload["web_provider"] = plan_item["provider"]

        result = await literature_workflow(payload)
        for item in result.get("items", []) or []:
            if not item.get("title"):
                continue
            collected.append(_normalize_candidate(item, plan_item))

        collected = dedupe_candidates(collected)
        collected = rank_candidates(collected, expected_title=target, preferred_provider=preferred_provider)
        if len(collected) >= candidate_limit:
            return collected[:candidate_limit]

    return rank_candidates(collected, expected_title=target, preferred_provider=preferred_provider)[:candidate_limit]
```

**Step 2: Verify import**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run python -c "from src.core.ingest_and_digitize_data.literature_acquisition.search_service import build_provider_plan, LANG_PROVIDER_MATRIX; print(f'{len(LANG_PROVIDER_MATRIX)} language plans')"`
Expected: `4 language plans`

**Step 3: Commit**

```bash
git add src/core/ingest_and_digitize_data/literature_acquisition/search_service.py
git commit -m "feat(literature): add multilingual search service with provider planning"
```

---

### Task 7: Workflow — Top-Level Entry Point

**Files:**
- Create: `src/core/ingest_and_digitize_data/literature_acquisition/workflow.py`

**Step 1: Create `workflow.py`**

Port from `.old_version/src/domain/literature/unified/workflow.py`. This is the main orchestrator that chains API providers with fallback logic.

```python
"""Top-level literature workflow — orchestrates providers with fallback chains."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .contracts import (
    GatewayResult,
    LiteratureItem,
    LiteratureRequest,
    LiteratureResponse,
    RouteInfo,
)
from .doi_fallback import doi_fallback_download
from .gateway import search_provider, download_from_provider
from .normalizers import normalize_items

DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s\"<>]+", re.IGNORECASE)
PMCID_PATTERN = re.compile(r"\bPMC\d+\b", re.IGNORECASE)
PMID_PATTERN = re.compile(r"PMID[:\s]*([0-9]{5,9})", re.IGNORECASE)

API_PROVIDER_CHAIN: Dict[str, List[str]] = {
    "doi": ["crossref", "unpaywall", "openalex", "europepmc"],
    "pmid": ["pmc"],
    "pmcid": ["pmc"],
    "default": ["crossref", "unpaywall", "openalex", "europepmc"],
}


def _extract_identifiers(texts: List[str]) -> Dict[str, Optional[str]]:
    info: Dict[str, Optional[str]] = {"doi": None, "pmcid": None, "pmid": None}
    for text in texts:
        if not text:
            continue
        if not info["doi"]:
            doi_match = DOI_PATTERN.search(text)
            if doi_match:
                info["doi"] = doi_match.group(0)
        if not info["pmcid"]:
            pmcid_match = PMCID_PATTERN.search(text)
            if pmcid_match:
                info["pmcid"] = pmcid_match.group(0)
        if not info["pmid"]:
            pmid_match = PMID_PATTERN.search(text)
            if pmid_match:
                info["pmid"] = pmid_match.group(1)
            elif text.isdigit() and 5 <= len(text) <= 9:
                info["pmid"] = text
    return info


def _select_initial_provider(
    request: LiteratureRequest,
    identifiers: Dict[str, Optional[str]],
) -> str:
    if request.api_provider:
        return request.api_provider
    if identifiers.get("pmcid") or identifiers.get("pmid"):
        return "pmc"
    if identifiers.get("doi"):
        return "crossref" if request.action == "search" else "unpaywall"
    return "crossref"


def _build_provider_chain(identifiers: Dict[str, Optional[str]]) -> List[str]:
    if identifiers.get("doi"):
        return list(API_PROVIDER_CHAIN["doi"])
    if identifiers.get("pmcid") or identifiers.get("pmid"):
        return list(API_PROVIDER_CHAIN["pmid"])
    return list(API_PROVIDER_CHAIN["default"])


def _build_query(request: LiteratureRequest) -> str:
    if request.query:
        return request.query.strip()
    return " ".join([s for s in request.identifiers if s])


def _build_gateway_identifiers(identifiers: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
    return {k: v for k, v in identifiers.items() if v is not None}


async def _execute_api_search(
    provider: str,
    request: LiteratureRequest,
    identifiers: Dict[str, Optional[str]],
    query: str,
) -> GatewayResult:
    return await search_provider(
        provider=provider,
        query=query,
        identifiers=_build_gateway_identifiers(identifiers),
        limit=request.limit,
        raw=request.raw,
        params=request.api_params,
    )


async def _execute_api_download(
    provider: str,
    request: LiteratureRequest,
    identifiers: Dict[str, Optional[str]],
    query: str,
) -> GatewayResult:
    return await download_from_provider(
        provider=provider,
        query=query,
        identifiers=_build_gateway_identifiers(identifiers),
        limit=request.limit,
        raw=request.raw,
        download_path=request.download_path,
        selected_index=request.selected_index,
        selected_title=request.selected_title,
        detail_link=request.detail_link,
        params=request.api_params,
    )


async def _try_doi_fallback(
    identifiers: Dict[str, Optional[str]],
    request: LiteratureRequest,
    warnings: List[str],
) -> Optional[Dict[str, Any]]:
    doi = identifiers.get("doi")
    if not doi or request.action != "download":
        return None
    fallback = doi_fallback_download(
        doi,
        download_path=request.download_path,
    )
    warnings.extend(fallback.get("warnings") or [])
    if fallback.get("success"):
        return fallback
    return None


async def literature_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Unified literature workflow — search or download with fallback chains."""
    try:
        request = LiteratureRequest.model_validate(payload)
    except Exception as exc:
        route = RouteInfo(prefer="auto", used="none", reason="invalid_request")
        response = LiteratureResponse(
            success=False,
            items=[],
            warnings=[f"invalid_request: {exc}"],
            route=route,
        )
        return response.model_dump()

    query = _build_query(request)
    identifiers = _extract_identifiers([request.query or ""] + request.identifiers)

    route = RouteInfo(
        prefer=request.prefer,
        used="none",
        reason=None,
        fallback_used=False,
    )
    warnings: List[str] = []

    if request.action == "search":
        return await _handle_search(request, identifiers, query, route, warnings)
    return await _handle_download(request, identifiers, query, route, warnings)


async def _handle_search(
    request: LiteratureRequest,
    identifiers: Dict[str, Optional[str]],
    query: str,
    route: RouteInfo,
    warnings: List[str],
) -> Dict[str, Any]:
    """Handle search action with provider chain fallback."""
    if request.api_provider:
        # Single provider specified
        route.api_provider = request.api_provider
        result = await _execute_api_search(request.api_provider, request, identifiers, query)
        items = normalize_items(result.provider, result.items) if result.success else []
        warnings.extend(result.warnings)
        route.used = "api"
        route.reason = f"api_provider:{request.api_provider}"
        return LiteratureResponse(
            success=bool(items),
            items=items,
            warnings=warnings,
            route=route,
            raw=result.raw if request.raw else None,
        ).model_dump()

    # Fallback chain
    provider_chain = _build_provider_chain(identifiers)
    initial = _select_initial_provider(request, identifiers)
    if initial not in provider_chain:
        provider_chain = [initial] + provider_chain

    route.api_provider = initial
    for provider in provider_chain:
        result = await _execute_api_search(provider, request, identifiers, query)
        items = normalize_items(result.provider, result.items) if result.success else []
        warnings.extend(result.warnings)
        if items:
            route.used = "api"
            route.reason = f"api_provider:{provider}"
            return LiteratureResponse(
                success=True,
                items=items,
                warnings=warnings,
                route=route,
                raw=result.raw if request.raw else None,
            ).model_dump()

    route.reason = "api_no_items"
    warnings.append("FETCH_NO_RESULT")
    return LiteratureResponse(
        success=False,
        items=[],
        warnings=warnings,
        route=route,
    ).model_dump()


async def _handle_download(
    request: LiteratureRequest,
    identifiers: Dict[str, Optional[str]],
    query: str,
    route: RouteInfo,
    warnings: List[str],
) -> Dict[str, Any]:
    """Handle download action with provider chain fallback + DOI fallback."""
    if request.api_provider:
        route.api_provider = request.api_provider
        result = await _execute_api_download(request.api_provider, request, identifiers, query)
        warnings.extend(result.warnings)
        if result.success and result.downloads:
            route.used = "api"
            route.reason = f"api_provider:{request.api_provider}"
            return LiteratureResponse(
                success=True,
                downloads=result.downloads,
                warnings=warnings,
                route=route,
                raw=result.raw if request.raw else None,
            ).model_dump()

    # Fallback chain
    provider_chain = _build_provider_chain(identifiers)
    initial = _select_initial_provider(request, identifiers)
    if initial not in provider_chain:
        provider_chain = [initial] + provider_chain

    route.api_provider = initial
    for provider in provider_chain:
        result = await _execute_api_download(provider, request, identifiers, query)
        warnings.extend(result.warnings)
        if result.success and result.downloads:
            route.used = "api"
            route.reason = f"api_provider:{provider}"
            return LiteratureResponse(
                success=True,
                downloads=result.downloads,
                warnings=warnings,
                route=route,
                raw=result.raw if request.raw else None,
            ).model_dump()

    # DOI fallback
    doi_result = await _try_doi_fallback(identifiers, request, warnings)
    if doi_result:
        route.fallback_used = True
        route.reason = "doi_fallback:landing_probe"
        return LiteratureResponse(
            success=True,
            downloads=[{"pdf_url": doi_result.get("pdf_url"), "file_path": doi_result.get("file_path")}],
            warnings=warnings,
            route=route,
        ).model_dump()

    route.reason = "api_download_failed"
    warnings.append("FULLTEXT_UNAVAILABLE")
    return LiteratureResponse(
        success=False,
        downloads=[],
        warnings=warnings,
        route=route,
    ).model_dump()
```

**Step 2: Verify import**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run python -c "from src.core.ingest_and_digitize_data.literature_acquisition.workflow import literature_workflow; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/core/ingest_and_digitize_data/literature_acquisition/workflow.py
git commit -m "feat(literature): add unified workflow with provider fallback chains"
```

---

### Task 8: Module Public API

**Files:**
- Modify: `src/core/ingest_and_digitize_data/literature_acquisition/__init__.py`

**Step 1: Update `__init__.py` with public exports**

```python
"""Literature acquisition module — layered architecture."""

from .contracts import (
    LiteratureItem,
    LiteratureRequest,
    LiteratureResponse,
    RouteInfo,
)
from .doi_fallback import doi_fallback_download, probe_doi_landing_page
from .gateway import call_provider, download_from_provider, search_provider
from .normalizers import normalize_items
from .pubmed_service import PubMedArticle, PubMedCandidate, PubMedService, get_pubmed_service
from .search_service import build_provider_plan, search_multilingual
from .workflow import literature_workflow

__all__ = [
    # Contracts
    "LiteratureItem",
    "LiteratureRequest",
    "LiteratureResponse",
    "RouteInfo",
    # Gateway
    "call_provider",
    "search_provider",
    "download_from_provider",
    # DOI fallback
    "probe_doi_landing_page",
    "doi_fallback_download",
    # PubMed
    "PubMedService",
    "PubMedCandidate",
    "PubMedArticle",
    "get_pubmed_service",
    # Search
    "build_provider_plan",
    "search_multilingual",
    # Workflow
    "literature_workflow",
    # Normalizers
    "normalize_items",
]
```

**Step 2: Verify full module import**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run python -c "from src.core.ingest_and_digitize_data.literature_acquisition import literature_workflow, search_multilingual, get_pubmed_service; print('All exports OK')"`
Expected: `All exports OK`

**Step 3: Commit**

```bash
git add src/core/ingest_and_digitize_data/literature_acquisition/__init__.py
git commit -m "feat(literature): add public API exports for literature acquisition module"
```

---

### Task 9: Unit Tests — Contracts and Normalizers

**Files:**
- Create: `tests/core/ingest_and_digitize_data/literature_acquisition/__init__.py`
- Create: `tests/core/ingest_and_digitize_data/literature_acquisition/test_contracts.py`
- Create: `tests/core/ingest_and_digitize_data/literature_acquisition/test_normalizers.py`

**Step 1: Create test directories**

```bash
mkdir -p tests/core/ingest_and_digitize_data/literature_acquisition
touch tests/core/ingest_and_digitize_data/literature_acquisition/__init__.py
```

**Step 2: Create `test_contracts.py`**

```python
"""Tests for literature acquisition contracts."""

from src.core.ingest_and_digitize_data.literature_acquisition.contracts import (
    LiteratureItem,
    LiteratureRequest,
    LiteratureResponse,
    RouteInfo,
)


class TestLiteratureRequest:
    def test_default_values(self):
        req = LiteratureRequest()
        assert req.action == "search"
        assert req.limit == 20
        assert req.prefer == "auto"
        assert req.identifiers == []

    def test_identifier_alias(self):
        req = LiteratureRequest(identifier="10.1234/test")
        assert req.identifiers == ["10.1234/test"]

    def test_text_alias(self):
        req = LiteratureRequest(text="cancer therapy")
        assert req.query == "cancer therapy"

    def test_limit_clamped(self):
        req = LiteratureRequest(limit=500)
        assert req.limit == 200
        req = LiteratureRequest(limit=0)
        assert req.limit == 1

    def test_identifiers_normalized(self):
        req = LiteratureRequest(identifiers="single-id")
        assert req.identifiers == ["single-id"]
        req = LiteratureRequest(identifiers=["a", "b"])
        assert req.identifiers == ["a", "b"]


class TestLiteratureItem:
    def test_construction(self):
        item = LiteratureItem(source="crossref", title="Test Paper")
        assert item.source == "crossref"
        assert item.title == "Test Paper"
        assert item.authors == []
        assert item.identifiers == {}


class TestRouteInfo:
    def test_defaults(self):
        route = RouteInfo(prefer="auto")
        assert route.used is None
        assert route.fallback_used is False


class TestLiteratureResponse:
    def test_success_response(self):
        route = RouteInfo(prefer="auto", used="api", reason="api_provider:crossref")
        resp = LiteratureResponse(success=True, items=[], route=route)
        assert resp.success is True
        assert resp.warnings == []

    def test_model_dump(self):
        route = RouteInfo(prefer="auto")
        resp = LiteratureResponse(success=False, route=route)
        data = resp.model_dump()
        assert "success" in data
        assert "route" in data
```

**Step 3: Create `test_normalizers.py`**

```python
"""Tests for provider normalizers."""

from src.core.ingest_and_digitize_data.literature_acquisition.normalizers import (
    normalize_crossref,
    normalize_doaj,
    normalize_europepmc,
    normalize_jstage,
    normalize_openalex,
    normalize_pmc,
    normalize_unpaywall,
    normalize_items,
    NORMALIZER_MAP,
)


class TestNormalizerRegistry:
    def test_all_providers_registered(self):
        expected = {"crossref", "unpaywall", "pmc", "jstage", "doaj", "openalex", "europepmc"}
        assert set(NORMALIZER_MAP.keys()) == expected

    def test_normalize_items_unknown_provider(self):
        assert normalize_items("unknown", [{"title": "test"}]) == []

    def test_normalize_items_empty(self):
        assert normalize_items("crossref", []) == []


class TestCrossrefNormalizer:
    def test_basic_item(self):
        raw = {
            "title": ["Test Paper Title"],
            "author": [{"given": "John", "family": "Doe"}],
            "container-title": ["Journal of Testing"],
            "DOI": "10.1234/test",
            "URL": "https://doi.org/10.1234/test",
            "issued": {"date-parts": [[2024]]},
        }
        item = normalize_crossref(raw)
        assert item.source == "crossref"
        assert item.title == "Test Paper Title"
        assert item.authors == ["John Doe"]
        assert item.journal == "Journal of Testing"
        assert item.doi == "10.1234/test"
        assert item.year == "2024"

    def test_minimal_item(self):
        item = normalize_crossref({})
        assert item.source == "crossref"
        assert item.title is None


class TestUnpaywallNormalizer:
    def test_with_best_oa(self):
        raw = {
            "title": "OA Paper",
            "doi": "10.1234/oa",
            "best_oa_location": {"url_for_pdf": "https://example.com/paper.pdf"},
        }
        item = normalize_unpaywall(raw)
        assert item.source == "unpaywall"
        assert item.title == "OA Paper"
        assert "https://example.com/paper.pdf" in item.links


class TestPmcNormalizer:
    def test_basic_item(self):
        raw = {
            "title": "PMC Article",
            "authors": ["Author A", "Author B"],
            "journal_title": "PMC Journal",
        }
        item = normalize_pmc(raw)
        assert item.source == "pmc"
        assert item.title == "PMC Article"


class TestJstageNormalizer:
    def test_japanese_title(self):
        raw = {
            "article_title_ja": "日本語のタイトル",
            "article_title_en": "Japanese Title",
            "material_title_en": "J-Stage Journal",
            "doi": "10.1234/jstage",
        }
        item = normalize_jstage(raw)
        assert item.source == "jstage"
        assert item.title == "Japanese Title"
        assert item.language == "ja"


class TestDoajNormalizer:
    def test_basic_item(self):
        raw = {
            "title": "DOAJ Article",
            "journal_title": "DOAJ Journal",
            "doi": "10.1234/doaj",
        }
        item = normalize_doaj(raw)
        assert item.source == "doaj"
        assert item.title == "DOAJ Article"


class TestOpenalexNormalizer:
    def test_basic_item(self):
        raw = {
            "title": "OpenAlex Paper",
            "publication_year": 2023,
            "doi": "https://doi.org/10.1234/oalex",
        }
        item = normalize_openalex(raw)
        assert item.source == "openalex"
        assert item.year == "2023"


class TestEuropepmcNormalizer:
    def test_basic_item(self):
        raw = {
            "title": "Europe PMC Paper",
            "journalTitle": "EPMC Journal",
            "pubYear": "2022",
            "doi": "10.1234/epmc",
        }
        item = normalize_europepmc(raw)
        assert item.source == "europepmc"
        assert item.year == "2022"
```

**Step 4: Run tests**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/ingest_and_digitize_data/literature_acquisition/ -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add tests/core/ingest_and_digitize_data/literature_acquisition/
git commit -m "test(literature): add unit tests for contracts and normalizers"
```

---

### Task 10: Unit Tests — Gateway and Workflow

**Files:**
- Create: `tests/core/ingest_and_digitize_data/literature_acquisition/test_gateway.py`
- Create: `tests/core/ingest_and_digitize_data/literature_acquisition/test_workflow.py`

**Step 1: Create `test_gateway.py`**

```python
"""Tests for gateway module — with mocked rust_io."""

from unittest.mock import AsyncMock, patch

import pytest

from src.core.ingest_and_digitize_data.literature_acquisition.gateway import (
    _build_fetch_params,
    _rust_result_to_gateway,
    call_provider,
    search_provider,
)
from src.core.ingest_and_digitize_data.literature_acquisition.contracts import GatewayRequest


class TestBuildFetchParams:
    def test_basic_params(self):
        request = GatewayRequest(provider="crossref", action="search", query="cancer", limit=10)
        params = _build_fetch_params(request)
        assert params["query"] == "cancer"
        assert params["limit"] == 10
        assert params["raw"] is False

    def test_with_identifiers(self):
        request = GatewayRequest(
            provider="unpaywall",
            identifiers={"doi": "10.1234/test"},
        )
        params = _build_fetch_params(request)
        assert params["identifiers"] == {"doi": "10.1234/test"}


class TestRustResultToGateway:
    def test_success_result(self):
        raw = {
            "provider": "crossref",
            "success": True,
            "items": [{"title": "Paper"}],
            "downloads": [],
            "warnings": [],
        }
        result = _rust_result_to_gateway("crossref", raw)
        assert result.success is True
        assert len(result.items) == 1

    def test_failure_result(self):
        raw = {
            "provider": "crossref",
            "success": False,
            "items": [],
            "downloads": [],
            "warnings": ["error"],
        }
        result = _rust_result_to_gateway("crossref", raw)
        assert result.success is False


class TestCallProvider:
    @pytest.mark.asyncio
    async def test_rust_io_not_available(self):
        with patch("builtins.__import__", side_effect=ImportError("no rust_io")):
            result = await call_provider(GatewayRequest(provider="crossref"))
            assert result.success is False
            assert "not available" in result.warnings[0]
```

**Step 2: Create `test_workflow.py`**

```python
"""Tests for workflow module — with mocked gateway."""

from unittest.mock import AsyncMock, patch

import pytest

from src.core.ingest_and_digitize_data.literature_acquisition.workflow import (
    _extract_identifiers,
    _select_initial_provider,
    _build_provider_chain,
    literature_workflow,
)


class TestExtractIdentifiers:
    def test_doi_extraction(self):
        ids = _extract_identifiers(["10.1234/test.paper"])
        assert ids["doi"] == "10.1234/test.paper"

    def test_pmid_extraction(self):
        ids = _extract_identifiers(["PMID: 12345678"])
        assert ids["pmid"] == "12345678"

    def test_pmcid_extraction(self):
        ids = _extract_identifiers(["PMC12345678"])
        assert ids["pmcid"] == "PMC12345678"

    def test_multiple_identifiers(self):
        ids = _extract_identifiers(["10.1234/test", "PMID: 99999"])
        assert ids["doi"] == "10.1234/test"
        assert ids["pmid"] == "99999"


class TestSelectInitialProvider:
    def test_doi_search(self):
        from src.core.ingest_and_digitize_data.literature_acquisition.contracts import LiteratureRequest
        req = LiteratureRequest(action="search")
        ids = {"doi": "10.1234/test", "pmcid": None, "pmid": None}
        assert _select_initial_provider(req, ids) == "crossref"

    def test_doi_download(self):
        from src.core.ingest_and_digitize_data.literature_acquisition.contracts import LiteratureRequest
        req = LiteratureRequest(action="download")
        ids = {"doi": "10.1234/test", "pmcid": None, "pmid": None}
        assert _select_initial_provider(req, ids) == "unpaywall"

    def test_pmid(self):
        from src.core.ingest_and_digitize_data.literature_acquisition.contracts import LiteratureRequest
        req = LiteratureRequest()
        ids = {"doi": None, "pmcid": None, "pmid": "12345"}
        assert _select_initial_provider(req, ids) == "pmc"


class TestBuildProviderChain:
    def test_doi_chain(self):
        ids = {"doi": "10.1234/test", "pmcid": None, "pmid": None}
        chain = _build_provider_chain(ids)
        assert "crossref" in chain
        assert "unpaywall" in chain

    def test_pmid_chain(self):
        ids = {"doi": None, "pmcid": None, "pmid": "12345"}
        chain = _build_provider_chain(ids)
        assert chain == ["pmc"]


class TestLiteratureWorkflow:
    @pytest.mark.asyncio
    async def test_invalid_request(self):
        result = await literature_workflow({"action": "invalid"})
        assert result["success"] is False
        assert "invalid_request" in result["warnings"][0]

    @pytest.mark.asyncio
    async def test_search_no_providers(self):
        with patch(
            "src.core.ingest_and_digitize_data.literature_acquisition.workflow.search_provider",
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = AsyncMock(
                success=False, items=[], downloads=[], warnings=[], provider="crossref"
            )
            result = await literature_workflow({"action": "search", "query": "test"})
            assert "FETCH_NO_RESULT" in str(result.get("warnings"))
```

**Step 3: Run tests**

Run: `cd /data/[redacted-user]/Projects/01_ACMG_Lingua/backend && uv run pytest tests/core/ingest_and_digitize_data/literature_acquisition/ -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add tests/core/ingest_and_digitize_data/literature_acquisition/test_gateway.py tests/core/ingest_and_digitize_data/literature_acquisition/test_workflow.py
git commit -m "test(literature): add unit tests for gateway and workflow"
```

---

### Task 11: Progress Logging

**Files:**
- Modify: `progress.txt`

**Step 1: Log milestone**

Append to `progress.txt`:
```
[2026-05-06] literature_acquisition module: contracts, normalizers, gateway, doi_fallback, pubmed_service, search_service, workflow [completed]
```

**Step 2: Commit**

```bash
git add progress.txt
git commit -m "chore: log literature acquisition module completion in progress.txt"
```

---

## Summary

| Task | Component | I/O Boundary | Key Files |
|------|-----------|-------------|-----------|
| 1 | Contracts | — | `contracts.py` |
| 2 | Normalizers | — | `normalizers.py` |
| 3 | Gateway | `rust_io.literature` | `gateway.py` |
| 4 | DOI Fallback | httpx (HTML parsing) | `doi_fallback.py` |
| 5 | PubMed | httpx (XML API) | `pubmed_service.py` |
| 6 | Search Service | — | `search_service.py` |
| 7 | Workflow | — | `workflow.py` |
| 8 | Public API | — | `__init__.py` |
| 9 | Tests (data) | — | `test_contracts.py`, `test_normalizers.py` |
| 10 | Tests (logic) | — | `test_gateway.py`, `test_workflow.py` |
| 11 | Progress | — | `progress.txt` |

**Delegation to rust_io:**
- All 7 API provider HTTP calls (crossref, doaj, europepmc, jstage, openalex, pmc, unpaywall) → `rust_io.literature.fetch_one()`
- Web scraping → `rust_io.literature.scrape_web()`

**Stays in Python (I/O acceptable):**
- DOI landing page probe (complex HTML parsing for PDF links)
- PubMed XML API (esearch/esummary/efetch with XML parsing)
- All business logic (routing, normalization, fallback chains)
