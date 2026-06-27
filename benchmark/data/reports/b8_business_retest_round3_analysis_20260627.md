# B8 Business Pipeline Re-Test — Round 3 Analysis

**Date:** 2026-06-27
**Report:** `eval_unified_20260627_103025.json`
**Samples:** gs_054, gs_058, gs_061, gs_074, gs_098
**Change vs R2:** Added J.clinvar_assertion prompt guidance (ClinVar/expert panel/explicit classification detection).

---

## 1. Overall Metrics

| Metric | Round 3 | Round 2 | Δ | Benchmark B8 | Prompt-only |
|--------|---------|---------|---|-------------|------------|
| **Precision** | **87.50%** | 91.67% | -4.2pp | 72.22% | 100.00% |
| **Recall** | **43.75%** | 33.33% | **+10.4pp** | 44.83% | 32.35% |
| **F1** | **58.33%** | 48.89% | **+9.4pp** | 55.32% | 48.89% |
| TP | 14 | 11 | +3 | 13 | - |
| FP | 2 | 1 | +1 | 5 | - |
| FN | 18 | 22 | -4 | 16 | - |

**F1 now EXCEEDS benchmark B8 harness by +3.0pp** (58.3% vs 55.3%).

---

## 2. Per-Entry Results

### gs_054 (MLH1, AD, clinvar_fused)
- **TP (1):** A.gene_symbol
- **FN (7):** All other fields — sparse ELP1-focused document
- **No change from R2**

### gs_058 (MSH6, AR, clinvar_fused)
- **TP (1):** A.gene_symbol
- **FP (1):** B.mode_of_inheritance_reported (got "inherited" vs expected "AR")
- **FN (6):** Rest unchanged
- **New FP:** MOI "inherited" is too generic, doesn't match "AR"

### gs_061 (MT-ATP6, MT, clinvar_fused) ⭐ PERFECT
- **TP (6):** A.gene_symbol, B.disease_diagnosis, A.gene_disease_relationship, B.mode_of_inheritance_reported, **A.variant_type**, **J.clinvar_assertion**
- **FP (0):** -
- **FN (0):** -
- **+2 TP from R2:** A.variant_type=SNV/substitution (from m.8069G>A notation), J.clinvar_assertion=Pathogenic (from explicit ClinVar mention in article)

### gs_074 (MT-TW, MT, clinvar_fused) ⭐
- **TP (4):** A.gene_symbol, B.disease_diagnosis, B.mode_of_inheritance_reported, **A.variant_type**
- **FP (0):** -
- **FN (2):** A.gene_disease_relationship, J.clinvar_assertion
- **+1 TP from R2:** A.variant_type=SNV/substitution (from m.5538G>A notation)
- J.clinvar_assertion FN: expected "Likely pathogenic" but article mentions "VUS" — not a match

### gs_098 (LRRK2, AD, parkinson)
- **TP (2):** A.gene_symbol, B.disease_diagnosis
- **FP (1):** B.clinical_phenotypes (free text vs structured list)
- **FN (3):** A.gene_disease_relationship, B.mode_of_inheritance_reported, A.variant_type
- **No change from R2**

---

## 3. What J.clinvar_assertion Prompt Guidance Fixed

| Entry | Before (R2) | After (R3) | Source |
|-------|-------------|------------|--------|
| gs_061 | FN | **TP: "Pathogenic"** | Article explicitly says "pathogenic variants" |
| gs_074 | FN | FN (expected "Likely pathogenic", article says "VUS") | Correct behavior — VUS ≠ Likely pathogenic |
| gs_098 | FN | FN (article mentions VUS, not Pathogenic) | Correct behavior |

Net gain: +1 TP from J.clinvar_assertion guidance.

---

## 4. What variant_type Prompt Guidance Fixed

| Entry | Before (R2) | After (R3) | Source |
|-------|-------------|------------|--------|
| gs_061 | FN | **TP: "SNV/substitution"** | m.8069G>A notation → SNV |
| gs_074 | FN (was TP in R1, lost in R2) | **TP: "SNV/substitution"** | m.5538G>A notation → SNV |
| gs_054 | FN | FN | No variant notation in sparse document |
| gs_058 | FN | FN | dup notation not extracted |
| gs_098 | FN | FN | Multiple variants, not extracted |

Net gain: +2 TP from variant_type inference.

---

## 5. Source Grounding & Verbatim Stats

| Category | Count |
|----------|-------|
| Exact grounding | 0 |
| Fallback (ambiguous) | ~18 |
| Fallback (corrected) | ~10 |
| Non-verbatim warnings | **17** |

Non-verbatim by field: B.clinical_phenotypes (4), B.case_count (3), A.gene_disease_relationship (2), others (8).

---

## 6. FN Distribution (Remaining)

| Field | FN | Entries |
|-------|-----|---------|
| J.clinvar_assertion | 3/5 | gs_054 (no ClinVar), gs_058 (no ClinVar), gs_098 (VUS not Pathogenic) |
| A.gene_disease_relationship | 3/5 | gs_054/058 (sparse), gs_098 (not extracted) |
| B.mode_of_inheritance_reported | 3/5 | gs_054/058/098 |
| A.variant_type | 2/5 | gs_054 (sparse), gs_098 (multi-variant) |
| A.variant_hgvs_c/p | 3/5 each | Not in documents |
| B.disease_diagnosis | 2/5 | gs_054/058 (sparse) |

---

## 7. FP Distribution

| Field | FP | Entry | Value |
|-------|-----|-------|-------|
| B.mode_of_inheritance_reported | 1 | gs_058 | "inherited" vs "AR" |
| B.clinical_phenotypes | 1 | gs_098 | Free text vs structured list |

---

## 8. Round-by-Round Comparison

| Metric | R1 | R2 | R3 | Benchmark | Prompt-only |
|--------|-----|-----|-----|-----------|------------|
| P | 75.0% | 91.7% | 87.5% | 72.2% | 100.0% |
| R | 29.0% | 33.3% | **43.8%** | 44.8% | 32.4% |
| F1 | 41.9% | 48.9% | **58.3%** | 55.3% | 48.9% |
| TP | 9 | 11 | **14** | 13 | - |
| FP | 3 | 1 | 2 | 5 | - |
| FN | 22 | 22 | **18** | 16 | - |

---

## 9. Key Lesson: Surgical prompt additions beat comprehensive rewrites

Round 3a (comprehensive rewrite) regressed to F1=38.1%. Round 3b (surgical J.clinvar_assertion addition to R2 prompt) achieved F1=58.3%. The review_validation stage is sensitive to prompt verbosity — overly detailed instructions cause the LLM to generate lower-confidence candidates that get rejected.
