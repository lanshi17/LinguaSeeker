# Dataset D Publication Profile Evaluation — Diagnostic Report

Generated: 2026-06-24T20:40 (updated with Phase 3 gate fix)

## 1. Evaluation Status

| Metric | Value |
|--------|-------|
| v3 entries completed | 13/73 |
| v3 entries failed/timeout | 3 |
| Profile | `dataset_d_publication` (20 fields) |
| Status | **IN PROGRESS** — slow due to LLM API rate limits |
| Average time per entry | ~8 minutes (236s–1811s) |
| Log | `/tmp/dataset_d_pub_eval_v3.log` |

## 2. Baseline Comparison

| System | P | R | F1 | n |
|--------|------|------|------|---|
| SYSTEM | 0.7751 | 0.4410 | 0.5622 | 73 |
| B7-expanded | 0.7044 | 0.5416 | 0.6124 | 73 |

## 3. 11-Entry Diagnostic (v1 cached data, confirmed by DB analysis)

### 3.1 Diagnostic Table

Database-level evidence for each completed entry from the v1 cached evaluation.
The `—` symbol means the field is **absent from the DB entirely** (never produced
by Phase 2 catalog extraction), not merely "not_found."

| Entry | Match Cat | Items | Found | Scored Found | Has Identity | A.gene_symbol | B.disease_dx | A.gene_dis_rel | A.var_hgvs_c | A.var_type | B.MOI | B.clin_pheno | B.sex | C.de_novo |
|-------|-----------|-------|-------|-------------|-------------|---------------|-------------|----------------|--------------|------------|-------|-------------|-------|-----------|
| rett_001 | 0 match | 36 | 7 | 0 | **NO** | — | not_found | — | — | — | — | not_found | — | — |
| rett_003 | FP only | 22 | 4 | 2 | **NO** | — | not_found | — | — | — | — | mixed | not_found | — |
| rett_004 | 2 TP | 159 | 6 | 3 | YES | found | — | not_found | found | — | found | not_found | — | — |
| rett_005 | FP only | 17 | 6 | 4 | **NO** | — | — | — | — | — | — | mixed | not_found | — |
| rett_006 | 4 TP | 8 | 8 | 6 | YES | found | found | found | found | found | found | — | — | — |
| rett_007 | FP only | 54 | 7 | 4 | **NO** | — | — | — | — | — | — | mixed | — | — |
| rett_008 | 4 TP | 162 | 11 | 7 | YES | found | found | found | found | — | found | not_found | found | found |
| rett_009 | FP only | 19 | 6 | 3 | **NO** | — | — | — | — | — | — | mixed | not_found | — |
| rett_011 | 4 TP | 162 | 10 | 5 | YES | found | found | found | found | — | not_found | not_found | not_found | found |
| rett_012 | FP only | 17 | 10 | 8 | **NO** | — | — | — | — | — | — | mixed | not_found | — |
| rett_013 | 0 match | 0 | 0 | 0 | **NO** | — | — | — | — | — | — | — | — | — |

Legend: `found` = extracted with status=FOUND; `not_found` = extracted but status=NOT_FOUND;
`mixed` = multiple rows, some found some not_found; `—` = field absent from DB entirely.

### 3.2 Source Document Analysis

All source documents contain the target gene and disease:

| Entry | MECP2 mentions | Rett mentions | Source lines | Identity in DB |
|-------|---------------|---------------|-------------|---------------|
| rett_001 | 85 | 23 | 1361 | NO |
| rett_005 | 27 | 10 | 110 | NO |
| rett_006 | 26 | 20 | 110 | YES |
| rett_007 | 21 | 15 | 215 | NO |
| rett_008 | 9 | 28 | 194 | YES |

**The zero-match source documents contain abundant target entity text.** The failure is
not a source-availability problem.

## 4. Root Cause Diagnosis

### 4.1 Primary Loss Point: Phase 2 Catalog Extraction Intermittent Failure

For zero-match and FP-only entries, **A.gene_symbol and B.disease_diagnosis are
absent from the database entirely** (`—`). They were never produced by Phase 2
catalog extraction. This is not a downstream filtering problem (target_guard,
role_routing) — those stages would leave items with status≠found, not remove
them entirely.

For nonzero-match entries (rett_004, 006, 008, 011), the same fields ARE present
with status=found. The source documents are similar in content and length.

**Diagnosis:** The catalog_extraction LLM call intermittently fails to produce
core identity fields. This is an extraction reliability problem, not a field
profile or gating problem.

### 4.2 B.clinical_phenotypes: ClinicalContextStage Adds Wrong Values

For entries where B.clinical_phenotypes appears (rett_003, 005, 007, 009, 012),
the ClinicalContextStage adds items, but the evaluator marks them as `wrong_value`.
The source-visible gate accepts the snippets (they ARE in the document), but the
extracted values don't match the ground truth format.

### 4.3 Phase 3 Entities Don't Count

Zero-match entries produce Phase 3 standardization entities (`gene_mention`,
`disease_mention`) that are NOT counted by the benchmark evaluator. The evaluator
only considers Phase 2 evidence items with matching `field_id`.

### 4.4 Infrastructure Only Partially Responsible

- LLM 429 rate limits add delays but don't cause extraction failure
- Pipeline timeouts (rett_018) are infrastructure-only
- The extraction failures occur even when the pipeline completes successfully

## 5. Answers to Diagnostic Questions

### Q1: Is the profile propagated correctly?
**Yes.** The content hash fix ensures v3 entries use the correct profile. The
v1 cached entries used the general pipeline (all 143 fields), which also fails
for the same entries — so the profile is not the cause.

### Q2: Are 0-match entries producing no evidence items, or producing values the evaluator rejects?
**Both patterns exist:**
- rett_013: 0 items total (complete pipeline failure)
- rett_001: 36 items, but NO scored fields in FOUND status (Phase 2 didn't produce them)
- rett_003/005/007/009/012: ClinicalContextStage produces B.clinical_phenotypes that the evaluator rejects as wrong_value

### Q3: Is clinical_context adding items that later disappear?
**No.** ClinicalContextStage items persist through the pipeline. They are present
in the DB. The evaluator rejects them because the values don't match ground truth.

### Q4: Does source grounding/target guard remove candidates disproportionately?
**No.** The absence of A.gene_symbol/B.disease_diagnosis in zero-match entries
is at the Phase 2 level — these fields are never produced. Target_guard would
leave them with a different status, not remove them entirely.

### Q5: Are 0-match entries missing because source documents lack target spans?
**No.** All source documents contain abundant MECP2 and Rett syndrome text.
rett_001 has 85 MECP2 mentions and still produces no A.gene_symbol.

### Q6: Are failed entries due to infrastructure only?
**No.** Infrastructure failures (429, timeout) account for 3 failed entries.
The zero-match entries (rett_001, 005, 007, etc.) completed successfully but
with no scored field extraction. This is an extraction reliability issue.

## 6. Key Finding

**The loss point is Phase 2 catalog_extraction LLM reliability**, not field
profile restriction or downstream gating. The same pipeline produces good results
for some entries (rett_006: 8/8 found) and zero results for others (rett_001:
0/13 scored found), despite similar source document content.

The ClinicalContextStage adds B.clinical_phenotypes items but with values that
don't match ground truth — this is a value-format mismatch, not a presence
problem.

## 7. Recommended Next Steps

**Do NOT add another extraction stage.** The problem is extraction reliability,
not extraction coverage. Recommended approaches (in priority order):

1. **Retry-on-empty (IMPLEMENTED):** After normal catalog extraction, if
   A.gene_symbol or B.disease_diagnosis is missing, run one focused retry
   with a compact 4-field prompt (A.gene_symbol, B.disease_diagnosis,
   A.variant_hgvs_c, A.variant_hgvs_p). Uses target-rich blocks.
   Merge semantics: don't overwrite higher-confidence existing FOUND items.
   See `stages/catalog_extraction.py` `_maybe_retry_core_identity`.

2. **Structured output JSON repair:** Check if the LLM sometimes returns
   valid JSON that the parser rejects. The `invoke_structured` fallback to
   JSON text mode may be losing data.

3. **Catalog group decomposition:** Split the high_signal group (62 fields)
   into smaller sub-groups (e.g., A-identity: 5 fields, B-phenotype: 10 fields,
   D-E-J: remaining). Run each sub-group as a separate LLM call. This reduces
   per-call field count and may improve reliability.

4. **Post-extraction identity recovery:** After catalog_extraction, if
   A.gene_symbol is missing but gene_mention exists in Phase 3 output,
   recover the gene symbol from the standardization entity.

## 8. Commands

Run evaluation:
```bash
PYTHONPATH=. uv run --project backend python -m benchmark.layer3.evaluate \
  --base-url http://localhost:8000 \
  --ground-truth-root benchmark/data/ground_truth/merged_73 \
  --no-preprocessed \
  --api-key <key> \
  --extraction-profile dataset_d_publication \
  --concurrency 1
```

Monitor progress:
```bash
tail -f /tmp/dataset_d_pub_eval_v3.log
```

## 9. Post-Retry Targeted Validation (rett_001, rett_005)

### 9.1 Setup

- Server restarted with retry code loaded (confirmed via `core_identity_retry` log messages)
- Redis + PostgreSQL processing cache cleared for rett_001 and rett_005
- Eval command: `--entries rett_001 rett_005 --no-preprocessed --extraction-profile dataset_d_publication --concurrency 1`

### 9.2 Retry Triggered Correctly

Server log confirms:
```
20:24:56 core_identity_retry: missing B.disease_diagnosis, running focused extraction
20:25:06 core_identity_retry: rescued B.disease_diagnosis
```

The retry correctly:
1. Detected B.disease_diagnosis was missing after normal extraction
2. Ran the focused 4-field prompt
3. Rescued B.disease_diagnosis

### 9.3 Results Still 0/8 for rett_001

Despite the retry rescuing B.disease_diagnosis at the Phase 2 level, the benchmark still reports 0 matched fields. **Root cause: Phase 3 gene-variant coexistence gate.**

Phase 3 `_find_gene_variant_complete_groups()` (repositories.py:1272) requires BOTH `A.gene_symbol` AND at least one variant (`A.variant_hgvs_c` or `A.variant_hgvs_p`) in FOUND status within the same `group_id`. When no group satisfies this condition, ALL track payload items are silently dropped from the database.

For rett_001:
- Normal extraction found A.gene_symbol but NOT A.variant_hgvs_c/p (variant extraction failed)
- Retry rescued B.disease_diagnosis (correct)
- But no group has both gene + variant → coexistence gate drops everything
- Only Phase 3 fallback entities (gene_mention, disease_mention) survive

DB state for post-retry run `cd1baa16`:
```
B.clinical_phenotypes: not_found
disease_mention: found x2    (Phase 3 fallback)
gene_mention: found x2       (Phase 3 fallback)
variant_mention: not_found   (Phase 3 fallback)
```

### 9.4 Diagnosis

| Layer | Status | Notes |
|-------|--------|-------|
| Phase 2 catalog_extraction | Partial | A.gene_symbol found, B.disease_diagnosis rescued by retry, variant NOT found |
| Phase 2 retry | **Working** | Correctly triggers and rescues B.disease_diagnosis |
| Phase 3 coexistence gate | **Blocking** | Drops all items when no group has gene+variant |
| Benchmark evaluator | Correct | Only sees DB items, which are Phase 3 fallbacks |

### 9.5 Conclusion

The core identity retry works correctly at the Phase 2 level. However, the **Phase 3 gene-variant coexistence gate** is the actual bottleneck for 0-match entries. The gate drops ALL track payload items when no evidence group has both `A.gene_symbol` AND a variant in FOUND status.

**The retry fix alone will NOT rescue these entries.** The coexistence gate is the dominant failure mode.

### 9.6 Recommended Next Steps

1. **Extend retry trigger:** Also trigger retry when `A.gene_symbol` is found but no variant is found in the same group. The retry prompt already asks for variant fields — the issue is that the retry only fires for missing gene/disease, not for missing variants.

2. **Relax coexistence gate for identity fields:** Allow `A.gene_symbol` and `B.disease_diagnosis` to persist even without a co-located variant. These are independently valuable identity fields.

3. **Catalog group decomposition:** Split the high_signal group into smaller focused groups (identity, variant, phenotype) to improve variant extraction reliability.

**Full 73-entry evaluation should NOT be started** until the coexistence gate issue is addressed, as the retry alone cannot improve results.

---

## 10. Phase 3 Coexistence Gate Fix

### 10.1 Root Cause

The gene-variant coexistence gate (`repositories.py:1272`) was all-or-nothing: if no evidence group had both `A.gene_symbol` AND a variant (`A.variant_hgvs_c`/`A.variant_hgvs_p`) in FOUND status, ALL track payload items were silently dropped. This meant that even when Phase 2 correctly extracted gene and disease (via the core identity retry), Phase 3 discarded them because no variant was co-located.

### 10.2 Fix: Field-Aware Two-Tier Gate

The gate is now field-aware with two tiers:

1. **Full gate** (unchanged): groups with both gene and variant in FOUND status accept ALL fields.
2. **Identity gate** (new): groups anchored by `A.gene_symbol` or `B.disease_diagnosis` in FOUND status accept identity fields even without variant co-location.

**Identity fields** that survive independently:
- `A.gene_symbol`, `A.variant_hgvs_c`, `A.variant_hgvs_p`
- `B.disease_diagnosis`, `B.clinical_phenotypes`, `B.sex`, `B.age_of_onset`, `B.mode_of_inheritance_reported`
- `C.inheritance_source`, `C.de_novo_status`

**Anchor fields** (make a group passable): only `A.gene_symbol` and `B.disease_diagnosis`. Variant-only groups without gene or disease remain blocked.

**Variant-dependent fields** (still require full gate): functional evidence, segregation, pathogenicity, allele frequency, etc.

### 10.3 Implementation

- `_GATE_IDENTITY_FIELDS`: frozenset of 10 identity field IDs
- `_GATE_ANCHOR_FIELDS`: frozenset of 2 anchor field IDs (`A.gene_symbol`, `B.disease_diagnosis`)
- `_find_identity_passable_groups()`: new static method returning groups with anchor fields in FOUND status
- `_build_run_item_specs()`: two-tier gate — full gate first, identity gate as fallback for non-full-gate groups

### 10.4 Tests

- 43 repository tests pass (6 new tests added)
- Key new tests:
  - `test_identity_fields_survive_gene_only_group`: gene+disease without variant → 2 identity fields persist
  - `test_variant_only_group_still_blocked`: variant without gene/disease → still blocked
  - `test_variant_dependent_fields_blocked_in_identity_only_group`: non-identity fields blocked in identity-only group
  - `test_rett_001_scenario_gene_disease_no_variant`: full rett_001 reproduction → 5 identity fields survive
  - `test_find_identity_passable_groups`: groups with gene or disease are passable
  - `test_find_identity_passable_groups_returns_empty_for_no_anchors`: groups without gene or disease are not passable

### 10.5 Status

Targeted validation for `rett_001` pending — requires server restart and cache clearing.
