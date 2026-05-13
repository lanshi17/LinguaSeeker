# Code Review: feat/cross-lingual-module

- **Branch**: `feat/cross-lingual-module`
- **Date**: 2026-05-12
- **Reviewer**: AI Code Review
- **Scope**: `backend/src/core/cross_lingual_process_and_extract_evidence/` — contracts, format, translate, workflow; 24 files, +1747 lines

## Summary Decision

✅ All blocking and important issues resolved — 2 blocking, 3 important fixed; 2 important deferred

## Strengths

- 🎉 Clean architecture layering: `contracts` → `format` → `translate` → `workflow`, each testable independently
- 🎉 Bbox tracking with `SentenceRegion` (page/offset/span) preserves positional mapping for future UI
- 🎉 LangGraph `StateGraph` with conditional routing (`format` → `detect` → `translate|skip`) consistent with project agent patterns
- 🎉 `SecretStr` for API keys; `TranslationConfig` from pydantic-settings singleton
- 🎉 Integration tests mock `ChatOpenAI` with `side_effect` to simulate full 5-stage pipeline; both Chinese→English and English-skip paths covered
- 🎉 Biomedical-domain-aware prompts with explicit HGVS/gene-symbol/accession preservation rules

## Findings

### ~~🔴 [blocking] `should_skip_translation("")` returns `False`~~ ✅ Fixed

**File**: `translate/language_detector.py:42-45`

```python
if not sample:
    return True  # ✅ fixed
```

### ~~🔴 [blocking] Lingua `LanguageDetector` initialized twice~~ ✅ Fixed

**Files**: `translate/language_detector.py:8` + `translate/validator.py:9`

Validator now imports `_DETECTOR` and `_CJK_RE` from `language_detector`. ~80MB saved.

### ~~🟡 [important] `Translator.translate()` returns opaque 6-tuple~~ ✅ Fixed

**File**: `translate/translator.py:145`

Renamed to `_translate()` (private). ABC updated. First element now `Dict[str, str]` (terminology_map).

### ~~🟡 [important] No retry/error handling for individual LLM stages~~ ✅ Fixed

**File**: `translate/translator.py:108-115`

Added `_invoke_with_retry(max_retries=2)` used by all LLM stages. Per-segment failures retry before raising.

### ~~🟡 [important] CJK-unaware `max_chars` penalizes CJK documents~~ ✅ Fixed

**File**: `format/segmenter.py:74`

Now uses blended `chars_per_token` (4.0 for ASCII → 1.2 for CJK-heavy) based on actual content composition.

### ~~🟡 [important] `TerminologyMap` always empty in result~~ ✅ Fixed

**File**: `translate/translator.py:193`

Added `_parse_terminology()` to parse `source:target` lines into `Dict[str, str]`. Map now populated in result.

### 🟡 [important] Test coverage gaps

Missing tests: `_resolve_page` with empty map, `_normalize_whitespace`/`_fix_markdown_headings` edge cases, `_split_paragraph` hard-split path, `_to_text` with top-level dict content, empty document through full workflow (would catch blocking issue #1), `extract_sentences` with CJK-only punctuation.

### 🟢 [nit] Sentence boundary regex misses CJK commas/semicolons

`(?<=[。！？.!?])\s*` doesn't handle `，`、`；`. Acceptable for biomedical text.

### 🟢 [nit] `FormattedDocument.from_pages()` dead code path

Creates document without sentence extraction — actual extraction happens in `format_markdown()`.

### 🟢 [nit] Empty `__init__.py` in `format/` and `translate/`

Consider adding re-exports for public API surface.

### 🟢 [nit] `_resolve_page` O(pages) per sentence

Fine in practice (~microseconds); `bisect` would be O(log N).

## Security

- [x] No hardcoded secrets — `SecretStr` + config
- [x] No SQL/XSS risk — no database or HTML output in this module
- [x] Prompt injection: accepted risk (translation inherently requires full source text in prompt)

## Verification

```
uv run ruff check                              → All checks passed
uv run pytest tests/core/cross_lingual.../ -v  → 44 passed in 0.64s
```

### Remaining (deferred)

- **I5**: Test coverage gaps — edge cases for helpers and empty-doc workflow
- **Nits**: sentence boundary regex, dead `from_pages()`, empty `__init__.py`, `_resolve_page` O(n)
