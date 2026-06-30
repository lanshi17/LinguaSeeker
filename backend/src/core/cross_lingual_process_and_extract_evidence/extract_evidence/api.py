"""Public facade for one-track and dual-track evidence extraction."""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Literal

from loguru import logger

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
    EvidenceExtractionStatus,
    EvidenceStatus,
    ExtractionTarget,
    FieldEligibilitySummary,
    PageSpan,
    Track,
    TrackDocument,
)
from ..contracts import TranslationAlignmentChunk
from .providers import LangChainEvidenceProvider
from .reconcile.api import CrossTrackReconcileService
from .field_profile import ExtractionProfile, resolve_profile_fields
from .stages.review_validation import DEFAULT_REVIEW_REJECT_POLICY, resolve_review_reject_policy
from .translation_traceback import apply_translation_traceback
from .workflow import DEFAULT_EXTRACTION_WORKFLOW_MODE, EvidenceExtractionWorkflow, resolve_extraction_mode


ExtractionTrackMode = Literal["dual", "original_only", "english_pivot"]


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
        enable_review_validation: bool = True,
        enable_target_guard: bool = True,
        review_reject_policy: str = DEFAULT_REVIEW_REJECT_POLICY,
    ):
        self._ctx = EvidenceExtractionConfigContext.from_config(cfg)
        self._provider = LangChainEvidenceProvider(self._ctx)
        self._extraction_mode = resolve_extraction_mode(extraction_mode)
        self._enable_review_validation = enable_review_validation
        self._enable_target_guard = enable_target_guard
        self._review_reject_policy = resolve_review_reject_policy(review_reject_policy)
        profile_fields = resolve_profile_fields(extraction_profile)
        self._workflow = EvidenceExtractionWorkflow(
            provider=self._provider, field_profile=profile_fields,
            extraction_mode=extraction_mode,
            enable_review_validation=enable_review_validation,
            enable_target_guard=enable_target_guard,
            review_reject_policy=self._review_reject_policy,
        )
        self._reconcile_service = CrossTrackReconcileService()

    async def run(
        self,
        document: TrackDocument,
        extraction_profile: ExtractionProfile | str | None = None,
        extraction_mode: str | None = None,
        enable_review_validation: bool | None = None,
        enable_target_guard: bool | None = None,
        review_reject_policy: str | None = None,
    ) -> EvidenceExtractionResult:
        workflow = self._workflow_for(
            extraction_profile,
            extraction_mode=extraction_mode,
            enable_review_validation=enable_review_validation,
            enable_target_guard=enable_target_guard,
            review_reject_policy=review_reject_policy,
        )
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
        original_only: bool = False,
        enable_review_validation: bool | None = None,
        enable_target_guard: bool | None = None,
        review_reject_policy: str | None = None,
        extraction_track_mode: str = "dual",
    ) -> DualEvidenceExtractionResult:
        track_mode = _resolve_extraction_track_mode(extraction_track_mode)
        if original_only:
            track_mode = "original_only"
        if track_mode == "original_only":
            original_result = await self.run(
                documents.original,
                extraction_profile=extraction_profile,
                extraction_mode=extraction_mode,
                enable_review_validation=enable_review_validation,
                enable_target_guard=enable_target_guard,
                review_reject_policy=review_reject_policy,
            )
            translated_result = EvidenceExtractionResult(
                status=EvidenceExtractionStatus.NOT_RELEVANT,
                document_id=documents.translated.document_id,
                track=documents.translated.track,
                evidence_map=None,
                evidence_items=[],
                evidence_chains=[],
                special_evidence=[],
                quality_report=None,
                normalization_issues=[],
                extraction_target=documents.translated.extraction_target,
                phenotype_evidence=[],
                discarded_evidence=[],
                channel_classification=None,
                field_eligibility_summary=None,
            )
        elif track_mode == "english_pivot":
            original_result = EvidenceExtractionResult(
                status=EvidenceExtractionStatus.NOT_RELEVANT,
                document_id=documents.original.document_id,
                track=documents.original.track,
                evidence_map=None,
                evidence_items=[],
                evidence_chains=[],
                special_evidence=[],
                quality_report=None,
                normalization_issues=[],
                extraction_target=documents.original.extraction_target,
                phenotype_evidence=[],
                discarded_evidence=[],
                channel_classification=None,
                field_eligibility_summary=None,
            )
            translated_result = await self.run(
                documents.translated,
                extraction_profile=extraction_profile,
                extraction_mode=extraction_mode,
                enable_review_validation=enable_review_validation,
                enable_target_guard=enable_target_guard,
                review_reject_policy=review_reject_policy,
            )
            translated_result = apply_translation_traceback(
                documents.original,
                documents.translated,
                translated_result,
            )
        else:
            original_result, translated_result = await asyncio.gather(
                self.run(
                    documents.original,
                    extraction_profile=extraction_profile,
                    extraction_mode=extraction_mode,
                    enable_review_validation=enable_review_validation,
                    enable_target_guard=enable_target_guard,
                    review_reject_policy=review_reject_policy,
                ),
                self.run(
                    documents.translated,
                    extraction_profile=extraction_profile,
                    extraction_mode=extraction_mode,
                    enable_review_validation=enable_review_validation,
                    enable_target_guard=enable_target_guard,
                    review_reject_policy=review_reject_policy,
                ),
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
        enable_review_validation: bool | None = None,
        enable_target_guard: bool | None = None,
        review_reject_policy: str | None = None,
    ) -> EvidenceExtractionWorkflow:
        """Return the workflow for the given profile/mode/ablation override.

        Returns the cached default workflow when no overrides are active.
        Creates a fresh workflow otherwise.
        """
        mode = extraction_mode or self._extraction_mode
        erv = self._enable_review_validation if enable_review_validation is None else enable_review_validation
        etg = self._enable_target_guard if enable_target_guard is None else enable_target_guard
        rrp = self._review_reject_policy if review_reject_policy is None else resolve_review_reject_policy(review_reject_policy)
        if (
            extraction_profile is None
            and mode == self._extraction_mode
            and erv == self._enable_review_validation
            and etg == self._enable_target_guard
            and rrp == self._review_reject_policy
        ):
            return self._workflow
        profile_fields = resolve_profile_fields(extraction_profile)
        return EvidenceExtractionWorkflow(
            provider=self._provider, field_profile=profile_fields,
            extraction_mode=mode,
            enable_review_validation=erv,
            enable_target_guard=etg,
            review_reject_policy=rrp,
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
        formatted_text = _filter_evidence_text(str(data["formatted_text"]))
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


def _filter_evidence_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove document metadata and back matter from extraction input."""
    filtered: list[dict[str, Any]] = []
    skip_non_evidence = False

    for block in blocks:
        if not isinstance(block, dict):
            continue
        text = _block_text(block)
        if _is_section_heading(text):
            if _EVIDENCE_SECTION_RE.match(text.strip()):
                skip_non_evidence = False
            elif _NON_EVIDENCE_SECTION_RE.match(text.strip()):
                skip_non_evidence = True

        if skip_non_evidence:
            continue

        block_type = str(block.get("type", "text")).lower()
        if block_type in {"header", "footer", "page_number"}:
            continue
        filtered.append(block)

    return filtered


def _filter_evidence_text(text: str) -> str:
    """Apply the evidence-section filter to paragraph/line-only text."""
    kept: list[str] = []
    skip_non_evidence = False

    for part in re.split(r"\n\s*\n|\n", text):
        stripped = part.strip()
        if not stripped:
            continue
        if _is_section_heading(stripped):
            if _EVIDENCE_SECTION_RE.match(stripped):
                skip_non_evidence = False
            elif _NON_EVIDENCE_SECTION_RE.match(stripped):
                skip_non_evidence = True
        if skip_non_evidence:
            continue
        kept.append(stripped)

    return "\n".join(kept)


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
