"""Prompt builders for evidence extraction stages."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..domain.channel_contracts import DocumentEvidenceChannel

if TYPE_CHECKING:
    from ..domain.channel_contracts import DocumentChannelClassification
    from ..contracts import ExtractionTarget, Track

_EVIDENCE_MAP_JSON_EXAMPLE = {
    "relevant": True,
    "disease_terms": ["Fabry disease", "renal failure"],
    "gene_terms": ["GLA"],
    "variant_terms": ["p.R227X", "c.680C>T"],
    "case_references": ["proband", "family members"],
    "authority_references": ["ClinVar"],
    "contradictions": [],
    "structure_hints": ["Table 1: clinical features"],
    "selected_channels": ["case_report"],
    "confidence": 0.82,
    "rationale": "Single-proband case report describing phenotype and a de novo variant.",
    "supporting_block_ids": ["block_3", "block_7"],
}



def get_evidence_map_prompt(
    document_id: str,
    track: Track,
    text: str,
) -> str:
    return f"""DEFAULT: Set "relevant" to TRUE. Most biomedical case reports, studies, and clinical documents contain relevant evidence. When in doubt, set relevant to TRUE.

You are analyzing a biomedical document for evidence extraction.

Document ID: {document_id}
Track: {track.value}

TASK: Scan this document for biomedical/genetic content and list all relevant terms you find.

Set "relevant" to FALSE ONLY if the document is:
- A purely methodological paper (e.g. statistical methods, software tools)
- An editorial, letter, or comment with no patient data
- Completely unrelated to medicine, genetics, or biology

If you find ANY of the following, you MUST set "relevant" to TRUE and list them:
- Disease names, diagnoses, or phenotypes (in any language)
- Gene symbols or names
- Genetic variants, mutations, or HGVS notation
- Patient cases, probands, family pedigrees
- Lab results, biomarkers, clinical findings
- Drug treatments or therapeutic interventions

CRITICAL: Do NOT return empty lists if the document contains biomedical content. List every term you find.

If you are unsure whether the document is relevant, set relevant to TRUE.

CHANNEL CLASSIFICATION:
Classify the document into one or more evidence channels based on the study design and evidence type present.
Set "selected_channels" to a non-empty array of exactly one of these labels (use lowercase):
- "case_report": individual patient/proband/family evidence — phenotype description, variant identification, segregation, de novo, pedigree.
- "functional_study": wet-lab, cell-model, animal-model, or patient-cell assay evidence — functional readout, controls, quantitative results, rescue experiments.
- "cohort_study": aggregate cohort, case-control, recurrence, association, enrichment, or burden/statistical evidence across multiple individuals.
- "mixed": use when two or more concrete channels are materially present in the document.
- "unknown": use ONLY when the document type cannot be determined from the available text.

For "mixed", instead of the "mixed" label you MAY list the concrete channels that apply (e.g. ["case_report", "functional_study"]) — both forms are accepted. Prefer listing concrete channels when the evidence is clearly separable.

Set "confidence" to a float in [0.0, 1.0] reflecting how certain you are of the channel assignment.
Set "rationale" to a one-sentence justification citing the study design features that drove the classification.
Set "supporting_block_ids" to the block identifiers (e.g. "block_3") that contain the evidence supporting the classification; use an empty array if block IDs are not available.

JSON OUTPUT:
Return only a single valid json object. Do not wrap it in markdown code fences or add commentary.
Return JSON matching this schema (fill in values found in the document):
{json.dumps(_EVIDENCE_MAP_JSON_EXAMPLE, ensure_ascii=False, indent=2)}

DOCUMENT TEXT:
{text}
"""


def _target_prompt_section(extraction_target: ExtractionTarget | None) -> str:
    if extraction_target is None:
        return "TARGET: Not provided."
    return (
        f"TARGET GENE: {extraction_target.gene_symbol}\n"
        f"TARGET DISEASE: {extraction_target.disease_name}\n"
        f"TARGET VARIANT C: {extraction_target.variant_hgvs_c or 'not specified'}\n"
        f"TARGET VARIANT P: {extraction_target.variant_hgvs_p or 'not specified'}\n"
        f"CLINGEN ENTRY: {extraction_target.clingen_entry_id or 'not specified'}"
    )


def relationship_decision_guidance() -> str:
    """Return field-specific guidance for gene-disease relationship extraction."""
    return """"causative": use when the document supports an established causal relationship, including known disease gene assertions, pathogenic/likely pathogenic variants in affected cases, replicated genetic evidence, functional validation, biallelic loss-of-function evidence for recessive disease, or deficiency language directly linking the target gene to the target disease.
"associated": use only when the gene-disease link is explicitly preliminary, correlative, cohort-level, or not established as causal. Do not choose associated merely because the sentence contains associated, predicted, or involved.
"susceptibility": use when the gene or variant is described as a risk factor, modifier, predisposition, or susceptibility locus rather than a deterministic disease cause.
"uncertain": use when evidence is insufficient, variant interpretation is uncertain, the text says the relationship remains unclear, or the sentence uses incidental-finding / might be due / may be due / could be due / pathogenic-link-unclear language.
"disputed": use when the document describes conflicting evidence, disputed validity, contradictory reports, unresolved disagreement, or computationally predicted targets that are not directly validated.
"refuted": use when the document provides evidence against the gene-disease relationship, says the association is not supported, or rules it out.
"no_relationship": use when there is no gene-disease relationship between the target gene and target disease in the cited span."""


def disease_boundary_guidance() -> str:
    """Return target-only disease boundary guidance for diagnosis extraction."""
    return """TARGET DISEASE BOUNDARY for B.disease_diagnosis:
- Extract the primary target disease name, not every disease term in the document.
- Do NOT extract disease lists, differential diagnoses, exclusion lists, or unrelated disease examples.
- Do NOT extract comorbidities, complications, manifestations, phenotypes, or general medical history as the primary diagnosis.
- Do NOT extract background diseases from introductions, reviews, controls, or family history unless the target gene is directly linked to that disease in the same evidence context.
- Do NOT over-specialize or under-specialize the target disease name. Preserve the target-level disease boundary supported by the evidence span."""


_CASE_REPORT_STRATEGY = """CASE-REPORT STRATEGY:
This document is classified as an individual case report or family study. Prioritize extraction of patient/proband/family-level evidence:
- Phenotype: extract clinical phenotypes, HPO terms, biochemical markers, and disease diagnosis for the affected individual(s).
- Onset and age: extract age of onset, current/last follow-up age, and disease progression details.
- Inheritance: extract reported mode of inheritance, consanguinity, and zygosity context.
- Segregation: extract de novo status, parentage confirmation, parental genotypes/phenotypes, and segregation counts (G+/P+, G-/P- etc.).
- Variant observations: extract the variant(s) observed in affected individuals, including HGVS notation, variant type, and protein effect.
- Do not extract cohort-level statistics, case-control odds ratios, or population frequency data unless clearly individual-level evidence is present."""

_FUNCTIONAL_STUDY_STRATEGY = """FUNCTIONAL-STUDY STRATEGY:
This document is classified as a functional/experimental study. Prioritize extraction of assay-level evidence:
- Assay system: extract assay type, assay system, and physiologic context (patient-derived vs model organism vs in vitro).
- Tested variant: extract the specific variant tested in the assay and its molecular consequence.
- Controls: extract positive controls, negative controls, total controls, and control quality.
- Quantitative result: extract functional result, quantitative result, OddsPath, and evidence strength tier.
- Result classification: distinguish normal, abnormal, and inconclusive functional results.
- Disease mechanism: extract declared disease mechanism and check assay-disease mechanism consistency.
- CRITICAL: Do not treat in silico computational predictions (PP3/BP4) as functional evidence. Only wet-lab, cell-model, animal-model, or patient-cell assays qualify as F.* functional evidence."""

_COHORT_STUDY_STRATEGY = """COHORT-STUDY STRATEGY:
This document is classified as a cohort, case-control, or population study. Prioritize extraction of aggregate-level evidence:
- Cohort size: extract study design, case count, control count, and case definition.
- Statistics: extract odds ratio, confidence interval, p-value, and statistical method.
- Population frequency: extract allele frequency, allele count, allele number, and population subgroup from population databases.
- Detection quality: extract control matching quality, detection methodology equivalence, and bias/confounding factors.
- Recurrence: extract case-control status and any enrichment/burden evidence.
- Do not extract single-case phenotypes, individual patient onset, or family segregation details unless the document clearly reports individual-level evidence alongside the aggregate data."""

_GENERIC_STRATEGY = """DOCUMENT-CHANNEL STRATEGY:
No specific document channel was detected. Extract evidence using the standard catalog rules above. Do not over-specialize extraction strategy; treat each eligible field according to its general catalog definition."""


def get_channel_strategy_guidance(
    channel_classification: DocumentChannelClassification | None,
) -> str:
    """Return extraction strategy guidance tailored to the document channel(s).

    - ``None`` or ``UNKNOWN``: conservative generic guidance.
    - Concrete channels: the corresponding strategy block.
    - ``mixed`` (bare, no concrete): generic guidance.
    - Multiple concrete channels: concatenated guidance blocks for each,
      without duplicating generic text.
    """
    if channel_classification is None:
        return _GENERIC_STRATEGY

    effective = channel_classification.effective_channels
    if not effective:
        return _GENERIC_STRATEGY

    blocks: list[str] = []
    _STRATEGY_MAP = {
        DocumentEvidenceChannel.CASE_REPORT: _CASE_REPORT_STRATEGY,
        DocumentEvidenceChannel.FUNCTIONAL_STUDY: _FUNCTIONAL_STUDY_STRATEGY,
        DocumentEvidenceChannel.COHORT_STUDY: _COHORT_STUDY_STRATEGY,
    }
    for channel in effective:
        block = _STRATEGY_MAP.get(channel)
        if block and block not in blocks:
            blocks.append(block)
    if not blocks:
        return _GENERIC_STRATEGY
    return "\n".join(blocks)


def expanded_field_coverage_guidance() -> str:
    """Return B7-inspired field coverage guidance scoped to the eligible catalog."""
    return """EXPANDED FIELD COVERAGE GUIDANCE:
Use the eligible catalog as the source of truth. When these field IDs are listed, apply the following stronger coverage cues:
- Simple factual fields: A.gene_symbol, B.disease_diagnosis, A.gene_disease_relationship.
- Variant detail fields: A.variant_hgvs_c, A.variant_hgvs_p, A.variant_type, A.variant_consequence_class.
- Contextual patient fields: B.sex, B.age_of_onset, B.mode_of_inheritance_reported, B.clinical_phenotypes, B.hpo_terms.
- Segregation/de novo fields: C.inheritance_source, C.de_novo_status, C.segregation_observed, C.segregation_count.
- Functional evidence fields: F.assay_type, F.assay_system, F.functional_result, F.quantitative_result, F.assay_controls.
- Cohort/statistical fields: G.study_design, G.case_count, G.control_count, G.odds_ratio, G.confidence_interval, G.p_value.
Do not add any field outside the eligible catalog. This guidance expands attention to medium and complex fields without changing the current pipeline, validation, or source-grounding requirements."""

