"""Prompt builders for evidence extraction stages."""
from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .catalog import EvidenceFieldSpec
    from .contracts import ContentBlock, Track, TrackDocument


_EVIDENCE_MAP_JSON_EXAMPLE = {
    "relevant": False,
    "disease_terms": [],
    "gene_terms": [],
    "variant_terms": [],
    "case_references": [],
    "authority_references": [],
    "contradictions": [],
    "structure_hints": [],
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
    return f"""You are analyzing a biomedical document for evidence extraction.

Document ID: {document_id}
Track: {track.value}

TASK: Determine if this document contains GDV/ACMG-relevant evidence. If relevant, identify:
- Disease terms mentioned
- Gene symbols mentioned
- Variant identifiers mentioned
- Case/proband references
- Authority or database references (ClinVar, expert panels)
- Any contradictions or exclusions noted
- Structural hints (tables, figures, supplementary material)

RELEVANCE CRITERIA — set "relevant" to true if the document mentions ANY of:
- Disease or phenotype names (e.g. Fabry disease, cancer, cardiomyopathy)
- Gene symbols (e.g. GLA, BRCA1, TP53)
- Genetic variants (e.g. p.R227X, c.680C>T, rs12345)
- Patient cases, probands, or family studies
- Diagnostic or clinical findings related to genetic conditions

Set "relevant" to false ONLY for documents that are purely methodological, editorial, administrative, or completely unrelated to biomedical/genetic evidence.

Do not score or classify ACMG/GDV evidence. Only scan for relevance and structure.

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
