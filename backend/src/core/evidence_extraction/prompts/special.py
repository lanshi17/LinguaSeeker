"""Prompt builders for evidence extraction stages."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ..contracts import Track

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
        f"  - page={c['page']}, start={c['start_offset']}, end={c['end_offset']}" for c in candidate_locations
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


