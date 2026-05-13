# Code Review: feat/cross-lingual-module-v2 (Round 3)

- **Branch**: `feat/cross-lingual-module-v2`
- **Date**: 2026-05-12
- **Reviewer**: AI Code Review
- **Scope**: `backend/src/core/cross_lingual_process_and_extract_evidence/` — 29 files, +1848 lines
- **Previous rounds**: v1 (`feat/cross-lingual-module`) → v2 → v2-after-fixes (this review)

## Summary Decision

✅ Approve — all v1 blockers, v2 important items, and v2 nits resolved.

## v2 → v2-after-fixes Resolution

| # | v2 Issue | Status | How |
|---|----------|--------|-----|
| 🟡 I1 | `_invoke_with_retry` catches everything | ✅ Fixed | `_TRANSIENT_EXCEPTIONS` tuple: `openai.APITimeoutError`, `openai.APIConnectionError`, `openai.RateLimitError`, `openai.InternalServerError`, `httpx.TimeoutException`, `httpx.ConnectError` |
| 🟡 I2 | `_parse_terminology` regex too lenient | ✅ Fixed | Validates source ≤10 words, target ≤10 words, source contains non-ASCII |
| 🟡 I3 | Missing tests for new v2 code | ✅ Fixed | +4 tests: `LanguageRouter` (4 cases), `_parse_terminology` (5 cases), `_invoke_with_retry` (3 cases including transient+retry and non-transient+no-retry), `TranslationConfigContext.from_config()` (2 cases) |
| 🟢 N1 | `_translate` abstract method with `_` prefix | ✅ Fixed | Renamed to `run_pipeline()` |
| 🟢 N2 | `format_markdown` public but only used by formatter | ✅ Fixed | Renamed to `_format_markdown()` |
| 🟢 N3 | `route()` checked `needs_translation` redundantly | ✅ Fixed | Removed `needs_translation` check; simpler: `if should_skip_translation(text): return "skip_translate"` |
| 🟢 N4 | `_node_format` + `_node_detect_language` double language detection | ✅ Fixed | Removed `detect_language` call from `_node_format` |

## Strengths (cumulative)

- 🎉 **All 11 issues from v1 and v2 resolved** — zero findings remain
- 🎉 **`_TRANSIENT_EXCEPTIONS`** uses `openai.*` and `httpx.*` specific exceptions — only retries on genuine transient failures
- 🎉 **`_parse_terminology`** validates: ≤10 words per side, source must contain non-ASCII → robust against false positives
- 🎉 **`_invoke_with_retry` tests** cover: success, transient-then-success, non-transient-no-retry (`ValueError` passes through)
- 🎉 **`LanguageRouter` tests** cover: English, Chinese, empty, no-formatted — all 4 routing paths
- 🎉 **58 tests** (up from 41 in v1), 0 failures

## Verification

```
uv run pytest tests/core/cross_lingual.../ -v  → 58 passed in 0.58s
uv run ruff check                               → 3 errors (all pre-existing, none in this module)
```
