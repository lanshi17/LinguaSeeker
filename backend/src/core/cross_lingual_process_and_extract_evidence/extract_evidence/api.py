"""Public facade for one-track and dual-track evidence extraction."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from .config_context import EvidenceExtractionConfigContext
from .contracts import (
    ContentBlock,
    DualEvidenceExtractionResult,
    DualTrackDocuments,
    EvidenceExtractionResult,
    PageSpan,
    Track,
    TrackDocument,
)
from .providers import LangChainEvidenceProvider
from .workflow import EvidenceExtractionWorkflow


class EvidenceExtractionService:
    """Public facade for one-track and dual-track evidence extraction.

    Usage::

        from src.core.config import get_config
        from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import (
            EvidenceExtractionService,
        )

        cfg = get_config()
        service = EvidenceExtractionService(cfg=cfg)
        result = await service.run(document)
    """

    def __init__(self, cfg: Any):
        self._ctx = EvidenceExtractionConfigContext.from_config(cfg)
        self._provider = LangChainEvidenceProvider(self._ctx)
        self._workflow = EvidenceExtractionWorkflow(provider=self._provider)

    async def run(self, document: TrackDocument) -> EvidenceExtractionResult:
        state = await self._workflow.run_async(document)
        return EvidenceExtractionResult(
            status=state.status,
            document_id=document.document_id,
            track=document.track,
            evidence_map=state.evidence_map,
            evidence_items=state.evidence_items,
            evidence_chains=state.evidence_chains,
            special_evidence=state.special_evidence,
            quality_report=state.quality_report,
            normalization_issues=state.normalization_issues,
        )

    async def run_dual(self, documents: DualTrackDocuments) -> DualEvidenceExtractionResult:
        original_result, translated_result = await asyncio.gather(
            self.run(documents.original),
            self.run(documents.translated),
        )
        return DualEvidenceExtractionResult(
            document_id=documents.document_id,
            original_result=original_result,
            translated_result=translated_result,
        )

    def run_sync(self, document: TrackDocument) -> EvidenceExtractionResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run(document))
        raise RuntimeError(
            "run_sync() cannot be called from within a running event loop. "
            "Use run() instead."
        )

    def run_dual_sync(self, documents: DualTrackDocuments) -> DualEvidenceExtractionResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run_dual(documents))
        raise RuntimeError(
            "run_dual_sync() cannot be called from within a running event loop. "
            "Use run_dual() instead."
        )

    @staticmethod
    def build_dual_documents_from_output_dir(output_dir: str | Path) -> DualTrackDocuments:
        base = Path(output_dir)
        original = _build_track_document_from_json(base / "original.json", Track.ORIGINAL)
        translated = _build_track_document_from_json(base / "translated.json", Track.TRANSLATED)
        return DualTrackDocuments(
            document_id=original.document_id,
            original=original,
            translated=translated,
        )


def _build_track_document_from_json(path: Path, track: Track) -> TrackDocument:
    data = json.loads(path.read_text(encoding="utf-8"))
    metadata = data.get("metadata", {})
    document_id = metadata.get("doc_id") or path.parent.name
    blocks = data.get("blocks", [])
    parsed_blocks = _parse_content_blocks(blocks)
    formatted_text, page_spans = _format_blocks_with_page_spans(blocks, track)

    # Fallback: when blocks are empty, use persisted formatted_text
    if not formatted_text and data.get("formatted_text"):
        formatted_text = data["formatted_text"]
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
    )


def _parse_content_blocks(blocks: list[dict[str, Any]]) -> list[ContentBlock]:
    parsed: list[ContentBlock] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        parsed.append(ContentBlock(
            type=str(block.get("type", "text")),
            page_idx=int(block.get("page_idx", 0)),
            bbox=list(block.get("bbox", [])),
            text=str(block.get("text", "")),
            content=str(block.get("content", "")),
            table_body=str(block.get("table_body", "")),
            img_path=str(block.get("img_path", "")),
            image_caption=[str(v) for v in block.get("image_caption", [])],
            table_caption=[str(v) for v in block.get("table_caption", [])],
            chart_caption=[str(v) for v in block.get("chart_caption", [])],
        ))
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
        page_spans.append(
            PageSpan(span_id=f"{track.value}-p1", page=1, start_offset=0, end_offset=0)
        )
    return formatted_text, page_spans


def _block_text(block: dict[str, Any]) -> str:
    for key in ("text", "content", "table_body", "code_body"):
        value = block.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
