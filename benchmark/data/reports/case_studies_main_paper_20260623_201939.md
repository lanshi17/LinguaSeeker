# Case Studies for BIBM Main Paper

Generated: 2026-06-23T20:19:39

## Case 1: SYSTEM extracts sex and age of onset from clinical context; B0 produces nothing

- **Dataset**: rett
- **Entry**: rett_003
- **Fields**: B.sex, B.age_of_onset
- **Difficulty**: medium_contextual

### Source Snippet

> # De novo deletion in MECP2 in a monozygotic twin pair: a case report  Kirti Mittal1 , Madhulika Kabra2 , Ramesh Juyal3 and Thelma BK1\*  ## Abstract  Background: Rett syndrome (RTT) is a severe, pro

### Extraction Comparison

| Field | Expected | SYSTEM | B0 |
|---|---|---|---|
| B.sex | female | Female (matched) | None (missing) |
| B.age_of_onset | ~2 years (regression at 2 years in young | Regression of milestones was observed fo (matched) | None (missing) |

### Analysis

The source is an English-language case report about monozygotic twins with Rett syndrome. SYSTEM's multi-track extraction identifies 'female' as patient sex and 'regression at 2 years' as age of onset from the clinical narrative. B0's single-prompt extraction does not produce these fields at all — the naive prompt focuses on gene/disease/variant and ignores contextual clinical metadata.

### Paper Paragraph

In rett_003, a case report of monozygotic twins with Rett syndrome, the pipeline extracted patient sex (Female) and age of onset (~2 years, regression after seizures) from the clinical narrative. The naive baseline produced neither field, as its single-prompt approach focuses on gene-disease-variant triads and does not request contextual metadata. This illustrates the pipeline's advantage on medium-difficulty fields requiring cross-sentence clinical reasoning.

**Suggested display**: Table: side-by-side field extraction comparison for rett_003

---

## Case 2: SYSTEM identifies de novo status from parent genotyping; B0 cannot

- **Dataset**: rett
- **Entry**: rett_004
- **Fields**: C.de_novo_status
- **Difficulty**: complex_evidence

### Source Snippet

> -- | | 患儿20C204774 | 杂合变异 | 130 | | 患儿父亲20C204776 | 无变异 | 130 | | 患儿母亲20C204775 | 无变异 | 130 | </details>  基因检测发现 MECP2 基因有 1个杂合突变，c.502C>T（p.R168X），患儿父母该位点无变异，箭头示该位点。  图2　基因检测结果  Fig. 2    Gene test results  ## 2　讨　论  RTT是一种影响儿童精神运动发育的疾病，1966年由 Andreas Rett首次发现 ，X染色体上的甲基化CpG 结合蛋白 2（MECP2）基因突变，并伴有 X 

### Extraction Comparison

| Field | Expected | SYSTEM | B0 |
|---|---|---|---|
| C.de_novo_status | de novo | confirmed de novo (matched) | None (missing) |

### Analysis

The source (Chinese-language case report) states that the child has a heterozygous MECP2 mutation c.502C>T (p.R168X) and that neither parent carries the variant ('parents have no variant at this position'). SYSTEM's cross-lingual extraction identifies this as 'confirmed de novo'. B0 does not extract de novo status — this requires multi-sentence reasoning across the family genotyping table and the clinical narrative, which a single-prompt LLM does not attempt.

### Paper Paragraph

In rett_004, a Chinese-language case report, the pipeline identified the MECP2 c.502C>T (p.R168X) mutation as de novo by cross-referencing the family genotyping table (parents negative) with the clinical narrative. The baseline produced no de novo assessment, as this requires source-grounded reasoning across multiple document sections — a task that exceeds single-prompt extraction capability.

**Suggested display**: Figure: extraction flow showing cross-section reasoning for de novo status

---

## Case 3: SYSTEM extracts HGVS variant notation from Chinese biomedical text

- **Dataset**: rett
- **Entry**: rett_004
- **Fields**: A.variant_hgvs_c, A.variant_hgvs_p
- **Difficulty**: simple_explicit

### Source Snippet

> -------------- | ----- | | 患儿20C204774 | 杂合变异 | 130 | | 患儿父亲20C204776 | 无变异 | 130 | | 患儿母亲20C204775 | 无变异 | 130 | </details>  基因检测发现 MECP2 基因有 1个杂合突变，c.502C>T（p.R168X），患儿父母该位点无变异，箭头示该位点。  图2　基因检测结果  Fig. 2    Gene test results  ## 2　讨　论  RTT是一种影响儿童精神运动发育的疾病，1966年由 Andreas Rett首次发现 ，X染色体上的甲基化CpG 结合蛋白

### Extraction Comparison

| Field | Expected | SYSTEM | B0 |
|---|---|---|---|
| A.variant_hgvs_c | c.502C>T | c.502C>T (matched) | None (missing) |
| A.variant_hgvs_p | p.R168X | p.R168X (matched) | None (missing) |

### Analysis

The source is a Chinese-language paper. The variant c.502C>T (p.R168X) appears in the genotyping results section. SYSTEM's cross-lingual pipeline translates and extracts the HGVS notation precisely. B0 misses both variants — likely because the Chinese text is not processed by the English-only naive prompt, or the variant is buried in a table that the single-prompt approach does not parse.

### Paper Paragraph

In rett_004, the pipeline extracted both HGVS notations (c.502C>T, p.R168X) from a Chinese-language genotyping report. The baseline missed both variants, demonstrating that cross-lingual extraction with structured variant parsing outperforms English-only single-prompt approaches on non-English literature.

**Suggested display**: Table: variant extraction comparison across Chinese-language entries

---

## Case 4: Parkinson low-complexity dataset: B0 matches or exceeds SYSTEM on simple fields

- **Dataset**: parkinson
- **Entry**: parkinson_013
- **Fields**: A.gene_symbol, A.gene_disease_relationship, B.disease_diagnosis
- **Difficulty**: simple_explicit

### Source Snippet

> ported in these genes [17]. Highly penetrant mutations in the SNCA and LRRK2 genes are found in families with autosomal dominant inheritance, whereas autosomal recessive families with a typical PD phenotype carry mutations in the PARK2/ PARKIN, PARK6/PINK1 and PARK7/DJ-1 genes [18]. Most genetic stu

### Extraction Comparison

| Field | Expected | SYSTEM | B0 |
|---|---|---|---|
| A.gene_symbol | PRKN | PARK2 (wrong_value (PARK2 vs PRKN)) | PRKN (PARK2 / PARKIN mentioned in text) (matched) |
| A.gene_disease_relationship | associated | None (missing) | causative (matched) |
| B.disease_diagnosis | Parkinson disease | — (—) | — (—) |

### Analysis



### Paper Paragraph

In parkinson_013, a simple English-language gene association study, B0 correctly extracted the gene symbol (PRKN) and disease relationship (causative/associated), while SYSTEM extracted the alias 'PARK2' and missed the relationship field. This illustrates that on low-complexity datasets with simple explicit fields, the pipeline's multi-track reconciliation can introduce noise without compensating gains. The pipeline's primary advantage lies in medium and complex evidence extraction, not simple factual lookups.

**Suggested display**: Table: SYSTEM vs B0 on Parkinson simple fields showing B0 advantage

---

## Summary Takeaways

- Case 1 (medium contextual): Pipeline extracts sex and age of onset from clinical narratives where B0 produces nothing. These fields require cross-sentence reasoning beyond gene-disease-variant triads.
- Case 2 (complex evidence): Pipeline identifies de novo status by cross-referencing family genotyping tables with clinical narrative. B0 cannot perform multi-section reasoning.
- Case 3 (variant extraction): Pipeline extracts HGVS notation from Chinese-language biomedical text via cross-lingual processing. B0 misses variants in non-English literature.
- Case 4 (limitation): On low-complexity English datasets with simple explicit fields, B0 matches or exceeds SYSTEM. Pipeline reconciliation adds noise without compensating gains on straightforward factual lookups.
