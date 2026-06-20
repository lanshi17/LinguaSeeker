# Document Acquisition

> Unified document acquisition facade for LinguaSeeker's Phase 1 pipeline. Provides a single `acquire()` entry point that routes to either local file upload or online literature search/download with multi-provider fallback chains, multilingual query translation, MinerU batch pre-parsing, and typed LLM relevance gating.

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
    ├── workflow.py (three-phase pipeline)
    │   ├── online_acquisition_workflow()     — single-language path
    │   │   Phase 1: _acquire_links_api (parallel) + _acquire_links_firecrawl
    │   │   Phase 2: _download_candidates (DOI→OA, PMCID→PMC, URL→direct)
    │   │   Phase 3: run_relevance_gate
    │   │
    │   └── multilingual_acquisition_workflow() — multilingual path
    │       Phase 0: query_translator → en/zh/ja/de/fr/ru
    │       Phase 1: search_language × 6 (search_parallel)
    │       Phase 2: _download_candidates
    │       Phase 2.5: _batch_parse_downloads (MinerU)
    │       Phase 3: run_relevance_gate (typed)
    │
    ├── gateway.py (net_io bridge)
    │   ├── call_provider() → net_io.fetch_one()
    │   ├── search_provider() — with retry
    │   ├── resolve_oa_url() — Unpaywall OA URL extraction
    │   └── download_file_from_url() — HTTP file download
    │
    ├── search_service.py (multilingual orchestration)
    │   ├── build_provider_plan() — language-based routing from LANG_PROVIDER_MATRIX
    │   ├── search_multilingual() — sequential plan walk with health-aware reordering
    │   ├── search_parallel() — concurrent search with asyncio.Semaphore
    │   ├── dedupe_candidates() — DOI/URL/title dedup
    │   └── rank_candidates() — title match + DOI + year ranking
    │
    ├── query_translator.py — LLM query translation to 6 languages
    ├── relevance_gate.py — LLM-based content relevance gate (typed/untyped)
    ├── normalizers.py — per-provider → OnlineAcquisitionItem
    ├── pubmed_service.py — PubMed esearch/esummary/efetch
    ├── provider_health.py — sliding-window health tracking
    ├── literature_type_classifier.py — keyword-based classification
    └── web_search/
        ├── adapter.py — SearchLink data contract
        └── firecrawl_adapter.py — Firecrawl search + scrape integration
```

Data flows top-down: the facade dispatches to a submodule, which calls the gateway (Rust `net_io`) for API providers. All raw provider responses are normalized to `OnlineAcquisitionItem` before returning.

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
| `api_provider` | `Optional[str]` | `None` | Force a specific API provider |
| `use_cache` | `bool` | `True` | Enable response caching |
| `proxy` | `Optional[str]` | `None` | Network proxy override |
| `email` | `str` | `"[redacted-email]"` | Email for Unpaywall OA resolution |
| `relevance_gate` | `bool` | `True` | Enable LLM-based relevance filtering after download |
| `literature_types` | `Optional[List[str]]` | `None` | Activate typed gate (e.g. `["case_report"]`) |

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
| `cached` | `bool` | Whether result came from cache |
| `retries` | `int` | Number of retry attempts used |
| `elapsed_time` | `float` | Wall-clock seconds |

### `DocumentDownloadEntry`

| Field | Type | Description |
|-------|------|-------------|
| `file_path` | `Optional[str]` | Path to downloaded PDF |
| `pdf_url` | `Optional[str]` | Original PDF URL |
| `resolved_url` | `Optional[str]` | Final URL after redirects |
| `pre_parsed_markdown` | `Optional[str]` | MinerU pre-parsed markdown (bypasses Phase 2 re-parsing) |

### `OnlineAcquisitionItem` (Pydantic)

Standardized literature metadata returned by all providers after normalization.

| Field | Type | Description |
|-------|------|-------------|
| `source` | `str` | Provider name (e.g. `"crossref"`, `"openalex"`) |
| `title` | `Optional[str]` | Article title |
| `authors` | `List[str]` | Author names |
| `journal` | `Optional[str]` | Journal name |
| `year` | `Optional[str]` | Publication year |
| `doi` | `Optional[str]` | DOI |
| `url` | `Optional[str]` | Primary URL |
| `links` | `List[str]` | All discovered URLs |
| `language` | `Optional[str]` | ISO language code |
| `publisher` | `Optional[str]` | Publisher name |
| `issn` | `List[str]` | ISSN identifiers |
| `identifiers` | `Dict[str, Any]` | Provider-specific IDs (pmcid, pmid, issn) |
| `keywords` | `List[str]` | Subject keywords |
| `literature_type` | `Optional[str]` | Classification: `case_report`, `sequencing`, `functional` |

## Internal Design

### Two Workflow Paths

The `_handle_literature` method in `service.py` routes between two workflows:

- **`multilingual_acquisition_workflow`** — when the request has a free-text query and `language ∈ {None, "", "auto"}`. Translates the query into 6 languages, fans out to per-language provider plans, deduplicates globally, batch-parses PDFs via MinerU, and gates survivors through a typed LLM classifier.
- **`online_acquisition_workflow`** — when an explicit language is set or only identifiers are present (no query). Single-language parallel API search + optional Firecrawl, download, and untyped relevance gate.

### Provider Plan Resolution

`search_service.LANG_PROVIDER_MATRIX` is the single source of truth for per-language provider order. Each entry is `{"route": "api", "provider": "<name>"}`.

| Language | Priority |
|----------|----------|
| `zh` (Chinese) | crossref → unpaywall → openalex → doaj → pmc |
| `ja` (Japanese) | jstage → cinii → crossref → unpaywall → doaj → pmc |
| `ko` (Korean) | crossref → unpaywall → doaj |
| `es` (Spanish) | scielo → crossref → unpaywall |
| `pt` (Portuguese) | scielo → crossref → unpaywall |
| `en` (English) | pmc → europepmc → crossref → arxiv → biorxiv → medrxiv → openalex → openaire → base → core → unpaywall → doaj |
| `de` (German) | crossref → europepmc → unpaywall → openalex → base → doaj |
| `fr` (French) | crossref → europepmc → unpaywall → openalex → doaj → pmc |
| `ru` (Russian) | pmc → europepmc → crossref → unpaywall → openalex |
| `auto` | crossref → unpaywall → openalex → europepmc → doaj → pmc |

### Multilingual Routing

`search_service.build_provider_plan()` selects provider order based on language. The multilingual workflow fans out to all 6 target languages (`en`, `zh`, `ja`, `de`, `fr`, `ru`) via `query_translator.translate_query()`, which makes a single LLM call with `temperature=0.2` to produce language-optimized search queries. Gene symbols (HGNC) and HGVS variant nomenclature are preserved as-is.

### Download Routing

`_download_candidates` tries three routes per candidate, in order:

1. **DOI route** — call Unpaywall, then `resolve_oa_url` → `download_file_from_url`
2. **PMCID route** — try `europepmc.org/articles/PMC{id}?pdf=render` first, then `ncbi.nlm.nih.gov/pmc/articles/PMC{id}/pdf/` as fallback
3. **Direct URL** — HTTP download with HTML-to-PDF redirect handling

### Provider Health Tracking

`ProviderHealthTracker` maintains a thread-safe sliding window (default 1 hour) of success/failure records per provider. `reorder_plan()` deprioritizes providers with <50% success rate (minimum 3 samples). Each `call_provider()` call records latency and outcome.

### Normalization

Each API provider has a dedicated normalizer function in `normalizers.py` that maps raw JSON responses to `OnlineAcquisitionItem`. The `NORMALIZER_MAP` registry dispatches by provider name.

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

### Web Search (Firecrawl)

`web_search/firecrawl_adapter.py` provides `FirecrawlAdapter` for web-based literature discovery. Used by `online_acquisition_workflow` when `prefer="auto"` and no deterministic identifier is present. Runs in parallel with API providers. The adapter searches for links and optionally scrapes the top 5 results for additional PDF links.

### MinerU Batch Pre-Parsing (Multilingual)

The multilingual workflow includes a Phase 2.5 step (`_batch_parse_downloads`) that submits all surviving PDFs through `parse_document.create_parse_service().parse_local_files(...)` in one MinerU batch. The parsed markdown is:
1. Used by `relevance_gate` for content classification (preferred over fitz extraction)
2. Forwarded via `DocumentDownloadEntry.pre_parsed_markdown` to downstream Phase 1, bypassing MinerU re-parsing

### Relevance Gate

`relevance_gate.run_relevance_gate()` filters downloaded PDFs by LLM-judged relevance. Two modes:
- **Untyped**: returns `{relevant, reason}` — used when `literature_types` is empty
- **Typed**: returns `{relevant, doc_type, reason}` — used when `literature_types` is set. Missing or mismatched `doc_type` is conservatively rejected.

Errored judgments are kept (never lose a file because the gate failed). Confirmed-irrelevant downloads have their files deleted (`delete_files=True`).

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
print(result.route.used)     # "api"
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
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.search_service import (
    build_provider_plan,
    search_parallel,
)

plan = build_provider_plan(language="en")
candidates = await search_parallel(
    query="Fabry disease GLA variant case report",
    plan=plan,
    concurrency=4,
    candidate_limit=10,
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

### Multilingual variant search with typed gate

```python
result = await service.acquire(DocumentAcquisitionRequest(
    source=AcquisitionSource.ONLINE,
    action="download",
    query="MECP2 Rett syndrome case report",
    limit=18,
    literature_types=["case_report"],
    download_path="./downloads/rett",
))
# Phase 0: 6-lang translation → Phase 1: parallel search → Phase 2: download
# Phase 2.5: MinerU batch parse → Phase 3: typed gate
for d in result.downloads:
    print(d.file_path, d.pre_parsed_markdown[:100] if d.pre_parsed_markdown else "")
```

### Disable the relevance gate

```python
result = await service.acquire(DocumentAcquisitionRequest(
    source=AcquisitionSource.ONLINE,
    action="download",
    query="ACMG variant classification",
    relevance_gate=False,
))
```

## Extension Guide

### Adding a new API provider

1. Implement the provider in Rust `net-io` crate with `search` and `download` actions
2. Add the provider name to `ApiProvider` literal type in `contracts.py`
3. Add a normalizer function in `normalizers.py` and register in `NORMALIZER_MAP`
4. Add to `_API_SEARCH_PROVIDERS` and `_ID_PROVIDER_MAP` in `workflow.py` for fallback inclusion
5. Add to `LANG_PROVIDER_MATRIX` in `search_service.py` for language-based routing

### Modifying the fallback chain

Edit `_API_SEARCH_PROVIDERS` in `workflow.py` to change the order or add/remove providers from the fallback sequence. Identifier-specific overrides are in `_ID_PROVIDER_MAP`.

## Performance Notes

- **Rust I/O**: API provider HTTP calls go through `net_io.fetch_one()` (Rust/PyO3), which handles connection pooling and async I/O natively
- **Health-based reordering**: Unhealthy providers (<50% success rate) are deprioritized in multilingual search
- **Deduplication**: `search_service.dedupe_candidates()` uses DOI/URL/title matching; O(n) per provider call
- **Concurrency**: `search_parallel()` uses `asyncio.Semaphore(4)` for concurrent provider calls within a language; multilingual fans out 6 language tasks via `asyncio.gather`
- **PDF validation**: All downloaded PDFs are validated by checking `%PDF` magic bytes before writing to disk
- **Translation cost**: 1 LLM call per multilingual request (~200–400 tokens out)
- **Gate cost**: 1 LLM call per surviving download; concurrency capped at 6
- **MinerU batch**: one batch call per multilingual workflow run, dominated by the largest PDF

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `rust_io.net` (via `src.utils.rust_io`) | HTTP I/O for API providers (crossref, unpaywall, etc.) |
| `rust_io.files` (via `src.utils.rust_io`) | SHA-256 hashing and file write for local upload |
| `httpx` | Async HTTP for downloads, DOI probing, Firecrawl |
| `pydantic` | Request/response validation |
| `openai` (`AsyncOpenAI`) | LLM calls for `query_translator` and `relevance_gate` |
| `pymupdf` (`fitz`) | PDF text extraction fallback when MinerU markdown is absent |
| `loguru` | Structured logging |

## Testing

```bash
cd backend

# Run document acquisition tests
uv run pytest tests/core/ingest_and_digitize_data/document_acquisition/ -v

# Run a specific test
uv run pytest tests/core/ingest_and_digitize_data/document_acquisition/test_service.py::test_local_upload -v

# Query translator tests
uv run pytest tests/unit/test_query_translator.py

# Relevance gate tests
uv run pytest tests/unit/test_relevance_gate_parsed.py

# MinerU batch parse tests
uv run pytest tests/unit/test_batch_parse_downloads.py
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
| `tests/unit/test_query_translator.py` | Query translation, JSON parsing, missing-language fallback |
| `tests/unit/test_relevance_gate_parsed.py` | Typed gate strictness (missing/mismatch/match) + markdown bypass |
| `tests/unit/test_batch_parse_downloads.py` | MinerU batch attach / failure / empty input |
