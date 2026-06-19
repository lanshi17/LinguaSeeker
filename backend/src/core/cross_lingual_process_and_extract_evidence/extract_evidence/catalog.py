"""Static GDV/ACMG evidence field catalog."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceFieldSpec:
    field_id: str
    category_id: str
    category_name: str
    field_name: str
    description: str
    acmg_codes: tuple[str, ...] = ()
    clingen_modules: tuple[str, ...] = ()
    required_for_scorable: bool = False


EVIDENCE_FIELD_SPECS: tuple[EvidenceFieldSpec, ...] = (
    # Category A: Variant Information
    EvidenceFieldSpec("A.gene_symbol", "A", "Variant Information", "Gene symbol", "Gene symbol", ("PVS1", "PP2", "BP1"), ("variant_evidence",), True),
    EvidenceFieldSpec("A.gene_aliases", "A", "Variant Information", "Gene aliases or old names", "Gene aliases or old names", (), ("variant_evidence",)),
    EvidenceFieldSpec("A.gene_disease_relationship", "A", "Variant Information", "Reported gene-disease relationship", "Reported gene-disease relationship", ("PP4",), ("variant_evidence",)),
    EvidenceFieldSpec("A.transcript_id", "A", "Variant Information", "Transcript ID", "Transcript ID", (), ("variant_evidence",)),
    EvidenceFieldSpec("A.reference_sequence", "A", "Variant Information", "Reference sequence or genome build", "Reference sequence or genome build", (), ("variant_evidence",)),
    EvidenceFieldSpec("A.variant_hgvs_c", "A", "Variant Information", "HGVS coding variant", "HGVS coding variant", ("PS1", "PM5"), ("variant_evidence",), True),
    EvidenceFieldSpec("A.variant_hgvs_p", "A", "Variant Information", "HGVS protein variant", "HGVS protein variant", ("PS1", "PM5"), ("variant_evidence",), True),
    EvidenceFieldSpec("A.variant_hgvs_g", "A", "Variant Information", "HGVS genomic variant", "HGVS genomic variant", (), ("variant_evidence",)),
    EvidenceFieldSpec("A.variant_legacy_name", "A", "Variant Information", "Legacy or traditional variant name", "Legacy or traditional variant name", (), ("variant_evidence",)),
    EvidenceFieldSpec("A.variant_type", "A", "Variant Information", "Variant type", "Variant type", ("PVS1", "BP1", "BP7"), ("variant_evidence",)),
    EvidenceFieldSpec("A.null_variant_detail", "A", "Variant Information", "Null variant detail and LoF context", "Null variant detail and LoF context", ("PVS1",), ("variant_evidence",)),
    EvidenceFieldSpec("A.protein_effect", "A", "Variant Information", "Protein effect description", "Protein effect description", ("PM4", "BP3", "BP7"), ("variant_evidence",)),
    EvidenceFieldSpec("A.same_amino_acid_known_variant", "A", "Variant Information", "Same amino acid as known pathogenic variant", "Same amino acid as known pathogenic variant", ("PS1",), ("variant_evidence",)),
    EvidenceFieldSpec("A.same_residue_other_missense", "A", "Variant Information", "Same residue different missense pathogenic reference", "Same residue different missense pathogenic reference", ("PM5",), ("variant_evidence",)),
    EvidenceFieldSpec("A.functional_domain_or_hotspot", "A", "Variant Information", "Functional domain or mutational hotspot", "Functional domain or mutational hotspot", ("PM1",), ("variant_evidence",)),
    EvidenceFieldSpec("A.protein_length_change", "A", "Variant Information", "Protein length change", "Protein length change", ("PM4",), ("variant_evidence",)),
    EvidenceFieldSpec("A.repeat_region_status", "A", "Variant Information", "Repeat region status", "Repeat region status", ("BP3",), ("variant_evidence",)),
    EvidenceFieldSpec("A.splice_or_synonymous_effect", "A", "Variant Information", "Synonymous or splice effect statement", "Synonymous or splice effect statement", ("BP7",), ("variant_evidence",)),
    EvidenceFieldSpec("A.gene_missense_constraint", "A", "Variant Information", "Gene missense constraint evidence", "Gene-level missense intolerance evidence (e.g. gnomAD missense Z-score, obs/exp ratio). Requires external database lookup, not directly stated in literature. (PP2)", ("PP2",), ("variant_evidence",)),
    EvidenceFieldSpec("A.gene_truncating_mechanism_evidence", "A", "Variant Information", "Gene truncating mechanism evidence", "Evidence that gene disease mechanism is primarily through truncating/LOF variants (e.g. ClinGen curation, LOEUF). Requires external database lookup. (BP1)", ("BP1",), ("variant_evidence",)),
    EvidenceFieldSpec("A.variant_consequence_class", "A", "Variant Information", "Variant consequence class (GDV)", "Predicted null vs other variant with gene impact vs gain-of-function (GDV-12)", ("PVS1", "BP1"), ("variant_evidence",)),
    EvidenceFieldSpec("A.identity_by_descent_variant", "A", "Variant Information", "Identity-by-descent or founder variant", "Known founder variant in specific population (GDV-12 p24)", (), ("population",)),

    # Category B: Case/Phenotype Information
    EvidenceFieldSpec("B.proband_status", "B", "Case/Phenotype Information", "Proband status", "Proband status", (), ("phenotype_consistency",)),
    EvidenceFieldSpec("B.case_count", "B", "Case/Phenotype Information", "Independent case count", "Independent case count", ("PS4",), ("case_level",)),
    EvidenceFieldSpec("B.disease_diagnosis", "B", "Case/Phenotype Information", "Disease diagnosis", "Disease diagnosis", ("PP4",), ("phenotype_consistency",), True),
    EvidenceFieldSpec("B.phenotype_specificity", "B", "Case/Phenotype Information", "Phenotype specificity", "Phenotype specificity", ("PP4",), ("phenotype_consistency",)),
    EvidenceFieldSpec("B.hpo_terms", "B", "Case/Phenotype Information", "HPO phenotype terms", "HPO phenotype terms", ("PP4",), ("phenotype_consistency",)),
    EvidenceFieldSpec("B.clinical_phenotypes", "B", "Case/Phenotype Information", "Key clinical phenotypes", "Key clinical phenotypes", ("PP4",), ("phenotype_consistency",)),
    EvidenceFieldSpec("B.biochemical_markers", "B", "Case/Phenotype Information", "Biochemical or laboratory markers", "Biochemical or laboratory markers", ("PP4",), ("phenotype_consistency",)),
    EvidenceFieldSpec("B.age_current_or_last_followup", "B", "Case/Phenotype Information", "Current or last follow-up age", "Current or last follow-up age", ("BS2",), ("case_level",)),
    EvidenceFieldSpec("B.age_of_onset", "B", "Case/Phenotype Information", "Age of onset", "Age of onset", (), ("phenotype_consistency",)),
    EvidenceFieldSpec("B.sex", "B", "Case/Phenotype Information", "Sex", "Sex", (), ("variant_evidence",)),
    EvidenceFieldSpec("B.ancestry_or_population", "B", "Case/Phenotype Information", "Ancestry or population", "Ancestry or population", ("PM2", "BA1", "BS1"), ("population",)),
    EvidenceFieldSpec("B.consanguinity", "B", "Case/Phenotype Information", "Consanguinity", "Consanguinity", ("PM3",), ("segregation",)),
    EvidenceFieldSpec("B.mode_of_inheritance_reported", "B", "Case/Phenotype Information", "Reported mode of inheritance", "Reported mode of inheritance", ("PVS1", "PM3", "BP2"), ("variant_evidence",)),
    EvidenceFieldSpec("B.single_genetic_etiology_claim", "B", "Case/Phenotype Information", "Single genetic etiology claim", "Single genetic etiology claim", ("PP4",), ("phenotype_consistency",)),
    EvidenceFieldSpec("B.alternative_diagnosis_excluded", "B", "Case/Phenotype Information", "Other diagnoses excluded", "Other diagnoses excluded", ("BP5",), ("contradiction",)),
    EvidenceFieldSpec("B.additional_pathogenic_variant", "B", "Case/Phenotype Information", "Additional pathogenic variant", "Additional pathogenic variant", ("BP5",), ("contradiction",)),
    EvidenceFieldSpec("B.testing_method", "B", "Case/Phenotype Information", "Variant testing method", "Variant testing method", (), ("segregation",)),
    EvidenceFieldSpec("B.sequencing_method_quality", "B", "Case/Phenotype Information", "Sequencing method quality", "Sequencing method quality", (), ("segregation",)),
    EvidenceFieldSpec("B.healthy_adult_status", "B", "Case/Phenotype Information", "Healthy adult observation", "Healthy adult observation", ("BS2",), ("variant_evidence",)),

    # Category C: Segregation/Family Information
    EvidenceFieldSpec("C.inheritance_source", "C", "Segregation/Family Information", "Inherited or de novo source", "Inherited or de novo source", ("PS2", "PM6"), ("variant_evidence",)),
    EvidenceFieldSpec("C.de_novo_status", "C", "Segregation/Family Information", "De novo status", "De novo status", ("PS2", "PM6"), ("variant_evidence",)),
    EvidenceFieldSpec("C.parentage_confirmed", "C", "Segregation/Family Information", "Parentage confirmation", "Parentage confirmation", ("PS2", "PM6"), ("variant_evidence",)),
    EvidenceFieldSpec("C.maternal_genotype", "C", "Segregation/Family Information", "Maternal genotype", "Maternal genotype", ("PS2", "PM6", "BS4"), ("segregation",)),
    EvidenceFieldSpec("C.maternal_phenotype", "C", "Segregation/Family Information", "Maternal phenotype", "Maternal phenotype", ("PS2", "PM6", "BS4"), ("segregation",)),
    EvidenceFieldSpec("C.paternal_genotype", "C", "Segregation/Family Information", "Paternal genotype", "Paternal genotype", ("PS2", "PM6", "BS4"), ("segregation",)),
    EvidenceFieldSpec("C.paternal_phenotype", "C", "Segregation/Family Information", "Paternal phenotype", "Paternal phenotype", ("PS2", "PM6", "BS4"), ("segregation",)),
    EvidenceFieldSpec("C.phase_status", "C", "Segregation/Family Information", "Phase status", "Phase status", ("PM3", "BP2"), ("variant_evidence",)),
    EvidenceFieldSpec("C.in_trans_confirmation", "C", "Segregation/Family Information", "In trans confirmation", "In trans confirmation", ("PM3",), ("variant_evidence",)),
    EvidenceFieldSpec("C.cis_or_trans_context", "C", "Segregation/Family Information", "Cis or trans context", "Cis or trans context", ("BP2",), ("variant_evidence",)),
    EvidenceFieldSpec("C.g_plus_p_plus_count", "C", "Segregation/Family Information", "G+/P+ count", "G+/P+ count", ("PP1",), ("segregation",)),
    EvidenceFieldSpec("C.g_plus_p_minus_count", "C", "Segregation/Family Information", "G+/P- count", "G+/P- count", ("BS4",), ("segregation",)),
    EvidenceFieldSpec("C.g_minus_p_plus_count", "C", "Segregation/Family Information", "G-/P+ count", "G-/P+ count", ("BS4",), ("segregation",)),
    EvidenceFieldSpec("C.g_minus_p_minus_count", "C", "Segregation/Family Information", "G-/P- count", "G-/P- count", (), ("segregation",)),
    EvidenceFieldSpec("C.obligate_carriers", "C", "Segregation/Family Information", "Obligate carriers", "Obligate carriers", ("PP1",), ("segregation",)),
    EvidenceFieldSpec("C.lod_score", "C", "Segregation/Family Information", "LOD score", "LOD score", ("PP1",), ("segregation",)),
    EvidenceFieldSpec("C.de_novo_without_parentage_confirmation", "C", "Segregation/Family Information", "De novo without full parentage confirmation", "De novo without full parentage confirmation (PM6: assumed de novo, but without confirmation of paternity and maternity)", ("PM6",), ("variant_evidence",)),

    # Category D: Population/Frequency Information
    EvidenceFieldSpec("D.population_database_name", "D", "Population/Frequency Information", "Population database name", "Population database name", ("PM2", "BA1", "BS1"), ("variant_evidence",)),
    EvidenceFieldSpec("D.allele_frequency", "D", "Population/Frequency Information", "Allele frequency", "Allele frequency", ("PM2", "BA1", "BS1"), ("variant_evidence",), True),
    EvidenceFieldSpec("D.allele_count", "D", "Population/Frequency Information", "Allele count", "Allele count", ("PM2", "BA1", "BS1"), ("variant_evidence",)),
    EvidenceFieldSpec("D.allele_number", "D", "Population/Frequency Information", "Allele number", "Allele number", ("PM2", "BA1", "BS1"), ("variant_evidence",)),
    EvidenceFieldSpec("D.homozygote_count", "D", "Population/Frequency Information", "Homozygote count", "Homozygote count", ("BS2",), ("variant_evidence",)),
    EvidenceFieldSpec("D.population_subgroup", "D", "Population/Frequency Information", "Population subgroup", "Population subgroup", ("PM2", "BA1", "BS1"), ("variant_evidence",)),
    EvidenceFieldSpec("D.absent_or_rare_statement", "D", "Population/Frequency Information", "Absent or rare population statement", "Absent or rare population statement", ("PM2",), ("variant_evidence",)),
    EvidenceFieldSpec("D.healthy_carrier_observation", "D", "Population/Frequency Information", "Healthy carrier population observation", "Healthy carrier population observation", ("BS2",), ("variant_evidence",)),

    # Category E: Computational/Prediction Evidence
    EvidenceFieldSpec("E.prediction_tools_list", "E", "Computational/Prediction Evidence", "Prediction tools list", "Prediction tools list", ("PP3", "BP4"), ("computational",)),
    EvidenceFieldSpec("E.deleterious_prediction_summary", "E", "Computational/Prediction Evidence", "Deleterious prediction summary", "Deleterious prediction summary", ("PP3",), ("computational",)),
    EvidenceFieldSpec("E.benign_prediction_summary", "E", "Computational/Prediction Evidence", "Benign prediction summary", "Benign prediction summary", ("BP4",), ("computational",)),
    EvidenceFieldSpec("E.splice_prediction", "E", "Computational/Prediction Evidence", "Splice prediction", "Splice prediction", ("PP3", "BP4"), ("computational",)),
    EvidenceFieldSpec("E.conservation_score", "E", "Computational/Prediction Evidence", "Conservation score", "Conservation score", ("PP3", "BP4"), ("computational",)),
    EvidenceFieldSpec("E.in_silico_consensus", "E", "Computational/Prediction Evidence", "In silico consensus", "In silico consensus", ("PP3", "BP4"), ("computational",)),
    EvidenceFieldSpec("E.prediction_conflict", "E", "Computational/Prediction Evidence", "Computational prediction conflict", "Computational prediction conflict", ("PP3", "BP4"), ("computational",)),

    # Category F: Functional Evidence
    EvidenceFieldSpec("F.assay_id", "F", "Functional Evidence", "Functional assay identifier", "Functional assay identifier", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.assay_type", "F", "Functional Evidence", "Functional assay type", "Functional assay type", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.assay_system", "F", "Functional Evidence", "Functional assay system", "Functional assay system", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.tested_variant", "F", "Functional Evidence", "Tested variant", "Tested variant", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.functional_result", "F", "Functional Evidence", "Functional result", "Functional result", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.quantitative_result", "F", "Functional Evidence", "Quantitative functional result", "Quantitative functional result", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.positive_controls", "F", "Functional Evidence", "Positive controls", "Positive controls", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.negative_controls", "F", "Functional Evidence", "Negative controls", "Negative controls", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.total_controls", "F", "Functional Evidence", "Total positive plus benign controls", "Total positive plus benign controls", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.control_quality", "F", "Functional Evidence", "Control quality", "Quality of both experimental controls (wild-type/null demonstrating assay dynamic range) and clinical validation controls (known pathogenic/benign variants with independent classifications). SVI distinguishes these two types; experimental controls demonstrate dynamic range while validation controls determine OddsPath (ACMG 2019 SVI)", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.replicates_or_statistics", "F", "Functional Evidence", "Replicates or functional statistics", "Replicates or functional statistics", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.patient_cell_evidence", "F", "Functional Evidence", "Patient-cell functional evidence", "Patient-cell functional evidence", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.non_patient_cell_evidence", "F", "Functional Evidence", "Non-patient-cell functional evidence", "Non-patient-cell functional evidence", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.functional_normal_result", "F", "Functional Evidence", "Functional normal result", "Functional normal result", ("BS3",), ("functional_alteration",)),
    EvidenceFieldSpec("F.functional_inconclusive_result", "F", "Functional Evidence", "Functional inconclusive result", "Functional inconclusive result", (), ("functional_alteration",)),
    EvidenceFieldSpec("F.odds_path", "F", "Functional Evidence", "Odds of pathogenicity (OddsPath)", "Calculated OddsPath from functional assay validation (ACMG 2019 SVI Table 3)", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.evidence_strength_tier", "F", "Functional Evidence", "PS3/BS3 evidence strength tier", "PS3_supporting (OddsPath >2.1) / PS3_moderate (>4.3) / PS3 (>18.7) / PS3_very_strong (>350) / BS3_supporting (<0.48) / BS3_moderate (<0.23) / BS3_strong (<0.053). Note: BS3_strong is the SVI strong-level equivalent, distinct from the generic ACMG BS3 code (ACMG 2019 SVI Table 3)", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.physiologic_context", "F", "Functional Evidence", "Physiologic context of assay", "Patient-derived material vs model organism vs in vitro cellular system (ACMG 2019 SVI Rec 1-2)", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.declared_disease_mechanism", "F", "Functional Evidence", "Declared disease mechanism", "Loss-of-function / gain-of-function / dominant-negative. Prerequisite for Step 1 consistency check; F.disease_mechanism_consistency compares assay against this (ACMG 2019 SVI Step 1 Table 2)", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.molecular_consequence", "F", "Functional Evidence", "Molecular consequence of variant on assay", "NMD-escaped / splicing impact / protein truncation / missense in assay context (ACMG 2019 SVI Rec 3)", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.disease_mechanism_consistency", "F", "Functional Evidence", "Disease mechanism consistency", "Whether assay models LoF / GoF / dominant-negative consistent with known disease mechanism (ACMG 2019 SVI Step 1)", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.assay_validation_method", "F", "Functional Evidence", "Assay validation method", "Three qualifying paths per SVI Step 3 Fig 2: (a) supporting: controls + replicates but <=10 validation controls or historically accepted assay; (b) moderate: >=11 validation controls (mix of benign/pathogenic) without formal OddsPath; (c) formal OddsPath calculated at any strength tier (ACMG 2019 SVI Step 3)", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.allelic_series_size", "F", "Functional Evidence", "Allelic series validation control count", "Total classified variant controls for validation; must include a mix of benign AND pathogenic variants; >=11 total required for moderate-level evidence (ACMG 2019 SVI Step 3)", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.clia_laboratory_status", "F", "Functional Evidence", "CLIA laboratory status", "Whether assay performed in CLIA laboratory or with commercially available kit (ACMG 2019 SVI Rec 5)", ("PS3", "BS3"), ("functional_alteration",)),

    # Category G: Case-Control Evidence
    EvidenceFieldSpec("G.study_design", "G", "Case-Control Evidence", "Case-control study design", "Case-control study design", ("PS4",), ("case_control",)),
    EvidenceFieldSpec("G.case_count", "G", "Case-Control Evidence", "Case-control case count", "Case-control case count", ("PS4",), ("case_control",)),
    EvidenceFieldSpec("G.control_count", "G", "Case-Control Evidence", "Case-control control count", "Case-control control count", ("PS4",), ("case_control",)),
    EvidenceFieldSpec("G.case_definition", "G", "Case-Control Evidence", "Case definition", "Case definition", ("PS4",), ("case_control",)),
    EvidenceFieldSpec("G.control_matching", "G", "Case-Control Evidence", "Control matching quality", "Control matching quality", ("PS4",), ("case_control",)),
    EvidenceFieldSpec("G.variant_count_cases", "G", "Case-Control Evidence", "Variant count in cases", "Variant count in cases", ("PS4",), ("case_control",)),
    EvidenceFieldSpec("G.variant_count_controls", "G", "Case-Control Evidence", "Variant count in controls", "Variant count in controls", ("PS4",), ("case_control",)),
    EvidenceFieldSpec("G.odds_ratio", "G", "Case-Control Evidence", "Odds ratio", "Odds ratio", ("PS4",), ("case_control",)),
    EvidenceFieldSpec("G.confidence_interval", "G", "Case-Control Evidence", "Confidence interval", "Confidence interval", ("PS4",), ("case_control",)),
    EvidenceFieldSpec("G.p_value", "G", "Case-Control Evidence", "P-value", "P-value", ("PS4",), ("case_control",)),
    EvidenceFieldSpec("G.statistical_method", "G", "Case-Control Evidence", "Statistical method", "Statistical method", ("PS4",), ("case_control",)),
    EvidenceFieldSpec("G.case_control_negative_result", "G", "Case-Control Evidence", "Negative case-control result", "Negative case-control result", (), ("contradiction",)),
    EvidenceFieldSpec("G.case_control_status", "G", "Case-Control Evidence", "Case-control scoring status (GDV)", "Score / Contradicts / Review status per GDV-12 p39", ("PS4",), ("case_control",)),
    EvidenceFieldSpec("G.detection_methodology_quality", "G", "Case-Control Evidence", "Detection methodology equivalence (GDV)", "Whether cases and controls analyzed using methods with equivalent analytical performance (GDV-12 p39)", ("PS4",), ("case_control",)),
    EvidenceFieldSpec("G.bias_confounding_factors", "G", "Case-Control Evidence", "Bias and confounding factors (GDV)", "Selection bias, demographic matching, genetic ancestry control (GDV-12 p39)", ("PS4",), ("case_control",)),

    # Category H: Contradiction/Exclusion Evidence
    EvidenceFieldSpec("H.misdiagnosis_or_reclassification", "H", "Contradiction/Exclusion Evidence", "Misdiagnosis or reclassification", "Misdiagnosis or reclassification", ("BP5",), ("contradiction",)),
    EvidenceFieldSpec("H.alternative_causative_gene", "H", "Contradiction/Exclusion Evidence", "Alternative causative gene", "Alternative causative gene", ("BP5",), ("contradiction",)),
    EvidenceFieldSpec("H.other_pathogenic_variant", "H", "Contradiction/Exclusion Evidence", "Other pathogenic variant", "Other pathogenic variant", ("BP5",), ("contradiction",)),
    EvidenceFieldSpec("H.non_segregation", "H", "Contradiction/Exclusion Evidence", "Non-segregation", "Non-segregation", ("BS4",), ("contradiction",)),
    EvidenceFieldSpec("H.healthy_carrier_contradiction", "H", "Contradiction/Exclusion Evidence", "Healthy carrier contradiction", "Healthy carrier contradiction", ("BS2",), ("contradiction",)),
    EvidenceFieldSpec("H.negative_functional_result", "H", "Contradiction/Exclusion Evidence", "Negative functional result", "Negative functional result", ("BS3",), ("contradiction",)),
    EvidenceFieldSpec("H.animal_model_no_phenotype", "H", "Contradiction/Exclusion Evidence", "Animal model no phenotype", "Animal model no phenotype", (), ("contradiction",)),
    EvidenceFieldSpec("H.contradiction_type", "H", "Contradiction/Exclusion Evidence", "Contradictory evidence type (GDV)", "MAF too high / non-significant CC / non-replicated / non-segregation / non-supporting functional (GDV-12 p46)", ("BS1", "BS4"), ("contradiction",)),
    EvidenceFieldSpec("H.contradiction_severity", "H", "Contradiction/Exclusion Evidence", "Contradiction severity level (GDV)", "Disputed vs Refuted severity assessment (GDV-12 p5-8)", (), ("contradiction",)),

    # Category I: Gene Function/Experimental Evidence
    EvidenceFieldSpec("I.gene_function_biochemical", "I", "Gene Function/Experimental Evidence", "Biochemical gene function evidence", "Biochemical gene function evidence", (), ("function",)),
    EvidenceFieldSpec("I.gene_function_protein_interaction", "I", "Gene Function/Experimental Evidence", "Protein interaction evidence", "Protein interaction evidence", (), ("function",)),
    EvidenceFieldSpec("I.gene_expression_pattern", "I", "Gene Function/Experimental Evidence", "Gene expression pattern", "Gene expression pattern", (), ("function",)),
    EvidenceFieldSpec("I.disease_relevant_expression", "I", "Gene Function/Experimental Evidence", "Disease-relevant expression", "Disease-relevant expression", (), ("function",)),
    EvidenceFieldSpec("I.functional_alteration_patient_cells", "I", "Gene Function/Experimental Evidence", "Patient-cell functional alteration", "Patient-cell functional alteration", (), ("functional_alteration",)),
    EvidenceFieldSpec("I.functional_alteration_non_patient_cells", "I", "Gene Function/Experimental Evidence", "Non-patient-cell functional alteration", "Non-patient-cell functional alteration", (), ("functional_alteration",)),
    EvidenceFieldSpec("I.animal_model_type", "I", "Gene Function/Experimental Evidence", "Animal model type", "Animal model type", (), ("models",)),
    EvidenceFieldSpec("I.animal_model_phenotype", "I", "Gene Function/Experimental Evidence", "Animal model phenotype", "Animal model phenotype", (), ("models",)),
    EvidenceFieldSpec("I.animal_model_genotype", "I", "Gene Function/Experimental Evidence", "Animal model genotype", "Animal model genotype", (), ("models",)),
    EvidenceFieldSpec("I.cell_model_type", "I", "Gene Function/Experimental Evidence", "Cell model type", "Cell model type", (), ("models",)),
    EvidenceFieldSpec("I.cell_model_phenotype", "I", "Gene Function/Experimental Evidence", "Cell model phenotype", "Cell model phenotype", (), ("models",)),
    EvidenceFieldSpec("I.human_rescue_experiment", "I", "Gene Function/Experimental Evidence", "Human rescue experiment", "Human rescue experiment", (), ("rescue",)),
    EvidenceFieldSpec("I.animal_rescue_experiment", "I", "Gene Function/Experimental Evidence", "Animal rescue experiment", "Animal rescue experiment", (), ("rescue",)),
    EvidenceFieldSpec("I.cell_rescue_experiment", "I", "Gene Function/Experimental Evidence", "Cell rescue experiment", "Cell rescue experiment", (), ("rescue",)),
    EvidenceFieldSpec("I.rescue_result", "I", "Gene Function/Experimental Evidence", "Rescue result", "Rescue result", (), ("rescue",)),
    EvidenceFieldSpec("I.experimental_replication", "I", "Gene Function/Experimental Evidence", "Experimental replication", "Experimental replication", (), ("function",)),

    # Category J: Authority/Time Validity
    EvidenceFieldSpec("J.clinvar_assertion", "J", "Authority/Time Validity", "ClinVar assertion", "ClinVar assertion", ("PP5", "BP6"), ("time_validity",)),
    EvidenceFieldSpec("J.expert_panel_assertion", "J", "Authority/Time Validity", "Expert panel assertion", "Expert panel assertion", ("PP5", "BP6"), ("time_validity",)),
    EvidenceFieldSpec("J.authority_classification", "J", "Authority/Time Validity", "Authority classification", "Authority classification", ("PP5", "BP6"), ("time_validity",)),
    EvidenceFieldSpec("J.known_pathogenic_variant_reference", "J", "Authority/Time Validity", "Known pathogenic variant reference", "Known pathogenic variant reference", ("PS1", "PM5"), ("time_validity",)),
    EvidenceFieldSpec("J.ps1_pm5_relationship", "J", "Authority/Time Validity", "PS1 or PM5 relationship to current variant", "PS1 or PM5 relationship to current variant", ("PS1", "PM5"), ("time_validity",)),
    EvidenceFieldSpec("J.reputable_benign_assertion", "J", "Authority/Time Validity", "Reputable source benign assertion without shared data", "Reputable source recently reports variant as benign, but evidence is not available for independent evaluation (BP6)", ("BP6",), ("time_validity",)),

    # Category K: Gene-Disease Validity Curation (ClinGen GDV SOP v12)
    # Cross-paper curation fields; not single-paper extractable.
    EvidenceFieldSpec("K.mode_of_inheritance", "K", "Gene-Disease Validity Curation", "Mode of inheritance", "AD / AR / SD / XL / Mitochondrial / Somatic Mosaicism / Undetermined (GDV-12 Table 1)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.disease_entity_mondo", "K", "Gene-Disease Validity Curation", "Disease entity MONDO ID", "Monarch Disease Ontology identifier for curated disease entity (GDV-12 p10)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.disease_name", "K", "Gene-Disease Validity Curation", "Disease name", "Curated disease name per ClinGen naming conventions (GDV-12 p10)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.disease_prevalence", "K", "Gene-Disease Validity Curation", "Disease prevalence", "Disease prevalence used for frequency threshold derivation (GDV-12 p36)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.precuration_id", "K", "Gene-Disease Validity Curation", "Precuration identifier", "Precuration ID from GeneTracker required for new GCI records (GDV-12 p10)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.gene_disease_validity_classification", "K", "Gene-Disease Validity Curation", "Gene-disease validity classification", "Definitive / Strong / Moderate / Limited / Disputed / Refuted / No Known Disease Relationship (GDV-12 p5-8)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.replication_over_time_flag", "K", "Gene-Disease Validity Curation", "Replication over time flag", ">2 independent publications over >3 years (GDV-12 Figure 9 col D)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.genetic_evidence_total_score", "K", "Gene-Disease Validity Curation", "Genetic evidence total score", "0-12 points from case-level + segregation + case-control data (GDV-12 Figure 2)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.experimental_evidence_total_score", "K", "Gene-Disease Validity Curation", "Experimental evidence total score", "0-6 points from function + functional alteration + models + rescue (GDV-12 Figure 8)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.calculated_total_score", "K", "Gene-Disease Validity Curation", "Calculated total score", "0-18 points sum of genetic + experimental evidence (GDV-12 Figure 9 col C)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.modified_classification", "K", "Gene-Disease Validity Curation", "Modified classification", "Manual override of calculated classification by expert panel (GDV-12 p49)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.curator_classification", "K", "Gene-Disease Validity Curation", "Curator classification", "Curator-assigned classification before expert panel approval (GDV-12 Figure 9 col F)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.final_published_classification", "K", "Gene-Disease Validity Curation", "Final published classification", "Approved classification published to clinicalgenome.org (GDV-12 Figure 9 col G)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.gcep_affiliation", "K", "Gene-Disease Validity Curation", "GCEP affiliation", "Gene Curation Expert Panel affiliation (GDV-12 p4)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.curation_version", "K", "Gene-Disease Validity Curation", "Curation version", "Version number of published classification (GDV-12 p49)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.independent_publication_count", "K", "Gene-Disease Validity Curation", "Independent publication count", "Number of independent publications for replication assessment (GDV-12 p47)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.years_since_original_publication", "K", "Gene-Disease Validity Curation", "Years since original publication", "Time span from original gene-disease assertion for replication (>3 years required) (GDV-12 p47)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.pmid", "K", "Gene-Disease Validity Curation", "PubMed ID", "PMID of evidence source publication (GDV-12 p12)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.publication_date", "K", "Gene-Disease Validity Curation", "Publication date", "Publication date for replication over time assessment (GDV-12 p47)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.original_assertion_pmid", "K", "Gene-Disease Validity Curation", "Original assertion PMID", "PMID of first publication asserting gene-disease relationship (GDV-12 p15)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.valid_contradictory_evidence_flag", "K", "Gene-Disease Validity Curation", "Valid contradictory evidence flag", "Whether valid contradictory evidence exists for this gene-disease curation (GDV-12 Figure 9 row E)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.contradictory_evidence_pmids", "K", "Gene-Disease Validity Curation", "Contradictory evidence PMIDs", "PMIDs and description of contradictory evidence at curation level (GDV-12 Figure 9 row E)", (), ("gene_disease_validity",)),
    EvidenceFieldSpec("K.modified_classification_rationale", "K", "Gene-Disease Validity Curation", "Modified classification rationale", "Required free-text rationale when expert panel overrides calculated classification (GDV-12 p49)", (), ("gene_disease_validity",)),
)


_FIELD_BY_ID = {spec.field_id: spec for spec in EVIDENCE_FIELD_SPECS}


def get_field_spec(field_id: str) -> EvidenceFieldSpec:
    return _FIELD_BY_ID[field_id]


# ── Catalog groups ─────────────────────────────────────────────────────
# 166 fields split into 3 groups:
#   - high_signal (62): A,B,D,E,J — variant, case, population, prediction, authority
#   - supporting  (81): C,F,G,H,I — segregation, functional, case-control, contradiction, gene
#   - curation    (23): K         — cross-paper GDV (NOT for single-paper LLM extraction)
# CatalogExtractionStage filters out `curation`; it is consumed downstream by the
# cross-paper GDV pipeline.
_CATALOG_GROUP_CATEGORIES = {
    "high_signal": ("A", "B", "D", "E", "J"),   # 62 fields: variant, case, population, prediction, authority
    "supporting":  ("C", "F", "G", "H", "I"),    # 81 fields: segregation, functional, case-control, contradiction, gene
    "curation":    ("K",),                       # 23 fields: gene-disease validity curation (cross-paper, GDV SOP v12)
}

CATALOG_GROUPS: dict[str, tuple[EvidenceFieldSpec, ...]] = {}
for _group_name, _cat_ids in _CATALOG_GROUP_CATEGORIES.items():
    CATALOG_GROUPS[_group_name] = tuple(
        spec for spec in EVIDENCE_FIELD_SPECS if spec.category_id in _cat_ids
    )
