"""Token-budgeted prompt chunking helpers for evidence extraction."""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import DocumentEvidenceMap
from ..cross_lingual.format.segmenter import segment_text

DEFAULT_INPUT_BUDGET_TOKENS = 16_000
_SAFETY_MARGIN_TOKENS = 20


@dataclass(frozen=True)
class EvidencePromptChunk:
    """One prompt-safe slice of document text."""

    index: int
    total: int
    text: str
    block_indices: tuple[int, ...] = ()


def build_text_prompt_chunks(
    text: str,
    input_budget_tokens: int = DEFAULT_INPUT_BUDGET_TOKENS,
    prompt_overhead_tokens: int = 0,
) -> list[EvidencePromptChunk]:
    """Split plain document text into prompt-safe chunks."""
    segments = segment_text(
        text,
        max_tokens=input_budget_tokens,
        prompt_overhead_tokens=prompt_overhead_tokens,
    )
    total = len(segments)
    return [
        EvidencePromptChunk(index=index, total=total, text=segment)
        for index, segment in enumerate(segments, start=1)
    ]


def merge_evidence_maps(maps: list[DocumentEvidenceMap]) -> DocumentEvidenceMap:
    """Merge chunk-level relevance scans into one document-level evidence map."""
    if not maps:
        return DocumentEvidenceMap(relevant=False)
    return DocumentEvidenceMap(
        relevant=any(item.relevant for item in maps),
        disease_terms=_dedupe([term for item in maps for term in item.disease_terms]),
        gene_terms=_dedupe([term for item in maps for term in item.gene_terms]),
        variant_terms=_dedupe([term for item in maps for term in item.variant_terms]),
        case_references=_dedupe([term for item in maps for term in item.case_references]),
        authority_references=_dedupe([term for item in maps for term in item.authority_references]),
        contradictions=_dedupe([term for item in maps for term in item.contradictions]),
        structure_hints=_dedupe([term for item in maps for term in item.structure_hints]),
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
