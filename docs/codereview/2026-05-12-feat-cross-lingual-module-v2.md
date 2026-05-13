# Code Review: feat/cross-lingual-module-v2

- **Branch**: `feat/cross-lingual-module-v2`
- **Date**: 2026-05-12
- **Reviewer**: AI Code Review
- **Scope**: `backend/src/core/cross_lingual_process_and_extract_evidence/` — contracts, config_context, format, translate, router, middleware, workflow; 29 files, +1848 lines
- **Previous review**: v1 (`feat/cross-lingual-module`) — all blocking issues resolved

## Summary Decision

✅ All issues resolved — 3 important fixes + 4 nits addressed. 58/58 tests pass.

## v1 Review Resolution

All issues from the v1 review (`2026-05-12-feat-cross-lingual-module.md`) have been addressed:

| v1 Issue | Status | How |
|----------|--------|-----|
| 🔴 B1: `should_skip_translation("")` → `False` | ✅ Fixed | `return True` at L43 |
| 🔴 B2: Lingua model loaded twice | ✅ Fixed | `validator.py` imports `_CJK_RE`, `_DETECTOR` from `language_detector` |
| 🟡 I1: Opaque 6-tuple return | ✅ Fixed | Renamed to `_translate()`, `BaseTranslator` ABC enforces contract |
| 🟡 I2: No LLM retry | ✅ Fixed | `_invoke_with_retry()` with `_MAX_RETRIES = 2` |
| 🟡 I3: CJK-unaware max_chars | ✅ Fixed | `chars_per_token = 4.0 - cjk_ratio * 2.8` (adaptive) |
| 🟡 I4: `terminology_map={}` always empty | ✅ Fixed | `_parse_terminology()` parses `"source: target"` lines |
| 🟡 I5: Test coverage gaps | ✅ Improved | +5 tests: `PipelineState`, `LanguageRouter`, config, formatter, translator |
| 🟢 N1-N5: Various nits | Partially | `PipelineState` typed (not bare dict), `extract_sentences` rewritten with `finditer` |

## Strengths

- 🎉 **All v1 blocking issues resolved** — zero blockers remain
- 🎉 **ABC hierarchy**: `BaseFormatter` + `BaseTranslator` enable swappable implementations for testing
- 🎉 **`TranslationConfigContext`**: Clean config injection boundary; modules no longer reach into raw `cfg` objects
- 🎉 **`PipelineState` as Pydantic BaseModel**: Replaces bare `Dict[str, Any]` with typed fields; catches missing required fields at construction
- 🎉 **`LanguageRouter`**: Single-responsibility routing extracted from orchestrator
- 🎉 **`traced_node` middleware**: LangSmith tracing + loguru logging via decorator — consistent observability across all nodes
- 🎉 **`_invoke_with_retry`**: Proper retry with logging, configurable `_MAX_RETRIES`
- 🎉 **`extract_sentences` rewrite**: Uses `finditer` for offset tracking — more robust than v1's `text.find()` approach
- 🎉 **`MultiStageTranslator` builds LLM once**: `ChatOpenAI` constructed in `__init__` (not on every call)

## Findings

### ~~🟡 [important] `_invoke_with_retry` retries ALL exceptions indiscriminately~~ ✅ Fixed

**File**: `translate/translator.py:67-75`

Now catches only transient exceptions:
```python
_TRANSIENT_EXCEPTIONS = (
    openai.APITimeoutError, openai.APIConnectionError,
    openai.RateLimitError, openai.InternalServerError,
    httpx.TimeoutException, httpx.ConnectError,
)
```

### ~~🟡 [important] `_parse_terminology` regex too lenient~~ ✅ Fixed

**File**: `translate/translator.py:78-86`

Added validation: both sides must be ≤10 words, source side must contain non-ASCII (non-English). English sentences with colons are now skipped.

### ~~🟡 [important] Tests missing for new v2 code~~ ✅ Fixed

+14 tests added:

| Coverage | Tests |
|---|---|
| `_parse_terminology` | 5 tests: valid, skips ASCII-only, skips long, empty, blank lines |
| `_invoke_with_retry` | 3 tests: success, transient retry, non-transient no retry |
| `LanguageRouter.route()` | 4 tests: English, Chinese, empty, no formatted |
| `TranslationConfigContext.from_config()` | 2 tests: normal, default temperature |

### ~~🟢 [nit] `BaseTranslator._translate` — abstract method with private naming convention~~ ✅ Fixed

**File**: `translate/base.py:19`

Renamed to `run_pipeline` — public ABC method with public naming.

### ~~🟢 [nit] `format_markdown` top-level function is public but only used by `MarkdownFormatter`~~ ✅ Fixed

**File**: `format/formatter.py:97`

Renamed to `_format_markdown` — private helper, `MarkdownFormatter` is the public API.

### ~~🟢 [nit] `LanguageRouter.route()` checks `state.needs_translation` redundantly~~ ✅ Fixed

**File**: `router.py:17-19`

Simplified to only check `should_skip_translation(text)`.

### 🟢 [nit] No ABC for segmenter — inconsistency with `BaseFormatter`/`BaseTranslator`

Formatter and translator have ABCs; segmenter remains a collection of bare functions. If the ABC pattern is the project convention, segmenter should follow. If stateless functions are acceptable, formatter could also drop its ABC (since there's only one implementation).

### ~~🟢 [nit] `_node_format` and `_node_detect_language` both call `detect_language`~~ ✅ Fixed

Removed duplicate `detect_language` call from `_node_format`. Language detection now only happens in `_node_detect_language`.

### 💡 [suggestion] `_translate` return tuple could still benefit from a dataclass

**File**: `translate/translator.py:144`

```python
def _translate(self, formatted) -> Tuple[str, Dict[str, str], str, str, List[str], List[str]]:
```

Even though it's private, a 6-element tuple is fragile. A `_TranslationPipelineResult` dataclass would make `translate_to_result()` more readable. But since it's private, this is low priority.

## Security

- [x] No hardcoded secrets — `SecretStr` + `TranslationConfigContext`
- [x] No SQL/XSS — no database or HTML output
- [x] Prompt injection: accepted risk (full source text in LLM prompt is inherent)

## Verification

```
pytest tests/core/cross_lingual.../ -v  → 58 passed in 0.59s
ruff check                              → All checks passed
```

## Architecture Assessment

The v2 architecture is substantially improved over v1:

```
v1:  workflow.py ← Translator ← functions
     (LangGraph, bare dicts, raw cfg leak)

v2:  workflow.py → LanguageRouter  → language_detector
     (orchestrator)  MarkdownFormatter → format_markdown
                     MultiStageTranslator → prompts, validator
                     (ABCs, typed PipelineState, ConfigContext, middleware)
```

- **Dependency direction**: All inward toward contracts — good
- **Abstraction level**: ABCs for swappable strategies — appropriate for the domain
- **Singletons**: `_DETECTOR`, `_CJK_RE` shared across modules — good
- **LangGraph usage**: Typed `StateGraph(PipelineState)` replaces bare dict — good
