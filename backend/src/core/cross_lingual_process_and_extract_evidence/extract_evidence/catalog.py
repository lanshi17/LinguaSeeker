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

    # Category B: Case/Phenotype Information
    EvidenceFieldSpec("B.case_id", "B", "Case/Phenotype Information", "Case or proband identifier", "Case or proband identifier", (), ("phenotype_consistency",)),
    EvidenceFieldSpec("B.proband_status", "B", "Case/Phenotype Information", "Proband status", "Proband status", (), ("phenotype_consistency",)),
    EvidenceFieldSpec("B.case_count", "B", "Case/Phenotype Information", "Independent case count", "Independent case count", ("PS4",), ("case_level",)),
    EvidenceFieldSpec("B.disease_diagnosis", "B", "Case/Phenotype Information", "Disease diagnosis", "Disease diagnosis", ("PP4",), ("phenotype_consistency",), True),
    EvidenceFieldSpec("B.diagnosis_sufficiency", "B", "Case/Phenotype Information", "Diagnosis sufficiency", "Diagnosis sufficiency", (), ("scoreability",), True),
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
    EvidenceFieldSpec("C.family_id", "C", "Segregation/Family Information", "Family identifier", "Family identifier", ("PP1", "BS4"), ("segregation",)),
    EvidenceFieldSpec("C.pedigree_available", "C", "Segregation/Family Information", "Pedigree availability", "Pedigree availability", ("PP1", "BS4"), ("segregation",)),
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

    # Category D: Population/Frequency Information
    EvidenceFieldSpec("D.population_database_name", "D", "Population/Frequency Information", "Population database name", "Population database name", ("PM2", "BA1", "BS1"), ("variant_evidence",)),
    EvidenceFieldSpec("D.allele_frequency", "D", "Population/Frequency Information", "Allele frequency", "Allele frequency", ("PM2", "BA1", "BS1"), ("variant_evidence",), True),
    EvidenceFieldSpec("D.allele_count", "D", "Population/Frequency Information", "Allele count", "Allele count", ("PM2", "BA1", "BS1"), ("variant_evidence",)),
    EvidenceFieldSpec("D.allele_number", "D", "Population/Frequency Information", "Allele number", "Allele number", ("PM2", "BA1", "BS1"), ("variant_evidence",)),
    EvidenceFieldSpec("D.homozygote_count", "D", "Population/Frequency Information", "Homozygote count", "Homozygote count", ("BS2",), ("variant_evidence",)),
    EvidenceFieldSpec("D.population_subgroup", "D", "Population/Frequency Information", "Population subgroup", "Population subgroup", ("PM2", "BA1", "BS1"), ("variant_evidence",)),
    EvidenceFieldSpec("D.frequency_threshold_context", "D", "Population/Frequency Information", "Disease frequency threshold context", "Disease frequency threshold context", ("BA1", "BS1"), ("variant_evidence",)),
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
    EvidenceFieldSpec("F.case_level_or_gene_level", "F", "Functional Evidence", "Case-level or gene-level assignment", "Case-level or gene-level assignment", ("PS3", "BS3"), ("function",)),
    EvidenceFieldSpec("F.functional_result", "F", "Functional Evidence", "Functional result", "Functional result", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.quantitative_result", "F", "Functional Evidence", "Quantitative functional result", "Quantitative functional result", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.positive_controls", "F", "Functional Evidence", "Positive controls", "Positive controls", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.negative_controls", "F", "Functional Evidence", "Negative controls", "Negative controls", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.total_controls", "F", "Functional Evidence", "Total positive plus benign controls", "Total positive plus benign controls", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.control_quality", "F", "Functional Evidence", "Control quality", "Control quality", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.replicates_or_statistics", "F", "Functional Evidence", "Replicates or functional statistics", "Replicates or functional statistics", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.mechanism_consistency", "F", "Functional Evidence", "Mechanism consistency", "Mechanism consistency", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.patient_cell_evidence", "F", "Functional Evidence", "Patient-cell functional evidence", "Patient-cell functional evidence", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.non_patient_cell_evidence", "F", "Functional Evidence", "Non-patient-cell functional evidence", "Non-patient-cell functional evidence", ("PS3", "BS3"), ("functional_alteration",)),
    EvidenceFieldSpec("F.functional_normal_result", "F", "Functional Evidence", "Functional normal result", "Functional normal result", ("BS3",), ("functional_alteration",)),
    EvidenceFieldSpec("F.functional_inconclusive_result", "F", "Functional Evidence", "Functional inconclusive result", "Functional inconclusive result", (), ("functional_alteration",)),

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

    # Category H: Contradiction/Exclusion Evidence
    EvidenceFieldSpec("H.misdiagnosis_or_reclassification", "H", "Contradiction/Exclusion Evidence", "Misdiagnosis or reclassification", "Misdiagnosis or reclassification", ("BP5",), ("contradiction",)),
    EvidenceFieldSpec("H.alternative_causative_gene", "H", "Contradiction/Exclusion Evidence", "Alternative causative gene", "Alternative causative gene", ("BP5",), ("contradiction",)),
    EvidenceFieldSpec("H.other_pathogenic_variant", "H", "Contradiction/Exclusion Evidence", "Other pathogenic variant", "Other pathogenic variant", ("BP5",), ("contradiction",)),
    EvidenceFieldSpec("H.non_segregation", "H", "Contradiction/Exclusion Evidence", "Non-segregation", "Non-segregation", ("BS4",), ("contradiction",)),
    EvidenceFieldSpec("H.healthy_carrier_contradiction", "H", "Contradiction/Exclusion Evidence", "Healthy carrier contradiction", "Healthy carrier contradiction", ("BS2",), ("contradiction",)),
    EvidenceFieldSpec("H.population_frequency_contradiction", "H", "Contradiction/Exclusion Evidence", "Population frequency contradiction", "Population frequency contradiction", ("BS1",), ("contradiction",)),
    EvidenceFieldSpec("H.negative_functional_result", "H", "Contradiction/Exclusion Evidence", "Negative functional result", "Negative functional result", ("BS3",), ("contradiction",)),
    EvidenceFieldSpec("H.negative_case_control_result", "H", "Contradiction/Exclusion Evidence", "Negative case-control result", "Negative case-control result", (), ("contradiction",)),
    EvidenceFieldSpec("H.animal_model_no_phenotype", "H", "Contradiction/Exclusion Evidence", "Animal model no phenotype", "Animal model no phenotype", (), ("contradiction",)),

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
    EvidenceFieldSpec("I.model_mechanism_match", "I", "Gene Function/Experimental Evidence", "Model mechanism match", "Model mechanism match", (), ("models",)),
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
    EvidenceFieldSpec("J.independent_publications_time_span", "J", "Authority/Time Validity", "Independent publications and time span", "Independent publications and time span", (), ("time_validity",)),
)


_FIELD_BY_ID = {spec.field_id: spec for spec in EVIDENCE_FIELD_SPECS}


def get_field_spec(field_id: str) -> EvidenceFieldSpec:
    return _FIELD_BY_ID[field_id]


# ── Catalog groups for parallel extraction ─────────────────────────────
# Split 134 fields into 2 balanced groups to reduce per-call output tokens
# and enable concurrent STRONG-tier LLM calls.
_CATALOG_GROUP_CATEGORIES = {
    "high_signal": ("A", "B", "D", "E", "J"),   # 61 fields: variant, case, population, prediction, authority
    "supporting":  ("C", "F", "G", "H", "I"),    # 73 fields: segregation, functional, case-control, contradiction, gene
}

CATALOG_GROUPS: dict[str, tuple[EvidenceFieldSpec, ...]] = {}
for _group_name, _cat_ids in _CATALOG_GROUP_CATEGORIES.items():
    CATALOG_GROUPS[_group_name] = tuple(
        spec for spec in EVIDENCE_FIELD_SPECS if spec.category_id in _cat_ids
    )
