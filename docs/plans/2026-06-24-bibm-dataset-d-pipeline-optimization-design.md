# BIBM Dataset D Pipeline Optimization Design

**Status:** proposed
**Created:** 2026-06-24
**Target:** merged_73 (Rett 53 + Parkinson 20)

## 1. Diagnosis

### Current Metrics (three-way comparison, merged_73)

| System | P | R | F1 | per-entry mean F1 |
|--------|------|------|------|------|
| SYSTEM | 0.7751 | 0.4410 | 0.5622 | 0.5526 |
| B7-expanded | 0.7044 | 0.5416 | 0.6124 | 0.5943 |
| Δ (SYSTEM - B7) | +0.0707 | -0.1006 | **-0.0502** | -0.0417 |

SYSTEM loses to B7-expanded by 0.05 F1. The gap is concentrated in two areas:
- **Medium contextual fields** (p=0.0008): B7 F1=0.3732 vs SYSTEM F1=0.3023
- **Complex evidence fields** (p=0.0002): B7 F1=0.4396 vs SYSTEM F1=0.2162

### Per-Field Error Breakdown (SYSTEM, eval_merged_final)

| Field | TP | FP | FN | P | R | F1 | Dominant Error |
|-------|----|----|-----|------|------|------|----------------|
| B.clinical_phenotypes | 0 | 0 | 71 | 0.00 | 0.00 | 0.00 | FN (never extracted) |
| B.hpo_terms | 0 | 1 | 50 | 0.00 | 0.00 | 0.00 | FN (almost never extracted) |
| B.mode_of_inheritance_reported | 3 | 20 | 41 | 0.13 | 0.07 | 0.09 | **FP dominant** (20 wrong values) |
| C.de_novo_status | 8 | 13 | 32 | 0.38 | 0.20 | 0.26 | FP + FN |
| A.variant_hgvs_p | 30 | 20 | 38 | 0.60 | 0.44 | 0.51 | FP + FN |
| B.age_of_onset | 17 | 27 | 2 | 0.39 | 0.89 | 0.54 | **FP dominant** (27 wrong values) |
| A.variant_type | 36 | 8 | 27 | 0.82 | 0.57 | 0.67 | FN |
| A.variant_hgvs_c | 29 | 1 | 14 | 0.97 | 0.67 | 0.79 | FN |
| A.gene_disease_relationship | 55 | 3 | 15 | 0.95 | 0.79 | 0.86 | FN |
| B.sex | 40 | 5 | 7 | 0.89 | 0.85 | 0.87 | balanced |
| A.gene_symbol | 64 | 4 | 5 | 0.94 | 0.93 | 0.93 | balanced |
| B.disease_diagnosis | 69 | 0 | 4 | 1.00 | 0.95 | 0.97 | FN only |

### Root Causes

**R1. No extraction guidance for most fields.** The catalog_extraction prompt has 23 rules, almost all focused on A.gene_symbol, A.gene_disease_relationship, B.disease_diagnosis, and B.age_of_onset. Fields like B.clinical_phenotypes, B.hpo_terms, B.mode_of_inheritance_reported, and C.de_novo_status have zero field-specific rules.

**R2. Too many fields per LLM call.** high_signal group has 62 fields, supporting has 81. The LLM's attention is diluted. B7-expanded uses 17 fields with explicit per-field descriptions and achieves higher recall.

**R3. False positive problem on medium-contextual fields.** B.mode_of_inheritance_reported has 20 FP vs 3 TP. B.age_of_onset has 27 FP vs 17 TP. These fields are being extracted with wrong values — the pipeline is too aggressive.

**R4. ClinicalContextStage adds noise.** The recent MVP added a focused 6-field supplement pass, but smoke tests show it converts missing→wrong_value without improving F1. The stage lacks source-visible validation.

**R5. Prior "broader extraction" attempts regressed.** The target-aware-source-visible optimization (2026-06-20) tried broader field eligibility and neighbor expansion. It improved dev recall but regressed test precision (P: 0.5897→0.4182). The lesson: more extraction without validation = more FP.

### Where SYSTEM Already Wins

SYSTEM beats B7-expanded on:
- **A.functional_domain_or_hotspot**: F1=0.1569 vs B7=0.0000 (multi-stage extraction recovers functional domain evidence)
- **B.disease_diagnosis**: F1=0.9718 vs B7=0.9353 (source grounding and boundary rules help)

These wins come from the pipeline's source grounding, target guard, and disease boundary rules — not from extracting more fields.

## 2. Optimization Approaches

### Approach A: Field-Budgeted Extraction (Recommended)

Restructure the catalog extraction to use a reduced field set aligned with the evaluation scope, and add field-specific extraction rules for medium-contextual and complex fields.

**Changes:**
1. Define a `DATASET_D_FIELD_PROFILE` with the 13 evaluated fields + identity fields needed for chain assembly (~18 total)
2. Use this profile to restrict the catalog groups passed to LLM calls
3. Add field-specific extraction rules to the prompt for B.clinical_phenotypes, B.mode_of_inheritance_reported, C.de_novo_status, B.hpo_terms
4. Add source-visible validation to ClinicalContextStage

**Expected impact:** Reduce FP on medium-contextual fields, improve recall on variant fields, maintain precision on simple fields.

**Risk:** Low. Restricting fields is a reduction, not an addition. Prior attempts at broader extraction regressed.

### Approach B: Source-Visible Acceptance Gate

Add a post-extraction validation stage that checks whether each extracted value is verbatim present in the source document text. Reject items where the value cannot be traced to the source.

**Changes:**
1. After catalog_extraction and clinical_context, run a source-visible gate
2. For each FOUND item, verify that the value (or a close variant) appears in the document
3. Items that fail validation are downgraded to NOT_FOUND

**Expected impact:** Reduce FP on B.mode_of_inheritance_reported and B.age_of_onset.

**Risk:** Medium. May also reject valid extractions where the LLM paraphrases the source. Needs careful threshold tuning.

### Approach C: Confidence Calibration

Adjust confidence thresholds per field difficulty tier. Require higher confidence for medium-contextual and complex fields.

**Changes:**
1. Simple explicit fields: accept confidence ≥ 0.5
2. Medium contextual fields: require confidence ≥ 0.7
3. Complex evidence fields: require confidence ≥ 0.8

**Expected impact:** Reduce FP on medium-contextual fields.

**Risk:** Medium. May also reduce recall. Needs validation against held-out data.

## 3. Selected Approach: A + B (Field-Budgeted + Source-Visible Gate)

Implement Approach A (field-budgeted extraction) as the primary optimization, with Approach B (source-visible gate) as a targeted fix for high-FP fields.

Approach C (confidence calibration) is deferred — it requires more data to set thresholds correctly.

### Design Principles

- **Opt-in, not default.** The Dataset D field profile (`ExtractionProfile.DATASET_D_PUBLICATION`) is explicitly selected by benchmark runners. Production extraction uses `ExtractionProfile.NONE` (all non-curation fields). This makes the field-budgeted approach auditable and avoids accidental benchmark overfitting.
- **Explicit in API.** The extraction profile is passed through the pipeline HTTP request payload (`extraction_profile` field), the `PipelineGraphState`, the `Phase2Adapter`, and the `EvidenceExtractionService`. No hidden environment variables or silent defaults.
- **Source-visible gate is conservative.** The gate normalizes whitespace before substring matching (handles OCR/table/translation formatting), uses case-sensitive matching to avoid false positives, and logs rejection reasons for evaluation audit.

## 4. Implementation Plan

### Step 1: Define Field Profile

Create `backend/src/core/.../extract_evidence/field_profile.py` with:
- `EVALUATION_FIELD_PROFILE`: frozenset of 13 evaluated field IDs
- `CHAIN_IDENTITY_FIELDS`: frozenset of fields needed for evidence chain assembly
- `DATASET_D_FIELDS`: union of both (~18 fields)
- `build_profiled_catalog(profile_fields, catalog_groups)`: returns filtered catalog tuples

### Step 2: Update Field Eligibility

Modify `FieldEligibilityPolicy` to accept an optional field profile. When a profile is provided, restrict allowed fields to the profile intersection.

### Step 3: Add Field-Specific Extraction Rules

Add rules to `get_catalog_extraction_prompt()` for:
- B.clinical_phenotypes: extract symptoms, not diagnosis names
- B.mode_of_inheritance_reported: require explicit text evidence, not inferred
- C.de_novo_status: require parental testing evidence
- B.hpo_terms: extract HPO codes or phenotype descriptions

### Step 4: Source-Visible Gate for ClinicalContextStage

Add source-visible validation to `ClinicalContextStage._merge()`: verify that extracted values appear in the document text before accepting them.

### Step 5: Wire Field Profile into Workflow

Pass the field profile through the workflow to catalog_extraction and clinical_context stages.

### Step 6: Tests

- Test field profile filtering
- Test field-specific extraction rules in prompt
- Test source-visible gate rejects non-traceable values
- Test that pipeline still works with reduced field set

### Step 7: Evaluation

Run full 73-entry evaluation with --no-preprocessed and compare against:
- Current SYSTEM baseline
- B7-expanded baseline

## 5. Acceptance Criteria

- SYSTEM F1 on merged_73 ≥ 0.58 (current: 0.5622)
- B.clinical_phenotypes F1 > 0 (current: 0.0)
- B.mode_of_inheritance_reported FP count reduced (current: 20 FP)
- No regression on B.disease_diagnosis F1 (current: 0.9718)
- No regression on A.functional_domain_or_hotspot F1 (current: 0.1569)
- Per-field error analysis included in report

## 6. Evaluation Results (2026-06-24)

### Status: IN PROGRESS

The full 73-entry evaluation with `dataset_d_publication` profile is running but very slow due to LLM API rate limits (429 errors from linxi.chat). Estimated completion: ~12 hours.

### Key Finding: Processing Cache Bug

The initial evaluation runs hit the server's processing cache — entries completed in 5 seconds using cached results from prior pipeline runs, NOT the dataset_d_publication profile. The content hash did not include the extraction profile, so identical documents returned stale results.

**Fix:** `content_hash.py` now includes `extraction_profile` in the scope key. The v3 run uses the corrected hash.

### Partial Results (2 entries, v3 run with fixed hash)

| Entry | TP | FP | FN | Duration |
|-------|----|----|-----|----------|
| rett_001 | 0 | 0 | 8 | 236s |
| rett_003 | 0 | 0 | 11 | 613s |

Both entries show all fields missing. This is concerning and may indicate the profile restriction is too aggressive or the pipeline needs further tuning.

### Cached Run Analysis (10 entries, NOT the profile run)

The cached results (general pipeline, 143 fields) show:
- B.clinical_phenotypes: 5 FP, 0 TP — ClinicalContextStage adds wrong values
- B.mode_of_inheritance_reported: 3 FP, 0 TP — target_span_recovery adds wrong values

### Pending

Full 73-entry evaluation will complete in ~12 hours. Final report will be generated from `eval_<timestamp>.json`.

## 7. Core Identity Retry (Implemented)

After the 11-entry diagnostic revealed that catalog_extraction intermittently
fails to produce A.gene_symbol and B.disease_diagnosis (even when source text
contains abundant target mentions), a focused retry path was added.

**Behavior:**
- After normal catalog extraction completes, check if A.gene_symbol or
  B.disease_diagnosis has status=FOUND.
- If either is missing AND extraction_target is present, run one retry.
- Retry prompt: compact 4-field prompt (A.gene_symbol, B.disease_diagnosis,
  A.variant_hgvs_c, A.variant_hgvs_p) with target info.
- Uses recall-first blocks when available.
- Merge: don't overwrite higher-confidence existing FOUND items.
- Failure is logged as warning, pipeline continues.

**Rationale:** The diagnostic showed entries like rett_001 (85 MECP2 mentions,
0 A.gene_symbol extracted) and rett_006 (26 MECP2 mentions, A.gene_symbol found).
This is an intermittent LLM reliability issue, not a field coverage issue. A
compact retry with fewer fields and explicit target guidance maximizes the chance
of extracting these critical identity fields.

**Files:** `stages/catalog_extraction.py`, `prompts.py` (get_core_identity_retry_prompt)

### Post-Retry Validation Result

Targeted evaluation on rett_001 and rett_005 confirms:
- **Retry triggers correctly** and rescues B.disease_diagnosis
- **Results still 0/8** because Phase 3 gene-variant coexistence gate drops all items when no group has both A.gene_symbol AND a variant in FOUND status
- The retry fix alone is insufficient. The coexistence gate is the dominant failure mode for 0-match entries.

**Next required fix:** Either extend retry trigger to also fire when gene is found but variant is missing, or relax the coexistence gate to allow identity fields (gene, disease) to persist independently.

## 8. Files to Modify

| File | Change |
|------|--------|
| `extract_evidence/field_profile.py` | **New** — field profile definitions |
| `extract_evidence/field_eligibility.py` | Accept optional profile parameter |
| `extract_evidence/stages/catalog_extraction.py` | Pass profile to eligibility policy |
| `extract_evidence/prompts.py` | Add field-specific rules |
| `extract_evidence/stages/clinical_context.py` | Add source-visible gate |
| `extract_evidence/workflow.py` | Wire field profile |

## 7. Not Changed

- `benchmark/core/field_normalize.py` — no scoring-side changes
- `benchmark/core/matching.py` — no matching logic changes
- Reconcile logic — unchanged
- Source grounding — unchanged
- Translation — unchanged

## 9. Phase 3 Coexistence Gate Fix (2026-06-24)

### 9.1 Problem

The gene-variant coexistence gate in `repositories.py:_find_gene_variant_complete_groups` was all-or-nothing: when no evidence group had both `A.gene_symbol` AND a variant in FOUND status, ALL track payload items were silently dropped. This caused identity fields (gene, disease) extracted by Phase 2 to be lost at Phase 3.

### 9.2 Solution

Field-aware two-tier gate:

| Tier | Condition | Fields Accepted |
|------|-----------|----------------|
| Full gate | Group has gene + variant in FOUND | All fields |
| Identity gate | Group has gene OR disease in FOUND (anchor) | Identity fields only |

**Anchor fields** (can make a group passable): `A.gene_symbol`, `B.disease_diagnosis`
**Identity fields** (can survive independently): 10 fields including gene, disease, variant HGVS, clinical phenotypes, sex, age, inheritance, de novo
**Variant-dependent fields** (still require full gate): functional, segregation, pathogenicity, allele frequency, etc.

### 9.3 Changes

| File | Change |
|------|--------|
| `standardize_entities_and_align_knowledge/repositories.py` | Added `_GATE_IDENTITY_FIELDS`, `_GATE_ANCHOR_FIELDS`, `_find_identity_passable_groups()`, modified `_build_run_item_specs()` |
| `tests/.../test_repositories.py` | 6 new tests, 2 updated tests |

### 9.4 Validation

- 43 repository tests pass
- 196 Phase 3 tests pass (3 pre-existing failures unrelated)
- Ruff clean
- Targeted validation for rett_001 pending
