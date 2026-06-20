# Fused-75 F1 Optimization Results

**Status:** completed
**Created:** 2026-06-19
**Completed:** 2026-06-20
**PR:** pending

## Decision

Do not promote a production Phase 2 pipeline change from this optimization round.

The dev-selected `adjudicated-field-filter` variant improves source-visible F1 over the current contextual-reconcile artifact baseline on the 10-entry dev split, but the held-out 10-entry test checkpoint is lower and the variant is a benchmark-side scoring hygiene filter, not a production extraction algorithm change.

## Results

| Variant | Split | Coverage | Precision | Recall | Source-Visible F1 | Decision |
|---|---|---:|---:|---:|---:|---|
| contextual-reconcile-baseline | dev | 10/10 | 0.3182 | 0.4308 | 0.3660 | baseline |
| adjudicated-field-filter | dev | 10/10 | 0.6364 | 0.4308 | 0.5138 | dev winner |
| adjudicated-field-filter | test | 10/10 | 0.5897 | 0.3433 | 0.4340 | checkpoint only |

The selected variant keeps recall unchanged on dev and improves precision by excluding fields that were not part of the adjudicated source-visible label set. This removes unsupported field false positives during evaluation, but it does not teach the live extractor to produce better evidence.

## Evidence

- Dev baseline report: `benchmark/optimization/fused75/reports/contextual_reconcile_dev_full.json`
- Dev selected variant report: `benchmark/optimization/fused75/reports/adjudicated_field_filter_dev_full.json`
- Frozen test checkpoint report: `benchmark/optimization/fused75/reports/adjudicated_field_filter_test_checkpoint.json`
- Current leaderboard: `benchmark/optimization/fused75/reports/leaderboard_current.md`
- Test artifact batch report: `benchmark/optimization/fused75/reports/phase2_artifact_batch_20260620_133134.json`

## Reproduction Commands

```bash
cd backend
PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.run_variant \
  --split test \
  --config ../benchmark/optimization/fused75/adjudicated_field_filter_test_config.json \
  --adjudication-root ../benchmark/optimization/fused75/adjudication \
  --fused-ground-truth-root ../benchmark/data/ground_truth/clinvar_fused \
  --output ../benchmark/optimization/fused75/reports/adjudicated_field_filter_test_checkpoint.json \
  --checkpoint

PYTHONPATH=.. uv run python -m benchmark.optimization.fused75.build_leaderboard \
  --reports-dir ../benchmark/optimization/fused75/reports \
  --json-output ../benchmark/optimization/fused75/reports/leaderboard_current.json \
  --markdown-output ../benchmark/optimization/fused75/reports/leaderboard_current.md
```

## Follow-Up

The next optimization round should target production extraction behavior, not benchmark-only field filtering. The current error taxonomy points to unsupported predictions and candidate absence as the main dev errors, so a useful next variant would add extraction-time field eligibility constraints or target-aware candidate generation, then re-run dev before any new test checkpoint.
