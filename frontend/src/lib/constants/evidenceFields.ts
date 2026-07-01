/**
 * Comprehensive evidence field catalog — mirrors backend catalog.py EVIDENCE_FIELD_SPECS.
 * 166 fields across 10 categories (A–K) for ACMG/ClinGen GDV evidence extraction.
 */

export interface EvidenceFieldSpec {
  fieldId: string;
  categoryId: string;
  categoryName: string;
  fieldName: string;
  description: string;
}

export const EVIDENCE_FIELD_SPECS: EvidenceFieldSpec[] = [
  // ── A: Variant Information ──
  { fieldId: "A.gene_symbol", categoryId: "A", categoryName: "Variant Information", fieldName: "Gene symbol", description: "Gene symbol" },
  { fieldId: "A.gene_aliases", categoryId: "A", categoryName: "Variant Information", fieldName: "Gene aliases", description: "Gene aliases or old names" },
  { fieldId: "A.gene_disease_relationship", categoryId: "A", categoryName: "Variant Information", fieldName: "Gene-disease relationship", description: "Reported gene-disease relationship" },
  { fieldId: "A.transcript_id", categoryId: "A", categoryName: "Variant Information", fieldName: "Transcript ID", description: "Transcript ID" },
  { fieldId: "A.reference_sequence", categoryId: "A", categoryName: "Variant Information", fieldName: "Reference sequence", description: "Reference sequence or genome build" },
  { fieldId: "A.variant_hgvs_c", categoryId: "A", categoryName: "Variant Information", fieldName: "HGVS coding variant", description: "HGVS coding variant" },
  { fieldId: "A.variant_hgvs_p", categoryId: "A", categoryName: "Variant Information", fieldName: "HGVS protein variant", description: "HGVS protein variant" },
  { fieldId: "A.variant_hgvs_g", categoryId: "A", categoryName: "Variant Information", fieldName: "HGVS genomic variant", description: "HGVS genomic variant" },
  { fieldId: "A.variant_legacy_name", categoryId: "A", categoryName: "Variant Information", fieldName: "Legacy variant name", description: "Legacy or traditional variant name" },
  { fieldId: "A.variant_type", categoryId: "A", categoryName: "Variant Information", fieldName: "Variant type", description: "Variant type" },
  { fieldId: "A.null_variant_detail", categoryId: "A", categoryName: "Variant Information", fieldName: "Null variant detail", description: "Null variant detail and LoF context" },
  { fieldId: "A.protein_effect", categoryId: "A", categoryName: "Variant Information", fieldName: "Protein effect", description: "Protein effect description" },
  { fieldId: "A.same_amino_acid_known_variant", categoryId: "A", categoryName: "Variant Information", fieldName: "Same AA known variant", description: "Same amino acid as known pathogenic variant" },
  { fieldId: "A.same_residue_other_missense", categoryId: "A", categoryName: "Variant Information", fieldName: "Same residue missense", description: "Same residue different missense pathogenic reference" },
  { fieldId: "A.functional_domain_or_hotspot", categoryId: "A", categoryName: "Variant Information", fieldName: "Functional domain/hotspot", description: "Functional domain or mutational hotspot" },
  { fieldId: "A.protein_length_change", categoryId: "A", categoryName: "Variant Information", fieldName: "Protein length change", description: "Protein length change" },
  { fieldId: "A.repeat_region_status", categoryId: "A", categoryName: "Variant Information", fieldName: "Repeat region status", description: "Repeat region status" },
  { fieldId: "A.splice_or_synonymous_effect", categoryId: "A", categoryName: "Variant Information", fieldName: "Splice/synonymous effect", description: "Synonymous or splice effect statement" },
  { fieldId: "A.gene_missense_constraint", categoryId: "A", categoryName: "Variant Information", fieldName: "Gene missense constraint", description: "Gene-level missense intolerance evidence" },
  { fieldId: "A.gene_truncating_mechanism_evidence", categoryId: "A", categoryName: "Variant Information", fieldName: "Gene truncating mechanism", description: "Evidence gene mechanism is primarily truncating/LOF" },
  { fieldId: "A.variant_consequence_class", categoryId: "A", categoryName: "Variant Information", fieldName: "Variant consequence class", description: "Predicted null vs other variant with gene impact" },
  { fieldId: "A.identity_by_descent_variant", categoryId: "A", categoryName: "Variant Information", fieldName: "IBD/founder variant", description: "Known founder variant in specific population" },

  // ── B: Case/Phenotype Information ──
  { fieldId: "B.proband_status", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Proband status", description: "Proband status" },
  { fieldId: "B.case_count", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Case count", description: "Independent case count" },
  { fieldId: "B.disease_diagnosis", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Disease diagnosis", description: "Disease diagnosis" },
  { fieldId: "B.phenotype_specificity", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Phenotype specificity", description: "Phenotype specificity" },
  { fieldId: "B.hpo_terms", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "HPO terms", description: "HPO phenotype terms" },
  { fieldId: "B.clinical_phenotypes", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Clinical phenotypes", description: "Key clinical phenotypes" },
  { fieldId: "B.biochemical_markers", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Biochemical markers", description: "Biochemical or laboratory markers" },
  { fieldId: "B.age_current_or_last_followup", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Current/follow-up age", description: "Current or last follow-up age" },
  { fieldId: "B.age_of_onset", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Age of onset", description: "Age of onset" },
  { fieldId: "B.sex", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Sex", description: "Sex" },
  { fieldId: "B.ancestry_or_population", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Ancestry/population", description: "Ancestry or population" },
  { fieldId: "B.consanguinity", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Consanguinity", description: "Consanguinity" },
  { fieldId: "B.mode_of_inheritance_reported", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Mode of inheritance", description: "Reported mode of inheritance" },
  { fieldId: "B.single_genetic_etiology_claim", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Single etiology claim", description: "Single genetic etiology claim" },
  { fieldId: "B.alternative_diagnosis_excluded", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Alt diagnosis excluded", description: "Other diagnoses excluded" },
  { fieldId: "B.additional_pathogenic_variant", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Additional pathogenic var", description: "Additional pathogenic variant" },
  { fieldId: "B.testing_method", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Testing method", description: "Variant testing method" },
  { fieldId: "B.sequencing_method_quality", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Sequencing quality", description: "Sequencing method quality" },
  { fieldId: "B.healthy_adult_status", categoryId: "B", categoryName: "Case/Phenotype", fieldName: "Healthy adult status", description: "Healthy adult observation" },

  // ── C: Segregation/Family Information ──
  { fieldId: "C.inheritance_source", categoryId: "C", categoryName: "Segregation/Family", fieldName: "Inheritance source", description: "Inherited or de novo source" },
  { fieldId: "C.de_novo_status", categoryId: "C", categoryName: "Segregation/Family", fieldName: "De novo status", description: "De novo status" },
  { fieldId: "C.parentage_confirmed", categoryId: "C", categoryName: "Segregation/Family", fieldName: "Parentage confirmed", description: "Parentage confirmation" },
  { fieldId: "C.maternal_genotype", categoryId: "C", categoryName: "Segregation/Family", fieldName: "Maternal genotype", description: "Maternal genotype" },
  { fieldId: "C.maternal_phenotype", categoryId: "C", categoryName: "Segregation/Family", fieldName: "Maternal phenotype", description: "Maternal phenotype" },
  { fieldId: "C.paternal_genotype", categoryId: "C", categoryName: "Segregation/Family", fieldName: "Paternal genotype", description: "Paternal genotype" },
  { fieldId: "C.paternal_phenotype", categoryId: "C", categoryName: "Segregation/Family", fieldName: "Paternal phenotype", description: "Paternal phenotype" },
  { fieldId: "C.phase_status", categoryId: "C", categoryName: "Segregation/Family", fieldName: "Phase status", description: "Phase status" },
  { fieldId: "C.in_trans_confirmation", categoryId: "C", categoryName: "Segregation/Family", fieldName: "In trans confirmation", description: "In trans confirmation" },
  { fieldId: "C.cis_or_trans_context", categoryId: "C", categoryName: "Segregation/Family", fieldName: "Cis/trans context", description: "Cis or trans context" },
  { fieldId: "C.g_plus_p_plus_count", categoryId: "C", categoryName: "Segregation/Family", fieldName: "G+/P+ count", description: "G+/P+ count" },
  { fieldId: "C.g_plus_p_minus_count", categoryId: "C", categoryName: "Segregation/Family", fieldName: "G+/P- count", description: "G+/P- count" },
  { fieldId: "C.g_minus_p_plus_count", categoryId: "C", categoryName: "Segregation/Family", fieldName: "G-/P+ count", description: "G-/P+ count" },
  { fieldId: "C.g_minus_p_minus_count", categoryId: "C", categoryName: "Segregation/Family", fieldName: "G-/P- count", description: "G-/P- count" },
  { fieldId: "C.obligate_carriers", categoryId: "C", categoryName: "Segregation/Family", fieldName: "Obligate carriers", description: "Obligate carriers" },
  { fieldId: "C.lod_score", categoryId: "C", categoryName: "Segregation/Family", fieldName: "LOD score", description: "LOD score" },
  { fieldId: "C.de_novo_without_parentage_confirmation", categoryId: "C", categoryName: "Segregation/Family", fieldName: "De novo unconfirmed", description: "De novo without full parentage confirmation" },

  // ── D: Population/Frequency Information ──
  { fieldId: "D.population_database_name", categoryId: "D", categoryName: "Population/Frequency", fieldName: "Population DB name", description: "Population database name" },
  { fieldId: "D.allele_frequency", categoryId: "D", categoryName: "Population/Frequency", fieldName: "Allele frequency", description: "Allele frequency" },
  { fieldId: "D.allele_count", categoryId: "D", categoryName: "Population/Frequency", fieldName: "Allele count", description: "Allele count" },
  { fieldId: "D.allele_number", categoryId: "D", categoryName: "Population/Frequency", fieldName: "Allele number", description: "Allele number" },
  { fieldId: "D.homozygote_count", categoryId: "D", categoryName: "Population/Frequency", fieldName: "Homozygote count", description: "Homozygote count" },
  { fieldId: "D.population_subgroup", categoryId: "D", categoryName: "Population/Frequency", fieldName: "Population subgroup", description: "Population subgroup" },
  { fieldId: "D.absent_or_rare_statement", categoryId: "D", categoryName: "Population/Frequency", fieldName: "Absent/rare statement", description: "Absent or rare population statement" },
  { fieldId: "D.healthy_carrier_observation", categoryId: "D", categoryName: "Population/Frequency", fieldName: "Healthy carrier obs", description: "Healthy carrier population observation" },

  // ── E: Computational/Prediction Evidence ──
  { fieldId: "E.prediction_tools_list", categoryId: "E", categoryName: "Computational/Prediction", fieldName: "Prediction tools", description: "Prediction tools list" },
  { fieldId: "E.deleterious_prediction_summary", categoryId: "E", categoryName: "Computational/Prediction", fieldName: "Deleterious prediction", description: "Deleterious prediction summary" },
  { fieldId: "E.benign_prediction_summary", categoryId: "E", categoryName: "Computational/Prediction", fieldName: "Benign prediction", description: "Benign prediction summary" },
  { fieldId: "E.splice_prediction", categoryId: "E", categoryName: "Computational/Prediction", fieldName: "Splice prediction", description: "Splice prediction" },
  { fieldId: "E.conservation_score", categoryId: "E", categoryName: "Computational/Prediction", fieldName: "Conservation score", description: "Conservation score" },
  { fieldId: "E.in_silico_consensus", categoryId: "E", categoryName: "Computational/Prediction", fieldName: "In silico consensus", description: "In silico consensus" },
  { fieldId: "E.prediction_conflict", categoryId: "E", categoryName: "Computational/Prediction", fieldName: "Prediction conflict", description: "Computational prediction conflict" },

  // ── F: Functional Evidence ──
  { fieldId: "F.assay_id", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Assay ID", description: "Functional assay identifier" },
  { fieldId: "F.assay_type", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Assay type", description: "Functional assay type" },
  { fieldId: "F.assay_system", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Assay system", description: "Functional assay system" },
  { fieldId: "F.tested_variant", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Tested variant", description: "Tested variant" },
  { fieldId: "F.functional_result", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Functional result", description: "Functional result" },
  { fieldId: "F.quantitative_result", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Quantitative result", description: "Quantitative functional result" },
  { fieldId: "F.positive_controls", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Positive controls", description: "Positive controls" },
  { fieldId: "F.negative_controls", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Negative controls", description: "Negative controls" },
  { fieldId: "F.total_controls", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Total controls", description: "Total positive plus benign controls" },
  { fieldId: "F.control_quality", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Control quality", description: "Quality of experimental and clinical validation controls" },
  { fieldId: "F.replicates_or_statistics", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Replicates/statistics", description: "Replicates or functional statistics" },
  { fieldId: "F.patient_cell_evidence", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Patient-cell evidence", description: "Patient-cell functional evidence" },
  { fieldId: "F.non_patient_cell_evidence", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Non-patient-cell evidence", description: "Non-patient-cell functional evidence" },
  { fieldId: "F.functional_normal_result", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Normal result", description: "Functional normal result" },
  { fieldId: "F.functional_inconclusive_result", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Inconclusive result", description: "Functional inconclusive result" },
  { fieldId: "F.odds_path", categoryId: "F", categoryName: "Functional Evidence", fieldName: "OddsPath", description: "Calculated OddsPath from functional assay validation" },
  { fieldId: "F.evidence_strength_tier", categoryId: "F", categoryName: "Functional Evidence", fieldName: "PS3/BS3 strength tier", description: "PS3/BS3 evidence strength tier" },
  { fieldId: "F.physiologic_context", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Physiologic context", description: "Physiologic context of assay" },
  { fieldId: "F.declared_disease_mechanism", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Disease mechanism", description: "Declared disease mechanism" },
  { fieldId: "F.molecular_consequence", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Molecular consequence", description: "Molecular consequence of variant on assay" },
  { fieldId: "F.disease_mechanism_consistency", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Mechanism consistency", description: "Disease mechanism consistency" },
  { fieldId: "F.assay_validation_method", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Assay validation", description: "Assay validation method" },
  { fieldId: "F.allelic_series_size", categoryId: "F", categoryName: "Functional Evidence", fieldName: "Allelic series size", description: "Allelic series validation control count" },
  { fieldId: "F.clia_laboratory_status", categoryId: "F", categoryName: "Functional Evidence", fieldName: "CLIA lab status", description: "CLIA laboratory status" },

  // ── G: Case-Control Evidence ──
  { fieldId: "G.study_design", categoryId: "G", categoryName: "Case-Control", fieldName: "Study design", description: "Case-control study design" },
  { fieldId: "G.case_count", categoryId: "G", categoryName: "Case-Control", fieldName: "CC case count", description: "Case-control case count" },
  { fieldId: "G.control_count", categoryId: "G", categoryName: "Case-Control", fieldName: "CC control count", description: "Case-control control count" },
  { fieldId: "G.case_definition", categoryId: "G", categoryName: "Case-Control", fieldName: "Case definition", description: "Case definition" },
  { fieldId: "G.control_matching", categoryId: "G", categoryName: "Case-Control", fieldName: "Control matching", description: "Control matching quality" },
  { fieldId: "G.variant_count_cases", categoryId: "G", categoryName: "Case-Control", fieldName: "Variant count (cases)", description: "Variant count in cases" },
  { fieldId: "G.variant_count_controls", categoryId: "G", categoryName: "Case-Control", fieldName: "Variant count (controls)", description: "Variant count in controls" },
  { fieldId: "G.odds_ratio", categoryId: "G", categoryName: "Case-Control", fieldName: "Odds ratio", description: "Odds ratio" },
  { fieldId: "G.confidence_interval", categoryId: "G", categoryName: "Case-Control", fieldName: "Confidence interval", description: "Confidence interval" },
  { fieldId: "G.p_value", categoryId: "G", categoryName: "Case-Control", fieldName: "P-value", description: "P-value" },
  { fieldId: "G.statistical_method", categoryId: "G", categoryName: "Case-Control", fieldName: "Statistical method", description: "Statistical method" },
  { fieldId: "G.case_control_negative_result", categoryId: "G", categoryName: "Case-Control", fieldName: "Negative CC result", description: "Negative case-control result" },
  { fieldId: "G.case_control_status", categoryId: "G", categoryName: "Case-Control", fieldName: "CC scoring status", description: "Case-control scoring status" },
  { fieldId: "G.detection_methodology_quality", categoryId: "G", categoryName: "Case-Control", fieldName: "Detection methodology", description: "Detection methodology equivalence" },
  { fieldId: "G.bias_confounding_factors", categoryId: "G", categoryName: "Case-Control", fieldName: "Bias/confounding", description: "Bias and confounding factors" },

  // ── H: Contradiction/Exclusion Evidence ──
  { fieldId: "H.misdiagnosis_or_reclassification", categoryId: "H", categoryName: "Contradiction/Exclusion", fieldName: "Misdiagnosis/reclass", description: "Misdiagnosis or reclassification" },
  { fieldId: "H.alternative_causative_gene", categoryId: "H", categoryName: "Contradiction/Exclusion", fieldName: "Alt causative gene", description: "Alternative causative gene" },
  { fieldId: "H.other_pathogenic_variant", categoryId: "H", categoryName: "Contradiction/Exclusion", fieldName: "Other pathogenic var", description: "Other pathogenic variant" },
  { fieldId: "H.non_segregation", categoryId: "H", categoryName: "Contradiction/Exclusion", fieldName: "Non-segregation", description: "Non-segregation" },
  { fieldId: "H.healthy_carrier_contradiction", categoryId: "H", categoryName: "Contradiction/Exclusion", fieldName: "Healthy carrier contra", description: "Healthy carrier contradiction" },
  { fieldId: "H.negative_functional_result", categoryId: "H", categoryName: "Contradiction/Exclusion", fieldName: "Negative functional", description: "Negative functional result" },
  { fieldId: "H.animal_model_no_phenotype", categoryId: "H", categoryName: "Contradiction/Exclusion", fieldName: "Animal model no pheno", description: "Animal model no phenotype" },
  { fieldId: "H.contradiction_type", categoryId: "H", categoryName: "Contradiction/Exclusion", fieldName: "Contradiction type", description: "Contradictory evidence type" },
  { fieldId: "H.contradiction_severity", categoryId: "H", categoryName: "Contradiction/Exclusion", fieldName: "Contradiction severity", description: "Contradiction severity level" },

  // ── I: Gene Function/Experimental Evidence ──
  { fieldId: "I.gene_function_biochemical", categoryId: "I", categoryName: "Gene Function/Experimental", fieldName: "Biochemical function", description: "Biochemical gene function evidence" },
  { fieldId: "I.gene_function_protein_interaction", categoryId: "I", categoryName: "Gene Function/Experimental", fieldName: "Protein interaction", description: "Protein interaction evidence" },
  { fieldId: "I.gene_expression_pattern", categoryId: "I", categoryName: "Gene Function/Experimental", fieldName: "Expression pattern", description: "Gene expression pattern" },
  { fieldId: "I.disease_relevant_expression", categoryId: "I", categoryName: "Gene Function/Experimental", fieldName: "Disease-relevant expr", description: "Disease-relevant expression" },
  { fieldId: "I.functional_alteration_patient_cells", categoryId: "I", categoryName: "Gene Function/Experimental", fieldName: "Patient-cell alteration", description: "Patient-cell functional alteration" },
  { fieldId: "I.functional_alteration_non_patient_cells", categoryId: "I", categoryName: "Gene Function/Experimental", fieldName: "Non-patient-cell alter", description: "Non-patient-cell functional alteration" },
  { fieldId: "I.animal_model_type", categoryId: "I", categoryName: "Gene Function/Experimental", fieldName: "Animal model type", description: "Animal model type" },
  { fieldId: "I.animal_model_phenotype", categoryId: "I", categoryName: "Gene Function/Experimental", fieldName: "Animal model phenotype", description: "Animal model phenotype" },
  { fieldId: "I.animal_model_genotype", categoryId: "I", categoryName: "Gene Function/Experimental", fieldName: "Animal model genotype", description: "Animal model genotype" },
  { fieldId: "I.cell_model_type", categoryId: "I", categoryName: "Gene Function/Experimental", fieldName: "Cell model type", description: "Cell model type" },
  { fieldId: "I.cell_model_phenotype", categoryId: "I", categoryName: "Gene Function/Experimental", fieldName: "Cell model phenotype", description: "Cell model phenotype" },
  { fieldId: "I.human_rescue_experiment", categoryId: "I", categoryName: "Gene Function/Experimental", fieldName: "Human rescue", description: "Human rescue experiment" },
  { fieldId: "I.animal_rescue_experiment", categoryId: "I", categoryName: "Gene Function/Experimental", fieldName: "Animal rescue", description: "Animal rescue experiment" },
  { fieldId: "I.cell_rescue_experiment", categoryId: "I", categoryName: "Gene Function/Experimental", fieldName: "Cell rescue", description: "Cell rescue experiment" },
  { fieldId: "I.rescue_result", categoryId: "I", categoryName: "Gene Function/Experimental", fieldName: "Rescue result", description: "Rescue result" },
  { fieldId: "I.experimental_replication", categoryId: "I", categoryName: "Gene Function/Experimental", fieldName: "Experimental replication", description: "Experimental replication" },

  // ── J: Authority/Time Validity ──
  { fieldId: "J.clinvar_assertion", categoryId: "J", categoryName: "Authority/Time Validity", fieldName: "ClinVar assertion", description: "ClinVar assertion" },
  { fieldId: "J.expert_panel_assertion", categoryId: "J", categoryName: "Authority/Time Validity", fieldName: "Expert panel assertion", description: "Expert panel assertion" },
  { fieldId: "J.authority_classification", categoryId: "J", categoryName: "Authority/Time Validity", fieldName: "Authority classification", description: "Authority classification" },
  { fieldId: "J.known_pathogenic_variant_reference", categoryId: "J", categoryName: "Authority/Time Validity", fieldName: "Known pathogenic ref", description: "Known pathogenic variant reference" },
  { fieldId: "J.ps1_pm5_relationship", categoryId: "J", categoryName: "Authority/Time Validity", fieldName: "PS1/PM5 relationship", description: "PS1 or PM5 relationship to current variant" },
  { fieldId: "J.reputable_benign_assertion", categoryId: "J", categoryName: "Authority/Time Validity", fieldName: "Reputable benign assert", description: "Reputable source benign assertion" },

  // ── K: Gene-Disease Validity Curation (cross-paper, GDV SOP v12) ──
  { fieldId: "K.mode_of_inheritance", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "GDV inheritance mode", description: "AD / AR / SD / XL / Mitochondrial / Somatic / Undetermined" },
  { fieldId: "K.disease_entity_mondo", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Disease MONDO ID", description: "Monarch Disease Ontology identifier" },
  { fieldId: "K.disease_name", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "GDV disease name", description: "Curated disease name per ClinGen naming conventions" },
  { fieldId: "K.disease_prevalence", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Disease prevalence", description: "Disease prevalence for frequency threshold derivation" },
  { fieldId: "K.precuration_id", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Precuration ID", description: "Precuration ID from GeneTracker" },
  { fieldId: "K.gene_disease_validity_classification", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "GDV classification", description: "Definitive / Strong / Moderate / Limited / Disputed / Refuted / No Known" },
  { fieldId: "K.replication_over_time_flag", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Replication over time", description: ">2 independent publications over >3 years" },
  { fieldId: "K.genetic_evidence_total_score", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Genetic evidence score", description: "0-12 points from case-level + segregation + case-control" },
  { fieldId: "K.experimental_evidence_total_score", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Experimental evidence score", description: "0-6 points from function + models + rescue" },
  { fieldId: "K.calculated_total_score", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Calculated total score", description: "0-18 points sum of genetic + experimental" },
  { fieldId: "K.modified_classification", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Modified classification", description: "Manual override by expert panel" },
  { fieldId: "K.curator_classification", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Curator classification", description: "Curator-assigned classification" },
  { fieldId: "K.final_published_classification", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Final published class", description: "Approved classification published to clinicalgenome.org" },
  { fieldId: "K.gcep_affiliation", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "GCEP affiliation", description: "Gene Curation Expert Panel affiliation" },
  { fieldId: "K.curation_version", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Curation version", description: "Version number of published classification" },
  { fieldId: "K.independent_publication_count", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Publication count", description: "Number of independent publications" },
  { fieldId: "K.years_since_original_publication", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Years since original pub", description: "Time span from original gene-disease assertion" },
  { fieldId: "K.pmid", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "PMID", description: "PubMed ID of evidence source" },
  { fieldId: "K.publication_date", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Publication date", description: "Publication date for replication assessment" },
  { fieldId: "K.original_assertion_pmid", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Original assertion PMID", description: "PMID of first publication asserting gene-disease relationship" },
  { fieldId: "K.valid_contradictory_evidence_flag", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Contradictory evidence flag", description: "Whether valid contradictory evidence exists" },
  { fieldId: "K.contradictory_evidence_pmids", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Contradictory PMIDs", description: "PMIDs of contradictory evidence" },
  { fieldId: "K.modified_classification_rationale", categoryId: "K", categoryName: "Gene-Disease Validity", fieldName: "Modified class rationale", description: "Rationale when expert panel overrides calculated classification" },
];

/** Quick lookup by field_id. */
export const FIELD_SPEC_BY_ID: Record<string, EvidenceFieldSpec> = Object.fromEntries(
  EVIDENCE_FIELD_SPECS.map((s) => [s.fieldId, s]),
);

/** Category display info (letter → name + CSS color hex). */
export const FIELD_CATEGORIES: Record<string, { name: string; hex: string }> = {
  A: { name: "Variant Information", hex: "#3B82F6" },
  B: { name: "Case/Phenotype", hex: "#8B5CF6" },
  C: { name: "Segregation/Family", hex: "#EC4899" },
  D: { name: "Population/Frequency", hex: "#F59E0B" },
  E: { name: "Computational/Prediction", hex: "#10B981" },
  F: { name: "Functional Evidence", hex: "#EF4444" },
  G: { name: "Case-Control", hex: "#6366F1" },
  H: { name: "Contradiction/Exclusion", hex: "#F97316" },
  I: { name: "Gene Function/Experimental", hex: "#14B8A6" },
  J: { name: "Authority/Time Validity", hex: "#EC4899" },
  K: { name: "Gene-Disease Validity", hex: "#A855F7" },
};
