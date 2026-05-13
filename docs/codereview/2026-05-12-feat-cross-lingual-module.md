# Code Review: feat/cross-lingual-module

- **Branch**: `feat/cross-lingual-module`
- **Date**: 2026-05-12
- **Reviewer**: AI Code Review
- **Scope**: `backend/src/core/cross_lingual_process_and_extract_evidence/` — contracts, format, translate, workflow; 24 files, +1747 lines

## Summary Decision

🔄 Request changes — 2 blocking issues, 5 important items

## Strengths

- 🎉 Clean architecture layering: `contracts` → `format` → `translate` → `workflow`, each testable independently
- 🎉 Bbox tracking with `SentenceRegion` (page/offset/span) preserves positional mapping for future UI
- 🎉 LangGraph `StateGraph` with conditional routing (`format` → `detect` → `translate|skip`) consistent with project agent patterns
- 🎉 `SecretStr` for API keys; `TranslationConfig` from pydantic-settings singleton
- 🎉 Integration tests mock `ChatOpenAI` with `side_effect` to simulate full 5-stage pipeline; both Chinese→English and English-skip paths covered
- 🎉 Biomedical-domain-aware prompts with explicit HGVS/gene-symbol/accession preservation rules

## Findings

### 🔴 [blocking] `should_skip_translation("")` returns `False` — empty docs go through 5 LLM calls

**File**: `translate/language_detector.py:42-45`

```python
def should_skip_translation(text: str) -> bool:
    sample = str(text or "").strip()
    if not sample:
        return False  # ❌ empty text → full LLM pipeline (5 calls on nothing)
```

Empty or whitespace-only text falls through to `terminology → structure → draft → polish → review`. For batch processing where some pages have no extractable text, this wastes significant API cost.

**Fix**: Return `True` (skip) for empty text:

```python
if not sample:
    return True
```

### 🔴 [blocking] Lingua `LanguageDetector` initialized twice — doubles memory (~80MB ×2)

**Files**: `translate/language_detector.py:8` + `translate/validator.py:9`

```python
# language_detector.py
_DETECTOR = LanguageDetectorBuilder.from_all_languages().build()

# validator.py (duplicate!)
_DETECTOR = LanguageDetectorBuilder.from_all_languages().build()
```

The all-languages model is non-trivial. `_CJK_RE` is also duplicated.

**Fix**: Import the module-level `_DETECTOR` and `_CJK_RE` from `language_detector` into `validator`, or extract both into a shared `translate/_detector.py`.

### 🟡 [important] `Translator.translate()` returns opaque 6-tuple

**File**: `translate/translator.py:145`

```python
def translate(self, formatted: FormattedDocument) -> tuple[str, str, str, str, list[str], list[str]]:
```

Violates project rule #22 (no bare dict/tuple return types). A 6-element tuple requires callers to remember positional order. Since this is only called by `translate_to_result()`, make it private (`_translate`) or use a lightweight dataclass.

### 🟡 [important] No retry/error handling for individual LLM stages

**File**: `translate/translator.py:108-115`

`translate_segments()` raises `RuntimeError` on any segment failure, losing all prior work. The old version had `node_translation_max_retries: int = 2`. Individual segment failures should be caught and reflected in warnings.

### 🟡 [important] CJK-unaware `max_chars` penalizes CJK documents

**File**: `format/segmenter.py:74`

```python
max_chars = effective_max * 4  # assumes 4 ASCII chars/token
```

CJK characters count as ~1 token each, so the char budget is 4× too small for CJK-heavy documents, causing over-segmentation. Since CJK documents are the primary translation target, this matters.

### 🟡 [important] `TerminologyMap` always empty in result

**File**: `translate/translator.py:193`

```python
terminology_map={},  # always empty — never parsed from LLM response
```

The terminology extraction LLM stage runs and feeds into draft/polish prompts, but the structured map is never parsed back. Either parse it or remove the field from `TranslationResult`.

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
uv run ruff check                              → 4 errors (all pre-existing, none in this module)
uv run pytest tests/core/cross_lingual.../ -q  → 41 passed in 12.31s
```
