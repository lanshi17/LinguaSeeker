# Cross-Lingual Core

> The translation engine brain: document formatting with bbox tracking, token-budgeted segmentation, multi-stage LLM translation with validation/fallback, and language detection routing. All domain logic; no orchestration.

This package contains the two feature sub-packages that `TranslationService` (the orchestrator in the parent module) delegates to:

```
cross_lingual/
├── format/          # Markdown normalization, sentence splitting, token budgeting
└── translate/       # Language detection, multi-stage LLM translation, validation
```

## Quick Start

```python
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.format.formatter import MarkdownFormatter
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator import MultiStageTranslator
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.language_detector import detect_language
from src.core.cross_lingual_process_and_extract_evidence.config_context import TranslationConfigContext

# 1. Format
formatter = MarkdownFormatter()
formatted = formatter.format(pages)  # pages: List[{"page_number": N, "markdown": "..."}]

# 2. Detect
lang = detect_language(formatted.formatted_markdown)  # "zh", "ja", "en", ...

# 3. Translate (only if lang != "en")
ctx = TranslationConfigContext(model="qwen2.5:14b", api_key="...", base_url="http://...")
translator = MultiStageTranslator(ctx=ctx)
result = translator.translate_to_result(formatted)
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          cross_lingual/                                  │
│                                                                          │
│  ┌───────────────────────┐   ┌────────────────────────────────────────┐ │
│  │       format/          │   │              translate/                │ │
│  │                        │   │                                        │ │
│  │  BaseFormatter (ABC)   │   │  BaseTranslator (ABC)                  │ │
│  │       ▲                │   │       ▲                                │ │
│  │       │                │   │       │                                │ │
│  │  MarkdownFormatter     │   │  MultiStageTranslator                  │ │
│  │                        │   │                                        │ │
│  │  segment_text()        │   │  providers.py    — LLM client + retry  │ │
│  │  estimate_tokens()     │   │  blocks.py       — block operations   │ │
│  │  extract_sentences()   │   │  postprocess.py  — dedup, quality     │ │
│  │  build_page_offset_map │   │  exceptions.py   — TranslationError   │ │
│  │                        │   │  prompts/        — stage prompts       │ │
│  │                        │   │  validator/      — validation + norms  │ │
│  └───────────────────────┘   └────────────────────────────────────────┘ │
│                                                                          │
│  Input: pages (List[Dict])    Input: FormattedDocument                   │
│  Output: FormattedDocument    Output: TranslationResult                  │
└──────────────────────────────────────────────────────────────────────────┘
```

**Data flow:**

1. `pages` (from MinerU parse) → `format/` → `FormattedDocument` (normalized markdown + sentence bbox)
2. `FormattedDocument` → `translate/` → `TranslationResult` (English markdown + terminology + segments)

Each sub-package has an abstract base class (`BaseFormatter`, `BaseTranslator`) defining the Clean Architecture boundary. Concrete implementations (`MarkdownFormatter`, `MultiStageTranslator`) are swappable for testing or alternative strategies.

---

## `format/` — Document Formatting

### Public API

#### `MarkdownFormatter`

```python
class MarkdownFormatter(BaseFormatter):
    def format(self, pages: List[Dict[str, Any]]) -> FormattedDocument: ...
```

The sole public method. Consumes upstream parse pages, produces a normalized `FormattedDocument`.

#### Module-level functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `build_page_offset_map` | `(pages: List[Dict]) -> Dict[int, int]` | Character offset → page number mapping |
| `extract_sentences` | `(text: str, page_offset_map: Optional[Dict]) -> List[SentenceRegion]` | Sentence split with bbox tracking |
| `segment_text` | `(text: str, max_tokens=8192, prompt_overhead_tokens=0) -> List[str]` | Token-budgeted chunking for LLM context windows |
| `estimate_tokens` | `(text: str) -> int` | Rough token count: ASCII chars ÷ 4 + CJK chars |

### Internal Design

#### Formatting Pipeline

`MarkdownFormatter.format()` delegates to `_format_markdown()` which runs three phases:

1. **Join & clean**: Concatenates per-page markdown with `\n\n` separators. Runs `_normalize_whitespace()` (collapses ≥3 blank lines, strips trailing spaces) and `_fix_markdown_headings()` (ensures `#` has a space after it).
`_format_markdown()` also accepts an optional `raw_markdown` parameter that bypasses the per-page join when the caller already has concatenated text.

2. **Bbox tracking**: `build_page_offset_map()` builds a dict where each key is the starting character offset of a page in the concatenated text, and the value is that page number. The +2 padding accounts for the `\n\n` joiner between pages. Example: a 3-page doc with markdown lengths 500, 300, 200 → `{0: 1, 502: 2, 804: 3}`.

3. **Sentence splitting**: `extract_sentences()` uses a pre-compiled `re.compile(r"(?<=[。！？.!?])\s*")` with `finditer` to split on CJK and Western sentence-ending punctuation. Each sentence gets its `start_offset`/`end_offset` in the full text, and `_resolve_page()` maps those offsets to page numbers via the offset map. The final segment after the last delimiter is captured separately.
`FormattedDocument.source_language` defaults to `""` when created by the formatter; the orchestrator sets it via `detect_language()` after formatting.

#### Token-Budgeted Segmentation

`segment_text()` is designed for LLM context window management:

- **Token estimator**: ASCII characters count as 0.25 tokens (4 chars/token), CJK characters count as 1 token each. The CJK ratio is computed from the actual text and used to blend the chars-per-token value:
  ```
  chars_per_token = 4.0 - cjk_ratio * 2.8
  ```
  CJK-heavy text gets ~1.2 chars/token; pure ASCII gets ~4 chars/token.

- **Segmentation strategy** (in order of precedence):
  1. **Paragraph boundaries**: splits on `\n\s*\n`, groups consecutive paragraphs that fit within budget
  2. **Sentence boundaries**: within an oversized paragraph, splits on CJK/Western punctuation
  3. **Hard split**: a single sentence that exceeds budget is chunked at `max_chars`

- `prompt_overhead_tokens` is subtracted from `max_tokens` before any calculation, so the segments always fit within the actual LLM context window.

---

## `translate/` — Multi-Stage Translation

### Public API

#### `MultiStageTranslator`

```python
class MultiStageTranslator(BaseTranslator):
    def __init__(self, ctx: TranslationConfigContext) -> None: ...
    def run_pipeline(self, formatted: FormattedDocument, blocks: List[ContentBlock] | None = None) -> Tuple[
        Dict[str, str], str, str, str, List[str], List[str], List[str]
    ]: ...
    def translate_to_result(self, formatted: FormattedDocument) -> TranslationResult: ...

    # Individual stages (callable independently for testing/debugging)
    def extract_terminology(self, formatted: FormattedDocument) -> str: ...
    def translate_segments(
        self, formatted: FormattedDocument, terminology: str, blocks: List[ContentBlock] | None = None,
    ) -> Tuple[str, List[str], List[str]]: ...
```

`run_pipeline()` returns a 7-tuple: `(terminology_map, structure_plan, "", translated, source_segments, translated_parts, warnings)`. `translate_to_result()` wraps this into the standard `TranslationResult` dataclass with per-segment bbox mapping.

#### Module-level functions

| Function | Module | Signature | Description |
|----------|--------|-----------|-------------|
| `detect_language` | `language_detector` | `(text: str, sample_size=4000) -> str` | ISO 639-1 code via `lingua` library |
| `validate_translation_output` | `validator` | `(source: str, translated: str) -> None` | Raises `ValueError` with `translation_validation_failed:` prefix |
| `validate_segment` | `validator` | `(source: str, translated: str) -> None` | Per-segment validation |
| `build_translated_blocks` | `postprocess` | `(original_blocks, segments, translated_text, ...) -> List[ContentBlock]` | Map translated text back to block structure |
| `deduplicate_bilingual_blocks` | `postprocess` | `(blocks: List[ContentBlock]) -> List[ContentBlock]` | Remove adjacent near-duplicate blocks |
| `check_block_language` | `postprocess` | `(blocks: List[ContentBlock], source_language: str) -> None` | Detect partial translation failures |
| `invoke_with_retry` | `providers` | `(llm, prompt, stage, system_prompt) -> str` | LLM text generation with retry |
| `invoke_json_with_retry` | `providers` | `(llm, prompt, stage, system_prompt) -> str` | LLM JSON-mode generation with retry |

#### Prompt functions (`prompts/`)

| Function | Module | Signature | Purpose |
|----------|--------|-----------|---------|
| `get_terminology_prompt` | `terminology` | `(markdown_content: str) -> str` | Extract bilingual term pairs |
| `get_system_prompt_generation_prompt` | `terminology` | `(source_language: str) -> str` | Generate system prompt for translation |
| `get_translate_prompt` | `translate` | `(segment, terminology, ...) -> str` | Translate one segment |
| `get_full_document_translate_prompt` | `translate` | `(markdown, terminology, ...) -> str` | Full-document translation |
| `get_self_review_prompt` | `translate` | `(source, translated) -> str` | Quality check and correction |
| `get_format_prompt` | `format` | `(markdown_content: str) -> str` | Clean/normalize markdown |

### Internal Design

#### Module Structure

```
translate/
├── __init__.py          # Re-exports public API
├── base.py              # BaseTranslator ABC
├── language_detector.py # Language detection via lingua
├── providers.py         # LLM client factory + retry logic
├── blocks.py            # Block merge/split/marker operations
├── postprocess.py       # Dedup, quality flagging, language check, block building
├── exceptions.py        # TranslationError
├── prompts/             # Stage-specific prompt templates
│   ├── __init__.py
│   ├── format.py        # Formatting/normalization prompts
│   ├── terminology.py   # Terminology extraction prompts
│   └── translate.py     # Translation + self-review prompts
├── validator/           # Validation and post-processing
│   ├── __init__.py
│   ├── core.py          # Validation functions
│   ├── normalize.py     # Text normalization (punctuation, placeholders, OCR fix)
│   ├── artifacts.py     # Prompt artifact stripping
│   └── redacted.py      # Redacted value marking
└── translator.py        # MultiStageTranslator orchestration
```

#### Translation Pipeline

`run_pipeline()` executes three stages sequentially:

```
terminology → translate → self-review → normalize → validate
```

1. **Terminology** (`extract_terminology`): LLM extracts bilingual term pairs. Output parsed by `_parse_terminology()`:
   - Lines must match `source: target` format
   - Both sides ≤10 words (filters out commentary lines)
   - Source side must contain non-ASCII for CJK/Cyrillic; Latin-script languages (es/pt) accept ASCII terms
   - Source ≈ target echo (same word) is filtered
   - Result: `Dict[str, str]` injected into all subsequent prompts

2. **Translate** (`translate_segments`): Block-aware translation. When MinerU blocks are available, each text/title/DOI-footer block is translated individually for guaranteed block-level alignment. Otherwise, the markdown is segmented via `segment_text()` and translated segment-by-segment. Short CJK keyword blocks (≤4 chars) are merged before translation to prevent hallucination, then split back afterward.

3. **Self-review** (`_self_review`): LLM compares source vs translated, catches silent corrections of product names, gene identifiers, and other proper nouns.

4. **Normalize**: Post-processing pipeline applied to the translated text:
   - Strip prompt artifacts and inline artifacts
   - Strip source-language contamination
   - Normalize CJK punctuation, placeholders, email addresses
   - Fix OCR truncations and word-boundary `[REDACTED]` insertions
   - Detect and trim LLM repetition loops

5. **Validate** (`validate_translation_output`): Critical check. Four checks:
   | Check | Failure condition | Message |
   |-------|-------------------|---------|
   | Emptiness | `translated` is empty string | `translation_validation_failed: empty` |
   | CJK ratio | >10% CJK characters in output | `translation_validation_failed: non_english_output` |
   | Similarity | ≥85% similarity with source (unchanged) | `translation_validation_failed: unchanged` |
   | Language detection | `lingua` detects non-English | `translation_validation_failed: non_english_output` |

   Critical failures (unchanged, non_english_output, empty) raise `TranslationError` — the pipeline aborts rather than persisting garbage. Non-critical warnings are collected and returned.

#### Retry Strategy

LLM retry logic lives in `providers.py` (module-level functions):

| Function | Purpose |
|----------|---------|
| `invoke_with_retry(llm, prompt, stage, system_prompt)` | Text generation with retry |
| `invoke_json_with_retry(llm, prompt, stage, system_prompt)` | JSON-mode generation with retry |

Both retry up to `_MAX_RETRIES` (3) on transient exceptions (timeout, connection, rate limit, server error). Non-transient exceptions propagate immediately.

#### Post-Processing (`postprocess.py`)

After translation, `translate_to_result()` builds the final `TranslationResult`:

1. **Block building** (`build_translated_blocks`): Maps translated text back to original block structure using delimiter-based split or segment matching
2. **Bilingual dedup** (`deduplicate_bilingual_blocks`): Removes adjacent near-duplicate blocks from bilingual documents (e.g. zh with English abstract)
3. **Per-block language check** (`check_block_language`): Catches partial translation failures where only some blocks were translated (e.g. ru doc where only first page was translated)
4. **Quality flagging** (`flag_quality_issues`): Flags blocks with truncated references, ambiguous pronouns, or medical English issues

#### Language Detection

`detect_language()` uses `lingua-language-detector` (`≥2.2.0`) with a 4000-character sample. The module-level `_DETECTOR` singleton is built once with `LanguageDetectorBuilder.from_all_languages().build()` and reused across all calls.

---

## Extension Guide

### Adding a new formatter strategy

1. Implement `BaseFormatter`:
   ```python
   class MyFormatter(BaseFormatter):
       def format(self, pages: List[Dict[str, Any]]) -> FormattedDocument:
           # Must produce formatted_markdown + sentences with bbox tracking
           ...
   ```
2. Required output contract: `FormattedDocument` must have `formatted_markdown` (the normalized text) and `sentences` (List[SentenceRegion] with page/offset tracking). If bbox tracking is not applicable, use `page=0, start_offset=0, end_offset=len(text)` for each sentence.

### Adding a new translation strategy

1. Implement `BaseTranslator`:
   ```python
   class MyTranslator(BaseTranslator):
       def run_pipeline(self, formatted: FormattedDocument) -> Tuple[...]: ...
       def translate_to_result(self, formatted: FormattedDocument) -> TranslationResult: ...
   ```
2. `run_pipeline()` returns `(terminology_map, structure_plan, "", translated, source_segments, translated_parts, warnings)`.
3. `translate_to_result()` wraps this into `TranslationResult` with per-segment bbox mapping.
4. The orchestrator (`TranslationService`) injects the translator; change it there.

### Adding a new prompt stage

1. Add the prompt function to the appropriate module in `prompts/`:
   ```python
   def get_my_stage_prompt(context: str) -> str:
       return f"MY_STAGE\n...\n\nCONTEXT:\n{context}"
   ```
2. Add the stage method to `MultiStageTranslator`:
   ```python
   def my_stage(self, context: str) -> str:
       return invoke_with_retry(self._llm, get_my_stage_prompt(context), "my_stage")
   ```
3. Wire into `run_pipeline()`.

### Common pitfalls

- **Don't call LLM methods directly** — always use `invoke_with_retry()` from `providers.py` to get transient failure handling.
- **Don't mutate `FormattedDocument` or `TranslationResult`** — they're plain dataclasses, but treat them as immutable outputs.
- **Don't change the `run_pipeline()` return tuple** without updating `translate_to_result()` and all callers.
- **Token estimation is approximate.** If tight context windows matter, use an actual tokenizer rather than the heuristic `estimate_tokens()`.
- **Bbox containment matching is fuzzy.** It uses substring containment (`text in segment` or `segment in text`), not a real alignment algorithm. Overlapping or duplicated sentences may produce wrong bbox mappings.

## Performance Notes

- **`estimate_tokens()`** is O(n) over the text with per-character inspection. For a 50KB document, this is ~50K operations (~1ms). The result is not cached, but each call typically processes a different segment.
- **`segment_text()`** worst case: a single 50KB paragraph with no sentence boundaries → one hard-split chunk. Best case: many small paragraphs that all fit within budget → single segment.
- **LLM calls are the bottleneck.** Each stage is a synchronous network round-trip. A 5-page CJK document makes LLM calls for terminology extraction, per-block/segment translation, and self-review — expect 10-30 seconds total.
- **Draft segments are serial**, not parallel. This is intentional: parallel drafts would lose context at segment boundaries, requiring an additional merge stage. If latency becomes critical, consider segment-level batching with an explicit merge pass.

## Dependencies

| Dependency | Version | Used In | Purpose |
|------------|---------|---------|---------|
| `langchain-core` | ≥1.4.0 | `translate/` | `HumanMessage` abstraction |
| `langchain-openai` | ≥1.2.1 | `translate/` | `ChatOpenAI` LLM client |
| `openai` | (transitive) | `translate/` | LLM API (exception types for retry) |
| `httpx` | (transitive) | `translate/` | HTTP transport (exception types for retry) |
| `lingua-language-detector` | ≥2.2.0 | `translate/` | Language detection |
| `loguru` | ≥0.7.0 | both | Structured logging |

`format/` has no external dependencies beyond the standard library and `loguru`. All heavy lifting in `format/` is pure Python string/regex operations.

## Testing

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v -k "formatter or segmenter or translator or validator or language_detector or prompts"
```

| Test file | Target | Key coverage |
|-----------|--------|-------------|
| `test_formatter.py` | `format/formatter.py` | Offset map construction, sentence extraction with page resolution, whitespace normalization, heading fix |
| `test_segmenter.py` | `format/segmenter.py` | Token estimation (ASCII, CJK, mixed), paragraph splitting, sentence splitting, hard chunk splitting, budget enforcement |
| `test_translator.py` | `translate/translator.py` | LLM init, `_to_text` content extraction, `_parse_terminology` parsing/validation, retry logic (success, transient→success, non-transient→fail) |
| `test_language_detector.py` | `translate/language_detector.py` | Language detection for zh/ja/en/ru, CJK fast-path, empty text, skip logic |
| `test_validator.py` | `translate/validator.py` | Empty check, CJK ratio check, similarity check, language check, error summarization |
| `test_prompts.py` | `translate/prompts.py` | All 5 prompt templates contain expected stage markers and input placeholders |

LLM-dependent tests use `unittest.mock.patch` on `ChatOpenAI.invoke` — no real API calls.
