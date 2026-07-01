# Plan: Multi-Lingual Agent-Based Literature Acquisition with Early MinerU + Relevance Gate

## Problem Statement

Current `online_acquisition_workflow` has two issues:
1. **Search is language-agnostic** — queries are submitted in one language only, missing literature written in other languages.
2. **MinerU parsing happens too late** — PDFs are parsed downstream in Phase 2 (parse_document), after the acquisition pipeline has already passed them through. Papers without genetic variant information waste MinerU API credits and downstream processing time.

## Goals

1. Translate a single query into 6 languages (en/zh/ja/de/fr/ru) and search concurrently.
2. Call MinerU **immediately after download** to get structured content.
3. Use an LLM agent to judge: "Does this paper contain genetic variant information?" — keep or discard.
4. Pass `ParseResult` downstream so the existing `parse_document` step skips re-parsing.

## Target Languages

| Code | Language | Rationale |
|------|----------|-----------|
| en | English | Primary biomedical language, PMC/PubMed coverage |
| zh | Chinese | Second-largest genomics research output, unique case reports |
| ja | Japanese | JStage/CiNii OA PDFs already working (14 PDFs in benchmark) |
| de | German | European genetics literature, 8 PDFs already downloaded |
| fr | French | EuropePMC strong coverage, 14 PDFs already downloaded |
| ru | Russian | Non-redundant case reports, eLibrary access |

## Architecture Overview

```
                              ┌─────────────────────┐
                              │  User Query (any)    │
                              └──────────┬──────────┘
                                         │
                              ┌──────────▼──────────┐
                              │  Query Translator    │
                              │  (LLM, 6 languages)  │
                              └──────────┬──────────┘
                                         │ 6 queries
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
              ┌─────▼─────┐       ┌─────▼─────┐       ┌─────▼─────┐
              │ Search     │       │ Search     │       │ Search     │
              │ Providers  │       │ Providers  │       │ Providers  │
              │ (parallel) │       │ (parallel) │       │ (parallel) │
              └─────┬─────┘       └─────┬─────┘       └─────┬─────┘
                    │                    │                    │
              ┌─────▼────────────────────▼────────────────────▼─────┐
              │            Download + Deduplicate                   │
              │        (DOI→OA, PMCID→PMC, URL→direct)              │
              └─────────────────────┬───────────────────────────────┘
                                    │ PDFs
                              ┌─────▼─────┐
                              │  MinerU    │  ← EARLY parse (batch)
                              │  Parse     │
                              └─────┬─────┘
                                    │ ParseResult
                              ┌─────▼─────┐
                              │  LLM       │  ← Variant relevance agent
                              │  Relevance │
                              │  Gate      │
                              └─────┬─────┘
                                    │
                          ┌─────────┼─────────┐
                          │                   │
                    ┌─────▼─────┐       ┌─────▼─────┐
                    │ KEEP       │       │ DISCARD    │
                    │ Pass       │       │ Delete PDF │
                    │ ParseResult│       │ Log reason │
                    │ downstream │       └───────────┘
                    └─────┬─────┘
                          │
                    ┌─────▼─────┐
                    │ Downstream │
                    │ Pipeline   │  ← Skips parse_document
                    │ (translate │     (ParseResult already provided)
                    │  extract)  │
                    └───────────┘
```

## Detailed Design

### Phase 0: Query Translation Agent

**New module:** `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/query_translator.py`

**Responsibility:** Given a user query (any language), produce search queries optimized for each of the 6 target languages.

**Implementation:**
- Single LLM call with structured output (JSON array of 6 query strings).
- Prompt instructs: "Given this biomedical/genetics query, produce search queries optimized for finding case reports with genetic variants in each of these languages. Use domain-specific terminology appropriate for each language's medical literature."
- Uses `LLM_MODEL` (fast/default model) — this is a lightweight translation task.

**Contracts:**
```python
@dataclass
class TranslatedQueries:
    en: str
    zh: str
    ja: str
    de: str
    fr: str
    ru: str
    source_query: str
```

**Cost:** 1 LLM call per acquisition request. Negligible.

### Phase 1: Multi-Lingual Parallel Search

**Modified module:** `workflow.py` — new entry point `multilingual_acquisition_workflow`

**Changes:**
1. Call Query Translator to get 6 language-specific queries.
2. For each language, build a `LANG_PROVIDER_MATRIX` plan (reuse from `search_service.py`).
3. Fire all 6 language searches in parallel using `asyncio.gather`.
4. Each language search calls its provider plan concurrently (already implemented in `search_parallel`).
5. Merge results, deduplicate by DOI/title, tag each candidate with `search_lang`.

**Provider routing per language** (reuse existing `LANG_PROVIDER_MATRIX`):

| Language | Primary Providers | Fallback |
|----------|------------------|----------|
| en | pmc, europepmc, crossref, arxiv, biorxiv, medrxiv | openalex, doaj, core |
| zh | crossref, unpaywall, openalex, doaj, pmc | — |
| ja | jstage, cinii, crossref, unpaywall, doaj, pmc | — |
| de | crossref, europepmc, unpaywall, openalex | base, doaj |
| fr | crossref, europepmc, unpaywall, openalex | doaj, pmc |
| ru | pmc, europepmc, crossref, pubmed | — |

**New:** Add `de` and `fr` entries to `LANG_PROVIDER_MATRIX` in `search_service.py` (currently they fall through to `auto`).

**Output:** `List[Dict[str, Any]]` — candidates with `search_lang`, `doi`, `title`, `url`, `pmcid`, etc.

### Phase 2: Download + Early MinerU Parse

**Modified module:** `workflow.py` — replace current `_download_candidates` with `_download_and_parse_candidates`

**Flow per candidate:**
1. Download PDF via existing routing (DOI→Unpaywall, PMCID→PMC, URL→direct).
2. On successful download, immediately submit to MinerU using **batch API** (`parse_local_files`).
3. Collect `(file_path, ParseResult)` pairs.

**Batch strategy:**
- MinerU batch API accepts up to 50 files per batch.
- Collect all downloaded PDFs, batch-submit to MinerU.
- Poll until all done (or per-file timeout).
- Concurrency: process batches of 50, with semaphore for download phase.

**New contracts:**
```python
@dataclass
class ParsedCandidate:
    """A downloaded and parsed literature candidate."""
    file_path: str
    parse_result: ParseResult
    source_provider: str
    search_lang: str
    doi: Optional[str] = None
    title: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### Phase 3: Variant Relevance Agent

**New module:** `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/variant_relevance_agent.py`

**Responsibility:** Given MinerU-parsed content, judge whether the paper contains genetic variant information relevant to ACMG evidence.

**Implementation:**
- LLM call per paper (concurrent, with semaphore).
- Input: title + abstract (extracted by MinerU) + first 2 pages of markdown.
- Uses `REASONING_LLM_MODEL` (high-precision model for judgment).
- Structured output:

```python
@dataclass
class VariantRelevanceJudgment:
    file_path: str
    has_variant: bool          # Does the paper mention specific genetic variants?
    variant_type: str          # "SNV", "indel", "CNV", "fusion", "none"
    gene_symbols: List[str]    # Extracted gene names (e.g., ["BRCA1", "TP53"])
    disease_context: str       # Disease/phenotype mentioned
    confidence: str            # "high", "medium", "low"
    reason: str                # Brief explanation
    doc_type: str              # "case_report", "sequencing", "functional", "review", "other"
```

**Prompt strategy:**
```
You are a medical genetics literature triage agent.
Given the parsed content of a biomedical paper, determine:
1. Does this paper contain specific genetic variant information (gene names, mutation descriptions, variant classifications)?
2. What type of document is this? (case_report, sequencing_study, functional_study, review, other)
3. Is this relevant to ACMG/AMP variant classification evidence?

Focus on: gene symbols (e.g., BRCA1, CFTR, MECP2), variant nomenclature (c., p., rsIDs),
inheritance patterns, pathogenicity classifications, phenotype-genotype correlations.

Return strict JSON only.
```

**Filtering logic:**
- `has_variant == True` AND `confidence in ("high", "medium")` → KEEP
- `doc_type == "review"` → DISCARD (reviews don't carry primary evidence)
- Everything else → DISCARD

**Cost estimate:** 1 fast LLM call per paper. For a typical batch of 20-50 candidates, this is 20-50 calls — cheaper than MinerU processing all of them downstream.

### Phase 4: Pass ParseResult Downstream

**Key change:** Documents that pass the relevance gate carry their `ParseResult` forward. The downstream pipeline (`TranslationService` → `EvidenceExtractionWorkflow`) receives these pre-parsed results.

**Implementation approach — `skip_parse` flag:**

Add an optional `parse_result` field to the pipeline entry contract:

```python
# In the pipeline input contract (e.g., PipelineRequest or similar)
class PipelineRequest(BaseModel):
    file_path: str
    parse_result: Optional[ParseResult] = None  # If provided, skip MinerU
    # ... other fields
```

In the `parse_document` service, check:
```python
async def parse_document(request: PipelineRequest) -> ParseResult:
    if request.parse_result is not None:
        logger.info("Skipping MinerU — pre-parsed result provided")
        return request.parse_result
    # ... existing MinerU parsing logic
```

This is a non-breaking change — existing callers that don't provide `parse_result` continue to work.

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `online_acquisition/query_translator.py` | **NEW** | LLM-based query translation to 6 languages |
| `online_acquisition/variant_relevance_agent.py` | **NEW** | LLM agent for variant relevance judgment |
| `online_acquisition/workflow.py` | **MODIFY** | New `multilingual_acquisition_workflow` entry point; integrate MinerU + relevance gate |
| `online_acquisition/search_service.py` | **MODIFY** | Add `de`, `fr`, `ru` entries to `LANG_PROVIDER_MATRIX` |
| `online_acquisition/contracts.py` | **MODIFY** | Add `ParsedCandidate`, `VariantRelevanceJudgment` dataclasses |
| `parse_document/service.py` | **MODIFY** | Add `skip_parse` / pre-parsed `ParseResult` bypass |
| `parse_document/contracts.py` | **MODIFY** | Ensure `ParseResult` is serializable for inter-module passing |
| `benchmark/literature_acquisition/benchmark.py` | **MODIFY** | New benchmark mode for multilingual acquisition |

## Implementation Order

### Step 1: Query Translator (standalone, no dependencies)
- Create `query_translator.py`
- Unit test with mock LLM
- **Verify:** produces 6 language-specific queries from a single input

### Step 2: Add de/fr/ru to LANG_PROVIDER_MATRIX
- Edit `search_service.py`
- **Verify:** `build_provider_plan(language="de")` returns crossref + europepmc

### Step 3: Multi-lingual search integration
- New `multilingual_acquisition_workflow` in `workflow.py`
- Wire query translator → parallel search → merge/dedup
- **Verify:** returns candidates tagged with `search_lang`

### Step 4: Early MinerU batch parsing
- Modify download phase to call MinerU batch API after download
- Use `parse_local_files` (batch mode, up to 50 files)
- **Verify:** downloaded PDFs are parsed, `ParseResult` available

### Step 5: Variant relevance agent
- Create `variant_relevance_agent.py`
- Wire into workflow after MinerU parse
- **Verify:** irrelevant papers are filtered, relevant papers pass through with `ParseResult`

### Step 6: Downstream skip-parse integration
- Modify `parse_document/service.py` to accept pre-parsed results
- **Verify:** pipeline skips MinerU when `parse_result` is provided

### Step 7: Benchmark
- Update benchmark to use `multilingual_acquisition_workflow`
- Compare: download count, relevance precision, total MinerU calls saved

## Cost-Benefit Analysis

| Component | Cost | Benefit |
|-----------|------|---------|
| Query translator | 1 LLM call per request | 6x search coverage |
| Multi-lingual search | 6x API calls (parallel, fast) | Literature from 6 languages |
| Early MinerU parse | Same MinerU calls, just earlier | Enables relevance filtering |
| Variant relevance agent | 1 LLM call per downloaded PDF | Eliminates irrelevant papers before downstream |
| Downstream skip | Zero (code change only) | Saves duplicate MinerU calls for accepted papers |

**Net effect:** More literature found (6 languages), fewer wasted MinerU calls (irrelevant papers filtered early), no duplicate parsing (ParseResult passed through).

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| MinerU batch timeout | Per-file timeout + fallback to relevance check on abstract/title alone |
| LLM relevance false negatives | Conservative threshold — keep on "medium" confidence |
| Query translation quality | Use medical terminology in prompt; validate with known queries |
| Download failure rate (de/tr) | europepmc + PMC fallback enrichment already addresses this |
| API rate limits | Semaphore-based concurrency control (existing pattern) |
