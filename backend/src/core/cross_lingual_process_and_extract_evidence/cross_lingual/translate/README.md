# Translate Module

> Phase 2 submodule — 3-stage LLM-based biomedical translation pipeline: terminology extraction → block-level translation → validation, with CJK→English as the primary direction and 10 languages supported (en, zh, ja, ko, fr, de, es, pt, ru, ar).

## Quick Start

```python
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate import (
    MultiStageTranslator,
)
from src.core.cross_lingual_process_and_extract_evidence.config_context import (
    TranslationConfigContext,
)

ctx = TranslationConfigContext(model="gpt-4o", api_key="...", base_url="...")
translator = MultiStageTranslator(ctx)
result = translator.translate_to_result(formatted_doc)
print(f"Translated: {len(result.translated_english)} chars, {len(result.translation_warnings)} warnings")
```

## Architecture

```
MultiStageTranslator [translator.py]
│
├─ Stage 1: extract_terminology()
│   ├─ get_terminology_prompt()  → LLM (async, parallel for multi-segment docs)
│   ├─ _extract_terminology_json_pairs()  → JSON-mode fallback extraction
│   ├─ _clean_terminology()  → strip artifacts, normalize pairs
│   └─ _parse_terminology()  → Dict[str, str] with CJK validation
│
├─ Stage 2: translate_segments()
│   ├─ _generate_system_prompt()  → LLM meta-prompt for document-tailored system message
│   ├─ [blocks mode] _translate_blocks()  → one LLM call per document
│   │   ├─ merge_short_keywords()  [blocks.py]  → prevent context pollution
│   │   ├─ join_blocks_with_markers()  [blocks.py]  → [BLOCK_N] markers + English overrides
│   │   ├─ get_full_document_translate_prompt()  → inject strict English-only directive on retry
│   │   └─ split_by_markers()  [blocks.py]  → recover per-block translations
│   └─ [segment mode] _translate_one_segment()  → per-segment with retry
│       ├─ JSON-mode (attempt 1) + fallback
│       └─ validate_segment()  → CJK contamination check
│
├─ Stage 3: Self-review
│   └─ _self_review()  → LLM quality check (reverts if markers lost or >50% shrinkage)
│
├─ Post-processing [postprocess.py]
│   ├─ strip_prompt_artifacts() / strip_source_contamination()  [validator/artifacts.py]
│   ├─ normalize_cjk_punctuation() / normalize_placeholders()  [validator/normalize.py]
│   ├─ fix_email_placeholder() / fix_ocr_truncations() / fix_word_boundary_redacted()
│   ├─ trim_repetitive_content()  → LLM repetition loop guard
│   ├─ build_translated_blocks()  → pair original ↔ translated, per-block post-processing
│   ├─ deduplicate_bilingual_blocks()  → remove adjacent near-duplicate pairs
│   ├─ check_block_language()  → per-block source-language detection (>40% threshold)
│   ├─ _translate_auxiliary_blocks()  → batch-translate captions/footnotes for non-text blocks
│   └─ flag_quality_issues()  → mark truncated refs, ambiguous pronouns for manual review
│
├─ Per-block retry loop (translate_to_result)
│   └─ If check_block_language fails → retry run_pipeline with strict=True (max 1 retry)
│
└─ translate_to_result()  → TranslationResult with full metadata
```

## Public API

### `MultiStageTranslator`

```python
class MultiStageTranslator(BaseTranslator):
    def __init__(self, ctx: TranslationConfigContext)
    async def extract_terminology(self, formatted: FormattedDocument) -> str
    async def translate_segments(self, formatted, terminology, blocks=None, *, strict=False) -> Tuple[str, List[str], List[str]]
    async def run_pipeline(self, formatted, blocks=None, *, strict=False) -> Tuple[Dict[str, str], str, str, str, List[str], List[str], List[str]]
    async def translate_to_result(self, formatted: FormattedDocument) -> TranslationResult
```

### `BaseTranslator` (base.py)

```python
class BaseTranslator(ABC):
    async def run_pipeline(self, formatted: FormattedDocument) -> Tuple[Dict[str, str], str, List[str], List[str], List[str]]
    async def translate_to_result(self, formatted: FormattedDocument) -> TranslationResult
```

### Key Functions

| Module | Function | Description |
|--------|----------|-------------|
| `language_detector.py` | `detect_language(text, sample_size=4000)` | `lingua`-based detection, returns ISO 639-1 code |
| `language_detector.py` | `should_skip_translation(text)` | True if text is already English or empty |
| `providers.py` | `create_llm(model, api_key, base_url, temperature, max_tokens, timeout, api_keys)` | LLM client factory (`LLMPoolAdapter`) |
| `providers.py` | `create_json_llm(...)` | JSON-mode LLM factory |
| `providers.py` | `invoke_with_retry(llm, prompt, stage, system_prompt)` | LLM call with exponential backoff (3 retries, 30s base) |
| `providers.py` | `invoke_json_with_retry(llm, prompt, stage, system_prompt)` | JSON-mode LLM call with retry |
| `providers.py` | `get_llm_semaphore(concurrency=5)` | Module-level concurrency limiter |
| `blocks.py` | `merge_short_keywords(non_empty)` | Merge adjacent 1-4 char CJK keywords |
| `blocks.py` | `split_merged_keywords(parts, merge_map)` | Split merged keywords back after translation |
| `blocks.py` | `join_blocks_with_markers(non_empty)` | Join blocks with `[BLOCK_N]` markers, detect English-only blocks |
| `blocks.py` | `split_by_markers(marked_text, n)` | Split LLM output on block markers |
| `blocks.py` | `is_short_keyword(text)` | Check if text is 1-4 CJK chars |
| `blocks.py` | `is_predominantly_english(text)` | Check if <5% CJK characters |
| `postprocess.py` | `build_translated_blocks(blocks, segments, text, indices, aux)` | Map translated text back to block structure |
| `postprocess.py` | `deduplicate_bilingual_blocks(blocks)` | Remove adjacent near-duplicate blocks (75% token overlap) |
| `postprocess.py` | `check_block_coverage(original_blocks, translated_blocks)` | Reject fluent but incomplete translations that only cover the title/abstract |
| `postprocess.py` | `check_block_language(blocks, source_language)` | Detect partial translation failures (>40% untranslated threshold) |
| `postprocess.py` | `flag_quality_issues(blocks)` | Mark blocks needing manual review (truncated refs, ambiguous pronouns) |
| `postprocess.py` | `trim_repetitive_content(text)` | Remove repeated heading blocks from LLM repetition loops |
| `postprocess.py` | `compute_translation_drift(source_segs, translated_parts)` | Compute per-segment character drift |
| `exceptions.py` | `TranslationError` | Raised on critical translation failure |
| `validator/` | See [validator/README.md](validator/README.md) | Validation, normalization, artifact stripping |

### Prompts

| Module | Purpose |
|--------|---------|
| `prompts/translate.py` | Per-segment and full-document translation prompts; self-review prompt |
| `prompts/terminology.py` | Terminology extraction + dynamic system prompt generation |
| `prompts/format.py` | LLM formatting/redaction detection prescan prompt |

## Internal Design

### Dynamic system prompt generation

Before translation, `_generate_system_prompt()` sends a document sample to the LLM with a meta-prompt (`get_system_prompt_generation_prompt`) to produce a document-tailored system message. This prompt is reused for all segment/block translations of that document. Fallback: a generic biomedical translation prompt if the generated one is too short (<50 chars).

### Block-level translation (primary path)

When `blocks` are provided, the translator switches to **block-level mode** — all non-empty text/title blocks are translated in a single LLM call for guaranteed alignment:

1. `merge_short_keywords()` merges adjacent 1-4 char CJK keywords (e.g., "古菌" + "硫化叶菌" → "古菌；硫化叶菌") to prevent the LLM from filling them with nearby content
2. `join_blocks_with_markers()` wraps each block in `[BLOCK_N]`, strips `【摘要】`/`【关键词】` prefixes, marks `[REDACTED]` values, and detects English-only blocks to preserve as-is
3. A single LLM call translates the entire document at once (with `strict=True` English-only directive on retry)
4. `split_by_markers()` splits the output back into per-block translations
5. CJK prefixes (e.g., `【关键词】`) are translated separately in parallel and re-prepended
6. `split_merged_keywords()` expands merged keywords back to individual translations

### Per-segment translation (fallback path)

When no blocks are provided, the text is segmented by `segment_text()` and each segment is translated independently with neighboring context (prev/next 150 chars). Segments run in parallel (bounded by the 5-concurrent LLM semaphore). Each segment gets up to 3 retries with validation between attempts. First attempt uses JSON mode to prevent prompt echo.

### Terminology management

The terminology pipeline runs before translation:

1. LLM extracts bilingual term pairs (e.g., "乳腺癌: breast cancer")
2. For long documents, text is segmented and terminology is extracted in parallel per segment, then merged and deduplicated
3. `_clean_terminology()` strips LLM echo artifacts (markdown headers, bullet points, `**bold**` pairs, Source/Target language format)
4. `_parse_terminology()` validates: CJK sources require non-ASCII, Latin-script sources skip identical source/target, deduplicates by target, caps at 100 entries, strips `(保留)`/`(keep)`/`(preserve)` annotations
5. Validated pairs are injected into the translation prompt

### Contamination stripping

Post-translation, `strip_source_contamination()` (in `validator/artifacts.py`) uses a two-pass approach:
- **Pass 1 (leading):** Skip paragraphs at the start that are predominantly CJK (>10% CJK ratio)
- **Pass 2 (trailing):** Stop collecting paragraphs once a >40% CJK paragraph appears after 200+ chars of English content

Safety: if stripping leaves <100 chars, the original is preserved.

### Repetition loop detection

The guard in `run_pipeline()` catches infinite repetition: if translated output exceeds source x 5 and has suspicious heading uniqueness ratio, `trim_repetitive_content()` keeps only the first occurrence of each heading and its body. Safety: if trimming removes >90% of content and result is <30 chars, the original is preserved.

### Per-block language check and retry

After building translated blocks, `check_block_language()` detects partial translation failures (e.g., a Russian doc where only the first page was translated). If >40% of text/title blocks still contain source-language characters (Cyrillic, CJK, or Hangul), the entire pipeline is re-run once with `strict=True`, which appends an English-only directive to the prompt. Capped at `_MAX_PER_BLOCK_RETRIES = 1` to bound LLM cost.

### Block coverage check and retry

`check_block_coverage()` catches a different failure mode: the model returns fluent English but only translates the title/abstract of a full paper. It compares text/title block count and character coverage between the original and translated block sets. If coverage falls below the configured thresholds, translation is retried once with the same strict English-only path used by the language check. This prevents bilingual source documents with an existing English abstract from being mistaken for fully translated papers.

### Auxiliary block translation

`_translate_auxiliary_blocks()` translates captions and footnotes for non-text blocks (tables, images) in batches of 10, using JSON mode. These are injected into `build_translated_blocks()` to populate `table_caption`, `table_footnote`, `image_caption`, and `image_footnote` fields on the translated `ContentBlock` objects.

## Usage Patterns

### Full pipeline with blocks

```python
translator = MultiStageTranslator(ctx)
result = translator.translate_to_result(formatted_doc, blocks=content_blocks)
# result.translated_english — full translated text
# result.translated_blocks — per-block translations with alignment
# result.translation_warnings — quality issues
```

### Terminology-only extraction

```python
terms = translator.extract_terminology(formatted_doc)
# "乳腺癌: breast cancer\n靶向治疗: targeted therapy\n..."
```

### Language detection

```python
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate import detect_language
lang = detect_language("这是一段中文文本")
assert lang == "zh"
```

## Extension Guide

### Adding a new language

1. Add CJK/Latin detection patterns in `language_detector.py`
2. Add keyword patterns in `prompts/` for the new language
3. Add contamination-stripping rules in `validator/`
4. Add literature classification patterns in... (this is in online_acquisition, separate module)

### Adding a new translator backend

Subclass `BaseTranslator`:

```python
class NMTTranslator(BaseTranslator):
    async def run_pipeline(self, formatted: FormattedDocument):
        # Call external NMT API
        ...
        return terms, translated, source_segments, translated_parts, warnings

    async def translate_to_result(self, formatted: FormattedDocument) -> TranslationResult:
        ...
```

### Custom validation rules

Add to `validator/core.py`:

```python
def validate_my_rule(source: str, translated: str) -> None:
    if some_condition:
        raise ValueError("custom validation failed")
```

## Performance Notes

- Block-level translation: **1 LLM call** per document (not per-segment) — major latency win
- Terminology extraction: 1-N LLM calls (parallel for multi-segment documents)
- Dynamic system prompt generation: 1 additional LLM call per document
- Self-review: 1 additional LLM call
- Auxiliary block translation: batches of 10, parallelized
- Token budgets: `_INPUT_BUDGET = 16,000` tokens, terminology truncated at 40% of available budget
- `_MAX_SEGMENT_RETRIES = 3` per segment for per-segment mode
- `_MAX_PER_BLOCK_RETRIES = 1` for per-block language check retry with strict prompt
- `_LLM_CONCURRENCY = 5` — module-level semaphore limits parallel LLM calls
- `_BACKOFF_BASE = 30.0s` — exponential backoff on transient failures (30s, 60s, 120s)
- JSON mode (attempt 1) reduces prompt echo but adds ~200ms overhead
- `_MODEL_MAX_TOKENS = 200,000` — maximum context tokens for the general-purpose LLM

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `langchain_core` | LLM abstraction (messages, invocation) |
| `openai` | Transient exception types for retry logic |
| `httpx` | HTTP timeout/connection exceptions for retry |
| `loguru` | Structured logging |
| `re` | Block markers, CJK detection, artifact stripping |
| `json` | JSON-mode LLM output parsing |
| `asyncio` | Parallel segment/terminology translation, semaphore |
| Parent contracts (`...contracts`) | FormattedDocument, TranslationResult, ContentBlock, TranslationSegment, SegmentDrift |
| `..format.segmenter` | Token estimation + text segmentation |
| `src.utils.llm_adapter` | `LLMPoolAdapter`, `create_llm_client` — key-pool LLM factory |

## Testing

```bash
uv run pytest tests/ -k "translat" -v
```

Tests cover: terminology parsing, keyword merge/split, block marker round-trip, validation rules, contamination stripping, and language detection accuracy.
