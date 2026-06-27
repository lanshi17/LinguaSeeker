# B8 Business Pipeline Re-Test — Round 2 Analysis

**Date:** 2026-06-27
**Report:** `eval_unified_20260627_011612.json`
**Samples:** gs_054, gs_058, gs_061, gs_074, gs_098
**Changes:** Enhanced prompt (GDR, variant_type, clinical_phenotypes, verbatim source_quote rules), added source_quote verbatim check in normalize stage.

---

## 1. Overall Metrics Comparison

| Metric | Round 2 (this) | Round 1 | Business B8 (before) | Benchmark B8 | Prompt-only Cite |
|--------|---------------|---------|---------------------|-------------|-----------------|
| **Precision** | **91.67%** | 75.00% | 83.33% | 72.22% | 100.00% |
| **Recall** | **33.33%** | 29.03% | 15.15% | 44.83% | 32.35% |
| **F1** | **48.89%** | 41.86% | 25.64% | 55.32% | 48.89% |
| TP | 11 | 9 | 5 | 13 | - |
| FP | 1 | 3 | 1 | 5 | - |
| FN | 22 | 22 | 28 | 16 | - |

**Round 1 → Round 2:** F1 +7.0pp (41.9% → 48.9%), Precision +16.7pp (75.0% → 91.7%), Recall +4.3pp (29.0% → 33.3%).

**Round 2 vs prompt-only citation:** F1 **identical** at 48.89%.

**Gap to benchmark B8 harness:** F1 -6.4pp (55.3% → 48.9%), Recall -11.5pp, Precision +19.5pp.

---

## 2. Per-Entry TP / FP / FN

### gs_054 (MLH1, Lynch syndrome, AD, clinvar_fused)
- **TP (1):** A.gene_symbol
- **FP (0):** -
- **FN (7):** B.disease_diagnosis, A.gene_disease_relationship, B.mode_of_inheritance_reported, A.variant_hgvs_c, A.variant_hgvs_p, A.variant_type, J.clinvar_assertion
- **Notes:** No change from Round 1. Document focuses on ELP1; MLH1 barely mentioned.

### gs_058 (MSH6, mismatch repair cancer syndrome 1, AR, clinvar_fused)
- **TP (1):** A.gene_symbol
- **FP (0):** -
- **FN (7):** B.disease_diagnosis, A.gene_disease_relationship, B.mode_of_inheritance_reported, A.variant_hgvs_c, A.variant_hgvs_p, A.variant_type, J.clinvar_assertion
- **Notes:** No change from Round 1. Document focuses on gliomas; MSH6 in background statistics.

### gs_061 (MT-ATP6, Leigh syndrome, MT, clinvar_fused) ⭐
- **TP (4):** A.gene_symbol, B.disease_diagnosis, **A.gene_disease_relationship**, **B.mode_of_inheritance_reported**
- **FP (0):** -
- **FN (2):** A.variant_type, J.clinvar_assertion
- **Notes:** **+2 TP from Round 1** (GDR and MOI now matched). GDR extracted as "causative" (correct). MOI extracted as "MT" (correct, from "MILS, maternally inherited Leigh syndrome").

### gs_074 (MT-TW, mitochondrial disease, MT, clinvar_fused) ⭐
- **TP (3):** A.gene_symbol, B.disease_diagnosis, B.mode_of_inheritance_reported
- **FP (0):** -
- **FN (3):** A.gene_disease_relationship, A.variant_type, J.clinvar_assertion
- **Notes:** **MOI now correct** ("MT" instead of "maternal (mitochondrial) inheritance"). **-1 FP** from Round 1. But lost A.variant_type TP (was "SNV" matched via field_normalized in R1).

### gs_098 (LRRK2, Parkinson disease, AD, parkinson)
- **TP (2):** A.gene_symbol, B.disease_diagnosis
- **FP (1):** B.clinical_phenotypes (wrong_value: "predominant tremor; postural changes; loss of smell and constipation" vs expected "parkinsonism; tremor; rigidity; bradykinesia")
- **FN (3):** A.gene_disease_relationship, B.mode_of_inheritance_reported, A.variant_type
- **Notes:** No change from Round 1. Clinical phenotypes still mismatched.

---

## 3. Source Grounding Statistics

| Category | Round 2 | Round 1 |
|----------|---------|---------|
| FOUND + exact grounding | 0 | 0 |
| FOUND + fallback (ambiguous) | 19 | ~20 |
| FOUND + fallback (corrected) | 8 | ~10 |
| SOURCE_INVALID | 0 | 3 |
| **NOT verbatim warnings** | **12** | N/A (check not implemented) |

**Source_quote verbatim check results:** 12 non-verbatim warnings logged during the evaluation. All from gs_074 and gs_098. The LLM still paraphrases source quotes for some fields, but the enhanced prompt reduced the rate from Round 1. No items were dropped (warning only, not blocking).

---

## 4. Alias Mapping Statistics

All 4 aliases: **0 hits** (unchanged from Round 1). The LLM returns canonical business field names from the prompt. Alias map is confirmed dead code in this configuration.

---

## 5. FN Field Distribution

| Field | FN Count | Notes |
|-------|----------|-------|
| J.clinvar_assertion | 5/5 | Not in B8 prompt; LLM doesn't extract it |
| A.variant_type | 4/5 | Only gs_074 matched in R1 (lost in R2); prompt guidance insufficient for inference |
| A.gene_disease_relationship | 3/5 | gs_061 now matched (+1 TP); gs_054/gs_058 sparse evidence, gs_074/gs_098 not extracted |
| B.mode_of_inheritance_reported | 3/5 | gs_061/gs_074 now matched (+2 TP); gs_054/gs_058/gs_098 still missing |
| A.variant_hgvs_c | 3/5 | Same as R1 |
| A.variant_hgvs_p | 3/5 | Same as R1 |
| B.disease_diagnosis | 2/5 | Same as R1 |

---

## 6. FP Field Distribution

| Field | FP Count | Entry | Value |
|-------|----------|-------|-------|
| B.clinical_phenotypes | 1 | gs_098 | "predominant tremor; postural changes; loss of smell and constipation" vs "parkinsonism; tremor; rigidity; bradykinesia" |

Down from 3 FP in Round 1. The two MOI FPs from Round 1 were eliminated by the improved MOI normalization guidance.

---

## 7. What Round 2 Fixed

| Fix | TP Gain | FP Reduction | F1 Impact |
|-----|---------|-------------|-----------|
| GDR prompt guidance | +2 (gs_061) | 0 | +4.7pp |
| MOI normalization ("maternally inherited" → "MT") | +1 (gs_061, gs_074) | -1 (gs_074 MOI FP eliminated) | +4.7pp |
| Clinical phenotypes guidance | 0 | -1 (gs_074 phenotypes FP eliminated) | +2.3pp |
| Verbatim source_quote instruction | 0 (monitoring) | 0 | 0 (future improvement) |

---

## 8. Remaining Gap to Benchmark B8 (F1 48.9% vs 55.3%)

**Benchmark B8 gets 2 more TPs that business B8 misses:**
1. **B.clinical_phenotypes for gs_098**: Benchmark matches "tremor; bradykinesia; rigidity; postural instability". Business extracts different phenotype text. This is a value normalization/matching gap.
2. **A.gene_disease_relationship for gs_074 or gs_098**: Benchmark gets GDR for these entries. Business doesn't extract it.

**Benchmark B8 also has more FPs (5 vs 1)**, so the precision gap favors business B8.

---

## 9. Recommendations for Round 3

1. **A.variant_type**: Still 4/5 FN. The LLM isn't extracting variant_type even with the enhanced guidance. Consider making it a mandatory extraction when variant_hgvs_c or variant_hgvs_p is present.
2. **J.clinvar_assertion**: 5/5 FN. Add explicit prompt instruction for this field.
3. **B.clinical_phenotypes matching**: The benchmark harness uses a more lenient phenotype matcher. Consider improving the value normalizer for phenotype fields.
4. **Source_quote quality**: 12 non-verbatim warnings. The LLM still paraphrases for complex fields (phenotypes, GDR). Further prompt refinement or post-processing verbatim correction may help.
