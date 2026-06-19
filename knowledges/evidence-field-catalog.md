# ACMG/AMP + ClinGen GDV Evidence Field Catalog

> Complete catalog of literature-extractable and cross-paper GDV evidence fields across **11 categories (A-K)** for ACMG/AMP variant interpretation and ClinGen Gene-Disease Validity assessment.

**Source:** ACMG/AMP 2015 (Richards et al.), ClinGen SVI 2019 (Brnich et al.), ClinGen GDV SOP v12.

**Schema version:** 2.0.0  
**Total fields:** 166  
**Literature-extractable (A-J):** 141  
**Cross-paper GDV curation (K):** 20  
**Categories:** 11 (A-K)  
**ACMG criteria covered:** 28 / 28

## Table of Contents

- [Category A: Variant Information](#category-a-variant-information) (22 fields)
- [Category B: Case/Phenotype Information](#category-b-case-phenotype-information) (19 fields)
- [Category C: Segregation/Family Information](#category-c-segregation-family-information) (17 fields)
- [Category D: Population/Frequency Information](#category-d-population-frequency-information) (8 fields)
- [Category E: Computational/Prediction Evidence](#category-e-computational-prediction-evidence) (7 fields)
- [Category F: Functional Evidence](#category-f-functional-evidence) (24 fields)
- [Category G: Case-Control Evidence](#category-g-case-control-evidence) (15 fields)
- [Category H: Contradiction/Exclusion Evidence](#category-h-contradiction-exclusion-evidence) (9 fields)
- [Category I: Gene Function/Experimental Evidence](#category-i-gene-function-experimental-evidence) (16 fields)
- [Category J: Authority/Time Validity](#category-j-authority-time-validity) (6 fields)
- [Category K: Gene-Disease Validity Curation](#category-k-gene-disease-validity-curation) (23 fields)
- [ACMG Criteria Coverage](#acmg-criteria-coverage)
- [Extraction Groups](#extraction-groups)
- [Field Schema](#field-schema)
- [Required-for-Scorable Fields](#required-for-scorable-fields)
- [Source References](#source-references)
- [Related Documents](#related-documents)

## Category Summary

| ID | Category | Fields | Scope |
|----|----------|-------:|-------|
| A | Variant Information | 22 | literature + db-lookup |
| B | Case/Phenotype Information | 19 | literature-extractable |
| C | Segregation/Family Information | 17 | literature-extractable |
| D | Population/Frequency Information | 8 | literature-extractable |
| E | Computational/Prediction Evidence | 7 | literature-extractable |
| F | Functional Evidence | 24 | literature-extractable |
| G | Case-Control Evidence | 15 | literature-extractable |
| H | Contradiction/Exclusion Evidence | 9 | literature-extractable |
| I | Gene Function/Experimental Evidence | 16 | literature-extractable |
| J | Authority/Time Validity | 6 | literature-extractable |
| K | Gene-Disease Validity Curation | 23 | cross-paper curation |
| | **Total** | **166** | 121 lit + 45 cur |

## Category A: Variant Information

22 fields — extraction group: **high_signal**

| Field ID | Name | Description | ACMG Codes | ClinGen Module | Required |
|----------|------|-------------|------------|----------------|:--------:|
| `A.gene_symbol` | Gene symbol | Gene symbol | PVS1, PP2, BP1 | variant_evidence | ✓ |
| `A.gene_aliases` | Gene aliases or old names | Gene aliases or old names | — | variant_evidence |  |
| `A.gene_disease_relationship` | Reported gene-disease relationship | Reported gene-disease relationship | PP4 | variant_evidence |  |
| `A.transcript_id` | Transcript ID | Transcript ID | — | variant_evidence |  |
| `A.reference_sequence` | Reference sequence or genome build | Reference sequence or genome build | — | variant_evidence |  |
| `A.variant_hgvs_c` | HGVS coding variant | HGVS coding variant | PS1, PM5 | variant_evidence | ✓ |
| `A.variant_hgvs_p` | HGVS protein variant | HGVS protein variant | PS1, PM5 | variant_evidence | ✓ |
| `A.variant_hgvs_g` | HGVS genomic variant | HGVS genomic variant | — | variant_evidence |  |
| `A.variant_legacy_name` | Legacy or traditional variant name | Legacy or traditional variant name | — | variant_evidence |  |
| `A.variant_type` | Variant type | Variant type | PVS1, BP1, BP7 | variant_evidence |  |
| `A.null_variant_detail` | Null variant detail and LoF context | Null variant detail and LoF context | PVS1 | variant_evidence |  |
| `A.protein_effect` | Protein effect description | Protein effect description | PM4, BP3, BP7 | variant_evidence |  |
| `A.same_amino_acid_known_variant` | Same amino acid as known pathogenic variant | Same amino acid as known pathogenic variant | PS1 | variant_evidence |  |
| `A.same_residue_other_missense` | Same residue different missense pathogenic reference | Same residue different missense pathogenic reference | PM5 | variant_evidence |  |
| `A.functional_domain_or_hotspot` | Functional domain or mutational hotspot | Functional domain or mutational hotspot | PM1 | variant_evidence |  |
| `A.protein_length_change` | Protein length change | Protein length change | PM4 | variant_evidence |  |
| `A.repeat_region_status` | Repeat region status | Repeat region status | BP3 | variant_evidence |  |
| `A.splice_or_synonymous_effect` | Synonymous or splice effect statement | Synonymous or splice effect statement | BP7 | variant_evidence |  |
| `A.gene_missense_constraint` | Gene missense constraint evidence | Gene-level missense intolerance evidence (e.g. gnomAD missense Z-score, obs/exp ratio). Requires external database lookup, not directly stated in literature. (PP2) | PP2 | variant_evidence |  |
| `A.gene_truncating_mechanism_evidence` | Gene truncating mechanism evidence | Evidence that gene disease mechanism is primarily through truncating/LOF variants (e.g. ClinGen curation, LOEUF). Requires external database lookup. (BP1) | BP1 | variant_evidence |  |
| `A.variant_consequence_class` | Variant consequence class (GDV) | Predicted null vs other variant with gene impact vs gain-of-function (GDV-12) | PVS1, BP1 | variant_evidence |  |
| `A.identity_by_descent_variant` | Identity-by-descent or founder variant | Known founder variant in specific population (GDV-12 p24) | — | population |  |

## Category B: Case/Phenotype Information

19 fields — extraction group: **high_signal**

| Field ID | Name | Description | ACMG Codes | ClinGen Module | Required |
|----------|------|-------------|------------|----------------|:--------:|
| `B.proband_status` | Proband status | Proband status | — | phenotype_consistency |  |
| `B.case_count` | Independent case count | Independent case count | PS4 | case_level |  |
| `B.disease_diagnosis` | Disease diagnosis | Disease diagnosis | PP4 | phenotype_consistency | ✓ |
| `B.phenotype_specificity` | Phenotype specificity | Phenotype specificity | PP4 | phenotype_consistency |  |
| `B.hpo_terms` | HPO phenotype terms | HPO phenotype terms | PP4 | phenotype_consistency |  |
| `B.clinical_phenotypes` | Key clinical phenotypes | Key clinical phenotypes | PP4 | phenotype_consistency |  |
| `B.biochemical_markers` | Biochemical or laboratory markers | Biochemical or laboratory markers | PP4 | phenotype_consistency |  |
| `B.age_current_or_last_followup` | Current or last follow-up age | Current or last follow-up age | BS2 | case_level |  |
| `B.age_of_onset` | Age of onset | Age of onset | — | phenotype_consistency |  |
| `B.sex` | Sex | Sex | — | variant_evidence |  |
| `B.ancestry_or_population` | Ancestry or population | Ancestry or population | PM2, BA1, BS1 | population |  |
| `B.consanguinity` | Consanguinity | Consanguinity | PM3 | segregation |  |
| `B.mode_of_inheritance_reported` | Reported mode of inheritance | Reported mode of inheritance | PVS1, PM3, BP2 | variant_evidence |  |
| `B.single_genetic_etiology_claim` | Single genetic etiology claim | Single genetic etiology claim | PP4 | phenotype_consistency |  |
| `B.alternative_diagnosis_excluded` | Other diagnoses excluded | Other diagnoses excluded | BP5 | contradiction |  |
| `B.additional_pathogenic_variant` | Additional pathogenic variant | Additional pathogenic variant | BP5 | contradiction |  |
| `B.testing_method` | Variant testing method | Variant testing method | — | segregation |  |
| `B.sequencing_method_quality` | Sequencing method quality | Sequencing method quality | — | segregation |  |
| `B.healthy_adult_status` | Healthy adult observation | Healthy adult observation | BS2 | variant_evidence |  |

## Category C: Segregation/Family Information

17 fields — extraction group: **supporting**

| Field ID | Name | Description | ACMG Codes | ClinGen Module | Required |
|----------|------|-------------|------------|----------------|:--------:|
| `C.inheritance_source` | Inherited or de novo source | Inherited or de novo source | PS2, PM6 | variant_evidence |  |
| `C.de_novo_status` | De novo status | De novo status | PS2, PM6 | variant_evidence |  |
| `C.parentage_confirmed` | Parentage confirmation | Parentage confirmation | PS2, PM6 | variant_evidence |  |
| `C.maternal_genotype` | Maternal genotype | Maternal genotype | PS2, PM6, BS4 | segregation |  |
| `C.maternal_phenotype` | Maternal phenotype | Maternal phenotype | PS2, PM6, BS4 | segregation |  |
| `C.paternal_genotype` | Paternal genotype | Paternal genotype | PS2, PM6, BS4 | segregation |  |
| `C.paternal_phenotype` | Paternal phenotype | Paternal phenotype | PS2, PM6, BS4 | segregation |  |
| `C.phase_status` | Phase status | Phase status | PM3, BP2 | variant_evidence |  |
| `C.in_trans_confirmation` | In trans confirmation | In trans confirmation | PM3 | variant_evidence |  |
| `C.cis_or_trans_context` | Cis or trans context | Cis or trans context | BP2 | variant_evidence |  |
| `C.g_plus_p_plus_count` | G+/P+ count | G+/P+ count | PP1 | segregation |  |
| `C.g_plus_p_minus_count` | G+/P- count | G+/P- count | BS4 | segregation |  |
| `C.g_minus_p_plus_count` | G-/P+ count | G-/P+ count | BS4 | segregation |  |
| `C.g_minus_p_minus_count` | G-/P- count | G-/P- count | — | segregation |  |
| `C.obligate_carriers` | Obligate carriers | Obligate carriers | PP1 | segregation |  |
| `C.lod_score` | LOD score | LOD score | PP1 | segregation |  |
| `C.de_novo_without_parentage_confirmation` | De novo without full parentage confirmation | De novo without full parentage confirmation (PM6: assumed de novo, but without confirmation of paternity and maternity) | PM6 | variant_evidence |  |

## Category D: Population/Frequency Information

8 fields — extraction group: **high_signal**

| Field ID | Name | Description | ACMG Codes | ClinGen Module | Required |
|----------|------|-------------|------------|----------------|:--------:|
| `D.population_database_name` | Population database name | Population database name | PM2, BA1, BS1 | variant_evidence |  |
| `D.allele_frequency` | Allele frequency | Allele frequency | PM2, BA1, BS1 | variant_evidence | ✓ |
| `D.allele_count` | Allele count | Allele count | PM2, BA1, BS1 | variant_evidence |  |
| `D.allele_number` | Allele number | Allele number | PM2, BA1, BS1 | variant_evidence |  |
| `D.homozygote_count` | Homozygote count | Homozygote count | BS2 | variant_evidence |  |
| `D.population_subgroup` | Population subgroup | Population subgroup | PM2, BA1, BS1 | variant_evidence |  |
| `D.absent_or_rare_statement` | Absent or rare population statement | Absent or rare population statement | PM2 | variant_evidence |  |
| `D.healthy_carrier_observation` | Healthy carrier population observation | Healthy carrier population observation | BS2 | variant_evidence |  |

## Category E: Computational/Prediction Evidence

7 fields — extraction group: **high_signal**

| Field ID | Name | Description | ACMG Codes | ClinGen Module | Required |
|----------|------|-------------|------------|----------------|:--------:|
| `E.prediction_tools_list` | Prediction tools list | Prediction tools list | PP3, BP4 | computational |  |
| `E.deleterious_prediction_summary` | Deleterious prediction summary | Deleterious prediction summary | PP3 | computational |  |
| `E.benign_prediction_summary` | Benign prediction summary | Benign prediction summary | BP4 | computational |  |
| `E.splice_prediction` | Splice prediction | Splice prediction | PP3, BP4 | computational |  |
| `E.conservation_score` | Conservation score | Conservation score | PP3, BP4 | computational |  |
| `E.in_silico_consensus` | In silico consensus | In silico consensus | PP3, BP4 | computational |  |
| `E.prediction_conflict` | Computational prediction conflict | Computational prediction conflict | PP3, BP4 | computational |  |

## Category F: Functional Evidence

24 fields — extraction group: **supporting**

| Field ID | Name | Description | ACMG Codes | ClinGen Module | Required |
|----------|------|-------------|------------|----------------|:--------:|
| `F.assay_id` | Functional assay identifier | Functional assay identifier | PS3, BS3 | functional_alteration |  |
| `F.assay_type` | Functional assay type | Functional assay type | PS3, BS3 | functional_alteration |  |
| `F.assay_system` | Functional assay system | Functional assay system | PS3, BS3 | functional_alteration |  |
| `F.tested_variant` | Tested variant | Tested variant | PS3, BS3 | functional_alteration |  |
| `F.functional_result` | Functional result | Functional result | PS3, BS3 | functional_alteration |  |
| `F.quantitative_result` | Quantitative functional result | Quantitative functional result | PS3, BS3 | functional_alteration |  |
| `F.positive_controls` | Positive controls | Positive controls | PS3, BS3 | functional_alteration |  |
| `F.negative_controls` | Negative controls | Negative controls | PS3, BS3 | functional_alteration |  |
| `F.total_controls` | Total positive plus benign controls | Total positive plus benign controls | PS3, BS3 | functional_alteration |  |
| `F.control_quality` | Control quality | Quality of both experimental controls (wild-type/null demonstrating assay dynamic range) and clinical validation controls (known pathogenic/benign variants with independent classifications). SVI distinguishes these two types; experimental controls demonstrate dynamic range while validation controls determine OddsPath (ACMG 2019 SVI) | PS3, BS3 | functional_alteration |  |
| `F.replicates_or_statistics` | Replicates or functional statistics | Replicates or functional statistics | PS3, BS3 | functional_alteration |  |
| `F.patient_cell_evidence` | Patient-cell functional evidence | Patient-cell functional evidence | PS3, BS3 | functional_alteration |  |
| `F.non_patient_cell_evidence` | Non-patient-cell functional evidence | Non-patient-cell functional evidence | PS3, BS3 | functional_alteration |  |
| `F.functional_normal_result` | Functional normal result | Functional normal result | BS3 | functional_alteration |  |
| `F.functional_inconclusive_result` | Functional inconclusive result | Functional inconclusive result | — | functional_alteration |  |
| `F.odds_path` | Odds of pathogenicity (OddsPath) | Calculated OddsPath from functional assay validation (ACMG 2019 SVI Table 3) | PS3, BS3 | functional_alteration |  |
| `F.evidence_strength_tier` | PS3/BS3 evidence strength tier | PS3_supporting (OddsPath >2.1) / PS3_moderate (>4.3) / PS3 (>18.7) / PS3_very_strong (>350) / BS3_supporting (<0.48) / BS3_moderate (<0.23) / BS3_strong (<0.053). Note: BS3_strong is the SVI strong-level equivalent, distinct from the generic ACMG BS3 code (ACMG 2019 SVI Table 3) | PS3, BS3 | functional_alteration |  |
| `F.physiologic_context` | Physiologic context of assay | Patient-derived material vs model organism vs in vitro cellular system (ACMG 2019 SVI Rec 1-2) | PS3, BS3 | functional_alteration |  |
| `F.declared_disease_mechanism` | Declared disease mechanism | Loss-of-function / gain-of-function / dominant-negative. Prerequisite for Step 1 consistency check; F.disease_mechanism_consistency compares assay against this (ACMG 2019 SVI Step 1 Table 2) | PS3, BS3 | functional_alteration |  |
| `F.molecular_consequence` | Molecular consequence of variant on assay | NMD-escaped / splicing impact / protein truncation / missense in assay context (ACMG 2019 SVI Rec 3) | PS3, BS3 | functional_alteration |  |
| `F.disease_mechanism_consistency` | Disease mechanism consistency | Whether assay models LoF / GoF / dominant-negative consistent with known disease mechanism (ACMG 2019 SVI Step 1) | PS3, BS3 | functional_alteration |  |
| `F.assay_validation_method` | Assay validation method | Three qualifying paths per SVI Step 3 Fig 2: (a) supporting: controls + replicates but <=10 validation controls or historically accepted assay; (b) moderate: >=11 validation controls (mix of benign/pathogenic) without formal OddsPath; (c) formal OddsPath calculated at any strength tier (ACMG 2019 SVI Step 3) | PS3, BS3 | functional_alteration |  |
| `F.allelic_series_size` | Allelic series validation control count | Total classified variant controls for validation; must include a mix of benign AND pathogenic variants; >=11 total required for moderate-level evidence (ACMG 2019 SVI Step 3) | PS3, BS3 | functional_alteration |  |
| `F.clia_laboratory_status` | CLIA laboratory status | Whether assay performed in CLIA laboratory or with commercially available kit (ACMG 2019 SVI Rec 5) | PS3, BS3 | functional_alteration |  |

## Category G: Case-Control Evidence

15 fields — extraction group: **supporting**

| Field ID | Name | Description | ACMG Codes | ClinGen Module | Required |
|----------|------|-------------|------------|----------------|:--------:|
| `G.study_design` | Case-control study design | Case-control study design | PS4 | case_control |  |
| `G.case_count` | Case-control case count | Case-control case count | PS4 | case_control |  |
| `G.control_count` | Case-control control count | Case-control control count | PS4 | case_control |  |
| `G.case_definition` | Case definition | Case definition | PS4 | case_control |  |
| `G.control_matching` | Control matching quality | Control matching quality | PS4 | case_control |  |
| `G.variant_count_cases` | Variant count in cases | Variant count in cases | PS4 | case_control |  |
| `G.variant_count_controls` | Variant count in controls | Variant count in controls | PS4 | case_control |  |
| `G.odds_ratio` | Odds ratio | Odds ratio | PS4 | case_control |  |
| `G.confidence_interval` | Confidence interval | Confidence interval | PS4 | case_control |  |
| `G.p_value` | P-value | P-value | PS4 | case_control |  |
| `G.statistical_method` | Statistical method | Statistical method | PS4 | case_control |  |
| `G.case_control_negative_result` | Negative case-control result | Negative case-control result | — | contradiction |  |
| `G.case_control_status` | Case-control scoring status (GDV) | Score / Contradicts / Review status per GDV-12 p39 | PS4 | case_control |  |
| `G.detection_methodology_quality` | Detection methodology equivalence (GDV) | Whether cases and controls analyzed using methods with equivalent analytical performance (GDV-12 p39) | PS4 | case_control |  |
| `G.bias_confounding_factors` | Bias and confounding factors (GDV) | Selection bias, demographic matching, genetic ancestry control (GDV-12 p39) | PS4 | case_control |  |

## Category H: Contradiction/Exclusion Evidence

9 fields — extraction group: **supporting**

| Field ID | Name | Description | ACMG Codes | ClinGen Module | Required |
|----------|------|-------------|------------|----------------|:--------:|
| `H.misdiagnosis_or_reclassification` | Misdiagnosis or reclassification | Misdiagnosis or reclassification | BP5 | contradiction |  |
| `H.alternative_causative_gene` | Alternative causative gene | Alternative causative gene | BP5 | contradiction |  |
| `H.other_pathogenic_variant` | Other pathogenic variant | Other pathogenic variant | BP5 | contradiction |  |
| `H.non_segregation` | Non-segregation | Non-segregation | BS4 | contradiction |  |
| `H.healthy_carrier_contradiction` | Healthy carrier contradiction | Healthy carrier contradiction | BS2 | contradiction |  |
| `H.negative_functional_result` | Negative functional result | Negative functional result | BS3 | contradiction |  |
| `H.animal_model_no_phenotype` | Animal model no phenotype | Animal model no phenotype | — | contradiction |  |
| `H.contradiction_type` | Contradictory evidence type (GDV) | MAF too high / non-significant CC / non-replicated / non-segregation / non-supporting functional (GDV-12 p46) | BS1, BS4 | contradiction |  |
| `H.contradiction_severity` | Contradiction severity level (GDV) | Disputed vs Refuted severity assessment (GDV-12 p5-8) | — | contradiction |  |

## Category I: Gene Function/Experimental Evidence

16 fields — extraction group: **supporting**

| Field ID | Name | Description | ACMG Codes | ClinGen Module | Required |
|----------|------|-------------|------------|----------------|:--------:|
| `I.gene_function_biochemical` | Biochemical gene function evidence | Biochemical gene function evidence | — | function |  |
| `I.gene_function_protein_interaction` | Protein interaction evidence | Protein interaction evidence | — | function |  |
| `I.gene_expression_pattern` | Gene expression pattern | Gene expression pattern | — | function |  |
| `I.disease_relevant_expression` | Disease-relevant expression | Disease-relevant expression | — | function |  |
| `I.functional_alteration_patient_cells` | Patient-cell functional alteration | Patient-cell functional alteration | — | functional_alteration |  |
| `I.functional_alteration_non_patient_cells` | Non-patient-cell functional alteration | Non-patient-cell functional alteration | — | functional_alteration |  |
| `I.animal_model_type` | Animal model type | Animal model type | — | models |  |
| `I.animal_model_phenotype` | Animal model phenotype | Animal model phenotype | — | models |  |
| `I.animal_model_genotype` | Animal model genotype | Animal model genotype | — | models |  |
| `I.cell_model_type` | Cell model type | Cell model type | — | models |  |
| `I.cell_model_phenotype` | Cell model phenotype | Cell model phenotype | — | models |  |
| `I.human_rescue_experiment` | Human rescue experiment | Human rescue experiment | — | rescue |  |
| `I.animal_rescue_experiment` | Animal rescue experiment | Animal rescue experiment | — | rescue |  |
| `I.cell_rescue_experiment` | Cell rescue experiment | Cell rescue experiment | — | rescue |  |
| `I.rescue_result` | Rescue result | Rescue result | — | rescue |  |
| `I.experimental_replication` | Experimental replication | Experimental replication | — | function |  |

## Category J: Authority/Time Validity

6 fields — extraction group: **high_signal**

| Field ID | Name | Description | ACMG Codes | ClinGen Module | Required |
|----------|------|-------------|------------|----------------|:--------:|
| `J.clinvar_assertion` | ClinVar assertion | ClinVar assertion | PP5, BP6 | time_validity |  |
| `J.expert_panel_assertion` | Expert panel assertion | Expert panel assertion | PP5, BP6 | time_validity |  |
| `J.authority_classification` | Authority classification | Authority classification | PP5, BP6 | time_validity |  |
| `J.known_pathogenic_variant_reference` | Known pathogenic variant reference | Known pathogenic variant reference | PS1, PM5 | time_validity |  |
| `J.ps1_pm5_relationship` | PS1 or PM5 relationship to current variant | PS1 or PM5 relationship to current variant | PS1, PM5 | time_validity |  |
| `J.reputable_benign_assertion` | Reputable source benign assertion without shared data | Reputable source recently reports variant as benign, but evidence is not available for independent evaluation (BP6) | BP6 | time_validity |  |

## Category K: Gene-Disease Validity Curation

23 fields — extraction group: **curation**

| Field ID | Name | Description | ACMG Codes | ClinGen Module | Required |
|----------|------|-------------|------------|----------------|:--------:|
| `K.mode_of_inheritance` | Mode of inheritance | AD / AR / SD / XL / Mitochondrial / Somatic Mosaicism / Undetermined (GDV-12 Table 1) | — | gene_disease_validity |  |
| `K.disease_entity_mondo` | Disease entity MONDO ID | Monarch Disease Ontology identifier for curated disease entity (GDV-12 p10) | — | gene_disease_validity |  |
| `K.disease_name` | Disease name | Curated disease name per ClinGen naming conventions (GDV-12 p10) | — | gene_disease_validity |  |
| `K.disease_prevalence` | Disease prevalence | Disease prevalence used for frequency threshold derivation (GDV-12 p36) | — | gene_disease_validity |  |
| `K.precuration_id` | Precuration identifier | Precuration ID from GeneTracker required for new GCI records (GDV-12 p10) | — | gene_disease_validity |  |
| `K.gene_disease_validity_classification` | Gene-disease validity classification | Definitive / Strong / Moderate / Limited / Disputed / Refuted / No Known Disease Relationship (GDV-12 p5-8) | — | gene_disease_validity |  |
| `K.replication_over_time_flag` | Replication over time flag | >2 independent publications over >3 years (GDV-12 Figure 9 col D) | — | gene_disease_validity |  |
| `K.genetic_evidence_total_score` | Genetic evidence total score | 0-12 points from case-level + segregation + case-control data (GDV-12 Figure 2) | — | gene_disease_validity |  |
| `K.experimental_evidence_total_score` | Experimental evidence total score | 0-6 points from function + functional alteration + models + rescue (GDV-12 Figure 8) | — | gene_disease_validity |  |
| `K.calculated_total_score` | Calculated total score | 0-18 points sum of genetic + experimental evidence (GDV-12 Figure 9 col C) | — | gene_disease_validity |  |
| `K.modified_classification` | Modified classification | Manual override of calculated classification by expert panel (GDV-12 p49) | — | gene_disease_validity |  |
| `K.curator_classification` | Curator classification | Curator-assigned classification before expert panel approval (GDV-12 Figure 9 col F) | — | gene_disease_validity |  |
| `K.final_published_classification` | Final published classification | Approved classification published to clinicalgenome.org (GDV-12 Figure 9 col G) | — | gene_disease_validity |  |
| `K.gcep_affiliation` | GCEP affiliation | Gene Curation Expert Panel affiliation (GDV-12 p4) | — | gene_disease_validity |  |
| `K.curation_version` | Curation version | Version number of published classification (GDV-12 p49) | — | gene_disease_validity |  |
| `K.independent_publication_count` | Independent publication count | Number of independent publications for replication assessment (GDV-12 p47) | — | gene_disease_validity |  |
| `K.years_since_original_publication` | Years since original publication | Time span from original gene-disease assertion for replication (>3 years required) (GDV-12 p47) | — | gene_disease_validity |  |
| `K.pmid` | PubMed ID | PMID of evidence source publication (GDV-12 p12) | — | gene_disease_validity |  |
| `K.publication_date` | Publication date | Publication date for replication over time assessment (GDV-12 p47) | — | gene_disease_validity |  |
| `K.original_assertion_pmid` | Original assertion PMID | PMID of first publication asserting gene-disease relationship (GDV-12 p15) | — | gene_disease_validity |  |
| `K.valid_contradictory_evidence_flag` | Valid contradictory evidence flag | Whether valid contradictory evidence exists for this gene-disease curation (GDV-12 Figure 9 row E) | — | gene_disease_validity |  |
| `K.contradictory_evidence_pmids` | Contradictory evidence PMIDs | PMIDs and description of contradictory evidence at curation level (GDV-12 Figure 9 row E) | — | gene_disease_validity |  |
| `K.modified_classification_rationale` | Modified classification rationale | Required free-text rationale when expert panel overrides calculated classification (GDV-12 p49) | — | gene_disease_validity |  |

## ACMG Criteria Coverage

All 28 standard ACMG/AMP criteria are mapped to catalog fields:

| ACMG Code | Strength | Direction | Field Count | Field IDs |
|-----------|----------|-----------|:-----------:|-----------|
| **PVS1** | Very strong | Pathogenic | 5 | `A.gene_symbol`, `A.variant_type`, `A.null_variant_detail`, `A.variant_consequence_class`, `B.mode_of_inheritance_reported` |
| **PS1** | Strong | Pathogenic | 5 | `A.variant_hgvs_c`, `A.variant_hgvs_p`, `A.same_amino_acid_known_variant`, `J.known_pathogenic_variant_reference`, `J.ps1_pm5_relationship` |
| **PS2** | Strong | Pathogenic | 7 | `C.inheritance_source`, `C.de_novo_status`, `C.parentage_confirmed`, `C.maternal_genotype`, `C.maternal_phenotype`, `C.paternal_genotype`, `C.paternal_phenotype` |
| **PS3** | Strong | Pathogenic | 22 | `F.assay_id`, `F.assay_type`, `F.assay_system`, `F.tested_variant`, `F.functional_result`, `F.quantitative_result`, `F.positive_controls`, `F.negative_controls`, `F.total_controls`, `F.control_quality`, `F.replicates_or_statistics`, `F.patient_cell_evidence`, `F.non_patient_cell_evidence`, `F.odds_path`, `F.evidence_strength_tier`, `F.physiologic_context`, `F.declared_disease_mechanism`, `F.molecular_consequence`, `F.disease_mechanism_consistency`, `F.assay_validation_method`, `F.allelic_series_size`, `F.clia_laboratory_status` |
| **PS4** | Strong | Pathogenic | 15 | `B.case_count`, `G.study_design`, `G.case_count`, `G.control_count`, `G.case_definition`, `G.control_matching`, `G.variant_count_cases`, `G.variant_count_controls`, `G.odds_ratio`, `G.confidence_interval`, `G.p_value`, `G.statistical_method`, `G.case_control_status`, `G.detection_methodology_quality`, `G.bias_confounding_factors` |
| **PM1** | Moderate | Pathogenic | 1 | `A.functional_domain_or_hotspot` |
| **PM2** | Moderate | Pathogenic | 7 | `B.ancestry_or_population`, `D.population_database_name`, `D.allele_frequency`, `D.allele_count`, `D.allele_number`, `D.population_subgroup`, `D.absent_or_rare_statement` |
| **PM3** | Moderate | Pathogenic | 4 | `B.consanguinity`, `B.mode_of_inheritance_reported`, `C.phase_status`, `C.in_trans_confirmation` |
| **PM4** | Moderate | Pathogenic | 2 | `A.protein_effect`, `A.protein_length_change` |
| **PM5** | Moderate | Pathogenic | 5 | `A.variant_hgvs_c`, `A.variant_hgvs_p`, `A.same_residue_other_missense`, `J.known_pathogenic_variant_reference`, `J.ps1_pm5_relationship` |
| **PM6** | Moderate | Pathogenic | 8 | `C.inheritance_source`, `C.de_novo_status`, `C.parentage_confirmed`, `C.maternal_genotype`, `C.maternal_phenotype`, `C.paternal_genotype`, `C.paternal_phenotype`, `C.de_novo_without_parentage_confirmation` |
| **PP1** | Supporting | Pathogenic | 3 | `C.g_plus_p_plus_count`, `C.obligate_carriers`, `C.lod_score` |
| **PP2** | Supporting | Pathogenic | 2 | `A.gene_symbol`, `A.gene_missense_constraint` |
| **PP3** | Supporting | Pathogenic | 6 | `E.prediction_tools_list`, `E.deleterious_prediction_summary`, `E.splice_prediction`, `E.conservation_score`, `E.in_silico_consensus`, `E.prediction_conflict` |
| **PP4** | Supporting | Pathogenic | 7 | `A.gene_disease_relationship`, `B.disease_diagnosis`, `B.phenotype_specificity`, `B.hpo_terms`, `B.clinical_phenotypes`, `B.biochemical_markers`, `B.single_genetic_etiology_claim` |
| **PP5** | Supporting | Pathogenic | 3 | `J.clinvar_assertion`, `J.expert_panel_assertion`, `J.authority_classification` |
| **BA1** | Stand-alone | Benign | 6 | `B.ancestry_or_population`, `D.population_database_name`, `D.allele_frequency`, `D.allele_count`, `D.allele_number`, `D.population_subgroup` |
| **BS1** | Strong | Benign | 7 | `B.ancestry_or_population`, `D.population_database_name`, `D.allele_frequency`, `D.allele_count`, `D.allele_number`, `D.population_subgroup`, `H.contradiction_type` |
| **BS2** | Strong | Benign | 5 | `B.age_current_or_last_followup`, `B.healthy_adult_status`, `D.homozygote_count`, `D.healthy_carrier_observation`, `H.healthy_carrier_contradiction` |
| **BS3** | Strong | Benign | 24 | `F.assay_id`, `F.assay_type`, `F.assay_system`, `F.tested_variant`, `F.functional_result`, `F.quantitative_result`, `F.positive_controls`, `F.negative_controls`, `F.total_controls`, `F.control_quality`, `F.replicates_or_statistics`, `F.patient_cell_evidence`, `F.non_patient_cell_evidence`, `F.functional_normal_result`, `F.odds_path`, `F.evidence_strength_tier`, `F.physiologic_context`, `F.declared_disease_mechanism`, `F.molecular_consequence`, `F.disease_mechanism_consistency`, `F.assay_validation_method`, `F.allelic_series_size`, `F.clia_laboratory_status`, `H.negative_functional_result` |
| **BS4** | Strong | Benign | 8 | `C.maternal_genotype`, `C.maternal_phenotype`, `C.paternal_genotype`, `C.paternal_phenotype`, `C.g_plus_p_minus_count`, `C.g_minus_p_plus_count`, `H.non_segregation`, `H.contradiction_type` |
| **BP1** | Supporting | Benign | 4 | `A.gene_symbol`, `A.variant_type`, `A.gene_truncating_mechanism_evidence`, `A.variant_consequence_class` |
| **BP2** | Supporting | Benign | 3 | `B.mode_of_inheritance_reported`, `C.phase_status`, `C.cis_or_trans_context` |
| **BP3** | Supporting | Benign | 2 | `A.protein_effect`, `A.repeat_region_status` |
| **BP4** | Supporting | Benign | 6 | `E.prediction_tools_list`, `E.benign_prediction_summary`, `E.splice_prediction`, `E.conservation_score`, `E.in_silico_consensus`, `E.prediction_conflict` |
| **BP5** | Supporting | Benign | 5 | `B.alternative_diagnosis_excluded`, `B.additional_pathogenic_variant`, `H.misdiagnosis_or_reclassification`, `H.alternative_causative_gene`, `H.other_pathogenic_variant` |
| **BP6** | Supporting | Benign | 4 | `J.clinvar_assertion`, `J.expert_panel_assertion`, `J.authority_classification`, `J.reputable_benign_assertion` |
| **BP7** | Supporting | Benign | 3 | `A.variant_type`, `A.protein_effect`, `A.splice_or_synonymous_effect` |

## Extraction Groups

The 166-field catalog is organized into **4 extraction groups** — 3 active in the single-document LLM pipeline, 1 externalized to the GDV cross-paper curation service.

### Active Groups (single-document pipeline)

| Group | Categories | Fields | Skip Condition (evidence_map) |
|-------|-----------|--------|-------------------------------|
| `high_signal` | A, B, D, E, J | 62 | Never skipped |
| `segregation_functional` | C, F | 41 | Skip if no case/family references AND no functional assay signals |
| `case_control_gene` | G, H, I | 40 | Skip if no case-control data AND no contradiction signals |

### `high_signal` — 62 fields

**Categories:** A (22), B (19), D (8), E (7), J (6)  
**Description:** Variant identity, case/phenotype, population frequency, computational prediction, and authority fields  
**Priority:** Always extracted. Contains all 5 required-for-scorable fields.

### `segregation_functional` — 41 fields

**Categories:** C (17), F (24)  
**Description:** Family/segregation evidence and functional assay evidence (SVI OddsPath framework)  
**Skip condition:** `evidence_map.case_references` is empty AND no functional assay keywords detected

### `case_control_gene` — 40 fields

**Categories:** G (15), H (9), I (16)  
**Description:** Case-control statistical evidence, contradiction/exclusion markers, and gene-level functional context  
**Skip condition:** `evidence_map.authority_references` is empty AND no contradiction signals detected

### External Group (cross-paper curation)

### `curation` — 23 fields ⚡ External

**Categories:** K (23)  
**Description:** Gene-disease validity curation fields per GDV SOP v12 — cross-paper aggregation, NOT extractable from a single document  
**Status:** Removed from the single-document LLM extraction pipeline. Handled by the GDV cross-paper curation service (Phase 3b).  
**Fields:** `K.precuration_id`, `K.genetic_evidence_total_score`, `K.functional_evidence_total_score`, `K.total_score`, `K.replication_score`, `K.published_classification`, etc.

## Field Schema

| Attribute | Type | Description |
|-----------|------|-------------|
| `field_id` | string | Stable identifier (`<Category>.<name>`) |
| `category_id` | string | Single letter A–K (K is external-only) |
| `category_name` | string | Human-readable category name |
| `field_name` | string | Short English label |
| `description` | string | Field semantics |
| `acmg_codes` | string[] | Related ACMG criteria codes |
| `clingen_modules` | string[] | Related ClinGen GDV module names |
| `required_for_scorable` | bool | Required to produce a scorable variant classification |
| `priority` | enum | Extraction priority: `CRITICAL` (5) / `HIGH` (~20) / `NORMAL` (~80) / `LOW` (~61) — guides LLM output ordering |

## Required-for-Scorable Fields

Five fields are marked as required to produce a scorable variant classification:

- `A.gene_symbol` — Gene symbol
- `A.variant_hgvs_c` — HGVS coding variant
- `A.variant_hgvs_p` — HGVS protein variant
- `B.disease_diagnosis` — Disease diagnosis
- `D.allele_frequency` — Allele frequency

## Source References

| Reference | Coverage |
|-----------|----------|
| ACMG_AMP_2015 | Richards et al., Genetics in Medicine (2015) - 28 standard variant interpretation criteria |
| ClinGen_SVI_2019 | Brnich et al., Genome Medicine (2020) - PS3/BS3 OddsPath framework |
| ClinGen_GDV_v12 | ClinGen Gene Curation SOP v12 - Gene-Disease Validity Curation |

## Related Documents

- [`acmg-2015.md`](./acmg-2015.md) — ACMG/AMP 2015 guidelines
- [`acmg-2019.md`](./acmg-2019.md) — ClinGen SVI PS3/BS3 evaluation
- [`gdv-12.md`](./gdv-12.md) — ClinGen Gene-Disease Validity SOP v12
- [`acmg-2021-2026-outline.md`](./acmg-2021-2026-outline.md) — ACMG 2021-2026 developments

## Pipeline Revision (2026-06-19)

### Summary of Changes

| # | Change | Impact |
|---|--------|--------|
| P0-1 | **Remove K category from extraction** — 23 GDV curation fields moved to external service | −2 LLM calls per document (双轨) |
| P0-2 | **Split `supporting` group** (81 fields) → `segregation_functional` (41) + `case_control_gene` (40) | Max single-call fields: 81 → 62 |
| P1-1 | **evidence_map conditional skip** — skip irrelevant groups based on document signals | −30–50% LLM calls for typical papers |
| P1-2 | **Field backfill node** — fill missing fields as NOT_FOUND before quality_gate | Quality gate + benchmark denominator accuracy |
| P2-1 | **Field priority levels** — CRITICAL/HIGH/NORMAL/LOW guide LLM output ordering | Higher key_field hit rate |
| P2-2 | **special_evidence boundary** — catalog = structured fields, special = narrative evidence | Eliminate duplicate extraction |

### Before vs After: Per-Document LLM Calls

| Metric | Before | After (typical) |
|--------|--------|-----------------|
| Catalog groups per chunk | 3 (62 + 81 + 23) | 2–3 (62 + 41? + 40?) |
| Max fields per LLM call | 81 | 62 |
| Special evidence calls | 2 (双轨) | 2 (双轨, unchanged) |
| Total LLM calls (3 chunks) | 3×3×2 + 2 = 20 | 3×2.5×2 + 2 = 17 (est.) |
| Token budget per chunk | 8K (shared by 81-field group) | 8K (max 62-field group, +30% headroom) |

