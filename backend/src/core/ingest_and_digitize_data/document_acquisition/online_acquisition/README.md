# Online Acquisition Module

> Phase 1 submodule — searches and downloads academic literature from **14 API providers** with multi-level fallback chains, DOI resolution, and multilingual support. Web scrapers were archived on 2026-06-16.

## Quick Start

```python
import asyncio
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition import (
    online_acquisition_workflow,
)

result = asyncio.run(online_acquisition_workflow({
    "action": "search",
    "query": "BRCA1 breast cancer",
    "limit": 10,
}))
print(f"Found {len(result['items'])} items via {result['route']['used']}")
```

## Architecture

```
online_acquisition_workflow() [workflow.py]  ← single public entry point
│
├─ _extract_identifiers()   — parse DOI/PMID/PMCID from query text
├─ _build_provider_chain()  — select fallback chain based on identifier type
│
├─ SEARCH path:
│   └─ _handle_search()
│       ├─ search_provider() → call_provider_with_retry() → call_provider()
│       │   └─ net_io.fetch_one() [Rust]  → 14 API providers
│       ├─ normalize_items()  → per-provider → OnlineAcquisitionItem
│       ├─ _apply_literature_type_filter()  → classify + filter
│       └─ DOI fallback → probe_doi_landing_page()
│
├─ DOWNLOAD path:
│   └─ _handle_download()
│       ├─ download_from_provider()  → net_io + _download_pdf_from_candidates()
│       └─ DOI fallback → doi_fallback_download()
│
└─ ProviderHealthTracker  — sliding-window stats, auto-deprioritizes unhealthy providers
```

### Provider Catalog

| Type | Providers |
|------|-----------|
| **API** (via Rust `net-io`) | crossref, unpaywall, openalex, europepmc, pmc, jstage, doaj, scielo, base, core, openaire, arxiv, biorxiv, cinii |

**Note**: Web scrapers (pubscholar, cyberleninka, hans_publishers, chinaxiv, koreascience, redalyc) were archived on 2026-06-16. See `docs/archive/deprecated-modules/web-scraper-adapters/`.

### Fallback Chain

```
DOI query → [crossref → unpaywall → openalex → europepmc] → DOI landing probe
PMID/PMCID → [pmc] → DOI fallback
Text query → [crossref → ...]
```

**Note**: Web scraper fallback tier was removed on 2026-06-16.

## Public API

### `online_acquisition_workflow(payload: dict) -> dict`

Single entry point. Accepts a dict matching `OnlineAcquisitionRequest`, returns a dict matching `OnlineAcquisitionResponse`.

```python
async def online_acquisition_workflow(payload: Dict[str, Any]) -> Dict[str, Any]
```

### Data Types

| Type | Kind | Description |
|------|------|-------------|
| `OnlineAcquisitionRequest` | `pydantic.BaseModel` | Input: action, query, identifiers, limit, provider preferences |
| `OnlineAcquisitionResponse` | `pydantic.BaseModel` | Output: items, downloads, route info, warnings |
| `OnlineAcquisitionItem` | `pydantic.BaseModel` | Standardized metadata: title, authors, DOI, journal, year |
| `OnlineAcquisitionRouteInfo` | `pydantic.BaseModel` | Routing decision: which provider was used, fallback chain |
| `OnlineAcquisitionGatewayRequest` | `dataclass` | Internal: per-provider call parameters |
| `OnlineAcquisitionGatewayResult` | `dataclass` | Internal: per-provider return (items, downloads, traces) |
| `OnlineAcquisitionSourceTraceEntry` | `dataclass` | Debug: per-attempt trace for diagnostics |

### Key Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `call_provider` | `async (OnlineAcquisitionGatewayRequest) -> OnlineAcquisitionGatewayResult` | Single provider call via net-io |
| `call_provider_with_retry` | `async (request, max_attempts=2) -> OnlineAcquisitionGatewayResult` | Retry wrapper with trace aggregation |
| `search_provider` | `async (provider, query, identifiers, limit, raw, params) -> OnlineAcquisitionGatewayResult` | Shorthand for search action |
| `download_from_provider` | `async (provider, ..., download_path, selected_index, selected_title) -> OnlineAcquisitionGatewayResult` | Download with candidate URL resolution |
| `normalize_items` | `(provider, List[dict]) -> List[OnlineAcquisitionItem]` | Per-provider normalization to unified schema |
| `probe_doi_landing_page` | `async (doi, timeout, email, proxy) -> dict` | Probe DOI for direct PDF link |
| `doi_fallback_download` | `async (doi, download_path, email, timeout, proxy) -> dict` | Download PDF via DOI landing page |
| `classify_item` | `(OnlineAcquisitionItem) -> LiteratureType \| None` | Keyword-based classification |
| `get_health_tracker` | `() -> ProviderHealthTracker` | Thread-safe singleton for provider stats |

### Provider-Specific Normalizers

| Normalizer | Provider | Special Handling |
|------------|----------|------------------|
| `normalize_crossref` | crossref | Nested author structures, ISSN extraction |
| `normalize_unpaywall` | unpaywall | best_oa_location for OA status |
| `normalize_pmc` | pmc | Esummary format (articleids), generic XML |
| `normalize_openalex` | openalex | Nested authorships, primary_location.source |
| `normalize_europepmc` | europepmc | fullTextUrlList for PDF links |
| `normalize_web_generic` | (archived) | Previously handled web scraper output |

**Note**: Web provider normalizers were archived on 2026-06-16.

## Internal Design

### Provider routing strategy

1. **Explicit provider** (`request.api_provider` set) → skip chain, call directly
2. **Identifier-based** (DOI/PMID/PMCID detected) → chain pre-selected
3. **Text query** → default chain (API providers only)

**Note**: Web fallback was removed on 2026-06-16.

### DOI resolution

- Unicode hyphens are normalized to ASCII (`‐‑‒–—` → `-`)
- DOI landing pages are probed for direct PDF links
- Chinese domains (yiigle.com, wanfangdata.com.cn) are detected — DOI resolves but PDF requires institutional access

### Concurrency model

- All I/O is `async` via `httpx.AsyncClient`
- Gateway calls use retry with 0.5s × attempt backoff
- Health tracker uses `threading.Lock` (not asyncio) for cross-context safety

### Error handling

- Provider failures → `OnlineAcquisitionGatewayResult(success=False, warnings=[...])`, never exceptions
- Invalid requests → `OnlineAcquisitionResponse(success=False, ...)` with route info
- `source_trace` records every attempt for debugging

## Usage Patterns

### Search by DOI

```python
result = asyncio.run(online_acquisition_workflow({
    "action": "search",
    "identifiers": ["10.1038/s41586-020-2000-0"],
    "limit": 5,
}))
```

### Download PDF

```python
result = asyncio.run(online_acquisition_workflow({
    "action": "download",
    "query": "CRISPR gene editing review",
    "download_path": "./downloads",
}))
# result["downloads"][0]["file_path"] contains the local PDF path
```

### Filter by literature type

```python
result = asyncio.run(online_acquisition_workflow({
    "action": "search",
    "query": "TP53 mutations",
    "literature_types": ["case_report", "functional"],
}))
```

### Use a specific API provider

```python
result = asyncio.run(online_acquisition_workflow({
    "action": "search",
    "query": "genetic variants",
    "api_provider": "europepmc",
    "prefer": "api",
}))
```

## Extension Guide

### Adding a new API provider

1. Add provider name to `ApiProvider` literal in `contracts.py`
2. Implement the provider in `backend/libs/net-io/src/providers/` (Rust) — the Python layer just calls `net_io.fetch_one(provider=name, ...)`
3. Add a normalizer in `normalizers.py`
4. Add to `NORMALIZER_MAP` registry
5. Optionally add to `API_PROVIDER_CHAIN` in `workflow.py`

### Adding a new web scraper (Archived)

Web scraper adapters are no longer maintained. The archived module at `docs/archive/deprecated-modules/web-scraper-adapters/` contains the original implementation for reference only. New providers should be implemented as Rust-based API providers in `backend/libs/net-io/`.

### Changing the fallback chain

Modify `API_PROVIDER_CHAIN` in `workflow.py`:

```python
API_PROVIDER_CHAIN = {
    "doi": ["crossref", "unpaywall", "openalex", "europepmc"],
    "pmid": ["pmc"],
    "default": ["crossref", "unpaywall", "openalex", "europepmc"],
}
```

## Performance Notes

- Each provider call takes 0.5–5s depending on API latency
- Fallback chains multiply latency (3 providers × 2s = 6s worst case)
- PDF downloads can take 10–60s for large files
- `httpx.AsyncClient` is created per-request (not pooled) — expect connection overhead
- Literature classifier runs in ~1ms (regex-only, no LLM)

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `httpx` | Async HTTP client for DOI probing and PDF download |
| `src.utils.rust_io.net_io` | Rust-native provider calls (14 API providers) |
| `src.utils.text.sanitize_filename` | Safe filename generation |
| `pydantic` | Request/response validation |
| `dataclasses` | Internal contract types |
| `re` | DOI detection, literature classification |
| `threading` | Provider health tracker locking |

## Testing

```bash
uv run pytest tests/ -k "online_acquisition" -v
```

Tests exercise: provider selection, identifier extraction, normalizer output shape, workflow error handling, and literature classification accuracy.
