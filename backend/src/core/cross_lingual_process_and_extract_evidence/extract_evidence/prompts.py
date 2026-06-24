"""Prompt builders for evidence extraction stages."""
from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING

from .channel_contracts import DocumentEvidenceChannel

if TYPE_CHECKING:
    from .catalog import EvidenceFieldSpec
    from .channel_contracts import DocumentChannelClassification
    from .contracts import ContentBlock, ExtractionTarget, Track, TrackDocument


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


def map_block_type(block_type: str) -> str:
    if block_type == "table":
        return "table"
    if block_type == "image":
        return "image"
    if block_type == "chart":
        return "figure"
    return "text"


def block_readable_text(block: ContentBlock) -> str:
    parts: list[str] = []
    parts.extend(block.table_caption)
    parts.extend(block.image_caption)
    parts.extend(block.chart_caption)
    for value in (block.text, block.content, block.table_body, block.code_body):
        if value.strip():
            parts.append(value.strip())
    if block.list_items:
        parts.extend(item.strip() for item in block.list_items if item.strip())
    return "\n".join(parts).strip()


def block_context_ref(block: ContentBlock) -> str:
    captions = block.table_caption or block.image_caption or block.chart_caption
    return captions[0] if captions else ""


def format_block_prompt_entry(index: int, block: ContentBlock, body: str | None = None) -> str:
    block_body = body if body is not None else block_readable_text(block)
    mapped_type = map_block_type(block.type)
    caption = block_context_ref(block)
    caption_part = f" | caption: {caption}" if caption else ""
    return (
        f"[Block {index} | {mapped_type} | page {block.page_idx + 1}{caption_part}]\n"
        f"{block_body}"
    )


def build_block_prompt_text(
    document: TrackDocument,
    block_indices: Sequence[int] | None = None,
) -> str:
    if not document.blocks:
        return document.formatted_text
    indices = block_indices if block_indices is not None else range(len(document.blocks))
    parts: list[str] = []
    for index in indices:
        if index < 0 or index >= len(document.blocks):
            continue
        block = document.blocks[index]
        body = block_readable_text(block)
        if not body:
            continue
        parts.append(format_block_prompt_entry(index, block, body))
    return "\n\n".join(parts)


def _catalog_compact_text(catalog: tuple[EvidenceFieldSpec, ...]) -> str:
    lines: list[str] = []
    for spec in catalog:
        codes = ",".join(spec.acmg_codes) if spec.acmg_codes else "-"
        req = "*" if spec.required_for_scorable else ""
        lines.append(f"{spec.field_id}{req}: {spec.field_name} [{codes}]")
    return "\n".join(lines)


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

def get_catalog_extraction_prompt(
    document_id: str,
    track: Track,
    text: str,
    catalog: tuple[EvidenceFieldSpec, ...],
    evidence_map_summary: str,
    extraction_target: ExtractionTarget | None = None,
    channel_classification: DocumentChannelClassification | None = None,
) -> str:
    catalog_text = _catalog_compact_text(catalog)
    target_section = _target_prompt_section(extraction_target)
    relationship_guidance = relationship_decision_guidance()
    channel_strategy = get_channel_strategy_guidance(channel_classification)
    boundary_guidance = disease_boundary_guidance()
    return f"""You are extracting structured evidence from a biomedical document for a SPECIFIC target gene-disease pair.

{target_section}

STRICT TARGET RULES:
1. Extract evidence ONLY for the target gene-disease pair above when a target is provided.
2. Other genes mentioned for comparison, controls, family history, or differential diagnosis are context; do NOT extract them as primary findings.
3. If the document discusses multiple diseases, extract ONLY evidence relevant to the target disease as primary evidence.
4. The A.gene_symbol field MUST be a single string, not a list.

EVIDENCE ROLE: For each evidence item, assign evidence_role:
- "primary": directly supports or describes the TARGET gene-disease pair
- "phenotype": syndrome, subtype, HPO term, or downstream manifestation caused by the target disease
- "comparator": disease/gene mentioned only for differential diagnosis, comparison, controls, or exclusion
- "context": background information not specific to this target

Document ID: {document_id}
Track: {track.value}

EVIDENCE MAP SUMMARY:
{evidence_map_summary}

EVIDENCE CATALOG (field_id: field_name [ACMG_codes], * = required for scoring):
{catalog_text}

CATALOG SCOPE:
- This catalog is pre-scoped to eligible fields for the current extraction pass.
- Extract only the listed eligible fields. Do not add fields outside this catalog.
- Set status="not_found" for listed eligible fields when the document does not support a value.

{channel_strategy}

RULES:
1. For each catalog field, set status="found" with the extracted value, or status="not_found" if absent.
2. Do not score or classify ACMG/GDV evidence.
3. For "found" items, you MUST provide a source with block_index, context_type, context_ref, and text_snippet.
4. Extract assigned_acmg_codes and assigned_clingen_modules based on what the document supports.
5. Set confidence based on extraction certainty (0.0-1.0).
6. Use status="ocr_gap" only when the document indicates the evidence is in an image/table/figure but the text needed for extraction is unavailable.
7. Do not invent external database values. If allele frequency or ClinVar-like data is absent, mark it not_found and note that external completion is required.
8. For B.diagnosis_sufficiency, require an explicit diagnostic statement supported by genetic testing and/or clinical criteria.
9. For B.biochemical_markers, prefer baseline biochemical markers. Mention treatment response only as auxiliary context, not as scoring evidence.
10. source.text_snippet must be a verbatim continuous substring of DOCUMENT BLOCKS.
11. Copy punctuation exactly as it appears in the source, including Chinese punctuation (、。，；). Do not normalize or substitute.
12. Do not use "..." or "……" to bridge gaps, compress text, or join non-adjacent spans.
13. For translated track, still copy the snippet from the translated document text as written; do not retranslate or paraphrase it.
14. The snippet must be a verbatim continuous substring of the source text.
15. Copy punctuation exactly as it appears in the source text.
16. Do not calculate character offsets. Leave start_offset and end_offset absent or at defaults.
17. For A.gene_symbol, exhaustively extract a standalone HGNC-style gene symbol from titles, abstracts, variant descriptions, tables, and disease modifiers. If the gene appears as a disease-name prefix such as "AARS2-related disease", "AARS2-mutation related mitochondrial disease", or "AARS1-associated Charcot-Marie-Tooth disease", you must extract the gene symbol independently into A.gene_symbol and must not leave A.gene_symbol as not_found.
18. For A.gene_disease_relationship, the value MUST be one of: "causative", "associated", "susceptibility", "uncertain", "disputed", "refuted", "no_relationship". Do NOT return sentences or descriptions.
    Decision guidance:
{relationship_guidance}
19. For B.disease_diagnosis, extract ONLY the primary disease name relevant to the target gene (e.g., "Fabry disease", "Charcot-Marie-Tooth disease"). Do NOT extract lists of unrelated diseases, background comorbidities, or general medical history.
20. For B.disease_diagnosis, if the document mentions multiple diseases, extract ONLY the one most directly linked to the gene being curated. Ignore incidental mentions of other conditions.
{boundary_guidance}
21. For B.age_of_onset, extract referral, diagnosis, first symptoms, or presentation age. Do NOT use developmental milestones as B.age_of_onset, for example sitting, walking, or speaking ages unless the sentence explicitly states symptom onset.
22. Computational predictions support PP3/BP4 only. Do not treat in silico predictions as F.functional_result, F.assay_type, or other functional evidence fields unless there is a real wet-lab, cell, animal, or patient-derived assay.
23. E.prediction_tools_list requires named tools such as SpliceAI, CADD, REVEL, PolyPhen-2, SIFT, MutationTaster, or MaxEntScan. Generic phrases like "in silico tools" are insufficient and must be not_found.
24. For B.clinical_phenotypes, extract the patient's observed clinical features, symptoms, and signs — NOT the disease diagnosis name. Examples of valid phenotypes: seizures, developmental regression, ataxia, intellectual disability, loss of acquired hand skills, stereotypic hand movements, tremor, rigidity, bradykinesia, hypotonia, spasticity. Multiple phenotypes should be separated by semicolons. Do NOT use disease names (e.g. "Parkinson disease", "Rett syndrome") as phenotypes.
25. For B.mode_of_inheritance_reported, extract ONLY if the document explicitly states the inheritance pattern (e.g. "autosomal dominant", "autosomal recessive", "X-linked"). Do NOT infer inheritance from variant zygosity alone. If the document says "heterozygous variant" without stating the inheritance pattern, set not_found.
26. For C.de_novo_status, extract ONLY if the document explicitly confirms de novo status with parental or family testing evidence (e.g. "confirmed de novo", "de novo in the proband", "not inherited from parents"). Do NOT infer de novo from absence of family history alone.
27. For B.hpo_terms, extract HPO phenotype terms or clinical feature descriptions that correspond to HPO concepts. Use the HPO term name or ID if provided in the document. Multiple terms: separate with semicolons.

DOCUMENT BLOCKS:
{text}
"""


def get_special_evidence_prompt(
    document_id: str,
    track: Track,
    text: str,
    current_items_summary: str,
) -> str:
    return f"""You are performing a focused second pass on a biomedical document.

SCOPE: This pass is a focused gap-filler. The primary catalog extraction has
already produced the items shown in CURRENT EXTRACTION SUMMARY. Only emit
records for functional, case-control, authority, or contradiction evidence
that is NOT already represented there, OR where you have strictly higher-
confidence evidence (e.g. a direct quote vs an inferred summary). Do not
restate items already present.

Document ID: {document_id}
Track: {track.value}

CURRENT EXTRACTION SUMMARY:
{current_items_summary}

FOCUS ON:
1. Functional experiments (assays, cell studies, animal models)
2. Case-control studies (statistical evidence)
3. Authority/reference assertions (ClinVar, expert panels, known pathogenic variants)
4. Contradiction or exclusion evidence (negative results, alternative diagnoses)

For each finding, provide:
- record_type: "functional", "case_control", "authority", or "contradiction"
- description: what was found
- evidence_field_ids: which catalog fields this relates to
- source: location in document
- confidence: 0.0-1.0

SOURCE RULES:
- Reuse exact document wording.
- source.text_snippet must be a verbatim continuous substring of DOCUMENT BLOCKS.
- Copy punctuation exactly as it appears in the source, including Chinese punctuation (、。，；). Do not normalize or substitute.
- Do not shorten snippets with "..." or paraphrase them.
- If a snippet comes from a title, discussion paragraph, table caption, or table body, keep that exact text.
- Use block_index, context_type, context_ref, and text_snippet to identify the source.
- Do not calculate character offsets. Leave start_offset and end_offset absent or at defaults.
- The snippet must be a verbatim continuous substring of the source text.
- Copy punctuation exactly as it appears in the source text.

Do not score or classify ACMG/GDV evidence. Only extract structured facts.

DOCUMENT BLOCKS:
{text}
"""


def get_source_ambiguity_review_prompt(
    document_text: str,
    snippet: str,
    candidate_locations: list[dict[str, int]],
) -> str:
    candidates_text = "\n".join(
        f"  - page={c['page']}, start={c['start_offset']}, end={c['end_offset']}"
        for c in candidate_locations
    )
    return f"""A text snippet appears multiple times in a document. Select the best source location.

SNIPPET: "{snippet}"

CANDIDATE LOCATIONS:
{candidates_text}

DOCUMENT TEXT:
{document_text}

Select the location that best matches the context where this evidence is discussed (not just mentioned in passing).
Return the index (0-based) of the best candidate.
"""


def get_clinical_context_prompt(
    document_id: str,
    track: Track,
    text: str,
    current_items_summary: str,
) -> str:
    return f"""You are extracting clinical context from a biomedical document.

FOCUS: Extract ONLY the following fields. Do NOT extract any other fields.

FIELDS:
- B.clinical_phenotypes: Patient's clinical presentation, symptoms, neurological features,
  developmental regression, seizures, movement abnormalities, tremor, rigidity, bradykinesia,
  ataxia, intellectual disability, motor delay, speech delay, hypotonia, spasticity.
  Multiple phenotypes: separate with semicolons (e.g. "seizures; developmental regression; ataxia").
  Do NOT copy the disease diagnosis as a phenotype. Extract actual observed symptoms and signs.
- B.sex: Explicit sex or gender of the patient (e.g. "male", "female"). Only extract if clearly stated.
- B.age_of_onset: Age at first symptoms, diagnosis, or presentation. Only extract explicit ages
  (e.g. "3 years", "onset at age 2", "neonatal"). Do NOT use developmental milestones
  (sitting, walking, talking) unless they are explicitly described as symptom onset.
- B.mode_of_inheritance_reported: Inheritance pattern stated in the document
  (e.g. "autosomal recessive", "autosomal dominant", "X-linked", "AD", "AR", "XL").
  Only extract if explicitly stated.
- C.inheritance_source: Whether the variant was inherited or arose de novo
  (e.g. "inherited from mother", "paternal", "maternal", "de novo"). Must have family/
  parental/genotyping evidence.
- C.de_novo_status: Whether the variant was confirmed as de novo
  (e.g. "confirmed de novo", "likely de novo", "inherited"). Requires parental testing
  or family study evidence.

RULES:
1. Each found item MUST include a source with text_snippet that is a verbatim substring of the document.
2. Set status="found" with extracted value, or status="not_found" if the document does not contain the information.
3. Do not invent information not present in the document.
4. Confidence should reflect extraction certainty (0.0-1.0).
5. For B.clinical_phenotypes, look in case descriptions, clinical findings, patient presentations,
   results sections, tables with clinical features. Do NOT use disease names as phenotypes.

Document ID: {document_id}
Track: {track.value}

CURRENT EXTRACTION SUMMARY (what has already been extracted):
{current_items_summary}

DOCUMENT TEXT:
{text}
"""


def get_core_identity_retry_prompt(
    document_id: str,
    track: Track,
    text: str,
    extraction_target: ExtractionTarget,
) -> str:
    """Compact retry prompt targeting only core identity fields.

    Used when the normal catalog extraction fails to produce FOUND items
    for ``A.gene_symbol`` or ``B.disease_diagnosis``.  The prompt is
    deliberately small (4 fields, no full catalog) to maximise extraction
    reliability on these critical fields.
    """
    return f"""You are extracting core identity fields from a biomedical document.

TARGET GENE: {extraction_target.gene_symbol}
TARGET DISEASE: {extraction_target.disease_name}

Extract ONLY these four fields. For each, set status="found" with the
extracted value, or status="not_found" if the document does not support it.

FIELDS:
- A.gene_symbol: Extract the target gene symbol ({extraction_target.gene_symbol}) ONLY if it
  appears in the document text, title, abstract, or is unambiguously stated as the gene under study.
  Do NOT extract other genes mentioned for comparison or background.
- B.disease_diagnosis: Extract the target disease ({extraction_target.disease_name}) ONLY if the
  document discusses this disease (or a close named synonym) in relation to the target gene/variant.
  Do NOT extract unrelated diseases.
- A.variant_hgvs_c: Extract an exact HGVS coding-level variant string (e.g. "c.880C>T") ONLY if
  it appears verbatim in the document. Do NOT infer or construct variant strings.
- A.variant_hgvs_p: Extract an exact HGVS protein-level variant string (e.g. "p.R294X") ONLY if
  it appears verbatim in the document. Do NOT infer or construct variant strings.

RULES:
1. Do not infer values that are not explicitly stated in the document.
2. For found items, provide source with context_type, context_ref, and text_snippet (verbatim substring).
3. Confidence should reflect certainty (0.0-1.0).

Document ID: {document_id}
Track: {track.value}

DOCUMENT TEXT:
{text}
"""
