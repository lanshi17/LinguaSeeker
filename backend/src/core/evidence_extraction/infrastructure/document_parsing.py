"""Document parsing helpers for evidence extraction.

Utilities for loading track documents from persisted JSON, filtering
evidence sections, and building formatted text with page spans.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from loguru import logger

from src.core.cross_lingual_translation.contracts import TranslationAlignmentChunk
from src.core.standardize_entities_and_align_knowledge.context_pack.contracts import (
    TargetContextPack,
)
from src.core.standardize_entities_and_align_knowledge.context_pack.core import (
    build_context_pack_from_runtime_target,
)
from src.utils.text_normalize import unescape_mined_strings, unescape_mined_text

from ..contracts import (
    ContentBlock,
    DualTrackDocuments,
    EvidenceExtractionResult,
    ExtractionTarget,
    PageSpan,
    Track,
    TrackDocument,
)


ExtractionTrackMode = Literal["dual", "original_only", "english_pivot"]


def _resolve_extraction_track_mode(raw: str) -> ExtractionTrackMode:
    if raw not in ("dual", "original_only", "english_pivot"):
        raise ValueError(f"Unknown extraction_track_mode {raw!r}")
    return raw  # type: ignore[return-value]


def _build_runtime_context_pack(
    documents: DualTrackDocuments,
    original_result: EvidenceExtractionResult,
    translated_result: EvidenceExtractionResult,
) -> TargetContextPack | None:
    target = (
        original_result.extraction_target
        or translated_result.extraction_target
        or documents.original.extraction_target
        or documents.translated.extraction_target
    )
    if target is None:
        return None
    source_pmid = documents.original.external_ids.pmid or documents.translated.external_ids.pmid
    source_pmc = documents.original.external_ids.pmcid or documents.translated.external_ids.pmcid
    return build_context_pack_from_runtime_target(
        entry_id=target.clingen_entry_id or documents.document_id,
        gene_symbol=target.gene_symbol,
        disease_label=target.disease_name,
        hgnc_id=_first_metadata_value(documents, "hgnc_id"),
        mondo_id=_first_metadata_value(documents, "mondo_id"),
        moi=_first_metadata_value(documents, "moi", "mode_of_inheritance"),
        source_pmid=source_pmid,
        source_pmc=source_pmc,
    )


def _first_metadata_value(documents: DualTrackDocuments, *keys: str) -> str | None:
    for document in (documents.original, documents.translated):
        for key in keys:
            value = document.metadata.get(key, "").strip()
            if value:
                return value
    return None


def _build_track_document_from_json(
    path: Path,
    track: Track,
    extraction_target: ExtractionTarget | None = None,
) -> TrackDocument:
    data = json.loads(path.read_text(encoding="utf-8"))
    metadata = data.get("metadata", {})
    document_id = metadata.get("doc_id") or path.parent.name
    blocks = data.get("blocks", [])
    evidence_blocks = _filter_evidence_blocks(blocks)
    parsed_blocks = _parse_content_blocks(evidence_blocks)
    formatted_text, page_spans = _format_blocks_with_page_spans(evidence_blocks, track)

    # Fallback: when blocks are empty, use persisted formatted_text
    if not formatted_text and data.get("formatted_text"):
        formatted_text = _filter_evidence_text(unescape_mined_text(str(data["formatted_text"])))
        page_spans = [
            PageSpan(
                span_id=f"{track.value}-p1",
                page=1,
                start_offset=0,
                end_offset=len(formatted_text),
            )
        ]

    return TrackDocument(
        document_id=document_id,
        track=track,
        formatted_text=formatted_text,
        page_spans=page_spans,
        blocks=parsed_blocks,
        metadata={
            "source_path": str(path),
            "source_language": str(metadata.get("source_language", "")),
        },
        translation_alignment=_parse_translation_alignment(metadata.get("translation_alignment")),
        extraction_target=extraction_target,
    )


def _parse_translation_alignment(raw: Any) -> list[TranslationAlignmentChunk]:
    """Parse persisted translation alignment metadata."""
    if not isinstance(raw, list):
        return []
    chunks: list[TranslationAlignmentChunk] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            chunks.append(TranslationAlignmentChunk.model_validate(item))
        except ValueError:
            logger.warning("Skipping invalid translation alignment chunk: {}", item)
    return chunks


_EVIDENCE_SECTION_RE = re.compile(
    r"^\s*(?:"
    r"abstract|summary|introduction|background|methods?|materials\s+and\s+methods|"
    r"patients?|case\s+reports?|clinical\s+report|results?|findings?|discussion|"
    r"conclusions?|正文|摘要|引言|前言|背景|资料与方法|材料与方法|方法|病例|"
    r"临床资料|结果|讨论|结论"
    r")\b",
    re.IGNORECASE,
)
_NON_EVIDENCE_SECTION_RE = re.compile(
    r"^\s*(?:"
    r"references?|bibliography|acknowledg(?:e)?ments?|funding|conflicts?\s+of\s+interest|"
    r"competing\s+interests?|author\s+(?:information|contributions?|affiliations?)|"
    r"affiliations?|supplementary\s+(?:materials?|information)|"
    r"参\s*考\s*文\s*献|参考文献|致谢|基金|利益冲突|作者信息|作者贡献|作者单位|"
    r"补充材料|附录"
    r")\b",
    re.IGNORECASE,
)


def _is_section_heading(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if len(stripped) > 120:
        return False
    return bool(_EVIDENCE_SECTION_RE.match(stripped) or _NON_EVIDENCE_SECTION_RE.match(stripped))


def _should_skip_section(text: str, skip_non_evidence: bool) -> tuple[bool, bool]:
    """Return (should_skip, updated_skip_flag) for a line of text."""
    stripped = text.strip()
    if _is_section_heading(stripped):
        if _EVIDENCE_SECTION_RE.match(stripped):
            return False, False
        if _NON_EVIDENCE_SECTION_RE.match(stripped):
            return True, True
    return skip_non_evidence, skip_non_evidence


def _filter_evidence_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove document metadata and back matter from extraction input."""
    filtered: list[dict[str, Any]] = []
    skip = False
    for block in blocks:
        if not isinstance(block, dict):
            continue
        text = _block_text(block)
        skip, _ = _should_skip_section(text, skip)
        if skip:
            continue
        block_type = str(block.get("type", "text")).lower()
        if block_type in {"header", "footer", "page_number"}:
            continue
        filtered.append(block)
    return filtered


def _filter_evidence_text(text: str) -> str:
    """Apply the evidence-section filter to paragraph/line-only text."""
    kept: list[str] = []
    skip = False
    for part in re.split(r"\n\s*\n|\n", text):
        stripped = part.strip()
        if not stripped:
            continue
        skip, _ = _should_skip_section(stripped, skip)
        if skip:
            continue
        kept.append(stripped)
    return "\n".join(kept)


def _parse_content_blocks(blocks: list[dict[str, Any]]) -> list[ContentBlock]:
    parsed: list[ContentBlock] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        parsed.append(
            ContentBlock(
                type=str(block.get("type", "text")),
                page_idx=int(block.get("page_idx", 0)),
                bbox=list(block.get("bbox", [])),
                text=unescape_mined_text(str(block.get("text", ""))),
                content=unescape_mined_text(str(block.get("content", ""))),
                table_body=unescape_mined_text(str(block.get("table_body", ""))),
                img_path=str(block.get("img_path", "")),
                image_caption=unescape_mined_strings(block.get("image_caption", [])),
                table_caption=unescape_mined_strings(block.get("table_caption", [])),
                chart_caption=unescape_mined_strings(block.get("chart_caption", [])),
                code_body=unescape_mined_text(str(block.get("code_body", ""))),
                list_items=unescape_mined_strings(block.get("list_items", [])),
            )
        )
    return parsed


def _format_blocks_with_page_spans(blocks: list[dict[str, Any]], track: Track) -> tuple[str, list[PageSpan]]:
    text_parts: list[str] = []
    page_ranges: dict[int, list[int]] = {}
    offset = 0

    for block in blocks:
        part = _block_text(block)
        if not part:
            continue
        if text_parts:
            offset += 1
        start = offset
        text_parts.append(part)
        offset += len(part)
        page_idx = int(block.get("page_idx", 0))
        if page_idx not in page_ranges:
            page_ranges[page_idx] = [start, offset]
        else:
            page_ranges[page_idx][1] = offset

    formatted_text = "\n".join(text_parts)
    page_spans = [
        PageSpan(
            span_id=f"{track.value}-p{page_idx + 1}",
            page=page_idx + 1,
            start_offset=start,
            end_offset=end,
        )
        for page_idx, (start, end) in sorted(page_ranges.items())
    ]
    if not page_spans:
        page_spans.append(PageSpan(span_id=f"{track.value}-p1", page=1, start_offset=0, end_offset=0))
    return formatted_text, page_spans


def _block_text(block: dict[str, Any]) -> str:
    for key in ("text", "content", "table_body", "code_body"):
        value = block.get(key)
        if isinstance(value, str) and value.strip():
            return unescape_mined_text(value.strip())
    list_items = block.get("list_items")
    if isinstance(list_items, list) and list_items:
        joined = "\n".join(item for item in list_items if isinstance(item, str) and item.strip())
        return unescape_mined_text(joined) if joined else ""
    return ""
