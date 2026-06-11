# Code Review: ClinGen Batch Regression Extraction Quality

**Branch:** `feat/clingen-batch-regression-extraction-quality`
**Date:** 2026-06-10
**Reviewer:** (pending)
**Author:** AI Agent + [redacted-user]

## Summary

Improves ClinGen layer-3 batch regression reliability by normalizing harmless text differences, reducing missing gene extraction, and tightening relationship/precision behavior.

**8 commits, 13 files changed, +516 / -98 lines**

## Review Focus Areas

The reviewer should pay special attention to:

### 1. Benchmark normalization safety
`benchmark/layer3/evaluate.py` — `normalize_comparison_text()` applies NFKC normalization, dash/quote translation, and whitespace collapse before comparison. The raw `FieldMatch.extracted_value` is preserved unchanged so reports still show original text.

**Question:** Does this normalization hide meaningful biomedical differences? (e.g., distinguishing en-dash from hyphen in gene/disease names)

### 2. Gene symbol phrase cleanup conservatism
`backend/src/core/.../extract_evidence/core.py` — `_normalize_gene_symbol()` only extracts the token immediately before `related`, `mutation`, or `associated`. It rejects common placeholder/English words (unknown, none, patient, gene, etc.) to `NOT_FOUND`. All-lowercase tokens without an uppercase letter are preserved as-is.

**Question:** Is the placeholder list complete enough? Are there gene-like tokens that should NOT be rejected?

### 3. Relationship synonym mapping safety
`backend/src/core/.../extract_evidence/core.py` — `_normalize_enum()` applies negation/hedging checks BEFORE substring/keyword matching for `A.gene_disease_relationship`. The negation regex covers `non-causal`, `non-causative`, `not causal`, `not causative`, `not a causal`, `not a causative`. Hedging checks catch `preliminary association` and `only a preliminary`.

**Question:** Can the regex accidentally upgrade weak evidence? Are there negation patterns not covered?

### 4. Over-extraction precision accounting
`benchmark/layer3/evaluate.py` — `FieldMatch.extra_found_values` tracks extracted values that don't match any expected value. These are counted as false positives in precision calculations and exposed in `overall`, `by_field`, `by_classification`, and `by_moi` metrics.

**Question:** Does the deduplication logic in `compare_evidence()` correctly handle expected duplicates?

## Files Changed

| File | Change |
|------|--------|
| `benchmark/__init__.py` | Package marker with docstring |
| `benchmark/layer3/__init__.py` | Package marker with docstring |
| `benchmark/layer3/evaluate.py` | Text normalization, over-extraction metrics |
| `backend/pyproject.toml` | Added `pythonpath = [".."]` for benchmark tests |
| `backend/src/.../prompts.py` | Rule 17 (gene symbol), strengthened rule 18 (relationship) |
| `backend/src/.../core.py` | Gene symbol normalization, relationship negation/hedging |
| `backend/tests/benchmark/layer3/test_evaluate_matching.py` | 5 benchmark tests |
| `backend/tests/.../test_prompts.py` | 2 prompt tests |
| `backend/tests/.../test_normalizer.py` | 14 normalizer tests |
| `progress.txt` | Progress update |

## Test Results

```
63 passed in 0.52s
```

- 5 benchmark matching tests
- 16 prompt tests
- 20 normalizer tests
- 22 value normalization tests (pre-existing)

## Commits

```
3569633f fix: expand negation regex to cover non-causative and not a causative
cf12cd32 docs: record clingen regression quality work
89779295 feat: expose benchmark over extraction metrics
ee846c64 fix: tighten gene disease relationship extraction
e61c2849 fix: reject placeholder values in gene symbol normalization
e22ed466 fix: normalize extracted gene symbol phrases
96294147 fix: clarify gene symbol extraction prompt
bf48d498 test: cover clingen benchmark text normalization
```
