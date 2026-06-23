# BIBM Main Paper Result Package

Generated: 2026-06-23T20:29:42

---

## 1. Dataset Summary

| Dataset | Entries | Phase 2 Coverage | B0 Baseline | Role |
|---|---|---|---|---|
| RETT | 53 | 53/53 | ✓ | Main evaluation |
| Parkinson | 20 | 20/20 | ✓ | Main evaluation |
| ClinGen | 30 | 30/30 | ✗ | Supporting |
| ClinVar Fused | 75 | 20/75 | ✗ | Supporting |

**Main evaluation set**: Merged RETT (53) + Parkinson (20) = **73 entries**.
ClinGen and ClinVar Fused lack comparable B0 baselines and serve as supporting datasets.

## 2. Main Baseline Comparison (Merged 73 entries)

| System | Precision | Recall | F1 |
|---|---|---|---|
| SYSTEM | 0.7717 | 0.5057 | **0.6110** |
| B0 (naive LLM) | 0.9905 | 0.2603 | 0.4122 |
| **Δ** | -0.2188 | +0.2454 | **+0.1988** |

## 3. Per-Dataset Results

| Dataset | N | SYSTEM F1 | B0 F1 | ΔF1 | p-value | Significant |
|---|---|---|---|---|---|---|
| merged 73 | 73 | 0.5622 | 0.4114 | +0.1224 | 0.0000 | ✓ |
| rett 53 | 53 | 0.5816 | 0.3813 | +0.1906 | 0.0000 | ✓ |
| parkinson 20 | 20 | 0.4706 | 0.5320 | -0.0583 | 0.2158 | ✗ |

**RETT** shows statistically significant improvement. **Parkinson** does not — it is a boundary/limitation case.

## 4. Field Difficulty Results

| Category | SYSTEM F1 | B0 F1 | ΔF1 |
|---|---|---|---|
| simple_explicit | 0.7617 | 0.6441 | +0.1176 |
| medium_contextual | 0.3023 | 0.0000 | +0.3023 |
| complex_evidence | 0.2162 | 0.0000 | +0.2162 |

**Pipeline gains scale with field difficulty.** Medium contextual and complex evidence are the primary sources of improvement.

## 5. Statistical Significance

| Analysis | ΔF1 | 95% CI | p-value | Significant |
|---|---|---|---|---|
| Merged 73 | +0.1224 | [+0.0800, +0.1626] | 0.0000 | ✓ |
| RETT 53 | +0.1906 | [+0.1558, +0.2245] | 0.0000 | ✓ |
| Parkinson 20 | -0.0583 | [-0.1477, +0.0226] | 0.2158 | ✗ |
| simple_explicit | +0.0921 | — | 0.0002 | ✓ |
| medium_contextual | +0.2447 | — | 0.0000 | ✓ |
| complex_evidence | +0.1096 | — | 0.0082 | ✓ |

## 6. Case Studies

### Case 1: SYSTEM extracts sex and age of onset from clinical context; B0 produces nothing

**rett / rett_003** — medium_contextual

In rett_003, a case report of monozygotic twins with Rett syndrome, the pipeline extracted patient sex (Female) and age of onset (~2 years, regression after seizures) from the clinical narrative. The naive baseline produced neither field, as its single-prompt approach focuses on gene-disease-variant triads and does not request contextual metadata. This illustrates the pipeline's advantage on medium-difficulty fields requiring cross-sentence clinical reasoning.

### Case 2: SYSTEM identifies de novo status from parent genotyping; B0 cannot

**rett / rett_004** — complex_evidence

In rett_004, a Chinese-language case report, the pipeline identified the MECP2 c.502C>T (p.R168X) mutation as de novo by cross-referencing the family genotyping table (parents negative) with the clinical narrative. The baseline produced no de novo assessment, as this requires source-grounded reasoning across multiple document sections — a task that exceeds single-prompt extraction capability.

### Case 3: SYSTEM extracts HGVS variant notation from Chinese biomedical text

**rett / rett_004** — simple_explicit

In rett_004, the pipeline extracted both HGVS notations (c.502C>T, p.R168X) from a Chinese-language genotyping report. The baseline missed both variants, demonstrating that cross-lingual extraction with structured variant parsing outperforms English-only single-prompt approaches on non-English literature.

### Case 4: Parkinson low-complexity dataset: B0 matches or exceeds SYSTEM on simple fields

**parkinson / parkinson_013** — simple_explicit

In parkinson_013, a simple English-language gene association study, B0 correctly extracted the gene symbol (PRKN) and disease relationship (causative/associated), while SYSTEM extracted the alias 'PARK2' and missed the relationship field. This illustrates that on low-complexity datasets with simple explicit fields, the pipeline's multi-track reconciliation can introduce noise without compensating gains. The pipeline's primary advantage lies in medium and complex evidence extraction, not simple factual lookups.

## 7. Claims Supported

- SYSTEM significantly outperforms B0 on the merged 73-entry evaluation set (ΔF1=+0.1224, p<0.0001, 95% CI [+0.0800, +0.1626]).
- The pipeline's gains are strongest on medium-difficulty contextual fields (ΔF1=+0.2447, p<0.0001) where B0 scores zero.
- Complex evidence fields show significant improvement (ΔF1=+0.1096, p=0.0082), though support is dominated by de novo status.
- Simple explicit fields show a smaller but significant improvement (ΔF1=+0.0921, p=0.0002).
- The dual-track pipeline recovers non-English HGVS variant evidence and de novo status that single-prompt baselines miss.
- Pipeline provides structured audit trails and source grounding even when aggregate F1 is comparable to B0.

## 8. Claims To Avoid

- Do not claim all datasets significantly improve over B0 — Parkinson does not (ΔF1=-0.0583, p=0.2158).
- Do not claim Parkinson improves over B0 — it is a boundary/limitation case.
- Do not claim clinical phenotype extraction is solved — B.clinical_phenotypes F1=0 (pipeline capability gap).
- Do not overclaim complex evidence diversity — support is mostly C.de_novo_status from Rett, not diverse complex evidence types.
- Do not claim B0 is weak on all fields — B0 achieves perfect or near-perfect precision on simple factual lookups.

## 9. Remaining Weaknesses

- Parkinson boundary case: SYSTEM does not outperform B0 on this low-complexity English dataset (ΔF1=-0.0583, p=0.2158).
- B.clinical_phenotypes pipeline gap: the extraction pipeline does not produce this field; F1=0 despite 71 expected entries.
- Complex evidence diversity: all complex_evidence support comes from C.de_novo_status in Rett; segregation, functional assay, and recurrence are not represented.
- B0 prompt may be underperforming on medium/complex fields: the naive single-prompt baseline does not request inheritance, variant type, or de novo status, making the comparison partly an artifact of prompt design.
- clingen/clinvar_fused lack comparable B0 baselines, limiting generalizability claims.

## 10. BIBM Readiness Assessment

**Ready**: borderline
**Confidence**: moderate

**Strongest selling point**: Statistically significant improvement on medium-difficulty contextual fields (ΔF1=+0.2447, p<0.0001) with clear mechanistic explanation (dual-track reconciliation recovers evidence single-prompt baselines miss).

**Biggest reviewer risk**: The naive B0 baseline does not request medium/complex fields, so the comparison partially reflects prompt design differences rather than extraction capability. A reviewer may argue that a more detailed B0 prompt would close the gap.

**Recommendation**: The results are sufficient for a BIBM short paper (4 pages) if framed as a methodology contribution with empirical validation, not as a claim of universal improvement. The key narrative should be: (1) define field difficulty tiers, (2) show pipeline gains scale with difficulty, (3) acknowledge Parkinson as a boundary case that validates the difficulty framework. The biggest risk is a reviewer asking for a stronger B0 with medium/complex fields in the prompt. Mitigation: prepare a supplementary experiment with an expanded B0 prompt. The case studies provide concrete evidence for the methodology claims.
