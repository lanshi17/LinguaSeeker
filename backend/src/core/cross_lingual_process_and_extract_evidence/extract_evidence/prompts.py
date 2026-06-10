"""Prompt builders for evidence extraction stages."""
from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .catalog import EvidenceFieldSpec
    from .contracts import ContentBlock, Track, TrackDocument


_EVIDENCE_MAP_JSON_EXAMPLE = {
    "relevant": True,
    "disease_terms": ["Fabry disease", "renal failure"],
    "gene_terms": ["GLA"],
    "variant_terms": ["p.R227X", "c.680C>T"],
    "case_references": ["proband", "family members"],
    "authority_references": ["ClinVar"],
    "contradictions": [],
    "structure_hints": ["Table 1: clinical features"],
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
    for value in (block.text, block.content, block.table_body):
        if value.strip():
            parts.append(value.strip())
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

JSON OUTPUT:
Return only a single valid json object. Do not wrap it in markdown code fences or add commentary.
Return JSON matching this schema (fill in values found in the document):
{json.dumps(_EVIDENCE_MAP_JSON_EXAMPLE, ensure_ascii=False, indent=2)}

DOCUMENT TEXT:
{text}
"""


def get_catalog_extraction_prompt(
    document_id: str,
    track: Track,
    text: str,
    catalog: tuple[EvidenceFieldSpec, ...],
    evidence_map_summary: str,
) -> str:
    catalog_text = _catalog_compact_text(catalog)
    return f"""You are extracting structured evidence from a biomedical document.

Document ID: {document_id}
Track: {track.value}

EVIDENCE MAP SUMMARY:
{evidence_map_summary}

EVIDENCE CATALOG (field_id: field_name [ACMG_codes], * = required for scoring):
{catalog_text}

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
    Decision guidance: Use "causative" when the document supports an established causal relationship: known disease gene, pathogenic variants causing the disease, ACMG pathogenic/likely pathogenic variants in affected cases, ClinGen Definitive/Strong/Moderate curation, or replicated genetic/functional evidence. Do not choose associated merely because the sentence contains associated; choose "associated" only when the gene-disease link itself is explicitly preliminary, correlative, risk-modifying, or not established as causal.
19. For B.disease_diagnosis, extract ONLY the primary disease name relevant to the target gene (e.g., "Fabry disease", "Charcot-Marie-Tooth disease"). Do NOT extract lists of unrelated diseases, background comorbidities, or general medical history.
20. For B.disease_diagnosis, if the document mentions multiple diseases, extract ONLY the one most directly linked to the gene being curated. Ignore incidental mentions of other conditions.
21. For B.age_of_onset, extract referral, diagnosis, first symptoms, or presentation age. Do NOT use developmental milestones as B.age_of_onset, for example sitting, walking, or speaking ages unless the sentence explicitly states symptom onset.
22. Computational predictions support PP3/BP4 only. Do not treat in silico predictions as F.functional_result, F.assay_type, or other functional evidence fields unless there is a real wet-lab, cell, animal, or patient-derived assay.
23. E.prediction_tools_list requires named tools such as SpliceAI, CADD, REVEL, PolyPhen-2, SIFT, MutationTaster, or MaxEntScan. Generic phrases like "in silico tools" are insufficient and must be not_found.

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
