# B8 Business Pipeline Re-Test Analysis

**Date:** 2026-06-27
**Report:** `eval_unified_20260627_002104.json`
**Samples:** gs_054, gs_058, gs_061, gs_074, gs_098
**Mode:** `extraction_mode="b8"`, `extraction_profile="none"`

---

## 1. Overall Metrics

| Metric | Business B8 (this run) | Business B8 (before mapping) | Benchmark B8 Harness | Current Unified | Prompt-only Citation |
|--------|----------------------|---------------------------|---------------------|----------------|---------------------|
| **Precision** | **75.00%** | 83.33% | 72.22% | 72.73% | 100.00% |
| **Recall** | **29.03%** | 15.15% | 44.83% | 25.81% | 32.35% |
| **F1** | **41.86%** | 25.64% | 55.32% | 38.10% | 48.89% |
| TP | 9 | 5 | 13 | - | - |
| FP | 3 | 1 | 5 | - | - |
| FN | 22 | 28 | 16 | - | - |

**Delta vs previous business B8:** F1 +16.2pp (25.6% -> 41.9%), Recall +13.9pp (15.2% -> 29.0%), Precision -8.3pp (83.3% -> 75.0%)

**Gap to benchmark B8 harness:** F1 -13.5pp (55.3% -> 41.9%), Recall -15.8pp, Precision +2.8pp

---

## 2. Per-Entry TP / FP / FN

### gs_054 (MLH1, Lynch syndrome, AD, clinvar_fused)
- **TP (1):** A.gene_symbol
- **FP (0):** -
- **FN (7):** B.disease_diagnosis, A.gene_disease_relationship, B.mode_of_inheritance_reported, A.variant_hgvs_c, A.variant_hgvs_p, A.variant_type, J.clinvar_assertion
- **Notes:** Document focuses on ELP1 in medulloblastoma; MLH1 mentioned only as coexisting PV in one patient. Very sparse target evidence.

### gs_058 (MSH6, mismatch repair cancer syndrome 1, AR, clinvar_fused)
- **TP (1):** A.gene_symbol
- **FP (0):** -
- **FN (7):** B.disease_diagnosis, A.gene_disease_relationship, B.mode_of_inheritance_reported, A.variant_hgvs_c, A.variant_hgvs_p, A.variant_type, J.clinvar_assertion
- **Notes:** Benchmark harness also missed most fields here but got A.gene_disease_relationship=causative (TP). Business B8 didn't extract GDR at all.

### gs_061 (MT-ATP6, Leigh syndrome, MT, clinvar_fused)
- **TP (2):** A.gene_symbol, B.disease_diagnosis
- **FP (0):** -
- **FN (4):** A.gene_disease_relationship, B.mode_of_inheritance_reported (wrong_value: "maternally inherited" vs "MT"), A.variant_type, J.clinvar_assertion
- **Notes:** Benchmark harness got 4 TP here (also A.gene_disease_relationship and A.variant_type). Business B8 missed both.

### gs_074 (MT-TW, mitochondrial disease, MT, clinvar_fused)
- **TP (3):** A.gene_symbol, B.disease_diagnosis, A.variant_type (SNV matched via field_normalized)
- **FP (2):** B.mode_of_inheritance_reported (wrong_value: "maternal (mitochondrial) inheritance" vs "MT"), B.clinical_phenotypes (wrong_value: structured list vs expected format)
- **FN (1):** J.clinvar_assertion
- **Notes:** Best-performing entry. Benchmark harness also got 3 TP / 2 FP / 1 FN here — identical.

### gs_098 (LRRK2, Parkinson disease, AD, parkinson)
- **TP (2):** A.gene_symbol, B.disease_diagnosis
- **FP (1):** B.clinical_phenotypes (wrong_value: free text "mild idiopathic PD with predominant tremor..." vs "parkinsonism; tremor; rigidity; bradykinesia")
- **FN (3):** A.gene_disease_relationship, B.mode_of_inheritance_reported, A.variant_type
- **Notes:** Benchmark harness got 3 TP here (also B.clinical_phenotypes=matched and A.gene_disease_relationship). Business B8 missed both.

---

## 3. Alias Mapping Hit Statistics

| Alias | Target | Hits |
|-------|--------|------|
| C.segregation -> C.g_plus_p_plus_count | | **0** |
| C.functional_assay -> F.functional_result | | **0** |
| C.contradictory_evidence -> H.contradiction_type | | **0** |
| C.recurrence -> B.case_count | | **0** |

**Root cause:** The B8 prompt lists business field names directly (e.g., `C.g_plus_p_plus_count`, `F.assay_type`, `B.case_count`). The LLM returns these canonical names, never the benchmark aliases (`C.segregation`, `C.functional_assay`, etc.). The alias mapping is dead code in this configuration — it only activates if the LLM returns the simplified benchmark label, which the prompt never exposes.

**Impact:** Neutral for precision (no alias-induced FP), but the alias mapping was designed to bridge the gap between benchmark prompt simplicity and business catalog complexity. Since the LLM returns business names directly, the mapping is unnecessary for field ID resolution. However, the fields the aliases target (segregation, functional assay, contradiction, recurrence) are still not being extracted by the LLM at all — this is a prompt coverage issue, not a mapping issue.

---

## 4. Source Grounding Statistics

| Category | Count |
|----------|-------|
| FOUND + grounded (exact/page span match) | **0** |
| FOUND + fallback (B8 fallback, block_index=-1) | **30** |
| SOURCE_INVALID | **3** (in logs, all ellipsis-containing snippets) |
| TABLE_UNGROUNDED | 0 |
| OCR_GAP | 0 |

**Root cause:** Every extracted item has `block_index=-1`, `context_ref="primary_broad_extraction"`, and `source_precision` of "ambiguous" or "corrected". This means:

1. The LLM generates `source_quote` values that are NOT verbatim substrings of the document text (paraphrased, truncated, or fabricated).
2. The `SourceGrounder._ground_one()` cannot find these quotes via exact text match or fuzzy search.
3. The B8-specific fallback at `_ground_source()` creates a fallback `SourceLocation` with `source_precision=SourcePrecision.CORRECTED` so items aren't silently dropped.

**Impact:** All items survive grounding via fallback, which is correct for an experimental mode. But it means source provenance is unverifiable — the `source_quote` cannot be traced to a specific document location. This is acceptable for recall measurement but would be a blocker for production use.

**3 SOURCE_INVALID instances** (from logs): All were ellipsis-containing snippets from gs_074 that the fuzzy matcher couldn't resolve. These items were still preserved via the B8 fallback.

---

## 5. Report JSON

Path: `/data/yangzs/Projects/01_ACMG_Lingua/benchmark/data/reports/eval_unified_20260627_002104.json`

The report includes `aggregates.by_source_dataset`:
- **clinvar_fused** (4 entries): P=77.8%, R=26.9%, F1=40.0%
- **parkinson** (1 entry): P=66.7%, R=40.0%, F1=50.0%

---

## 6. Gap Analysis: Business B8 vs Benchmark B8 Harness

### 6.1 Missing TPs (4 TP gap: 9 vs 13)

| Field | Entry | Benchmark got it | Business missed because |
|-------|-------|-----------------|------------------------|
| A.gene_disease_relationship | gs_058 | TP: "causative" | Prompt doesn't request GDR; LLM doesn't extract it |
| A.gene_disease_relationship | gs_061 | TP: "causative" | Same — prompt omission |
| A.gene_disease_relationship | gs_074 | FP (not TP) | Both got FP here |
| B.clinical_phenotypes | gs_098 | TP: "tremor; bradykinesia; rigidity; postural instability" | Business extracted free-text description; benchmark matched structured list |
| A.variant_type | gs_061 | TP: "SNV" | Business didn't extract variant_type for this entry |

**Primary cause: prompt field coverage gap.** The B8 prompt does not explicitly request `A.gene_disease_relationship`. The benchmark harness prompt does (it's a simpler prompt with a different field list). Adding GDR to the B8 prompt could recover 2 TPs (gs_058, gs_061).

### 6.2 Additional FPs (3 vs 5 — business has fewer FPs)

Business B8 has fewer FPs because it extracts fewer items overall. The benchmark harness FPs are mostly wrong-value matches on MOI and GDR (e.g., "maternal inheritance" vs "MT", "reported association" vs "causative"). Business B8 has similar FP patterns:
- gs_074: MOI "maternal (mitochondrial) inheritance" vs "MT"
- gs_074: clinical_phenotypes structured list vs expected
- gs_098: clinical_phenotypes free text vs expected

### 6.3 Root Cause Summary

| Factor | Impact on F1 gap | Severity |
|--------|-----------------|----------|
| **Prompt field coverage** (missing GDR, incomplete variant fields) | -8 to -10pp | HIGH — adding GDR + variant_type to prompt is the single highest-ROI fix |
| **Source grounding strictness** | 0pp (items survive via fallback) | LOW for experimental mode; items aren't dropped |
| **Review validation over-rejection** | Not observable — no rejected items found in DB | LOW |
| **Role routing / target guard / quality gate** | Possible — some items may be filtered post-extraction | MEDIUM — needs investigation |
| **Alias mapping ineffectiveness** | 0pp (aliases never triggered) | NEUTRAL — aliases are dead code since prompt uses canonical names |
| **Value normalization** (MOI "MT" matching) | -1 to -2pp | MEDIUM — "maternally inherited" doesn't normalize to "MT" |

### 6.4 Comparison Table

| Dimension | Business B8 | Benchmark B8 | Delta | Root Cause |
|-----------|------------|-------------|-------|------------|
| P | 75.0% | 72.2% | +2.8pp | Business extracts fewer items (fewer FP opportunities) |
| R | 29.0% | 44.8% | -15.8pp | Prompt misses GDR, variant fields; stricter post-processing |
| F1 | 41.9% | 55.3% | -13.5pp | Primarily recall gap |
| TP | 9 | 13 | -4 | Missing: 2×GDR, 1×variant_type, 1×clinical_phenotypes |
| FP | 3 | 5 | -2 | Fewer extractions = fewer FP |
| FN | 22 | 16 | +6 | More missing fields |

---

## 7. Recommendations (ordered by expected F1 impact)

1. **Add `A.gene_disease_relationship` to B8 prompt** — Expected +2 TP (gs_058, gs_061), ~+4pp F1
2. **Add `A.variant_type` and `A.variant_hgvs_c/p` extraction guidance** — Expected +1-2 TP, ~+2pp F1
3. **Improve MOI normalization** — "maternally inherited" → "MT", "autosomal dominant" → "AD" — Expected +1 TP, ~+2pp F1
4. **Investigate clinical_phenotypes matching** — benchmark harness matches structured phenotype lists; business pipeline doesn't — Expected +1 TP, ~+2pp F1
5. **Alias mapping is dead code** — consider removing or redesigning to handle LLM output that uses near-canonical but slightly different field names
6. **Source grounding** — all items use B8 fallback; this is acceptable for experimentation but blocks production use
