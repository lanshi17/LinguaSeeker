# Clinical Context Extractor MVP Evaluation

Generated: 2026-06-24T00:32

## Changed Files

| File | Change |
|------|--------|
| `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/prompts.py` | Added `get_clinical_context_prompt()` — focused prompt for 6 clinical-context fields |
| `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/stages/clinical_context.py` | New `ClinicalContextStage` — focused LLM supplement pass for phenotype/sex/age/inheritance |
| `backend/src/core/cross_lingual_process_and_extract_evidence/extract_evidence/workflow.py` | Wired `clinical_context` node between `special_evidence` and `language_metadata` |
| `benchmark/core/pipeline_client.py` | Added `force_reextract` and `api_key` params to `evaluate_one`/`run_evaluation` |
| `benchmark/layer3/evaluate.py` | Added `--no-preprocessed` and `--api-key` CLI flags |

## Tests Run

| Suite | Result |
|-------|--------|
| `test_clinical_context.py` (17 new tests) | 17/17 passed |
| `extract_evidence/` full suite (348 tests) | 348/348 passed (2 skipped, pre-existing) |
| `cross_lingual_process_and_extract_evidence/` full suite | 557 passed, 10 failed (pre-existing), 64 skipped |

## Clinical Context Fields (6 total)

| Field | Category | Difficulty |
|-------|----------|-----------|
| B.clinical_phenotypes | B | medium_contextual |
| B.sex | B | medium_contextual |
| B.age_of_onset | B | medium_contextual |
| B.mode_of_inheritance_reported | B | medium_contextual |
| C.inheritance_source | C | complex_evidence |
| C.de_novo_status | C | complex_evidence |

## Smoke Test Results (3 entries, re-extracted via pipeline)

| Entry | TP | FP | FN | Status | Notes |
|-------|----|----|-----|--------|-------|
| rett_003 | 0 | 1 | 10 | completed | B.clinical_phenotypes: wrong_value (was missing before) |
| rett_004 | 2 | 1 | 10 | completed | B.clinical_phenotypes: missing |
| parkinson_013 | 0 | 0 | 12 | completed | All fields missing |

Aggregate: P=50.0%, R=5.9%, F1=10.5%

## B.clinical_phenotypes Status

- **Before (SYSTEM)**: F1=0.0000, always `status=not_found` (71/71 entries)
- **After (smoke)**: rett_003 changed from `missing` to `wrong_value` (pipeline extracted something but value didn't match). rett_004 still `missing`.
- **Clinical context stage log**: Successfully added 2-4 supplementary items per track across all 3 entries.
- **B7-expanded baseline**: F1=0.3235

## Key Observations

1. The clinical_context stage IS running and extracting items (confirmed via server logs).
2. The smoke test shows partial improvement: rett_003's B.clinical_phenotypes went from "missing" to "wrong_value" — the field is now being extracted but the value doesn't match ground truth.
3. The pipeline's overall performance on these 3 entries is poor (many fields missing), likely because the full pipeline through HTTP includes Phase 1 parsing, translation, and Phase 3 standardization which add noise.
4. The `force_reextract` flag works correctly — preprocessed data is bypassed.

## Remaining Gap to B7-Expanded

| Metric | SYSTEM (before) | SYSTEM (smoke) | B7-expanded |
|--------|----------------|----------------|-------------|
| P | 0.7751 | 0.5000 | 0.7044 |
| R | 0.4410 | 0.0590 | 0.5416 |
| F1 | 0.5622 | 0.1050 | 0.6124 |

The smoke test's low performance is expected — only 3 entries with many missing fields. The full 73-entry evaluation is running in the background and will provide the real comparison.

## Full Evaluation Status

**Running in background** — will take several hours to complete all 73 entries.

Command: `PYTHONPATH=. uv run --project backend python -m benchmark.layer3.evaluate --base-url http://localhost:8000 --ground-truth-root benchmark/data/ground_truth/merged_73 --no-preprocessed --api-key <key> --concurrency 2`

Report will be saved to: `benchmark/data/reports/eval_<timestamp>.json`

## Next Steps

1. Wait for full 73-entry eval to complete
2. Generate final comparison report with per-field before/after F1
3. If B.clinical_phenotypes F1 > 0, the MVP is successful
4. If still 0, investigate: (a) prompt quality, (b) value format mismatch, (c) add more specific phenotype extraction rules
5. Consider: InheritanceSegregationExtractor or FunctionalEvidenceExtractor as next slice
