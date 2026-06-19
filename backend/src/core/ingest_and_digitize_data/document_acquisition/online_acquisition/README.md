# Online Acquisition Module

> Phase 1 submodule for literature search and download. Two workflows: a single-language path with deterministic-identifier fanout (Crossref / Unpaywall / OpenAlex / EuropePMC / PMC / Firecrawl), and a multilingual path that auto-translates one query into 6 languages, fans out to 15 API providers in parallel, deduplicates globally, runs an early MinerU batch parse, and gates the survivors through a typed-LLM relevance classifier.

## Quick Start

```python
import asyncio
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition import (
    multilingual_acquisition_workflow,
)

# One free-text query → 6 languages → ranked candidates → PDFs → typed gate.
result = asyncio.run(multilingual_acquisition_workflow({
    "action": "download",
    "query": "MECP2 Rett syndrome case report",
    "limit": 12,
    "literature_types": ["case_report"],   # activates the typed gate
    "download_path": "./downloads",
}))
print(f"Downloaded: {len(result['downloads'])}, "
      f"warnings: {result['warnings']}")
```

For deterministic-identifier requests (DOI / PMID / PMCID) or when the caller has pinned a language, use `online_acquisition_workflow` instead — see [Public API](#public-api).

## Architecture

```
                     ┌─ multilingual_acquisition_workflow ─────────────────┐
                     │                                                     │
seed query ─┐        │  Phase 0   query_translator  → en/zh/ja/de/fr/ru    │
            │        │                ↓                                    │
            │        │  Phase 1   search_language × 6 (search_parallel)    │
            │        │                ↓                                    │
            │        │            dedupe_candidates + rank_candidates      │
            │        │                ↓                                    │
            │        │  Phase 2   _download_candidates                     │
            ├─→──────┤                ↓                                    │
            │        │  Phase 2.5 _batch_parse_downloads (MinerU)          │
            │        │                ↓                                    │
            │        │  Phase 3   run_relevance_gate (typed)               │
            │        │                ↓ surviving downloads                │
            │        └─────────────────────────────────────────────────────┘
            │
DOI / PMCID │        ┌─ online_acquisition_workflow ──────────────────────┐
identifier ─┤        │                                                    │
            │        │  Phase 1   _acquire_links_api (parallel)           │
            │        │                + _acquire_links_firecrawl          │
            │        │                ↓                                   │
            │        │            _merge_and_dedupe                       │
            │        │                ↓                                   │
            └─→──────┤  Phase 2   _download_candidates                    │
                     │                ↓                                   │
                     │  Phase 3   run_relevance_gate                      │
                     └────────────────────────────────────────────────────┘
```

The two workflows share Phases 2 and 3 (download + gate). Where they differ:

| Aspect | `online_acquisition_workflow` | `multilingual_acquisition_workflow` |
|---|---|---|
| Query expansion | none | LLM → 6 languages |
| Provider plan | `_API_SEARCH_PROVIDERS` (15) or `_ID_PROVIDER_MAP` if a deterministic identifier is detected | per-language `LANG_PROVIDER_MATRIX` × 6 (search_service) |
| Web fallback | Firecrawl when `prefer="auto"` and no identifier | none |
| Early MinerU | no | yes (`_batch_parse_downloads`) |
| Trace | per-provider | `multilingual-<lang>` per language |
| Failure mode | per-provider warnings | falls back to `online_acquisition_workflow` if translation fails |

### Routing — chosen by the orchestrator

`document_acquisition.service.DocumentAcquisitionService._handle_literature` picks between the two workflows:

- free-text `query` + `language ∈ {None, "", "auto"}` → multilingual
- explicit `language` (e.g. `"en"`, `"zh"`) → single-language (no translation of pinned-language queries)
- identifier-only request (no query) → single-language (DOIs aren't translated)

## Public API

### Workflows

```python
async def online_acquisition_workflow(payload: Dict[str, Any]) -> Dict[str, Any]
async def multilingual_acquisition_workflow(payload: Dict[str, Any]) -> Dict[str, Any]
```

Both accept a `dict` matching `OnlineAcquisitionRequest` and return a `dict` matching `OnlineAcquisitionResponse.model_dump()`. Calling them directly is fine — the service layer is just a router with payload shaping.

### `OnlineAcquisitionRequest` (pydantic)

| Field | Type | Default | Notes |
|---|---|---|---|
| `action` | `"search" \| "download"` | `"search"` | search returns `items` only; download adds `downloads[]` |
| `query` | `str \| None` | `None` | free-text or known identifier embedded |
| `identifiers` | `List[str]` | `[]` | DOIs / PMIDs / PMCIDs; coerced from scalar via validator |
| `prefer` | `"auto" \| "api" \| "web"` | `"auto"` | single-language only; multilingual is api-only |
| `raw` | `bool` | `False` | passes through to provider (returns provider-native JSON) |
| `limit` | `int` | `20` | clamped to `[1, 200]`; multilingual splits across 6 langs |
| `language` | `str \| None` | `"auto"` | override download path organization; `auto` lets DOI prefix detect |
| `literature_types` | `List[Literal["case_report","sequencing","functional"]]` | `[]` | activates typed gate + post-classify filter |
| `api_provider` | `ApiProvider \| None` | `None` | bypass chain, call one provider directly |
| `download_path` | `str` | `"./downloads"` | language code is appended in single-language mode |
| `relevance_gate` | `bool` | `True` | disables Phase 3 LLM call when `False` |

### `OnlineAcquisitionResponse` (pydantic)

```python
success: bool
items: List[OnlineAcquisitionItem]              # normalized metadata
downloads: List[Dict[str, Any]]                 # see download dict shape below
warnings: List[str]                             # FETCH_NO_RESULT / FULLTEXT_UNAVAILABLE / RELEVANCE_GATE / TRANSLATION_FAILED / SEARCH_FAILED_<lang>
route: OnlineAcquisitionRouteInfo
candidate_links: List[Dict[str, Any]]           # all candidates after dedup (ranked)
raw: Optional[Any]                              # source_trace under the multilingual path
```

### Download dict shape

After `_download_candidates`, before/after the gate:

```python
{
  "file_path": str,             # absolute, sanitized
  "source": str,                # "unpaywall" | "pmc" | "<provider>" | "direct"
  "doi": str | None,
  "pmcid": str | None,
  "url": str | None,            # final URL after redirects
  "warnings": List[str],
  # Multilingual workflow only:
  "search_lang": str,           # "en" | "zh" | "ja" | "de" | "fr" | "ru"
  "parsed_markdown": str,       # populated by _batch_parse_downloads (MinerU)
  "parser_used": str,           # "mineru-remote" / "mineru-local" / etc.
}
```

`parsed_markdown` is consumed by:
1. `relevance_gate._check_one` — preferred over fitz extraction.
2. The downstream `Phase1Adapter` via `DocumentDownloadEntry.pre_parsed_markdown`, bypassing MinerU re-parsing.

### Module-level helpers (re-exported via `__init__`)

| Symbol | Purpose |
|---|---|
| `call_provider(request)` | Single low-level provider call via `net_io.fetch_one`. |
| `search_provider(provider, query, ...)` | Convenience wrapper for `action="search"`. |
| `normalize_items(provider, items)` | Per-provider raw JSON → `OnlineAcquisitionItem`. |
| `build_provider_plan(language, provider_hints=None)` | Resolve a per-language provider list from `LANG_PROVIDER_MATRIX`. |
| `search_multilingual(target, disease, ...)` | Sequential plan walk with health-aware reordering (used by callers that want an explicit shortlist). |
| `OnlineAcquisitionPubMedService` | Direct PubMed esearch/esummary wrapper used by some callers (kept separate from the provider chain). |

### `relevance_gate.run_relevance_gate`

```python
async def run_relevance_gate(
    *,
    query: str,
    downloads: List[Dict[str, Any]],
    delete_files: bool = True,
    concurrency: int = 6,
    max_pages: int = 3,
    max_chars: int = 3000,
    literature_types: Optional[List[str]] = None,
) -> RelevanceGateResult
```

Two prompt modes: untyped (relevant/reason) and typed (relevant/doc_type/reason). When `literature_types` is set, the typed prompt is used **and** missing or mismatched `doc_type` is conservatively rejected — see [Internal Design / Typed Gate](#typed-gate).

### `query_translator.translate_query`

```python
async def translate_query(
    query: str,
    *,
    client: Optional[AsyncOpenAI] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> TranslatedQueries        # dataclass(frozen=True): en, zh, ja, de, fr, ru, source_query
```

Single LLM call, `temperature=0.2`, JSON-only output. Gene symbols (HGNC) and HGVS variant nomenclature are kept as-is per the system prompt.

## Internal Design

### Provider plan resolution

`search_service.LANG_PROVIDER_MATRIX` is the single source of truth for per-language provider order. Each entry is `{"route": "api", "provider": "<name>"}`. Notable choices:

- **`zh`** prefers `crossref`, `unpaywall`, `openalex`, `doaj`, `pmc` (no Chinese-specific provider — those were retired with the web scrapers on 2026-06-16; mainland-Chinese OA is sourced via Crossref/OpenAlex DOIs).
- **`ja`** leads with `jstage` and `cinii` (J-Stage indexes most Japanese medical journals; CiNii catches grey literature).
- **`es` / `pt`** lead with `scielo`.
- **`en` / `de` / `fr` / `ru`** are all Crossref-anchored. `en` is the widest matrix because most preprint and OA aggregators are English-first.
- **`auto`** is the safe-default fallback used when language detection produces nothing useful.

`build_provider_plan(language, provider_hints=None)` returns the matrix entry, optionally with `provider_hints` prepended in order.

### Single-language dispatch — `online_acquisition_workflow`

1. `_extract_identifiers` runs three regexes (`DOI_PATTERN`, `PMCID_PATTERN`, `PMID_PATTERN`) over `query + identifiers`. A bare numeric string of length 5–9 is also treated as a PMID — yes, this is heuristic; legitimate PMIDs almost always have explicit prefixes in caller-supplied input.
2. **Deterministic identifier present** (DOI / PMID / PMCID) — `_acquire_links_api` only. Firecrawl is skipped: provider APIs are authoritative for IDs and Firecrawl would burn credits scraping landing pages.
3. **Free-text query** — API and Firecrawl run concurrently via `asyncio.gather`. `_merge_and_dedupe` collapses duplicates by DOI → URL → normalized title.
4. **Phase 2** — `_download_candidates` tries three routes per candidate, in order:
   - **Route 1 (DOI)** — call Unpaywall, then `resolve_oa_url` → `download_file_from_url`.
   - **Route 2 (PMCID)** — try `https://europepmc.org/articles/PMC{id}?pdf=render` first, then `https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{id}/pdf/`. The PMC direct URL serves a JS interstitial, not bytes — that's why EuropePMC's render endpoint is the primary.
   - **Route 3 (URL)** — direct HTTP fetch with HTML→PDF redirect handling.
5. **Phase 3** — when `request.relevance_gate` is `True` (default) and there are downloads, `run_relevance_gate(literature_types=...)` filters them. Errored judgments are kept (conservative — never lose a file because the gate failed).

### Multilingual dispatch — `multilingual_acquisition_workflow`

1. **Phase 0** — `translate_query(base_query)`. Failure here doesn't poison the request: the workflow logs `TRANSLATION_FAILED`, falls back to `online_acquisition_workflow(payload)`, and returns. Test runs without LLM credentials therefore behave deterministically.
2. **Phase 1** — six concurrent `search_language(query, lang, candidate_limit=request.limit // 6 or 5)` tasks. Each task uses `search_parallel` (semaphore = 4) to fan out across that language's plan. Per-language failures are captured into `source_trace[multilingual-<lang>]` but never raise.
3. **Global merge** — `dedupe_candidates` then `rank_candidates(expected_title=base_query)`. Dedup keys are DOI → normalized URL → normalized title, so a paper indexed by Crossref-en and Crossref-de collapses into one entry. The first-seen `search_lang` wins; the rest are dropped.
4. **Phase 2** — same `_download_candidates` as the single-language path. Each download dict carries the `search_lang` of its winning candidate.
5. **Phase 2.5** — `_batch_parse_downloads` submits all surviving PDFs through `parse_document.create_parse_service().parse_local_files(...)` in **one** MinerU batch. The factory is imported lazily so unit tests that don't exercise parsing don't pull in the PyO3 native extension. Failures (extension missing, batch timeout, exception inside MinerU) are logged and the workflow continues — `relevance_gate` then falls back to fitz extraction.
6. **Phase 3** — typed gate when `literature_types` is non-empty. Surviving downloads carry their MinerU markdown forward via `parsed_markdown`.

### Typed gate

`run_relevance_gate(literature_types=["case_report", ...])` activates `_SYSTEM_PROMPT_TYPED`. The classifier returns `{relevant, doc_type, reason}`. Strict semantics:

| LLM response | Decision |
|---|---|
| `relevant=true`, `doc_type` missing | **rejected** with `doc_type_missing` (defeats typed filtering otherwise) |
| `relevant=true`, `doc_type` not in `literature_types` | **rejected** with `doc_type_mismatch: <type> not in <list>` |
| `relevant=true`, `doc_type` matches | accepted |
| `relevant=false` | rejected, reason from LLM |
| JSON parse error | `RelevanceJudgment(error="json_parse_error")` — kept as conservative fallback |

Errored judgments are kept; only confirmed-irrelevant downloads have their files deleted (`delete_files=True`) and their entries dropped from `OnlineAcquisitionResponse.downloads`.

### Concurrency model

- All I/O is async (`httpx.AsyncClient` / `net_io` from Rust). No threadpools at the Python layer except `provider_health` (`threading.Lock`, since the singleton crosses event loops).
- Multilingual fanout: 6 language tasks via `asyncio.gather(return_exceptions=True)`. Each task internally caps provider concurrency at 4.
- Relevance gate: `asyncio.Semaphore(_DEFAULT_CONCURRENCY=6)` around the LLM call only; PDF text extraction runs in a thread (`asyncio.to_thread`) because PyMuPDF is not async-friendly.
- MinerU batch parse: one call per workflow run regardless of download count — the batch is the unit of concurrency, not individual files.

### Error handling — what raises, what warns

- **Validation** (`OnlineAcquisitionRequest`) — pydantic raises; the workflow catches and returns `success=False, warnings=["invalid_request: ..."]`.
- **Provider call** — `call_provider_with_retry` aggregates `OnlineAcquisitionSourceTraceEntry` per attempt; the wrapper never raises. Final result is `success=False` with provider warnings.
- **Translation** — failure logs and falls back; never raises out of `multilingual_acquisition_workflow`.
- **MinerU batch** — caught and logged; downloads pass through with no `parsed_markdown`.
- **Relevance gate** — per-file errors become `RelevanceJudgment.error=<reason>` and the file is **kept** (the alternative would silently lose data).

### Provider health (`provider_health.ProviderHealthTracker`)

Sliding 1-hour window, `min_samples=3` before a provider is considered for de-prioritization. `reorder_plan` sorts unhealthy providers (failure_count ≥ min_samples and success_rate < 0.5) to the back without removing them. Used by `search_multilingual`. The parallel multilingual workflow currently does **not** consult the tracker — language plans are static — but each individual `search_provider` call still records its outcome via the gateway's `_record_provider` hook.

## Usage Patterns

### Resolve a known DOI (deterministic — single-language)

```python
result = asyncio.run(online_acquisition_workflow({
    "action": "download",
    "identifiers": ["10.1038/s41586-020-2649-8"],
    "download_path": "./downloads",
}))
# DOI route: Unpaywall → OA URL → PDF; falls back to Crossref/OpenAlex/EuropePMC.
# Firecrawl is skipped (deterministic identifier).
```

### Multilingual variant search with typed gate

```python
result = asyncio.run(multilingual_acquisition_workflow({
    "action": "download",
    "query": "MECP2 Rett syndrome",
    "limit": 18,                          # ≈ 3 per language after split
    "literature_types": ["case_report"],
    "download_path": "./downloads/rett",
}))
# Phase 0: 6-lang translation
# Phase 1: parallel search per LANG_PROVIDER_MATRIX
# Phase 2: download survivors
# Phase 2.5: MinerU batch parse
# Phase 3: typed gate — keeps only doc_type=="case_report"
for d in result["downloads"]:
    print(d["search_lang"], d["doi"], d["file_path"])
```

### Search-only (no PDF download, no gate)

```python
result = asyncio.run(multilingual_acquisition_workflow({
    "action": "search",
    "query": "BRCA1 functional study",
    "limit": 30,
}))
# returns candidate_links and items, downloads=[], gate is skipped.
```

### Pin a single language and provider

```python
# Routes to online_acquisition_workflow because language is explicit.
result = asyncio.run(online_acquisition_workflow({
    "action": "search",
    "query": "TP53 hotspot mutations",
    "language": "en",
    "api_provider": "europepmc",
    "prefer": "api",
}))
```

### Disable the relevance gate

```python
# Useful for benchmark runs where caller does its own classification.
result = asyncio.run(multilingual_acquisition_workflow({
    "action": "download",
    "query": "ACMG variant classification",
    "relevance_gate": False,
}))
```

## Extension Guide

### Adding a new API provider

The provider name lives in three places — keep all three in sync.

1. Add the literal to `ApiProvider` in `contracts.py`:
   ```python
   ApiProvider = Literal[..., "newprovider"]
   ```
2. Implement the provider in `backend/libs/net-io/src/providers/newprovider.rs` and register in the Rust dispatch table. The Python layer just calls `net_io.fetch_one(provider="newprovider", ...)`.
3. Add a normalizer in `normalizers.py` (`normalize_newprovider(items) -> List[OnlineAcquisitionItem]`) and register it in the `NORMALIZER_MAP`.
4. Add the provider to the relevant `LANG_PROVIDER_MATRIX` entries in `search_service.py`.
5. Optionally add it to `_API_SEARCH_PROVIDERS` (single-language workflow) and `_ID_PROVIDER_MAP` (deterministic identifier routing) in `workflow.py`.
6. Tests: extend `tests/online_acquisition/test_parallel_search.py` and the relevant normalizer test.

### Adding a new target language

1. Add the language code to `TARGET_LANGUAGES` in `query_translator.py` and to the `TranslatedQueries` dataclass.
2. Update the system prompt's example JSON to include the new key.
3. Add a `LANG_PROVIDER_MATRIX` entry in `search_service.py`. Pick provider order by what's authoritative for that language's medical literature — start with Crossref + Unpaywall, then layer regional indexes (e.g. KCI for Korean, ScienceDirect for Italian via Crossref). Don't add a language without a known regional provider — the matrix exists to do better than English-anchored aggregators.
4. Add an `OnlineAcquisitionPubMedCandidate.lang_name` mapping if benchmarks consume it.
5. Tests: `tests/unit/test_query_translator.py` should cover the new language end-to-end (mocked LLM is fine).

### Modifying the typed gate

- Document type list lives in `_SYSTEM_PROMPT_TYPED` in `relevance_gate.py`. If you add a type, also update the JSON schema sentence. The classifier output is constrained — adding a type the model has never seen leaves it stuck on `other`.
- The strict missing-doc_type rejection in `_check_one` is intentional. Loosening it (e.g. accepting `relevant=true` without a type) silently disables typed filtering — don't.

### Common pitfalls

- **Don't translate identifiers.** The router already prevents this, but if you call `multilingual_acquisition_workflow` directly with DOIs, you'll waste a translation call and get worse results. Use `online_acquisition_workflow` for ID-driven requests.
- **Don't bypass `_batch_parse_downloads` to call MinerU per-file.** The batch endpoint is throughput-limited; a per-file loop is roughly 6× slower for 12 PDFs.
- **Don't move `parsed_markdown` truncation into the gate's prompt builder.** It already truncates to `max_chars`; doubling the truncation drops abstracts (the most informative part) when `max_chars` is tight.
- **Don't add new fields to `OnlineAcquisitionRequest` without piping them into `OnlineAcquisitionGatewayRequest`.** Provider calls go through the gateway, not the request directly.

## Performance Notes

- **Per-language search latency** ≈ slowest provider in that language's matrix (parallel within a language). Crossref is consistently 1–2 s, EuropePMC 0.5–1 s, OpenAlex 1–3 s, jstage occasionally > 5 s.
- **Multilingual workflow latency** ≈ slowest **language** + translation (≈ 1 s) + MinerU batch + LLM gate (≈ 1.5 s/file at concurrency 6). For 12 candidates → ≈ 30 s end-to-end with warm caches.
- **Translation cost**: 1 LLM call per request (≈ 200–400 tokens out at `temperature=0.2`). Negligible vs. the gate.
- **Gate cost**: 1 LLM call per surviving download. The typed prompt is ~80 tokens longer than the untyped one. With `concurrency=6` this is the dominant wall-clock cost when downloads > 6.
- **MinerU batch**: dominated by the largest PDF in the batch. Submitting 12 small PDFs at once is roughly the same wall-clock as submitting one. This is the whole reason we don't parse per-file.
- **Filesystem**: `_download_candidates` writes one PDF per candidate sequentially within a single coroutine, but candidates run in `asyncio.gather`. SHA-prefixed filenames (`<title>_<urlhash>.pdf`) avoid collisions across languages.
- **`httpx.AsyncClient`** is created per-request (not pooled) in fallback paths. Most traffic goes through the Rust `net_io.download_file`, which has its own connection reuse.

## Dependencies

| Dependency | Version | Purpose |
|---|---|---|
| `pydantic` | ≥ 2 | request / response / item validation |
| `httpx` | (project pin) | async HTTP fallback for downloads, DOI probing |
| `loguru` | (project pin) | structured logging |
| `openai` (`AsyncOpenAI`) | ≥ 1.x | LLM calls for `query_translator` and `relevance_gate` |
| `pymupdf` (`fitz`) | (project pin) | text extraction fallback when MinerU markdown is absent |
| `src.utils.rust_io.net_io` | local PyO3 | 15 API provider clients + `download_file` |
| `src.utils.text.sanitize_filename` | local | safe filenames across OSes |
| `src.core.config.get_config` | local | LLM credentials, network proxy resolver, web search settings |
| `src.core.ingest_and_digitize_data.parse_document` | local (lazy) | MinerU batch parsing for `_batch_parse_downloads` |

The `parse_document` import is **lazy** inside `_batch_parse_downloads` so this module remains importable in test environments without the Rust extension built.

## Testing

```bash
# Unit tests for the new pieces (fast, no network)
uv run pytest tests/unit/test_query_translator.py
uv run pytest tests/unit/test_relevance_gate_parsed.py
uv run pytest tests/unit/test_batch_parse_downloads.py

# Workflow + provider tests
uv run pytest tests/online_acquisition/ tests/core/ingest_and_digitize_data/document_acquisition/

# Phase 1 adapter handoff (pre-parsed markdown bypass)
uv run pytest tests/agents/test_phase_1_pre_parsed_handoff.py
```

Coverage map:

| Area | Test |
|---|---|
| Query translation, JSON parsing, missing-language fallback | `tests/unit/test_query_translator.py` |
| Typed gate strictness (missing / mismatch / match) + markdown bypass | `tests/unit/test_relevance_gate_parsed.py` |
| MinerU batch attach / failure / empty input / unavailable extension | `tests/unit/test_batch_parse_downloads.py` |
| Provider parallel search + plan health reordering | `tests/online_acquisition/test_parallel_search.py`, `test_provider_health.py` |
| Literature type classifier (regex correctness) | `tests/online_acquisition/test_literature_type_classifier.py` |
| Service-level routing (multilingual vs single vs id-only) | `tests/core/.../document_acquisition/test_service.py` |
| End-to-end multilingual / providers / workflow (network-dependent — skipped without creds) | `tests/online_acquisition/test_e2e_*.py` |

E2E tests require live API credentials (`OPENAI_API_KEY`, `WEB_SEARCH_API_KEY` for Firecrawl, `UNPAYWALL_EMAIL` for OA resolution); they're auto-skipped in the unit-test sweep.
