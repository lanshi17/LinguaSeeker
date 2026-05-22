"""Prompt builders for evidence extraction stages."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .catalog import EvidenceFieldSpec
    from .contracts import Track


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

Do not score or classify ACMG/GDV evidence. Only scan for relevance and structure.

JSON OUTPUT:
Return only a single valid json object. Do not wrap it in markdown code fences or add commentary.
Use this exact shape:
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
3. For "found" items, you MUST provide a source with span_id, page, start_offset, end_offset, context_type, context_ref, and text_snippet.
4. Extract assigned_acmg_codes and assigned_clingen_modules based on what the document supports.
5. Set confidence based on extraction certainty (0.0-1.0).
6. Use status="ocr_gap" only when the document indicates the evidence is in an image/table/figure but the text needed for extraction is unavailable.
7. Do not invent external database values. If allele frequency or ClinVar-like data is absent, mark it not_found and note that external completion is required.
8. For B.diagnosis_sufficiency, require an explicit diagnostic statement supported by genetic testing and/or clinical criteria.
9. For B.biochemical_markers, prefer baseline biochemical markers. Mention treatment response only as auxiliary context, not as scoring evidence.

DOCUMENT TEXT:
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

Do not score or classify ACMG/GDV evidence. Only extract structured facts.

DOCUMENT TEXT:
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
