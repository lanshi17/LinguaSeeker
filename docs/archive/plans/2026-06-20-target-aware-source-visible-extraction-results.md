# Target-Aware Source-Visible Extraction Results

**Status:** completed
**Created:** 2026-06-20
**Completed:** 2026-06-20

## Summary

The target-aware source-visible extractor completed a dev-to-test benchmark loop, but it should not be promoted as the current fused-75 optimum.

The dev split improved slightly over the prior dev checkpoint, mainly by increasing recall, but the frozen test checkpoint regressed below the existing `adjudicated-field-filter` benchmark baseline.

## Metrics

| Variant | Split | Coverage | Precision | Recall | Source-visible F1 |
|---|---|---:|---:|---:|---:|
| target-aware-source-visible | dev | 10/10 | 0.5238 | 0.5077 | 0.5156 |
| target-aware-source-visible | test | 10/10 | 0.4182 | 0.3433 | 0.3770 |
| adjudicated-field-filter | test | 10/10 | 0.5897 | 0.3433 | 0.4340 |

## Decision

Do not promote `target-aware-source-visible`.

The held-out test gate was:

```text
test source-visible F1 > 0.4340
```

The checkpoint result was:

```text
test source-visible F1 = 0.3770
```

Recall did not improve on test (`0.3433` vs `0.3433`), and precision regressed (`0.4182` vs `0.5897`). This indicates the target-aware field eligibility and neighbor expansion did not solve the test split's candidate-absent recall bottleneck and introduced additional false positives.

## Artifacts

- Dev config: `benchmark/optimization/fused75/target_aware_source_visible_dev_config.json`
- Test config: `benchmark/optimization/fused75/target_aware_source_visible_test_config.json`
- Dev report: `benchmark/optimization/fused75/reports/target_aware_source_visible_dev_full.json`
- Test checkpoint: `benchmark/optimization/fused75/reports/target_aware_source_visible_test_checkpoint.json`
- Test Phase 2 batch: `benchmark/optimization/fused75/reports/phase2_artifact_batch_20260620_173112.json`
- Leaderboard: `benchmark/optimization/fused75/reports/leaderboard_current.md`

## Next Direction

The next optimization should focus on candidate generation and source evidence recovery rather than broader field eligibility:

- recover missing target-specific evidence before catalog extraction,
- add stricter source-visible quote validation before final scoring artifacts,
- use dev-only error taxonomy to isolate candidate-absent cases,
- keep frozen test as checkpoint-only.
