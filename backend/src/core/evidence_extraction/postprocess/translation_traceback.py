"""Deterministic English-to-original traceback for translated evidence."""

from __future__ import annotations

import re

from src.core.cross_lingual_translation.contracts import TranslationAlignmentChunk, TranslationSpanPair
from src.utils.text_normalize import find_html_aware

from ..contracts import (
    EvidenceExtractionResult,
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    SourceLocation,
    SourcePrecision,
    SpecialEvidenceRecord,
    TrackDocument,
)


_SPACE_RE = re.compile(r"\s+")


def apply_translation_traceback(
    original_document: TrackDocument,
    translated_document: TrackDocument,
    result: EvidenceExtractionResult,
) -> EvidenceExtractionResult:
    """Attach original-language raw sources to English-grounded extraction output."""
    return result.model_copy(
        update={
            "evidence_items": [
                _trace_item(original_document, translated_document, item) for item in result.evidence_items
            ],
            "phenotype_evidence": [
                _trace_item(original_document, translated_document, item) for item in result.phenotype_evidence
            ],
            "special_evidence": [
                _trace_special_record(original_document, translated_document, record)
                for record in result.special_evidence
            ],
        }
    )


def _trace_item(
    original_document: TrackDocument,
    translated_document: TrackDocument,
    item: EvidenceItem,
) -> EvidenceItem:
    if item.status != EvidenceStatus.FOUND:
        return item
    source = item.source or item.raw_source
    if source is None:
        return item
    original_source = _map_source_to_original(
        original_document,
        translated_document.translation_alignment,
        source,
    )
    if original_source is None:
        return item
    return item.model_copy(
        update={
            "raw_source": original_source,
            "notes": _append_note(item.notes, "translation_traceback: original source mapped from English span"),
        }
    )


def _trace_special_record(
    original_document: TrackDocument,
    translated_document: TrackDocument,
    record: SpecialEvidenceRecord,
) -> SpecialEvidenceRecord:
    source = record.source or record.raw_source
    if source is None:
        return record
    original_source = _map_source_to_original(
        original_document,
        translated_document.translation_alignment,
        source,
    )
    if original_source is None:
        return record
    return record.model_copy(update={"raw_source": original_source})


def _map_source_to_original(
    original_document: TrackDocument,
    chunks: list[TranslationAlignmentChunk],
    source: SourceLocation,
) -> SourceLocation | None:
    if not chunks:
        return _map_identity_source_to_original(original_document, source)

    chunk = _select_alignment_chunk(chunks, source)
    if chunk is None:
        return None

    pair = _select_alignment_pair(chunk, source)
    if pair is not None:
        start, end = pair.original_start_offset, pair.original_end_offset
        precision = SourcePrecision.EXACT
        snippet = pair.original_text
        if start >= 0 and end >= start and end <= len(original_document.formatted_text):
            snippet = original_document.formatted_text[start:end]
        span = _find_span(original_document.page_spans, start, end)
        block_index = _find_block_index(original_document, snippet, chunk.block_index)
        bbox = original_document.blocks[block_index].bbox if 0 <= block_index < len(original_document.blocks) else []
        context_ref = (
            f"{source.context_ref} | translation_traceback:{chunk.chunk_id}:{pair.pair_id}"
            if source.context_ref
            else f"translation_traceback:{chunk.chunk_id}:{pair.pair_id}"
        )
        return SourceLocation(
            span_id=span.span_id,
            page=span.page,
            start_offset=start,
            end_offset=end,
            context_type=source.context_type,
            context_ref=context_ref,
            text_snippet=snippet,
            block_index=block_index,
            bbox=bbox,
            block_type=source.block_type,
            source_precision=precision,
        )

    start, end, precision = _resolve_original_offsets(original_document, chunk)
    snippet = chunk.original_text
    if start >= 0 and end >= start and end <= len(original_document.formatted_text):
        snippet = original_document.formatted_text[start:end]

    span = _find_span(original_document.page_spans, start, end)
    block_index = _find_block_index(original_document, snippet, chunk.block_index)
    bbox = original_document.blocks[block_index].bbox if 0 <= block_index < len(original_document.blocks) else []
    context_ref = (
        f"{source.context_ref} | translation_traceback:{chunk.chunk_id}"
        if source.context_ref
        else f"translation_traceback:{chunk.chunk_id}"
    )
    return SourceLocation(
        span_id=span.span_id,
        page=span.page,
        start_offset=start,
        end_offset=end,
        context_type=source.context_type,
        context_ref=context_ref,
        text_snippet=snippet,
        block_index=block_index,
        bbox=bbox,
        block_type=source.block_type,
        source_precision=precision,
    )


def _map_identity_source_to_original(
    original_document: TrackDocument,
    source: SourceLocation,
) -> SourceLocation | None:
    snippet = source.text_snippet
    start, end = find_html_aware(original_document.formatted_text, snippet) if snippet else (-1, -1)
    precision = SourcePrecision.EXACT
    if start >= 0:
        snippet = original_document.formatted_text[start:end]
    elif 0 <= source.start_offset <= source.end_offset <= len(original_document.formatted_text):
        start = source.start_offset
        end = source.end_offset
        snippet = original_document.formatted_text[start:end]
        precision = SourcePrecision.CORRECTED
    else:
        return None

    span = _find_span(original_document.page_spans, start, end)
    block_index = _find_block_index(original_document, snippet, source.block_index)
    bbox = original_document.blocks[block_index].bbox if 0 <= block_index < len(original_document.blocks) else []
    context_ref = (
        f"{source.context_ref} | translation_traceback:identity"
        if source.context_ref
        else "translation_traceback:identity"
    )
    return SourceLocation(
        span_id=span.span_id,
        page=span.page,
        start_offset=start,
        end_offset=end,
        context_type=source.context_type,
        context_ref=context_ref,
        text_snippet=snippet,
        block_index=block_index,
        bbox=bbox,
        block_type=source.block_type,
        source_precision=precision,
    )


def _select_alignment_chunk(
    chunks: list[TranslationAlignmentChunk],
    source: SourceLocation,
) -> TranslationAlignmentChunk | None:
    if source.start_offset >= 0 and source.end_offset >= source.start_offset:
        for chunk in chunks:
            if chunk.english_start_offset <= source.start_offset and source.end_offset <= chunk.english_end_offset:
                return chunk

    snippet = _normalize(source.text_snippet)
    if snippet:
        for chunk in chunks:
            english = _normalize(chunk.english_text)
            if snippet in english or english in snippet:
                return chunk
    return None


def _select_alignment_pair(
    chunk: TranslationAlignmentChunk,
    source: SourceLocation,
) -> TranslationSpanPair | None:
    """Select the narrowest span pair matching the English source location."""
    if not chunk.span_pairs:
        return None

    if source.start_offset >= 0 and source.end_offset >= source.start_offset:
        matching = [
            pair
            for pair in chunk.span_pairs
            if (pair.english_start_offset <= source.start_offset and source.end_offset <= pair.english_end_offset)
            or (source.start_offset < pair.english_end_offset and source.end_offset > pair.english_start_offset)
        ]
        if matching:
            return min(
                matching,
                key=lambda pair: pair.english_end_offset - pair.english_start_offset,
            )

    snippet = _normalize(source.text_snippet)
    if snippet:
        for pair in chunk.span_pairs:
            english = _normalize(pair.english_text)
            if snippet in english or english in snippet:
                return pair
    return None


def _resolve_original_offsets(
    original_document: TrackDocument,
    chunk: TranslationAlignmentChunk,
) -> tuple[int, int, SourcePrecision]:
    if chunk.original_text:
        start = original_document.formatted_text.find(chunk.original_text)
        if start >= 0:
            return start, start + len(chunk.original_text), SourcePrecision.EXACT

    start = chunk.original_start_offset
    end = chunk.original_end_offset
    if start >= 0 and end >= start:
        return start, end, SourcePrecision.CORRECTED
    return -1, -1, SourcePrecision.CORRECTED


def _find_span(page_spans: list[PageSpan], start: int, end: int) -> PageSpan:
    for span in page_spans:
        if start >= span.start_offset and end <= span.end_offset:
            return span
    if page_spans:
        return page_spans[0]
    return PageSpan(span_id="original-p1", page=1, start_offset=max(start, 0), end_offset=max(end, 0))


def _find_block_index(
    document: TrackDocument,
    snippet: str,
    fallback: int,
) -> int:
    for index, block in enumerate(document.blocks):
        block_text = _block_text(block)
        if snippet and find_html_aware(block_text, snippet)[0] >= 0:
            return index
    if 0 <= fallback < len(document.blocks):
        return fallback
    return -1


def _block_text(block: object) -> str:
    parts: list[str] = []
    for attr in ("text", "content", "table_body", "code_body"):
        value = getattr(block, attr, "")
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    for attr in ("image_caption", "table_caption", "chart_caption", "list_items"):
        value = getattr(block, attr, [])
        if isinstance(value, list):
            parts.extend(str(item).strip() for item in value if str(item).strip())
    return "\n".join(parts)


def _normalize(value: str) -> str:
    return _SPACE_RE.sub(" ", value.strip()).casefold()


def _append_note(existing: str, addition: str) -> str:
    if not existing.strip():
        return addition
    if addition in existing:
        return existing
    return f"{existing.rstrip()} {addition}"
