# Document Acquisition

> Unified document acquisition facade for ACMG Lingua's Phase 1 pipeline. Provides a single `acquire()` entry point that routes to either local file upload or online literature search/download with multi-provider fallback chains.

## Quick Start

```python
from src.core.ingest_and_digitize_data.document_acquisition import (
    DocumentAcquisitionService,
    DocumentAcquisitionRequest,
    AcquisitionSource,
)

service = DocumentAcquisitionService()

# Upload a local PDF with deduplication
result = await service.acquire(DocumentAcquisitionRequest(
    source=AcquisitionSource.LOCAL,
    filename="paper.pdf",
    content=open("paper.pdf", "rb").read(),
    deduplicate=True,
))

# Search literature by query
result = await service.acquire(DocumentAcquisitionRequest(
    source=AcquisitionSource.ONLINE,
    action="search",
    query="BRCA1 variant classification",
    limit=10,
))

# Download full-text PDF by DOI
result = await service.acquire(DocumentAcquisitionRequest(
    source=AcquisitionSource.ONLINE,
    action="download",
    identifiers=["10.1234/example.doi"],
    download_path="./downloads",
))
```

## Architecture

```
DocumentAcquisitionService (facade)
├── source=LOCAL ──► local_upload/
│   ├── workflow.upload_document()
│   ├── service.validate_local_upload()
│   └── service.store_local_file()
│       └── rust_io.files (SHA-256 + disk write)
│
└── source=ONLINE ──► online_acquisition/
    ├── workflow.online_acquisition_workflow()
    │   ├── Identifier extraction (DOI/PMID/PMCID regex)
    │   ├── Provider chain selection (API vs Web)
    │   ├── _handle_search() — iterates API provider chain
    │   └── _handle_download() — API chain → DOI fallback → Web fallback
    │
    ├── gateway.py (net_io bridge)
    │   ├── call_provider() → net_io.fetch_one()
    │   ├── search_provider() — with retry
    │   └── download_from_provider() — candidate URL → PDF download
    │
    ├── search_service.py (multilingual orchestration)
    │   ├── build_provider_plan() — language-based routing
    │   ├── search_multilingual() — serial search with dedup
    │   └── search_parallel() — concurrent search with asyncio.Semaphore
    │
    ├── doi_fallback.py — DOI landing page probe → PDF extraction
    ├── web_providers.py — dispatcher to JS-rendered scrapers
    ├── normalizers.py — per-provider → OnlineAcquisitionItem
    ├── pubmed_service.py — PubMed esearch/esummary/efetch
    ├── provider_health.py — sliding-window health tracking
    ├── literature_type_classifier.py — keyword-based classification
    │
    └── web/ (crawl4ai + httpx scrapers)
        ├── base.py — shared crawl4ai/HTML utilities
        ├── pubscholar.py — PubScholar (Chinese)
        ├── cyberleninka.py — CyberLeninka (Russian)
        ├── hans_publishers.py — Hans Publishers (Chinese)
        ├── chinaxiv.py — ChinaXiv (Chinese)
        ├── koreascience.py — KoreaScience (Korean)
        ├── redalyc.py — Redalyc / La Referencia (Spanish/Portuguese)
        └── locators.py — XPath/CSS selectors for UI automation
```

Data flows top-down: the facade dispatches to a submodule, which calls the gateway (Rust `net_io`) for API providers or the web scrapers for JS-rendered sites. All raw provider responses are normalized to `OnlineAcquisitionItem` before returning.

## Public API

### `DocumentAcquisitionService`

| Method | Signature | Description |
|--------|-----------|-------------|
| `acquire` | `async acquire(request: DocumentAcquisitionRequest) -> DocumentAcquisitionResult` | Single entry point. Routes to local upload or online acquisition based on `request.source`. |

### `DocumentAcquisitionRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source` | `AcquisitionSource` | required | `"local"` or `"online"` |
| `filename` | `Optional[str]` | `None` | Original filename (local upload) |
| `content` | `Optional[bytes]` | `None` | Raw file bytes (local upload) |
| `content_type` | `Optional[str]` | `None` | MIME type (local upload) |
| `upload_dir` | `Optional[str]` | `None` | Target directory; `None` = temp dir |
| `deduplicate` | `bool` | `False` | Skip write if SHA-256 matches existing file |
| `action` | `Optional[str]` | `None` | `"search"` or `"download"` (online) |
| `query` | `Optional[str]` | `None` | Search query text |
| `identifiers` | `Optional[List[str]]` | `None` | DOI, PMID, or PMCID strings |
| `limit` | `int` | `20` | Max results (1–200) |
| `download_path` | `str` | `"./downloads"` | PDF save directory |
| `language` | `Optional[str]` | `"auto"` | Language hint for provider routing |
| `prefer` | `str` | `"auto"` | `"auto"`, `"api"`, or `"web"` |
| `web_provider` | `Optional[str]` | `None` | Force a specific web provider |
| `api_provider` | `Optional[str]` | `None` | Force a specific API provider |
| `max_retries` | `int` | `3` | Max retry attempts |
| `timeout` | `int` | `60` | Timeout in seconds |

### `DocumentAcquisitionResult`

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether acquisition succeeded |
| `source` | `AcquisitionSource` | Which source was used |
| `warnings` | `List[str]` | Non-fatal warnings (e.g. `"FETCH_NO_RESULT"`) |
| `error` | `Optional[str]` | Error message on failure |
| `stored_file` | `Optional[LocalStoredFile]` | Local upload result (path, SHA-256, size) |
| `deduplicated` | `bool` | Whether file was skipped due to dedup |
| `items` | `List[OnlineAcquisitionItem]` | Search result items |
| `downloads` | `List[DocumentDownloadEntry]` | Download result entries |
| `route` | `Optional[OnlineAcquisitionRouteInfo]` | Provider routing decision |
| `elapsed_time` | `float` | Wall-clock seconds |

### `OnlineAcquisitionItem` (Pydantic)

Standardized literature metadata returned by all providers after normalization.

| Field | Type | Description |
|-------|------|-------------|
| `source` | `str` | Provider name (e.g. `"crossref"`, `"pubscholar"`) |
| `title` | `Optional[str]` | Article title |
| `authors` | `List[str]` | Author names |
| `journal` | `Optional[str]` | Journal name |
| `year` | `Optional[str]` | Publication year |
| `doi` | `Optional[str]` | DOI |
| `url` | `Optional[str]` | Primary URL |
| `links` | `List[str]` | All discovered URLs |
| `language` | `Optional[str]` | ISO language code |
| `identifiers` | `Dict[str, Any]` | Provider-specific IDs (pmcid, pmid, issn) |
| `keywords` | `List[str]` | Subject keywords |
| `literature_type` | `Optional[str]` | Classification: `case_report`, `sequencing`, `functional` |

## Internal Design

### Provider Fallback Chain

The workflow uses a cascading fallback strategy for both search and download:

1. **API providers** (Rust `net_io`): crossref → unpaywall → openalex → europepmc → pmc → jstage → doaj → scielo → base → core → openaire → arxiv → biorxiv → medrxiv → cinii
2. **DOI fallback**: If API providers fail and a DOI is available, probe the DOI landing page for a direct PDF link
3. **Web providers** (Python crawl4ai/httpx): pubscholar, cyberleninka, hans_publishers, chinaxiv, koreascience, redalyc, la_referencia

The initial provider is selected based on identifier type:
- PMCID/PMID → `pmc`
- DOI + search → `crossref`
- DOI + download → `unpaywall`
- No identifier → `crossref`

### Multilingual Routing

`search_service.build_provider_plan()` selects provider order based on language:

| Language | Priority |
|----------|----------|
| `zh` (Chinese) | pubscholar → chinaxiv → hans_publishers → crossref → unpaywall → doaj → pmc |
| `ja` (Japanese) | jstage → cinii → crossref → unpaywall → doaj → pmc |
| `ko` (Korean) | koreascience → crossref → unpaywall → doaj |
| `es`/`pt` (Spanish/Portuguese) | scielo → redalyc → crossref → unpaywall |
| `en` (English) | pmc → crossref → arxiv → biorxiv → medrxiv → openaire → base → core → unpaywall → doaj |
| `auto` | crossref → unpaywall → doaj → pmc |

### Provider Health Tracking

`ProviderHealthTracker` maintains a thread-safe sliding window (default 1 hour) of success/failure records per provider. `reorder_plan()` deprioritizes providers with <50% success rate (minimum 3 samples). Each `call_provider()` call records latency and outcome.

### Normalization

Each API provider has a dedicated normalizer function in `normalizers.py` that maps raw JSON responses to `OnlineAcquisitionItem`. The `NORMALIZER_MAP` registry dispatches by provider name. Web providers use `normalize_web_generic()` for a common schema.

### Identifier Extraction

`workflow._extract_identifiers()` uses regex patterns to extract structured identifiers from free text:
- DOI: `10.xxxx/...`
- PMCID: `PMCxxxxxx`
- PMID: `PMID: xxxxxxx` or bare 5–9 digit numbers

Unicode hyphen/dash variants in DOIs are normalized to ASCII hyphens (`gateway._normalize_doi()`).

### Literature Type Classifier

`literature_type_classifier.classify_item()` categorizes articles by keyword matching in title and journal name:
- **case_report**: "case report", "case series", 病例报告, 症例報告, 증례 보고, etc.
- **sequencing**: "NGS", "whole exome sequencing", 基因测序, etc.
- **functional**: "in vitro", "knockout", 功能研究, etc.

Supports English, Chinese, Japanese, Korean, Spanish, Portuguese, and Russian keywords.

### Web Scrapers

Web providers use a two-tier strategy:
1. **Direct HTTP** (httpx): Try public APIs or static HTML parsing first (fastest)
2. **Browser automation** (crawl4ai): Fallback for JS-rendered sites. Uses `LLMExtractionStrategy` to extract structured data from rendered pages

Shared utilities in `web/base.py`: `crawl4ai_search()` orchestrates browser + LLM extraction; `download_pdf_from_candidates()` validates `%PDF` magic bytes; `extract_pdf_links_from_html()` uses Rust parser when available, falls back to selectolax.

### File Deduplication (Local Upload)

When `deduplicate=True`, the service computes SHA-256 of the file content before writing. If a file with the same hash already exists in `upload_dir`, it returns the existing path without writing. File names are `{sha256}{ext}`.

Storage uses `rust_io.files.File.write()` when available for verified disk I/O with SHA-256 verification from disk. Falls back to Python `open()` + `hashlib` when Rust is not installed.

## Usage Patterns

### Search with language-specific routing

```python
from src.core.ingest_and_digitize_data.document_acquisition import (
    DocumentAcquisitionService, DocumentAcquisitionRequest, AcquisitionSource,
)

service = DocumentAcquisitionService()
result = await service.acquire(DocumentAcquisitionRequest(
    source=AcquisitionSource.ONLINE,
    action="search",
    query="BRCA1 遗传变异",
    language="zh",
    limit=15,
))

# route.used shows which provider succeeded
print(result.route.used)     # "web"
print(result.route.web_provider)  # "pubscholar"
```

### Download by DOI with fallback

```python
result = await service.acquire(DocumentAcquisitionRequest(
    source=AcquisitionSource.ONLINE,
    action="download",
    identifiers=["10.1038/s41586-020-2649-8"],
    download_path="./papers",
    prefer="auto",
))

if result.success and result.downloads:
    print(result.downloads[0].file_path)  # "./papers/10.1038_s41586-020-2649-8.pdf"
```

### Force a specific provider

```python
result = await service.acquire(DocumentAcquisitionRequest(
    source=AcquisitionSource.ONLINE,
    action="search",
    query="variant classification ACMG",
    api_provider="openalex",
    limit=5,
))
```

### Direct search service usage (for orchestrator integration)

```python
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition import search_multilingual

candidates = await search_multilingual(
    target="BRCA1 c.5266dupC",
    disease="breast cancer",
    language="auto",
    candidate_limit=10,
)
# Returns ranked, deduplicated candidate list with candidate_id
```

### Parallel search with semaphore

```python
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition import search_multilingual
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.search_service import search_parallel

# Concurrent provider calls with semaphore control
candidates = await search_parallel(
    target="Fabry disease GLA variant",
    disease="Fabry disease",
    language="auto",
    candidate_limit=10,
    max_concurrency=4,
)
```

### PubMed article fetch

```python
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition import get_pubmed_service

pubmed = get_pubmed_service()
candidates = await pubmed.search_candidates("BRCA1 pathogenic variant", candidate_limit=5)
article = await pubmed.fetch_article(candidates[0].pmid)
print(article.abstract)
```

### Local upload with deduplication

```python
result = await service.acquire(DocumentAcquisitionRequest(
    source=AcquisitionSource.LOCAL,
    filename="report.pdf",
    content=pdf_bytes,
    upload_dir="./uploads",
    deduplicate=True,
))

if result.deduplicated:
    print("File already exists at", result.stored_file.file_path)
```

## Extension Guide

### Adding a new API provider

1. Implement the provider in Rust `net-io` crate with `search` and `download` actions
2. Add the provider name to `ApiProvider` literal type in `contracts.py`
3. Add a normalizer function in `normalizers.py` and register in `NORMALIZER_MAP`
4. Add to `API_PROVIDER_CHAIN` in `workflow.py` for fallback inclusion
5. Add to `LANG_PROVIDER_MATRIX` in `search_service.py` for language-based routing

### Adding a new web scraper

1. Create `online_acquisition/web/<provider>.py` with `<provider>_search()` and `<provider>_download()` functions
2. Use `crawl4ai_search()` from `base.py` for JS-rendered sites, or httpx for static pages
3. Register in `web_providers.py` `call_web_provider()` dispatcher
4. Add `XPath/CSS` locators to `web/locators.py`
5. Add to `WebProvider` literal type in `contracts.py`
6. Add to `LANG_PROVIDER_MATRIX` if language-specific

### Modifying the fallback chain

Edit `API_PROVIDER_CHAIN` in `workflow.py` to change the order or add/remove providers from the fallback sequence. The chain is selected by identifier type (doi/pmid/pmcid/default).

## Performance Notes

- **Rust I/O**: API provider HTTP calls go through `net_io.fetch_one()` (Rust/PyO3), which handles connection pooling and async I/O natively
- **Retry**: `call_provider_with_retry()` retries up to 2 attempts with exponential backoff (0.5s × attempt)
- **Health-based reordering**: Unhealthy providers (<50% success rate) are deprioritized in multilingual search
- **Deduplication**: `search_service.dedupe_candidates()` uses DOI/URL/title matching; O(n) per provider call
- **Web scrapers**: crawl4ai launches a headless browser per request; avoid using for high-throughput scenarios. Direct HTTP is attempted first
- **Concurrency**: `search_parallel()` uses `asyncio.Semaphore(4)` for concurrent provider calls
- **PDF validation**: All downloaded PDFs are validated by checking `%PDF` magic bytes before writing to disk

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `rust_io.net` (via `src.utils.rust_io`) | HTTP I/O for API providers (crossref, unpaywall, etc.) |
| `rust_io.files` (via `src.utils.rust_io`) | SHA-256 hashing and file write for local upload |
| `httpx` | Async HTTP for DOI fallback, web scrapers, PDF download |
| `selectolax` | Fast HTML parsing for web scrapers |
| `crawl4ai` | Headless browser automation for JS-rendered academic sites |
| `pydantic` | Request/response validation (`OnlineAcquisitionRequest`, `OnlineAcquisitionItem`) |
| `loguru` | Structured logging |

## Testing

```bash
cd backend

# Run document acquisition tests
uv run pytest tests/core/ingest_and_digitize_data/document_acquisition/ -v

# Run a specific test
uv run pytest tests/core/ingest_and_digitize_data/document_acquisition/test_service.py::test_local_upload -v
```

### Test coverage

| Test file | What it covers |
|-----------|---------------|
| `test_service.py` | `DocumentAcquisitionService.acquire()` facade routing |
| `local_upload/test_service.py` | `validate_local_upload()`, `store_local_file()`, SHA-256 dedup |
| `local_upload/test_workflow.py` | `upload_document()` workflow |
| `local_upload/test_integration.py` | End-to-end local upload with real file I/O |
| `online_acquisition/test_workflow.py` | `online_acquisition_workflow()`, identifier extraction, fallback chain |
| `online_acquisition/test_gateway.py` | `call_provider()`, `search_provider()`, `download_from_provider()` |
| `online_acquisition/test_contracts.py` | `OnlineAcquisitionRequest`, `OnlineAcquisitionItem` validation |
| `online_acquisition/test_normalizers.py` | Per-provider normalizer functions, `NORMALIZER_MAP` |
| `online_acquisition/test_web_providers.py` | `call_web_provider()` dispatcher, web scraper integration |
