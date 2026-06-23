# Three-Way Comparison: B0-naive vs B7-expanded vs SYSTEM

Generated: 2026-06-23T22:26:56
N entries: 73
Bootstrap iterations: 5000

## 1. Overall Merged (N=73)

| Group | N | SYS F1 | B0 F1 | B7 F1 | Δ(SYS-B7) | Δ(SYS-B0) | p(SYS-B7) | Sig |
|---|---|---|---|---|---|---|---|---|
| merged_73 | 73 | 0.5622 | 0.4114 | 0.6124 | -0.0417 | +0.1224 | 0.2066 | ✗ |

## 2. Per-Dataset

| Group | N | SYS F1 | B0 F1 | B7 F1 | Δ(SYS-B7) | Δ(SYS-B0) | p(SYS-B7) | Sig |
|---|---|---|---|---|---|---|---|---|
| rett_53 | 53 | 0.5816 | 0.3813 | 0.6171 | -0.0276 | +0.1906 | 0.2980 | ✗ |
| parkinson_20 | 20 | 0.4706 | 0.5320 | 0.5918 | -0.0789 | -0.0583 | 0.4166 | ✗ |

## 3. Per-Difficulty (Merged)

| Group | N | SYS F1 | B0 F1 | B7 F1 | Δ(SYS-B7) | Δ(SYS-B0) | p(SYS-B7) | Sig |
|---|---|---|---|---|---|---|---|---|
| merged_simple_explicit | 73 | 0.7247 | 0.6156 | 0.7714 | -0.0267 | +0.0921 | 0.4846 | ✗ |
| merged_medium_contextual | 73 | 0.3023 | 0.0000 | 0.3732 | -0.1539 | +0.2447 | 0.0008 | ✓ |
| merged_complex_evidence | 73 | 0.2162 | 0.0000 | 0.4396 | -0.1644 | +0.1096 | 0.0002 | ✓ |

## 4. Per-Field Comparison

| Field | Category | Support | SYS F1 | B0 F1 | B7 F1 | Δ(SYS-B7) |
|---|---|---|---|---|---|---|
| A.variant_hgvs_p | simple_explicit | 88 | 0.4348 | 0.0000 | 0.5509 | -0.1161 |
| A.gene_disease_relationship | simple_explicit | 73 | 0.8397 | 0.9437 | 0.9118 | -0.0721 |
| A.gene_symbol | simple_explicit | 73 | 0.9078 | 0.9790 | 0.9343 | -0.0265 |
| B.disease_diagnosis | simple_explicit | 73 | 0.9718 | 0.9931 | 0.9353 | +0.0365 |
| A.variant_type | simple_explicit | 71 | 0.6261 | 0.0000 | 0.7519 | -0.1258 |
| B.clinical_phenotypes | medium_contextual | 71 | 0.0000 | 0.0000 | 0.3235 | -0.3235 |
| B.mode_of_inheritance_reported | medium_contextual | 64 | 0.0690 | 0.0000 | 0.1513 | -0.0823 |
| C.de_novo_status | complex_evidence | 53 | 0.2162 | 0.0000 | 0.4396 | -0.2234 |
| B.sex | medium_contextual | 52 | 0.8247 | 0.0000 | 0.8400 | -0.0153 |
| B.hpo_terms | medium_contextual | 51 | 0.0000 | 0.0000 | 0.0000 | +0.0000 |
| A.functional_domain_or_hotspot | simple_explicit | 46 | 0.1569 | 0.0000 | 0.0000 | +0.1569 |
| B.age_of_onset | medium_contextual | 46 | 0.3778 | 0.0000 | 0.4368 | -0.0590 |
| A.variant_hgvs_c | simple_explicit | 44 | 0.7838 | 0.0000 | 0.9024 | -0.1186 |

## 5. Fields Where B7-expanded Closes Gap vs B0-naive

- **A.variant_hgvs_c** (simple_explicit): B0=0.0000 → B7=0.9024 (+0.9024)
- **A.variant_hgvs_p** (simple_explicit): B0=0.0000 → B7=0.5509 (+0.5509)
- **A.variant_type** (simple_explicit): B0=0.0000 → B7=0.7519 (+0.7519)
- **B.age_of_onset** (medium_contextual): B0=0.0000 → B7=0.4368 (+0.4368)
- **B.clinical_phenotypes** (medium_contextual): B0=0.0000 → B7=0.3235 (+0.3235)
- **B.mode_of_inheritance_reported** (medium_contextual): B0=0.0000 → B7=0.1513 (+0.1513)
- **B.sex** (medium_contextual): B0=0.0000 → B7=0.8400 (+0.8400)
- **C.de_novo_status** (complex_evidence): B0=0.0000 → B7=0.4396 (+0.4396)

## 6. Fields Where SYSTEM Still Wins vs B7-expanded

- **A.functional_domain_or_hotspot** (simple_explicit): SYSTEM=0.1569 vs B7=0.0000 (Δ=+0.1569)
- **B.disease_diagnosis** (simple_explicit): SYSTEM=0.9718 vs B7=0.9353 (Δ=+0.0365)

## 7. SYSTEM vs B7-expanded Statistical Significance

| Group | ΔF1 (mean) | 95% CI | p-value | Sig |
|---|---|---|---|---|
| merged_73 | -0.0417 | [-0.1024, +0.0230] | 0.2066 | ✗ |
| rett_53 | -0.0276 | [-0.0773, +0.0267] | 0.2980 | ✗ |
| parkinson_20 | -0.0789 | [-0.2570, +0.1115] | 0.4166 | ✗ |
| merged_simple_explicit | -0.0267 | [-0.0946, +0.0469] | 0.4846 | ✗ |
| merged_medium_contextual | -0.1539 | [-0.2434, -0.0681] | 0.0008 | ✓ |
| merged_complex_evidence | -0.1644 | [-0.2603, -0.0822] | 0.0002 | ✓ |

## 8. Paper-Ready Interpretation

SYSTEM does NOT outperform B7-expanded on overall F1.

ΔF1=-0.0417, p=0.2066.

The expanded single-prompt baseline matches or exceeds the pipeline. Paper framing should shift to emphasize auditability, cross-lingual robustness, and source grounding as the pipeline's differentiators rather than aggregate F1.