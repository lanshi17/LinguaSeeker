# Translate Validator

> Validation, normalization, and artifact stripping for the translation pipeline. Ensures translated output meets quality thresholds before persistence.

## Quick Start

```python
from ..validator import validate_translation_output, normalize_cjk_punctuation, strip_source_contamination

# Validate full-document translation
validate_translation_output(source_text, translated_text)
# Raises ValueError("translation_validation_failed: ...") on failure

# Normalize stray CJK punctuation
clean = normalize_cjk_punctuation("患者携带变异，建议筛查。")

# Strip source-language contamination from translation
clean = strip_source_contamination(translated_text, source_language="zh")
```

## Architecture

```
validator/
├── core.py        # Validation logic: validate_translation_output, validate_segment
├── normalize.py   # Text normalization: CJK punctuation, placeholders, OCR fixes
├── artifacts.py   # LLM artifact stripping: prompt echo, inline artifacts, source contamination
└── redacted.py    # OCR redaction marking: mark_redacted_values
```

## Public API

### `core.py` — Validation

| Function | Signature | Description |
|----------|-----------|-------------|
| `validate_translation_output` | `(source, translated) -> None` | Full-document quality check. Raises on: empty, prompt echo, >10% CJK, ≥85% similarity to source, non-English detected language. |
| `validate_segment` | `(source, translated) -> None` | Per-segment quality check: empty, >15% CJK, >=90% similarity (skipped for English-only source), repetition loop detection (>3x source size with duplicate headings). |
| `validate_image_references_preserved` | `(source, translated) -> None` | Check image refs (`![](...)`) preserved in translation. |
| `summarize_validation_error` | `(exc) -> str` | Extract concise error summary from validation exception. |

### `normalize.py` — Text Normalization

| Function | Signature | Description |
|----------|-----------|-------------|
| `normalize_cjk_punctuation` | `(text) -> str` | CJK → ASCII punctuation (18 characters: full-width space, Chinese comma/period/semicolon/colon, brackets, quotation marks, enumeration comma) |
| `normalize_placeholders` | `(text) -> str` | Remove empty OCR placeholders: `[ ]`, `(year)`, `[month]`, `[day]`, `[age]`, `[imaging]`, `blank`, `[blank]`, 年月日, `year month day`, `()`. Also cleans orphan prepositions and leading punctuation. |
| `fix_email_placeholder` | `(text) -> str` | Fix `Email: :` -> `Email: [unavailable]`, trailing orphan `, :` removal |
| `fix_ocr_truncations` | `(text) -> str` | Repair OCR truncations: `galactosidase ( , )` -> `α-galactosidase A (α-Gal A)`, `-linked` -> `X-linked`, trailing commas in parens |
| `fix_word_boundary_redacted` | `(text) -> str` | Fix `[REDACTED]` inserted mid-word (e.g., `Re[REDACTED]ferences`), inside names (e.g., `Takayuki [REDACTED]okia`), or adjacent to section headings |
| `normalize_keywords_capitalization` | `(text) -> str` | Normalize keyword list to sentence case (lowercase common terms, preserve abbreviations and proper nouns) |

### `artifacts.py` — Artifact Stripping

| Function | Signature | Description |
|----------|-----------|-------------|
| `strip_prompt_echo` | `(text) -> str` | Find the last prompt marker (`[SYSTEM INSTRUCTIONS`, `[TERMINOLOGY]`, `[TRANSLATE THIS SEGMENT]`, etc.) and return only content after it. Handles full prompt echo where the LLM reproduces the entire prompt before translating. |
| `strip_inline_artifacts` | `(text) -> str` | Remove inline artifacts within paragraphs: `[SYSTEM INSTRUCTIONS...]`, `[IMPORTANT:...]`, `[TRANSLATION]`, `«BLK»` |
| `strip_prompt_artifacts` | `(text) -> str` | Strip paragraphs whose first line matches artifact patterns (SYSTEM PROMPT, CRITICAL RULES, TERMINOLOGY MAP, stage headers, etc.). Stops at first artifact paragraph. |
| `strip_source_contamination` | `(text, lang) -> str` | Two-pass source-language removal: Pass 1 strips leading CJK paragraphs (>10% CJK ratio); Pass 2 strips trailing source paragraphs (>40% CJK after 200+ chars of English). Safety: preserves original if result <100 chars. |
| `_is_terminology_echo` | `(text) -> bool` | Detect when LLM echoed back 3+ consecutive `source: target` pairs instead of translating |

### `redacted.py` — OCR Redaction

| Function | Signature | Description |
|----------|-----------|-------------|
| `mark_redacted_values` | `(text) -> str` | Insert `[REDACTED]` markers for missing OCR values. Two-pass: structural artifacts (empty brackets) + CJK-gap safety net. |

## Internal Design

### Full-document Validation Thresholds (`validate_translation_output`)

| Check | Threshold | Error Code |
|-------|-----------|------------|
| Empty output | `len(translated) == 0` | `empty` |
| Prompt echo | First 200 chars contain prompt markers | `prompt_echo_only` |
| CJK ratio | >10% CJK characters | `non_english_output` |
| Similarity | ≥85% SequenceMatcher ratio (skipped for <100 char source) | `unchanged` |
| Language detection | `lingua` detects non-English | `non_english_output` |

### Per-segment Validation Thresholds (`validate_segment`)

| Check | Threshold | Error Code |
|-------|-----------|------------|
| Empty output | `len(translated) == 0` | `empty` |
| CJK ratio | >15% CJK characters (more lenient than full-doc) | `source_language_content` |
| Similarity | ≥90% SequenceMatcher (skipped for English-only source, <5% CJK) | `unchanged` |
| Repetition | Translated >3x source with duplicate headings | `repetition_loop` |

### CJK Punctuation Map

18 CJK punctuation characters mapped to ASCII equivalents: full-width space (U+3000), Chinese comma (U+FF0C), period (U+3002), semicolon (U+FF1B), colon (U+FF1A), parens (U+FF08/FF09), question mark (U+FF1F), exclamation (U+FF01), double quotes (U+201C/201D), single quotes (U+2018/2019), lenticular brackets (U+3010/3011), angle brackets (U+300A/300B), enumeration comma (U+3001).

### Placeholder Normalization Patterns

`normalize_placeholders` removes: `[ ]`, `(year)`, `(month)`, `(day)`, `[year]`, `[month]`, `[day]`, `[age]`, `[imaging]`, `blank`, `[blank]`, 年月日, `year month day`, `()`. Also cleans orphan prepositions left after removal.

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `lingua` | Language detection for output validation (`LanguageDetectorBuilder`, `Language`) |
| `difflib` | `SequenceMatcher` for similarity checks in validation |
| `loguru` | Artifact stripping and contamination logging |
| `re` | CJK detection, punctuation normalization, placeholder patterns, artifact patterns |

## Testing

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v -k validator
```
