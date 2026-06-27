"""Public facade for one-track and dual-track evidence extraction."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from src.core.standardize_entities_and_align_knowledge.context_pack.contracts import (
    TargetContextPack,
)
from src.core.standardize_entities_and_align_knowledge.context_pack.core import (
    build_context_pack_from_runtime_target,
)

from .config_context import EvidenceExtractionConfigContext
from .contracts import (
    ContentBlock,
    DualEvidenceExtractionResult,
    DualTrackDocuments,
    EvidenceExtractionResult,
    EvidenceStatus,
    ExtractionTarget,
    FieldEligibilitySummary,
    PageSpan,
    Track,
    TrackDocument,
)
from .providers import LangChainEvidenceProvider
from .reconcile.api import CrossTrackReconcileService
from .field_profile import ExtractionProfile, resolve_profile_fields
from .workflow import DEFAULT_EXTRACTION_WORKFLOW_MODE, EvidenceExtractionWorkflow


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

    ``extraction_profile`` controls which catalog fields are sent to the LLM.
    The default (``ExtractionProfile.NONE``) extracts all non-curation fields.
    Benchmark runners should explicitly select a publication profile such as
    ``ExtractionProfile.DATASET_D_PUBLICATION`` to restrict the field set.
    """

    def __init__(
        self,
        cfg: Any,
        extraction_profile: ExtractionProfile | str | None = ExtractionProfile.NONE,
        extraction_mode: str = DEFAULT_EXTRACTION_WORKFLOW_MODE,
    ):
        self._ctx = EvidenceExtractionConfigContext.from_config(cfg)
        self._provider = LangChainEvidenceProvider(self._ctx)
        self._extraction_mode = extraction_mode
        profile_fields = resolve_profile_fields(extraction_profile)
        self._workflow = EvidenceExtractionWorkflow(
            provider=self._provider, field_profile=profile_fields,
            extraction_mode=extraction_mode,
        )
        self._reconcile_service = CrossTrackReconcileService()

    async def run(
        self,
        document: TrackDocument,
        extraction_profile: ExtractionProfile | str | None = None,
        extraction_mode: str | None = None,
    ) -> EvidenceExtractionResult:
        workflow = self._workflow_for(extraction_profile, extraction_mode=extraction_mode)
        state = await workflow.run_async(document)

        # Compute field eligibility summary from state
        not_applicable_count = sum(
            1 for item in state.evidence_items if item.status == EvidenceStatus.NOT_APPLICABLE
        )
        not_attempted_count = sum(
            1 for item in state.evidence_items if item.status == EvidenceStatus.NOT_ATTEMPTED
        )
        field_eligibility_summary = FieldEligibilitySummary(
            eligible_field_count=len(state.evidence_items) - not_applicable_count - not_attempted_count,
            channel_excluded_field_count=len(state.channel_excluded_field_ids),
            target_excluded_field_count=len(state.target_excluded_field_ids),
            not_applicable_count=not_applicable_count,
            not_attempted_count=not_attempted_count,
        )

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
            extraction_target=document.extraction_target,
            phenotype_evidence=state.phenotype_evidence,
            discarded_evidence=state.discarded_evidence,
            channel_classification=state.channel_classification,
            field_eligibility_summary=field_eligibility_summary,
        )

    async def run_dual(
        self,
        documents: DualTrackDocuments,
        extraction_profile: ExtractionProfile | str | None = None,
        extraction_mode: str | None = None,
    ) -> DualEvidenceExtractionResult:
        original_result, translated_result = await asyncio.gather(
            self.run(documents.original, extraction_profile=extraction_profile, extraction_mode=extraction_mode),
            self.run(documents.translated, extraction_profile=extraction_profile, extraction_mode=extraction_mode),
        )
        context_pack = _build_runtime_context_pack(documents, original_result, translated_result)
        reconcile_output = self._reconcile_service.run_with_output(
            original_result,
            translated_result,
            context_pack=context_pack,
        )
        return DualEvidenceExtractionResult(
            document_id=documents.document_id,
            original_result=original_result,
            translated_result=translated_result,
            reconciled_result=reconcile_output.result,
            alignment_records=list(reconcile_output.alignment_records),
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

    def _workflow_for(
        self,
        extraction_profile: ExtractionProfile | str | None,
        extraction_mode: str | None = None,
    ) -> EvidenceExtractionWorkflow:
        """Return the workflow for the given profile override.

        Returns the default workflow when ``extraction_profile`` is ``None``
        (no override).  Creates a fresh workflow with the requested profile
        otherwise.  The default workflow is cached; per-profile workflows are
        created on demand.
        """
        mode = extraction_mode or self._extraction_mode
        if extraction_profile is None and mode == self._extraction_mode:
            return self._workflow
        profile_fields = resolve_profile_fields(extraction_profile)
        return EvidenceExtractionWorkflow(
            provider=self._provider, field_profile=profile_fields,
            extraction_mode=mode,
        )

    @staticmethod
    def build_dual_documents_from_output_dir(
        output_dir: str | Path,
        extraction_target: ExtractionTarget | None = None,
    ) -> DualTrackDocuments:
        base = Path(output_dir)
        original = _build_track_document_from_json(base / "original.json", Track.ORIGINAL, extraction_target)
        translated = _build_track_document_from_json(
            base / "translated.json", Track.TRANSLATED, extraction_target
        )
        return DualTrackDocuments(
            document_id=original.document_id,
            original=original,
            translated=translated,
        )


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
        extraction_target=extraction_target,
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
            code_body=str(block.get("code_body", "")),
            list_items=[str(v) for v in block.get("list_items", [])],
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
    list_items = block.get("list_items")
    if isinstance(list_items, list) and list_items:
        return "\n".join(item for item in list_items if isinstance(item, str) and item.strip())
    return ""
