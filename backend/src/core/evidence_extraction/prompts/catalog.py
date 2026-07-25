"""Prompt builders for evidence extraction stages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .evidence_map import (
    _target_prompt_section,
    disease_boundary_guidance,
    expanded_field_coverage_guidance,
    get_channel_strategy_guidance,
    relationship_decision_guidance,
)

if TYPE_CHECKING:
    from ..domain.catalog import EvidenceFieldSpec
    from ..domain.channel_contracts import DocumentChannelClassification
    from ..contracts import ExtractionTarget, Track

def _catalog_compact_text(catalog: tuple[EvidenceFieldSpec, ...]) -> str:
    lines: list[str] = []
    for spec in catalog:
        codes = ",".join(spec.acmg_codes) if spec.acmg_codes else "-"
        req = "*" if spec.required_for_scorable else ""
        lines.append(f"{spec.field_id}{req}: {spec.field_name} [{codes}]")
    return "\n".join(lines)



def get_catalog_extraction_prompt(
    document_id: str,
    track: Track,
    text: str,
    catalog: tuple[EvidenceFieldSpec, ...],
    evidence_map_summary: str,
    extraction_target: ExtractionTarget | None = None,
    channel_classification: DocumentChannelClassification | None = None,
    graph_context: str = "",
) -> str:
    catalog_text = _catalog_compact_text(catalog)
    target_section = _target_prompt_section(extraction_target)
    relationship_guidance = relationship_decision_guidance()
    channel_strategy = get_channel_strategy_guidance(channel_classification)
    boundary_guidance = disease_boundary_guidance()
    expanded_guidance = expanded_field_coverage_guidance()
    graph_section = _format_graph_context(graph_context)
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

{expanded_guidance}

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

{graph_section}
DOCUMENT BLOCKS:
{text}
"""


def _format_graph_context(graph_context: str) -> str:
    """Return a formatted graph context block, or empty string if none."""
    if not graph_context or not graph_context.strip():
        return ""
    return (
        "RELEVANT BIOMEDICAL KNOWLEDGE GRAPH CONTEXT (use as background, "
        "but ground all source snippets in the document blocks below):\n\n"
        f"{graph_context}\n"
    )


