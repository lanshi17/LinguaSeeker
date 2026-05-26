"""Token-budgeted prompt chunking helpers for evidence extraction."""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import ContentBlock, DocumentEvidenceMap, TrackDocument
from .prompts import block_readable_text, format_block_prompt_entry
from ..cross_lingual.format.segmenter import estimate_tokens, segment_text

DEFAULT_INPUT_BUDGET_TOKENS = 16_000
_DEFAULT_SEAM_CONTEXT_CHARS = 150
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
    seam_context_chars: int = _DEFAULT_SEAM_CONTEXT_CHARS,
) -> list[EvidencePromptChunk]:
    """Split plain document text into prompt-safe chunks."""
    segments = segment_text(
        text,
        max_tokens=input_budget_tokens,
        prompt_overhead_tokens=prompt_overhead_tokens,
    )
    total = len(segments)
    return [
        EvidencePromptChunk(
            index=index,
            total=total,
            text=_add_seam_context(segments, idx, seam_context_chars),
        )
        for idx, index in enumerate(range(1, total + 1))
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


def build_block_prompt_chunks(
    document: TrackDocument,
    input_budget_tokens: int = DEFAULT_INPUT_BUDGET_TOKENS,
    prompt_overhead_tokens: int = 0,
    seam_context_chars: int = _DEFAULT_SEAM_CONTEXT_CHARS,
) -> list[EvidencePromptChunk]:
    """Split document blocks into prompt-safe chunks while preserving block indices."""
    if not document.blocks:
        return build_text_prompt_chunks(
            document.formatted_text, input_budget_tokens, prompt_overhead_tokens, seam_context_chars,
        )

    effective_budget = max(1, input_budget_tokens - prompt_overhead_tokens - _SAFETY_MARGIN_TOKENS)
    pending_texts: list[str] = []
    pending_indices: list[int] = []
    raw_chunks: list[tuple[str, tuple[int, ...]]] = []

    for block_index, block in enumerate(document.blocks):
        body = block_readable_text(block)
        if not body:
            continue
        entries = _block_entries(block_index, block, body, effective_budget)
        for entry_text, entry_indices in entries:
            candidate = "\n\n".join([*pending_texts, entry_text]) if pending_texts else entry_text
            if pending_texts and estimate_tokens(candidate) > effective_budget:
                raw_chunks.append(("\n\n".join(pending_texts), tuple(pending_indices)))
                pending_texts = [entry_text]
                pending_indices = list(entry_indices)
                continue
            pending_texts.append(entry_text)
            pending_indices.extend(entry_indices)

    if pending_texts:
        raw_chunks.append(("\n\n".join(pending_texts), tuple(pending_indices)))

    texts = [text for text, _ in raw_chunks]
    total = len(raw_chunks)
    return [
        EvidencePromptChunk(
            index=idx + 1,
            total=total,
            text=_add_seam_context(texts, idx, seam_context_chars),
            block_indices=indices,
        )
        for idx, (_, indices) in enumerate(raw_chunks)
    ]


def _add_seam_context(segments: list[str], idx: int, chars: int) -> str:
    """Append neighboring segment context so evidence at boundaries isn't lost."""
    parts: list[str] = [segments[idx]]
    if idx > 0:
        recap = segments[idx - 1][-chars:]
        parts.append(f"\n\n--- PREVIOUS CONTEXT ---\n{recap}")
    if idx < len(segments) - 1:
        preview = segments[idx + 1][:chars]
        parts.append(f"\n\n--- NEXT CONTEXT ---\n{preview}")
    return "".join(parts)


def _block_entries(
    block_index: int,
    block: ContentBlock,
    body: str,
    effective_budget: int,
) -> list[tuple[str, tuple[int, ...]]]:
    entry = format_block_prompt_entry(block_index, block, body)
    if estimate_tokens(entry) <= effective_budget:
        return [(entry, (block_index,))]

    header_overhead = estimate_tokens(format_block_prompt_entry(block_index, block, ""))
    body_segments = segment_text(
        body,
        max_tokens=effective_budget,
        prompt_overhead_tokens=header_overhead,
    )
    return [
        (format_block_prompt_entry(block_index, block, segment), (block_index,))
        for segment in body_segments
    ]
