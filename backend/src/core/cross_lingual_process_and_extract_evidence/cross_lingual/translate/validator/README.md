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
| `validate_segment` | `(source, translated) -> None` | Per-segment quality check. Similar thresholds. |
| `validate_image_references_preserved` | `(source, translated) -> None` | Check image refs (`![](...)`) preserved in translation. |
| `summarize_validation_error` | `(exc) -> str` | Extract concise error summary from validation exception. |

### `normalize.py` — Text Normalization

| Function | Signature | Description |
|----------|-----------|-------------|
| `normalize_cjk_punctuation` | `(text) -> str` | CJK → ASCII punctuation (full-width spaces, Chinese commas, etc.) |
| `normalize_placeholders` | `(text) -> str` | Remove empty OCR placeholders: `[ ]`, `(year)`, `[month]`, etc. |
| `fix_email_placeholder` | `(text) -> str` | Fix email-like placeholders from OCR |
| `fix_ocr_truncations` | `(text) -> str` | Repair common OCR truncation patterns |
| `fix_word_boundary_redacted` | `(text) -> str` | Fix `[REDACTED]` markers split by word boundaries |

### `artifacts.py` — Artifact Stripping

| Function | Signature | Description |
|----------|-----------|-------------|
| `strip_prompt_echo` | `(text) -> str` | Remove prompt headers echoed by LLM (SYSTEM PROMPT, CRITICAL RULES, etc.) |
| `strip_inline_artifacts` | `(text) -> str` | Remove inline artifacts (`[SYSTEM INSTRUCTIONS...]`, `«BLK»`, etc.) |
| `strip_prompt_artifacts` | `(text) -> str` | Full artifact stripping pass (echo + inline) |
| `strip_source_contamination` | `(text, lang) -> str` | Remove source-language characters leaked into translation |

### `redacted.py` — OCR Redaction

| Function | Signature | Description |
|----------|-----------|-------------|
| `mark_redacted_values` | `(text) -> str` | Insert `[REDACTED]` markers for missing OCR values. Two-pass: structural artifacts (empty brackets) + CJK-gap safety net. |

## Internal Design

### Validation Thresholds

| Check | Threshold | Error Code |
|-------|-----------|------------|
| Empty output | `len(translated) == 0` | `empty` |
| Prompt echo | First 200 chars contain prompt markers | `prompt_echo_only` |
| CJK ratio | >10% CJK characters | `non_english_output` |
| Similarity | ≥85% SequenceMatcher ratio | `unchanged` |
| Language detection | `lingua` detects non-English | `non_english_output` |

### CJK Punctuation Map

18 CJK punctuation characters mapped to ASCII equivalents (full-width space, Chinese comma/period/semicolon/colon, brackets, quotation marks).

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `lingua` | Language detection for output validation |
| `loguru` | Artifact stripping logging |

## Testing

```bash
cd backend
uv run pytest tests/core/cross_lingual_process_and_extract_evidence/ -v -k validator
```
