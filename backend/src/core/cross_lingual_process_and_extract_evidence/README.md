# Cross-Lingual Process & Extract Evidence

> Phase 2 of the LinguaSeeker pipeline: format, translate, and persist non-English biomedical documents into structured bilingual JSON via a 3-stage LLM pipeline with block-level alignment and character drift tracking.

## Quick Start

```python
from src.core.config import get_config
from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService

cfg = get_config()
service = TranslationService(cfg=cfg)

# pages come from MinerU parse output: List[{"page_number": N, "markdown": "..."}]
# content_blocks come from MinerU content_list.json: List[{"type": "text", "text": "...", ...}]
pages = [{"page_number": 1, "markdown": "患者携带新的BRCA1变异。"}]
content_blocks = [{"type": "text", "page_idx": 0, "text": "患者携带新的BRCA1变异。"}]

result = await service.run(pages, content_blocks=content_blocks)

print(result.translated_english)   # "The patient carries a novel BRCA1 variant."
print(result.source_language)      # "zh"
print(result.terminology_map)      # {"变异": "variant", ...}
print(result.translated_blocks)    # List[ContentBlock] with translated text

# Persist to disk
output = service.save(result, output_dir="./output", doc_id="doc_001")
print(output.original_json_path)   # ./output/doc_001/original.json
print(output.translated_json_path) # ./output/doc_001/translated.json
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     TranslationService                            │
│  (workflow.py — LangGraph orchestrator, public API)               │
│                                                                  │
│  ┌──────────┐   ┌──────────────────┐   ┌──────────┐             │
│  │  format   │──▶│ detect_language   │──▶│ translate │─┐          │
│  │  (node)   │   │     (node)        │   │  (node)   │ │          │
│  └──────────┘   └──────────────────┘   └──────────┘ │          │
│       │                  │                    ┌──────┘          │
│       ▼                  ▼                    ▼                  │
│  MarkdownFormatter  LanguageRouter    MultiStageTranslator       │
│  (format/)          (router.py)      (translate/)               │
│                                                                  │
│  ┌──────────────────┐                                           │
│  │ skip_translate    │  (auto-skip for English documents)       │
│  └──────────────────┘                                           │
│                                                                  │
│  ┌──────────────────────────────┐                               │
│  │ DocumentPersistenceService   │  (persistence.py)             │
│  │ original.json / translated.json / metadata.json              │
│  └──────────────────────────────┘                               │
└──────────────────────────────────────────────────────────────────┘
```

**Data flow:**

1. **Input**: `List[Dict]` pages (MinerU `ParseResult.pages`) + optional `List[Dict]` content_blocks (MinerU `content_list.json`).
2. **Format**: `MarkdownFormatter` joins per-page markdown, normalizes whitespace/headings, builds `SentenceRegion` objects with page + character offsets, and converts `content_blocks` into typed `ContentBlock` objects. Output: `FormattedDocument`.
3. **Detect**: `detect_language()` uses the `lingua` library (with CJK regex fast-path). `LanguageRouter` decides `"translate"` or `"skip_translate"`.
4. **Translate**: `MultiStageTranslator` runs 3 stages: terminology extraction → full-document translation (block-marker aligned) → self-review → validation/normalization. Output: `TranslationResult` with `original_blocks` and `translated_blocks`.
5. **Skip**: For English documents, a synthetic `TranslationResult` is produced with `translated_english == formatted_original`.
6. **Persist**: `DocumentPersistenceService.save()` writes `original.json`, `translated.json`, `metadata.json`, and copies images.

## Directory Map

| Path | Purpose |
|------|---------|
| `contracts.py` | All data types: `SentenceRegion`, `ContentBlock`, `FormattedDocument`, `TranslationSegment`, `TranslationResult`, `PipelineState`, `CrossLingualOutput`, drift reports |
| `config_context.py` | `TranslationConfigContext` — extracts `cfg.translation` subset, injected into translator |
| (via `src.utils.observability`) | `traced_node` decorator — LangSmith tracing + loguru logging per graph node |
| `router.py` | `LanguageRouter` — single-responsibility routing decision |
| `workflow.py` | `TranslationService` — LangGraph graph wiring, `run()` / `run_sync()` / `save()` public API |
| `persistence.py` | `DocumentPersistenceService` — local filesystem persistence (original/translated JSON + metadata + images) |
| `cross_lingual/format/` | Document formatting: `MarkdownFormatter`, sentence segmentation, page offset tracking |
| `cross_lingual/translate/` | 3-stage LLM translation pipeline (see below) |

### `cross_lingual/translate/` submodules

| File | Purpose |
|------|---------|
| `translator.py` | `MultiStageTranslator` — main translation engine: terminology, block translation, self-review, validation |
| `providers.py` | LLM client factory (`create_llm`, `create_json_llm`) and retry logic (`invoke_with_retry`, `invoke_json_with_retry`) |
| `blocks.py` | Block-level operations: `join_blocks_with_markers`, `split_by_markers`, `merge_short_keywords`, `split_merged_keywords` |
| `postprocess.py` | Post-translation: `build_translated_blocks`, `deduplicate_bilingual_blocks`, `check_block_language`, `flag_quality_issues`, `compute_translation_drift` |
| `exceptions.py` | `TranslationError` — critical translation failures |
| `base.py` | `BaseTranslator` — abstract base class |
| `language_detector.py` | `detect_language()`, `_CJK_RE`, `should_skip_translation()` |
| `prompts/` | Stage-specific LLM prompt templates (see below) |
| `validator/` | Validation and normalization (see below) |

### `cross_lingual/translate/prompts/` submodules

| File | Purpose |
|------|---------|
| `terminology.py` | `get_terminology_prompt()`, `get_system_prompt_generation_prompt()` |
| `translate.py` | `get_translate_prompt()`, `get_full_document_translate_prompt()`, `get_self_review_prompt()` |
| `format.py` | `get_format_prompt()`, `get_prescan_prompt()` |

### `cross_lingual/translate/validator/` submodules

| File | Purpose |
|------|---------|
| `core.py` | `validate_translation_output()`, `validate_segment()`, `validate_image_references_preserved()`, `summarize_validation_error()` |
| `normalize.py` | `normalize_cjk_punctuation()`, `normalize_placeholders()`, `fix_email_placeholder()`, `fix_ocr_truncations()`, `fix_word_boundary_redacted()`, `normalize_keywords_capitalization()` |
| `artifacts.py` | `strip_prompt_echo()`, `strip_inline_artifacts()`, `strip_prompt_artifacts()`, `strip_source_contamination()` |
| `redacted.py` | `mark_redacted_values()` — inserts `[REDACTED]` for missing OCR values |

## Public API

### `TranslationService`

The sole public entry point. Constructed once per application lifetime.

```python
class TranslationService:
    def __init__(self, cfg: Any) -> None: ...
    async def run(self, pages: List[Dict[str, Any]], content_blocks: List[Dict[str, Any]] | None = None) -> TranslationResult: ...
    def run_sync(self, pages: List[Dict[str, Any]], content_blocks: List[Dict[str, Any]] | None = None) -> TranslationResult: ...
    def save(self, result: TranslationResult, output_dir: str, doc_id: str, image_paths: list[str] | None = None) -> CrossLingualOutput: ...
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(cfg: Any)` | Builds `TranslationConfigContext`, wires `MarkdownFormatter`, `LanguageRouter`, `MultiStageTranslator`, `DocumentPersistenceService`, and compiles the LangGraph |
| `run` | `async (pages, content_blocks?) -> TranslationResult` | Async entry point; runs the graph in a thread executor (LangGraph is sync) |
| `run_sync` | `(pages, content_blocks?) -> TranslationResult` | Synchronous wrapper; raises `RuntimeError` if called inside a running event loop |
| `save` | `(result, output_dir, doc_id, image_paths?) -> CrossLingualOutput` | Persist result to local storage and return downstream output contract |

### `TranslationResult`

```python
@dataclass
class TranslationResult:
    formatted_original: str              # Source-language formatted markdown
    translated_english: str              # Final English translation
    source_language: str                 # ISO 639-1 code (e.g. "zh", "ja", "en")
    terminology_map: Dict[str, str]      # Source term -> English term
    translation_warnings: List[str]      # Validation warnings, fallback notes
    sentences: List[SentenceRegion]      # Sentence-level bbox tracking
    segments: List[TranslationSegment]   # Per-segment source/translation/bbox pairs
    original_blocks: List[ContentBlock]  # Structured MinerU blocks (source)
    translated_blocks: List[ContentBlock] # Structured MinerU blocks (translated)
```

### `ContentBlock`

```python
@dataclass
class ContentBlock:
    type: str               # text, title, image, table, equation, code, list, header, footer, etc.
    page_idx: int           # Page number
    bbox: list[int]         # [x0, y0, x1, y1] normalized 0-1000
    text: str               # Text content (for text/title/header/footer types)
    img_path: str           # Image file path (for image/chart types)
    table_body: str         # HTML table content (for table type)
    # ... plus caption/footnote fields, quality flags, etc.

    def to_dict(self) -> dict[str, Any]: ...           # Serialize to MinerU content_list.json format
    @classmethod
    def from_mineru_block(cls, block: dict) -> ContentBlock: ...  # Create from MinerU block dict
```

### `FormattedDocument`

```python
@dataclass
class FormattedDocument:
    formatted_markdown: str
    sentences: List[SentenceRegion]
    source_language: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_markdown: str = ""
    original_blocks: List[ContentBlock] = field(default_factory=list)
```

### `CrossLingualOutput`

```python
class CrossLingualOutput(BaseModel):
    """Typed output contract passed to Phase 3 (standardize entities)."""
    formatted_original: str
    translated_english: str
    source_language: str
    terminology_map: Dict[str, str]
    translation_warnings: list[str]
    output_dir: str
    original_json_path: str
    translated_json_path: str
    image_paths: list[str]
```

### `SentenceRegion`

```python
@dataclass(frozen=True)
class SentenceRegion:
    page: int
    start_offset: int
    end_offset: int
    text: str
    @property
    def span(self) -> int: ...  # end_offset - start_offset
```

### `MultiStageTranslator`

```python
class MultiStageTranslator(BaseTranslator):
    def __init__(self, ctx: TranslationConfigContext) -> None: ...
    def extract_terminology(self, formatted: FormattedDocument) -> str: ...
    def translate_segments(self, formatted, terminology, blocks=None) -> Tuple[str, List[str], List[str]]: ...
    def run_pipeline(self, formatted, blocks=None) -> Tuple[Dict, str, str, str, List[str], List[str], List[str]]: ...
    def translate_to_result(self, formatted: FormattedDocument) -> TranslationResult: ...
```

### Module-level functions

| Function | Module | Signature | Description |
|----------|--------|-----------|-------------|
| `detect_language` | `language_detector` | `(text, sample_size=4000) -> str` | ISO 639-1 language code via `lingua` |
| `build_page_offset_map` | `format.formatter` | `(pages) -> Dict[int, int]` | Character offset -> page number mapping |
| `extract_sentences` | `format.formatter` | `(text, page_offset_map?) -> List[SentenceRegion]` | Sentence split with bbox tracking |
| `segment_text` | `format.segmenter` | `(text, max_tokens, prompt_overhead_tokens) -> List[str]` | Token-budgeted text segmentation |
| `estimate_tokens` | `format.segmenter` | `(text) -> int` | Rough token count (ASCII/4 + CJK/1) |
| `join_blocks_with_markers` | `blocks` | `(non_empty) -> (str, indices, prefixes, overrides)` | Join blocks with `[BLOCK_N]` markers |
| `split_by_markers` | `blocks` | `(marked_text, n_expected) -> List[str]` | Split LLM output on block markers |
| `merge_short_keywords` | `blocks` | `(non_empty) -> (merged, merge_map)` | Merge adjacent short CJK keyword blocks |
| `build_translated_blocks` | `postprocess` | `(original_blocks, segments, translated_text, ...) -> List[ContentBlock]` | Map translated text back to block structure |
| `deduplicate_bilingual_blocks` | `postprocess` | `(blocks) -> List[ContentBlock]` | Remove duplicate blocks from bilingual documents |
| `check_block_language` | `postprocess` | `(blocks, source_language) -> None` | Raise `TranslationError` if >40% blocks still in source language |
| `flag_quality_issues` | `postprocess` | `(blocks) -> int` | Flag blocks needing manual review (truncated refs, etc.) |
| `compute_translation_drift` | `postprocess` | `(source_segments, translated_parts) -> List[SegmentDrift]` | Character drift between source and translated segments |
| `validate_translation_output` | `validator` | `(source, translated) -> None` | Raises on quality failures |
| `validate_segment` | `validator` | `(source, translated) -> None` | Per-segment quality check |
| `strip_source_contamination` | `validator` | `(text, lang) -> str` | Remove source-language chars leaked into translation |
| `normalize_cjk_punctuation` | `validator` | `(text) -> str` | CJK -> ASCII punctuation normalization |
| `mark_redacted_values` | `validator` | `(text) -> str` | Insert `[REDACTED]` for missing OCR values |

## Internal Design

### 3-Stage Translation Pipeline

The `MultiStageTranslator` runs three sequential stages:

1. **Terminology** — Extract bilingual term pairs (`"基因": "gene"`). For long documents, text is segmented and results are merged/deduplicated. Parsed into `Dict[str, str]` with validation (<=10 words per side, CJK source must contain non-ASCII). Uses `_clean_terminology()` to strip LLM echo artifacts (headers, bullet formatting, language-pair format).

2. **Translate** — Two modes based on input:
   - **Block mode** (when `content_blocks` provided): Each non-empty text/title block is joined with `[BLOCK_N]` markers, translated in a single LLM call, then split back per-block. Adjacent short CJK keyword blocks are merged before translation to prevent context pollution. English-only blocks are preserved as-is. CJK bracket prefixes (`【关键词】`) are stripped before translation and re-added in English after.
   - **Segment mode** (fallback): Text is segmented by token budget, each segment translated with prev/next context. Per-segment validation with up to 3 retries.

3. **Self-review + Normalize** — LLM quality check comparing source vs translation. Then normalization: strip prompt artifacts, source contamination, CJK punctuation normalization, placeholder normalization, email/OCR fixes, repetitive content trimming.

### Block-Level Alignment

When MinerU `content_list.json` blocks are available, the translator joins all text/title blocks with `[BLOCK_N]` markers before sending to the LLM. After translation, `split_by_markers()` recovers per-block translations. This guarantees 1:1 alignment between source and translated blocks, enabling structured JSON output with per-block bbox coordinates.

Short keyword blocks (1-4 CJK chars like "古菌", "硫化叶菌") are merged before translation to prevent the LLM from filling them with nearby content (context pollution). After translation, `split_merged_keywords()` recovers individual translations.

### LLM Client Factory

`providers.py` centralizes LLM client creation and retry logic:
- `create_llm()` / `create_json_llm()` — standard and JSON-mode `ChatOpenAI` instances
- `invoke_with_retry()` / `invoke_json_with_retry()` — exponential backoff (30s base) on transient failures (`APITimeoutError`, `APIConnectionError`, `RateLimitError`, `InternalServerError`, `httpx.TimeoutException`, `ConnectError`). Up to 3 retries.
- System prompts are prepended to human messages (not sent as system role) for compatibility with models like `qwen-mt-flash` that only support user/assistant roles.

### Post-Processing Pipeline

`postprocess.py` handles the gap between raw LLM output and final structured blocks:
- `build_translated_blocks()` — Maps translated text back to original block structure via delimiter-based split or segment matching. Filters non-body blocks (headers, footers, page numbers) but preserves DOI-containing footers. Applies per-block normalization (placeholders, punctuation, email, OCR fixes). Translates auxiliary fields (captions, footnotes) for non-text blocks.
- `deduplicate_bilingual_blocks()` — Detects adjacent text/title blocks with >75% token overlap (common in bilingual documents with English abstract) and removes the shorter duplicate.
- `check_block_language()` — Per-block source-language character detection (CJK, Cyrillic, Hangul). Raises `TranslationError` if >40% of text/title blocks are still in the source language.
- `flag_quality_issues()` — Detects truncated references, 2-digit years, ambiguous pronouns, and "suspicious" (should be "suspected") for manual review.

### Validation & Fallback

Validation runs at two levels:
1. **Per-segment** (`validate_segment`): Each translated segment is checked individually during translation. Failures trigger retry (up to 3 attempts).
2. **Full-document** (`validate_translation_output`): After the pipeline produces a translation, checks: non-empty, CJK ratio <=10%, similarity ratio <85% vs source, and `lingua`-detected language is English.

Critical failures (unchanged output, non-English output, empty) raise `TranslationError` to prevent persisting garbage. Non-critical failures become `translation_warnings`.

### Validator Submodules

The `validator/` package is split into four focused modules:
- **`core.py`** — Core validation logic: `validate_translation_output()`, `validate_segment()`, `validate_image_references_preserved()`
- **`normalize.py`** — Text normalization: CJK punctuation, placeholders, email fixes, OCR truncation fixes, word-boundary `[REDACTED]` fixes
- **`artifacts.py`** — LLM artifact stripping: prompt echo, inline artifacts, prompt artifacts, source-language contamination
- **`redacted.py`** — OCR redaction marking: `mark_redacted_values()` inserts `[REDACTED]` for missing values

### Sentence-Level Bbox Tracking

`formatter.py` builds a `page_offset_map` mapping character offsets to page numbers. `extract_sentences()` splits on sentence-ending punctuation (`.!?。！？`) and records each sentence's page and character offset range. These `SentenceRegion` objects are preserved through to `TranslationSegment.source_bbox`, enabling downstream visualization to highlight source text on the original PDF.

### Character Drift Tracking

Two drift report types track position changes through the pipeline:
- `SentenceDrift` — Per-sentence drift from raw OCR to formatted text (format stage)
- `SegmentDrift` — Per-segment drift from source to translated text (translation stage)

Drift data is persisted in `metadata.json` for downstream debugging and visualization.

### Concurrency Model

- `TranslationService.run()` is `async` but runs the sync LangGraph in a thread executor (`loop.run_in_executor`).
- `run_sync()` wraps `asyncio.run()` for non-async contexts; raises if an event loop is already running.
- LLM calls within `MultiStageTranslator` are synchronous — block translation is a single LLM call; segment-mode segments are translated sequentially.

### Config Injection

`TranslationConfigContext` is built once from `cfg.translation` at service init and injected into `MultiStageTranslator`. This prevents raw config objects from leaking into deep translation code. The context is `frozen=True` to prevent mutation.

| Env Var | Field | Description |
|---------|-------|-------------|
| `TRANSLATION_MODEL` | `model` | LLM model name (e.g. `qwen2.5:14b`) |
| `TRANSLATION_API_KEY` | `api_key` | API key for translation LLM |
| `TRANSLATION_BASE_URL` | `base_url` | OpenAI-compatible endpoint |
| `TRANSLATION_TEMPERATURE` | `temperature` | LLM temperature (default 0.0) |

## Usage Patterns

### Basic: Translate a non-English document

```python
from src.core.config import get_config
from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService

cfg = get_config()
service = TranslationService(cfg=cfg)

# Pages + blocks from MinerU parse
result = await service.run(pages, content_blocks=content_blocks)

# result.translated_english is the final English markdown
# result.translated_blocks[i].text is the per-block translation
# result.terminology_map maps source terms to English
# result.sentences[i].page tells you which page each sentence came from
```

### Translate and persist

```python
result = await service.run(pages, content_blocks=content_blocks)
output = service.save(result, output_dir="./output", doc_id="doc_001")

# output.original_json_path   → ./output/doc_001/original.json
# output.translated_json_path → ./output/doc_001/translated.json
# output.image_paths          → copied image files
```

### English document (auto-skip)

```python
pages = [{"page_number": 1, "markdown": "The patient carries a BRCA1 variant."}]
result = await service.run(pages)
assert result.source_language == "en"
assert result.translated_english == result.formatted_original
assert len(result.segments) == 0  # no translation occurred
```

### Inspect warnings

```python
result = await service.run(pages, content_blocks=content_blocks)
for warning in result.translation_warnings:
    if warning == "repetition_loop":
        logger.warning("LLM entered repetition loop — output was trimmed")
    elif "per_block_check" in warning:
        logger.warning("Partial translation failure — some blocks remain in source language")
    elif "image_refs" in warning:
        logger.warning("Image references may be missing in translation")
```

### Sync usage (scripts, tests)

```python
service = TranslationService(cfg=get_config())
result = service.run_sync(pages, content_blocks=content_blocks)
```

## Extension Guide

### Adding a new translation strategy (e.g., NMT)

1. Implement `BaseTranslator` from `cross_lingual/translate/base.py`:
   ```python
   class NMTTranslator(BaseTranslator):
       def run_pipeline(self, formatted): ...
       def translate_to_result(self, formatted): ...
   ```
2. Update `TranslationService.__init__` to accept a translator factory or strategy parameter.
3. The rest of the pipeline (formatting, routing, persistence, LangGraph wiring) is unchanged.

### Adding a new formatter (e.g., HTML input)

1. Implement `BaseFormatter` from `cross_lingual/format/base.py`.
2. Produce a `FormattedDocument` with `formatted_markdown`, `sentences`, and `original_blocks`.
3. Inject into `TranslationService.__init__` — the graph's `format` node calls `self._formatter.format()`.

### Modifying the LangGraph topology

The graph is built in `TranslationService._build_graph()`. Add nodes and edges there. Each node method should:
- Accept and return `PipelineState`
- Be decorated with `@traced_node("name")` for observability
- Contain zero business logic (delegate to formatter/translator/router)

### Adding new prompt stages

1. Add prompt function to the appropriate file in `cross_lingual/translate/prompts/`.
2. Add stage method to `MultiStageTranslator`.
3. Wire into `run_pipeline()` return tuple and `translate_to_result()`.

### Adding new validation rules

1. Add validation function to `cross_lingual/translate/validator/core.py` or `normalize.py`.
2. Call from `run_pipeline()` normalization section or `_translate_one_segment()` retry loop.
3. Non-fatal warnings append to `warnings` list; fatal issues raise `TranslationError`.

### Common pitfalls

- **Don't bypass `TranslationConfigContext`.** Always inject typed config, never pass raw `Settings` to translation code.
- **Don't add fields to `PipelineState` lightly.** Each field is a pipeline artifact; the graph's conditional edges depend on `needs_translation`.
- **Validation warnings are non-fatal.** The pipeline never aborts on non-critical validation failure. If you need strict failure, handle it at the caller.
- **Block markers are fragile.** If you modify `join_blocks_with_markers()` or `split_by_markers()`, ensure the `[BLOCK_N]` pattern survives LLM translation. Test with documents that produce 10+ blocks.

## Performance Notes

- **LLM latency dominates.** Block mode makes 3-5 LLM calls (terminology + full-document + self-review + optional prefix translations). Segment mode makes 2 + N calls (where N = number of segments).
- **Block mode is preferred.** When `content_blocks` are available, block mode translates the entire document in a single LLM call, which is faster and produces better alignment than segment mode.
- **Token estimation is approximate.** `estimate_tokens()` uses a heuristic (ASCII/4 + CJK/1). For critical token budgets, instrument with actual tokenizer counts.
- **Memory.** `TranslationResult` holds the full source and translated text plus block metadata. A 50-page document with ~50K characters and ~200 blocks produces a ~500KB result object.
- **Thread executor.** The async `run()` method offloads LangGraph execution to a thread pool. This is acceptable because LangGraph's `invoke()` is CPU-bound graph traversal, not I/O.

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `langgraph` | >=1.2.0 | State graph execution for the pipeline |
| `langchain-core` | >=1.4.0 | Message abstraction for LLM calls |
| `langchain-openai` | >=1.2.1 | OpenAI-compatible ChatOpenAI client |
| `langsmith` | >=0.8.3 | Tracing and observability |
| `lingua-language-detector` | >=2.2.0 | Language detection (with CJK support) |
| `openai` | (transitive) | LLM API client |
| `httpx` | (transitive) | HTTP transport for LLM calls |
| `pydantic` | >=2.7.0 | PipelineState schema, CrossLingualOutput contract |
| `loguru` | >=0.7.0 | Structured logging |
| `rust_io.files` (via `src.utils.rust_io`) | (optional) | File I/O for persistence — falls back to stdlib `Path.write_text()` when unavailable |

## Testing

Tests live in `backend/tests/core/cross_lingual_process_and_extract_evidence/`.

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v
```

### Test coverage

| Test file | What it covers |
|-----------|---------------|
| `test_workflow.py` | `TranslationService` init, graph construction, `TranslationConfigContext` |
| `test_translator.py` | `MultiStageTranslator` init, `_to_text`, `_parse_terminology`, `_clean_terminology` |
| `test_translator_segmentation.py` | Segment-mode translation, token budgeting, retry logic |
| `test_formatter.py` | `MarkdownFormatter`, `build_page_offset_map`, `extract_sentences`, `compute_format_drift` |
| `test_segmenter.py` | `estimate_tokens`, `segment_text` token budgeting |
| `test_language_detector.py` | `detect_language`, `should_skip_translation` |
| `test_validator.py` | `validate_translation_output`, `validate_segment`, `summarize_validation_error` |
| `test_prompts.py` | Prompt template generation |
| `test_router.py` | `LanguageRouter.route` decisions |
| `test_contracts.py` | `SentenceRegion`, `FormattedDocument`, `ContentBlock`, `TranslationResult` construction |
| `test_drift_tracking.py` | `SentenceDrift`, `SegmentDrift`, `compute_translation_drift` |
| `test_persistence.py` | `DocumentPersistenceService.save()`, `to_output()` |
| `test_integration.py` | Full pipeline with mocked LLM (Chinese -> English, English skip) |
| `test_e2e_translation.py` | End-to-end translation with real LLM (if configured) |
| `test_e2e_es_pt.py` | End-to-end for Spanish/Portuguese documents |
| `test_round2_fixes.py` | Regression tests for specific bug fixes |

All LLM-dependent tests use `unittest.mock` patches — no real API calls are made in the unit test suite. E2E tests (`test_e2e_*`) require a configured LLM endpoint.
