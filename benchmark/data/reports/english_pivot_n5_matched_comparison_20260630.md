# English-pivot N=5 Matched Comparison

Sample IDs: gs_005, gs_071, gs_075, gs_076, gs_083 (seed=20260630).

| Condition | failed | Value P | Value R | Value F1 | Grounded F1 | Original-grounded F1 | DB-ready | ΔF1 vs C2-hard |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| c0_prompt_only | 0 | 0.9048 | 0.6552 | 0.7600 | 0.7308 | 0.0000 | 19 | +0.1078 |
| c1_catalog | 0 | 0.9286 | 0.4333 | 0.5909 | 0.5778 | 0.0000 | 13 | -0.0613 |
| c2_hard_full_broad | 0 | 0.9375 | 0.5000 | 0.6522 | 0.6383 | 0.0000 | 15 | +0.0000 |
| a1_no_reflection | 0 | 0.7895 | 0.5556 | 0.6522 | 0.6000 | 0.0000 | 15 | +0.0000 |
| a2_no_review | 0 | 0.8182 | 0.6667 | 0.7347 | 0.6792 | 0.0000 | 18 | +0.0825 |
| a3_no_target_guard | 0 | 0.8000 | 0.5926 | 0.6809 | 0.6275 | 0.0000 | 16 | +0.0287 |
| a4_original_only | 0 | 0.7895 | 0.5556 | 0.6522 | 0.6000 | 0.0000 | 15 | +0.0000 |
| c2_tristate_review | 0 | 0.9375 | 0.5000 | 0.6522 | 0.6383 | 0.0000 | 15 | +0.0000 |
| c2_english_pivot_hard | 3 | 0.8000 | 0.1333 | 0.2286 | 0.2222 | 0.0000 | 4 | -0.4236 |
| c2_english_pivot_tristate | 0 | 0.9375 | 0.5000 | 0.6522 | 0.6383 | 0.4762 | 10 | +0.0000 |

## Per-entry Hits

| Condition | gs_005 | gs_071 | gs_075 | gs_076 | gs_083 |
|---|---:|---:|---:|---:|---:|
| c0_prompt_only | 3/3 | 3/6 | 7/8 | 1/8 | 5/6 |
| c1_catalog | 2/3 | 3/6 | 2/8 | 1/8 | 5/6 |
| c2_hard_full_broad | 2/3 | 4/6 | 6/8 | 1/8 | 2/6 |
| a1_no_reflection | 2/3 | 3/6 | 6/8 | 1/8 | 3/6 |
| a2_no_review | 2/3 | 3/6 | 6/8 | 3/8 | 4/6 |
| a3_no_target_guard | 2/3 | 4/6 | 6/8 | 1/8 | 3/6 |
| a4_original_only | 2/3 | 5/6 | 3/8 | 1/8 | 4/6 |
| c2_tristate_review | 2/3 | 3/6 | 6/8 | 1/8 | 3/6 |
| c2_english_pivot_hard | 2/3 | 2/6 | 0/8 failed | 0/8 failed | 0/6 failed |
| c2_english_pivot_tristate | 2/3 | 4/6 | 3/8 | 1/8 | 5/6 |

## Excluded Reports

- c0_prompt_only_n5_20260630_130327: sample set differs from matched random N=5 or report predates identity traceback fix (gs_003, gs_015, gs_048, gs_115, gs_147)
- c2_soft_veto_n5_20260630_131800: sample set differs from matched random N=5 or report predates identity traceback fix (gs_002, gs_003, gs_004, gs_005, gs_007)
- hard_veto_disable_review_guard_n5_20260630_132847: sample set differs from matched random N=5 or report predates identity traceback fix (gs_003, gs_015, gs_048, gs_115, gs_147)
- english_pivot_tristate_prefix_20260630_150431: sample set differs from matched random N=5 or report predates identity traceback fix (gs_005, gs_071, gs_075, gs_076, gs_083)

## Direction Judgment

- English-pivot + tri-state does not improve value-F1 on this matched N=5 subset: it ties C2-hard at 0.6522 and remains below C0 prompt-only (0.7600) and A2 no-review (0.7347).
- The useful gain is provenance, not value extraction: English-pivot + tri-state is the only comparable condition with nonzero original-grounded-F1 (0.4762) and explicit original span traceback.
- Dual-track + tri-state also ties C2-hard on value-F1 and grounded-F1, so tri-state alone does not explain a quality gain on this subset.
- English-pivot + hard review is not viable in the current implementation: 3/5 entries failed with missing `phase_2/extraction_result.json`, and value-F1 drops to 0.2286.
- Current direction is therefore not ready to replace C0/A2 for extraction accuracy. The promising path is narrower: keep English-pivot + tri-state as a DB-ready/provenance-oriented mode, then fix recall and the hard-review artifact-write failure before any N=50 rerun.
