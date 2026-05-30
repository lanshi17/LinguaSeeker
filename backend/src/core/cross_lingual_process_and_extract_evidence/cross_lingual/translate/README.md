# Translate Module

> Phase 2 submodule — 3-stage LLM-based biomedical translation pipeline: terminology extraction → block-level translation → validation, with CJK→English as the primary direction and 9 languages supported.

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
│   ├─ get_terminology_prompt()  → LLM
│   ├─ _clean_terminology()  → strip artifacts, normalize pairs
│   └─ _parse_terminology()  → Dict[str, str] with CJK validation
│
├─ Stage 2: translate_segments()
│   ├─ [blocks mode] _translate_blocks()  → one LLM call per document
│   │   ├─ merge_short_keywords()  → prevent context pollution
│   │   ├─ join_blocks_with_markers()  → [BLOCK_N] markers
│   │   └─ split_by_markers()  → recover per-block translations
│   └─ [segment mode] _translate_one_segment()  → per-segment with retry
│       ├─ JSON-mode (attempt 1) + fallback
│       └─ validate_segment()  → CJK contamination check
│
├─ Stage 3: Normalize + Validate
│   ├─ _self_review()  → LLM quality check
│   ├─ strip_source_contamination()  → remove residual CJK
│   ├─ fix_ocr_truncations(), fix_email_placeholder()
│   └─ trim_repetitive_content()  → LLM repetition loop guard
│
├─ Post-processing
│   ├─ build_translated_blocks()  → pair original ↔ translated
│   ├─ deduplicate_bilingual_blocks()  → remove identical pairs
│   └─ check_block_language()  → partial failure detection
│
└─ translate_to_result()  → TranslationResult with full metadata
```

## Public API

### `MultiStageTranslator`

```python
class MultiStageTranslator(BaseTranslator):
    def __init__(self, ctx: TranslationConfigContext)
    def extract_terminology(self, formatted: FormattedDocument) -> str
    def translate_segments(self, formatted, terminology, blocks=None) -> Tuple[str, List[str], List[str]]
    def run_pipeline(self, formatted, blocks=None) -> Tuple[Dict, str, str, str, List[str], List[str], List[str]]
    def translate_to_result(self, formatted, blocks=None) -> TranslationResult
```

### Key Functions

| Function | Description |
|----------|-------------|
| `detect_language(text)` | Heuristic language detection (>50% CJK = zh/ja/ko) |
| `create_llm(model, api_key, base_url, temperature)` | LangChain LLM factory |
| `create_json_llm(...)` | JSON-mode LLM factory |
| `invoke_with_retry(llm, prompt, stage, system)` | LLM call with 3 retries |
| `merge_short_keywords(blocks)` | Merge adjacent CJK keywords to prevent context pollution |
| `split_merged_keywords(parts, map)` | Split merged keywords back after translation |
| `join_blocks_with_markers(blocks)` | Join text blocks with `[BLOCK_N]` markers |
| `split_by_markers(text, n)` | Split LLM output on block markers |
| `normalize_cjk_punctuation(text)` | Convert CJK punctuation (。、→.,) |
| `normalize_placeholders(text)` | Preserve `[REDACTED]` and image refs |
| `strip_prompt_artifacts(text)` | Remove echoed prompt instructions |
| `strip_source_contamination(text, lang)` | Remove residual source-language text |
| `validate_segment(source, translated)` | Check for untranslated CJK content |
| `validate_translation_output(source, translated)` | Full output validation |

### Prompts

| Module | Purpose |
|--------|---------|
| `prompts/translate.py` | Main translation prompt with terminology injection |
| `prompts/terminology.py` | Terminology extraction prompt |
| `prompts/format.py` | LLM formatting prompt (redaction detection) |

## Internal Design

### Block-level translation (primary path)

When `blocks` are provided, the translator switches to **block-level mode** — each non-empty text/title block is translated individually for guaranteed alignment:

1. `merge_short_keywords()` merges adjacent 1-4 char CJK keywords (e.g., "古菌" + "硫化叶菌" → "古菌；硫化叶菌") to prevent the LLM from filling them with nearby content
2. `join_blocks_with_markers()` wraps each block in `[BLOCK_N]` and strips `【摘要】`/`【关键词】` prefixes
3. A single LLM call translates the entire document at once
4. `split_by_markers()` splits the output back into per-block translations
5. `split_merged_keywords()` expands merged keywords back to individual translations

### Terminology management

The terminology pipeline runs before translation:

1. LLM extracts bilingual term pairs (e.g., "乳腺癌: breast cancer")
2. `_clean_terminology()` strips LLM echo artifacts (markdown headers, bullet points, notes)
3. `_parse_terminology()` validates: CJK sources require non-ASCII, deduplicates by target, caps at 100 entries
4. Validated pairs are injected into the translation prompt

### Contamination stripping

Post-translation, `strip_source_contamination()` detects residual source-language characters using the source language hint. CJK languages: any remaining CJK chars are checked. Latin-script sources: proportion-based threshold.

### Repetition loop detection

The `_LLM_REPETITION_LOOP` guard catches infinite repetition: if translated output exceeds source × 5 and has suspicious heading uniqueness ratio, it trims to the first occurrence of repeated content.

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
    def run_pipeline(self, formatted):
        # Call external NMT API
        ...
        return terms, "", "", translated, segments, warnings
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
- Terminology extraction: 1-N LLM calls depending on document length
- Self-review: 1 additional LLM call
- Token budgets: `_INPUT_BUDGET = 16,000` tokens, terminology truncated at 40% of available budget
- `_MAX_SEGMENT_RETRIES = 3` per segment for per-segment mode
- JSON mode (attempt 1) reduces prompt echo but adds ~200ms overhead

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `langchain_core` | LLM abstraction (messages, invocation) |
| `loguru` | Structured logging |
| `re` | Block markers, CJK detection, artifact stripping |
| `json` | JSON-mode LLM output parsing |
| Parent contracts (`...contracts`) | FormattedDocument, TranslationResult, ContentBlock |
| `..format.segmenter` | Token estimation + text segmentation |

## Testing

```bash
uv run pytest tests/ -k "translat" -v
```

Tests cover: terminology parsing, keyword merge/split, block marker round-trip, validation rules, contamination stripping, and language detection accuracy.
