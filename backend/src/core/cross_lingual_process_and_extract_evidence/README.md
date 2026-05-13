# Cross-Lingual Process & Extract Evidence

> Phase 2 of the ACMG Lingua pipeline: format, detect, and translate non-English biomedical documents into English via a multi-stage LLM pipeline with sentence-level bbox tracking for provenance.

## Quick Start

```python
from src.core.config import get_config
from src.core.cross_lingual_process_and_extract_evidence.workflow import TranslationService

cfg = get_config()
service = TranslationService(cfg=cfg)

# pages come from MinerU parse output: List[{"page_number": N, "markdown": "..."}]
pages = [{"page_number": 1, "markdown": "患者携带新的BRCA1变异。"}]
result = await service.run(pages)

print(result.translated_english)   # "The patient carries a novel BRCA1 variant."
print(result.source_language)      # "zh"
print(result.terminology_map)      # {"变异": "variant", ...}
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  TranslationService                      │
│  (workflow.py — LangGraph orchestrator, public API)      │
│                                                         │
│  ┌──────────┐   ┌──────────────────┐   ┌──────────────┐ │
│  │  format   │──▶│ detect_language   │──▶│   translate   │ │
│  │  (node)   │   │     (node)        │   │   or skip     │ │
│  └──────────┘   └──────────────────┘   └──────────────┘ │
│       │                  │                     │         │
│       ▼                  ▼                     ▼         │
│  MarkdownFormatter  LanguageRouter    MultiStageTranslator│
└─────────────────────────────────────────────────────────┘
         │                  │                     │
         ▼                  ▼                     ▼
   cross_lingual/      lingua library      cross_lingual/
   format/             + _CJK_RE           translate/
```

**Data flow:**

1. **Input**: `List[Dict[str, Any]]` pages — serialized MinerU `ParseResult.pages`, each with `page_number` and `markdown`.
2. **Format**: `MarkdownFormatter` joins per-page markdown, normalizes whitespace/headings, builds a page offset map, and splits text into `SentenceRegion` objects tracking page + character offsets. Output: `FormattedDocument`.
3. **Detect**: `detect_language()` uses the `lingua` library (with CJK regex fast-path). `LanguageRouter` decides `"translate"` or `"skip_translate"`.
4. **Translate**: `MultiStageTranslator` runs five LLM stages: terminology extraction → structure planning → segment-by-segment draft → polish → review → validate. Output: `TranslationResult`.
5. **Skip**: For already-English documents, a synthetic `TranslationResult` is produced with `translated_english == formatted_original`.

The pipeline is a LangGraph `StateGraph` with typed `PipelineState` (Pydantic). Nodes are thin delegates decorated with `@traced_node` for LangSmith observability.

## Directory Map

| Path | Purpose |
|------|---------|
| `contracts.py` | All data types: `SentenceRegion`, `FormattedDocument`, `TranslationSegment`, `TranslationResult`, `PipelineState` |
| `config_context.py` | `TranslationConfigContext` — extracts `cfg.translation` subset, injected into translator |
| `middleware.py` | `traced_node` decorator — LangSmith tracing + loguru logging per graph node |
| `router.py` | `LanguageRouter` — single-responsibility routing decision |
| `workflow.py` | `TranslationService` — LangGraph graph wiring, `run()` / `run_sync()` public API |
| `cross_lingual/format/` | Document formatting: `MarkdownFormatter`, sentence segmentation |
| `cross_lingual/translate/` | Multi-stage LLM translation: `MultiStageTranslator`, prompts, validation |

## Public API

### `TranslationService`

The sole public entry point. Constructed once per application lifetime.

```python
class TranslationService:
    def __init__(self, cfg: Settings) -> None: ...
    async def run(self, pages: List[Dict[str, Any]]) -> TranslationResult: ...
    def run_sync(self, pages: List[Dict[str, Any]]) -> TranslationResult: ...
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(cfg: Settings)` | Builds `TranslationConfigContext`, wires `MarkdownFormatter`, `LanguageRouter`, `MultiStageTranslator`, and compiles the LangGraph |
| `run` | `async (pages: List[Dict]) -> TranslationResult` | Async entry point; runs the graph in a thread executor (LangGraph is sync) |
| `run_sync` | `(pages: List[Dict]) -> TranslationResult` | Synchronous wrapper; raises `RuntimeError` if called inside a running event loop |

### `TranslationResult`

```python
@dataclass
class TranslationResult:
    formatted_original: str          # Source-language formatted markdown
    translated_english: str          # Final English translation
    source_language: str             # ISO 639-1 code (e.g. "zh", "ja", "en")
    terminology_map: Dict[str, str]  # Source term → English term
    translation_warnings: List[str]  # Validation warnings, fallback notes
    sentences: List[SentenceRegion]  # Sentence-level bbox tracking
    segments: List[TranslationSegment]  # Per-segment source/translation/bbo pairs
```

### `FormattedDocument`

```python
@dataclass
class FormattedDocument:
    formatted_markdown: str
    sentences: List[SentenceRegion]
    source_language: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### `SentenceRegion`

```python
@dataclass(frozen=True)
class SentenceRegion:
    page: int          # Page number in source document
    start_offset: int  # Character offset in concatenated markdown
    end_offset: int
    text: str
    @property
    def span(self) -> int: ...  # end_offset - start_offset
```

### `LanguageRouter`

```python
class LanguageRouter:
    @staticmethod
    def route(state: PipelineState) -> Literal["translate", "skip_translate"]: ...
```

### `MultiStageTranslator`

```python
class MultiStageTranslator(BaseTranslator):
    def __init__(self, ctx: TranslationConfigContext) -> None: ...
    def run_pipeline(self, formatted: FormattedDocument) -> Tuple[...]: ...
    def translate_to_result(self, formatted: FormattedDocument) -> TranslationResult: ...
```

### `MarkdownFormatter`

```python
class MarkdownFormatter(BaseFormatter):
    def format(self, pages: List[Dict[str, Any]]) -> FormattedDocument: ...
```

### Module-level functions (cross_lingual.format)

| Function | Signature | Description |
|----------|-----------|-------------|
| `build_page_offset_map` | `(pages: List[Dict]) -> Dict[int, int]` | Maps character offset → page number |
| `extract_sentences` | `(text: str, page_offset_map?) -> List[SentenceRegion]` | Sentence split with bbox tracking |
| `segment_text` | `(text: str, max_tokens=8192, prompt_overhead_tokens=0) -> List[str]` | Token-budgeted text segmentation |
| `estimate_tokens` | `(text: str) -> int` | Rough token count (ASCII/4 + CJK/1) |

### Module-level functions (cross_lingual.translate)

| Function | Signature | Description |
|----------|-----------|-------------|
| `detect_language` | `(text: str, sample_size=4000) -> str` | ISO 639-1 language code via `lingua` |
| `should_skip_translation` | `(text: str) -> bool` | True if already English or empty |
| `validate_translation_output` | `(source_text, translated_text) -> None` | Raises `ValueError` on quality failures |
| `summarize_validation_error` | `(exc: Exception) -> str` | Extracts `translation_validation_failed:` prefix |

## Internal Design

### Multi-Stage Translation Pipeline

The `MultiStageTranslator` runs five sequential LLM stages, each with a dedicated prompt from `prompts.py`:

1. **Terminology** — Extract bilingual term pairs (`"基因": "gene"`). Parsed into a `Dict[str, str]` with validation (≤10 words per side, source must contain non-ASCII).
2. **Structure** — Plan logical structure for English rendering (restore omitted subjects, split long clauses, make connectors explicit).
3. **Draft** — Segment-by-segment translation. Text is split via `segment_text()` to fit within the LLM context window (default 8192 tokens minus prompt overhead). Each segment gets a combined prompt with terminology map and structure plan.
4. **Polish** — Improve fluency for academic English while preserving biomedical literals and markdown structure.
5. **Review** — Compare source vs translated, identify unresolved ambiguity, dropped content, or terminology drift.

### Retry Strategy

`_invoke_with_retry` retries up to 2 times on transient failures only:
- `openai.APITimeoutError`, `APIConnectionError`, `RateLimitError`, `InternalServerError`
- `httpx.TimeoutException`, `ConnectError`

Non-transient exceptions (e.g., `ValueError`, `TypeError`) propagate immediately.

### Validation & Fallback

After the pipeline produces a translation:
1. `validate_translation_output()` checks: non-empty, CJK ratio ≤10%, similarity ratio <85% vs source, and `lingua`-detected language is English.
2. If validation fails on the polished output, the system falls back to the draft (retrying validation).
3. All validation failures become `translation_warnings` in the `TranslationResult` — they do not abort the pipeline.

### Sentence-Level Bbox Tracking

`formatter.py` builds a `page_offset_map` mapping character offsets to page numbers. `extract_sentences()` splits on sentence-ending punctuation (`.!?。！？`) and records each sentence's page and character offset range. These `SentenceRegion` objects are preserved through to `TranslationSegment.source_bbox`, enabling downstream visualization to highlight source text on the original PDF.

### Token-Budgeted Segmentation

`segment_text()` uses a CJK-aware token estimator:
- ASCII characters ≈ 4 chars/token
- CJK characters ≈ 1 token each (blended to ~1.2 chars/token for CJK-heavy text)

Segmentation splits on paragraph boundaries first, then on sentences, and hard-splits oversized sentences. The `prompt_overhead_tokens` parameter deducts the fixed prompt cost from the effective budget.

### Concurrency Model

- `TranslationService.run()` is `async` but runs the sync LangGraph in a thread executor (`loop.run_in_executor`).
- `run_sync()` is a `asyncio.run()` wrapper for non-async contexts; raises if an event loop is already running.
- LLM calls within `MultiStageTranslator` are synchronous — the segment-by-segment draft is serial (each segment calls the LLM in order).

### Config Injection

`TranslationConfigContext` is built once from `cfg.translation` at service init and injected into `MultiStageTranslator`. This prevents raw config objects from leaking into deep translation code. The context is `frozen=True` to prevent mutation.

The config maps to environment variables:
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

# Pages from MinerU parse
pages = json.loads(parse_result.model_dump_json())["pages"]
result = await service.run(pages)

# result.translated_english is the final English markdown
# result.terminology_map maps source terms to English
# result.sentences[i].page tells you which page each sentence came from
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
result = await service.run(pages)
for warning in result.translation_warnings:
    if warning == "fell_back_to_draft":
        logger.warning("Translation used draft fallback — polish may have introduced issues")
    elif "non_english_output" in warning:
        logger.warning("Translation output contains non-English text")
```

### Sync usage (scripts, tests)

```python
service = TranslationService(cfg=get_config())
result = service.run_sync(pages)  # wraps asyncio.run()
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
3. The rest of the pipeline (formatting, routing, LangGraph wiring) is unchanged.

### Adding a new formatter (e.g., HTML input)

1. Implement `BaseFormatter` from `cross_lingual/format/base.py`.
2. Produce a `FormattedDocument` with `formatted_markdown` and `sentences`.
3. Inject into `TranslationService.__init__` — the graph's `format` node calls `self._formatter.format()`.

### Modifying the LangGraph topology

The graph is built in `TranslationService._build_graph()`. Add nodes and edges there. Each node method should:
- Accept and return `PipelineState`
- Be decorated with `@traced_node("name")` for observability
- Contain zero business logic (delegate to formatter/translator/router)

### Adding new prompt stages

1. Add prompt function to `cross_lingual/translate/prompts.py`.
2. Add stage method to `MultiStageTranslator`.
3. Wire into `run_pipeline()` return tuple and `translate_to_result()`.

### Common pitfalls

- **Don't bypass `TranslationConfigContext`.** Always inject typed config, never pass raw `Settings` to translation code.
- **Don't add fields to `PipelineState` lightly.** Each field is a pipeline artifact; the graph's conditional edges depend on `needs_translation`.
- **Validation warnings are non-fatal.** The pipeline never aborts on validation failure — it falls back to draft. If you need strict failure, handle it at the caller.

## Performance Notes

- **LLM latency dominates.** The five-stage pipeline makes 2 + N LLM calls (where N = number of segments). A typical 5-page Chinese document yields 3-5 segments, totaling 5-7 LLM round-trips.
- **Segment serialization.** Draft segments are translated sequentially (not parallel) to maintain context coherence across segment boundaries. This is a deliberate tradeoff for translation quality.
- **Token estimation is approximate.** `estimate_tokens()` uses a heuristic (ASCII/4 + CJK/1). For critical token budgets, instrument with actual tokenizer counts.
- **Memory.** `TranslationResult` holds the full source and translated text plus sentence/segment metadata. A 50-page document with ~50K characters produces a ~200KB result object.
- **Thread executor.** The async `run()` method offloads LangGraph execution to a thread pool. This is acceptable because LangGraph's `invoke()` is CPU-bound graph traversal, not I/O.

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `langgraph` | ≥1.2.0 | State graph execution for the pipeline |
| `langchain-core` | ≥1.4.0 | Message abstraction for LLM calls |
| `langchain-openai` | ≥1.2.1 | OpenAI-compatible ChatOpenAI client |
| `langsmith` | ≥0.8.3 | Tracing and observability |
| `lingua-language-detector` | ≥2.2.0 | Language detection (with CJK support) |
| `openai` | (transitive) | LLM API client |
| `httpx` | (transitive) | HTTP transport for LLM calls |
| `pydantic` | ≥2.7.0 | PipelineState schema |
| `loguru` | ≥0.7.0 | Structured logging |

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
| `test_translator.py` | `MultiStageTranslator` init, `_to_text`, `_parse_terminology`, `_invoke_with_retry` |
| `test_formatter.py` | `MarkdownFormatter`, `build_page_offset_map`, `extract_sentences` |
| `test_segmenter.py` | `estimate_tokens`, `segment_text` token budgeting |
| `test_language_detector.py` | `detect_language`, `should_skip_translation` |
| `test_validator.py` | `validate_translation_output`, `summarize_validation_error` |
| `test_prompts.py` | Prompt template generation |
| `test_router.py` | `LanguageRouter.route` decisions |
| `test_contracts.py` | `SentenceRegion`, `FormattedDocument`, `TranslationResult` construction |
| `test_integration.py` | Full pipeline with mocked LLM (Chinese → English, English skip) |

All LLM-dependent tests use `unittest.mock` patches — no real API calls are made in the test suite.
