"""Public facade for one-track and dual-track evidence extraction."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from src.core.graph_rag.api import GraphRagService

from .config_context import EvidenceExtractionConfigContext
from .contracts import (
    DualEvidenceExtractionResult,
    DualTrackDocuments,
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceStatus,
    ExtractionTarget,
    FieldEligibilitySummary,
    Track,
    TrackDocument,
)
from .providers import LangChainEvidenceProvider
from .reconcile.api import CrossTrackReconcileService
from .domain.field_profile import ExtractionProfile, resolve_profile_fields
from .stages.graph_context_retrieval import GraphContextConfig
from .stages.review_validation import DEFAULT_REVIEW_REJECT_POLICY, resolve_review_reject_policy
from .postprocess.translation_traceback import apply_translation_traceback
from .workflow import DEFAULT_EXTRACTION_WORKFLOW_MODE, EvidenceExtractionWorkflow, resolve_extraction_mode


from .infrastructure.document_parsing import (
    _build_runtime_context_pack,
    _build_track_document_from_json,
    _resolve_extraction_track_mode,
)


def _empty_not_relevant_result(track_doc: TrackDocument) -> EvidenceExtractionResult:
    """Build a NOT_RELEVANT placeholder result for a skipped track."""
    return EvidenceExtractionResult(
        status=EvidenceExtractionStatus.NOT_RELEVANT,
        document_id=track_doc.document_id,
        track=track_doc.track,
        evidence_map=None,
        evidence_items=[],
        evidence_chains=[],
        special_evidence=[],
        quality_report=None,
        normalization_issues=[],
        extraction_target=track_doc.extraction_target,
        phenotype_evidence=[],
        discarded_evidence=[],
        channel_classification=None,
        field_eligibility_summary=None,
    )


class EvidenceExtractionService:
    """Public facade for one-track and dual-track evidence extraction.

    Usage::

        from src.core.config import get_config
        from src.core.evidence_extraction.api import (
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
        enable_source_grounding: bool = True,
        review_reject_policy: str = DEFAULT_REVIEW_REJECT_POLICY,
        graph_rag_service: GraphRagService | None = None,
    ):
        self._ctx = EvidenceExtractionConfigContext.from_config(cfg)
        self._provider = LangChainEvidenceProvider(self._ctx)
        self._extraction_mode = resolve_extraction_mode(extraction_mode)
        self._enable_review_validation = enable_review_validation
        self._enable_target_guard = enable_target_guard
        self._enable_source_grounding = enable_source_grounding
        self._review_reject_policy = resolve_review_reject_policy(review_reject_policy)
        self._graph_rag_service = graph_rag_service
        self._graph_rag_config = GraphContextConfig(
            enabled=self._ctx.graph_rag_enabled and graph_rag_service is not None,
            hops=self._ctx.graph_rag_hops,
            mode=self._ctx.graph_rag_mode,
        )
        profile_fields = resolve_profile_fields(extraction_profile)
        self._workflow = EvidenceExtractionWorkflow(
            provider=self._provider,
            field_profile=profile_fields,
            extraction_mode=extraction_mode,
            enable_review_validation=enable_review_validation,
            enable_target_guard=enable_target_guard,
            enable_source_grounding=enable_source_grounding,
            review_reject_policy=self._review_reject_policy,
            graph_rag_service=graph_rag_service,
            graph_rag_config=self._graph_rag_config,
        )
        self._reconcile_service = CrossTrackReconcileService()

    async def run(
        self,
        document: TrackDocument,
        extraction_profile: ExtractionProfile | str | None = None,
        extraction_mode: str | None = None,
        enable_review_validation: bool | None = None,
        enable_target_guard: bool | None = None,
        enable_source_grounding: bool | None = None,
        review_reject_policy: str | None = None,
    ) -> EvidenceExtractionResult:
        workflow = self._workflow_for(
            extraction_profile,
            extraction_mode=extraction_mode,
            enable_review_validation=enable_review_validation,
            enable_target_guard=enable_target_guard,
            enable_source_grounding=enable_source_grounding,
            review_reject_policy=review_reject_policy,
        )
        state = await workflow.run_async(document)

        # Compute field eligibility summary from state
        not_applicable_count = sum(1 for item in state.evidence_items if item.status == EvidenceStatus.NOT_APPLICABLE)
        not_attempted_count = sum(1 for item in state.evidence_items if item.status == EvidenceStatus.NOT_ATTEMPTED)
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
        enable_source_grounding: bool | None = None,
        review_reject_policy: str | None = None,
        extraction_track_mode: str = "dual",
        enable_translation_traceback: bool = True,
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
                enable_source_grounding=enable_source_grounding,
                review_reject_policy=review_reject_policy,
            )
            translated_result = _empty_not_relevant_result(documents.translated)
        elif track_mode == "english_pivot":
            original_result = _empty_not_relevant_result(documents.original)
            translated_result = await self.run(
                documents.translated,
                extraction_profile=extraction_profile,
                extraction_mode=extraction_mode,
                enable_review_validation=enable_review_validation,
                enable_target_guard=enable_target_guard,
                enable_source_grounding=enable_source_grounding,
                review_reject_policy=review_reject_policy,
            )
            if enable_translation_traceback:
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
                    enable_source_grounding=enable_source_grounding,
                    review_reject_policy=review_reject_policy,
                ),
                self.run(
                    documents.translated,
                    extraction_profile=extraction_profile,
                    extraction_mode=extraction_mode,
                    enable_review_validation=enable_review_validation,
                    enable_target_guard=enable_target_guard,
                    enable_source_grounding=enable_source_grounding,
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
        raise RuntimeError("run_sync() cannot be called from within a running event loop. Use run() instead.")

    def run_dual_sync(self, documents: DualTrackDocuments) -> DualEvidenceExtractionResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run_dual(documents))
        raise RuntimeError("run_dual_sync() cannot be called from within a running event loop. Use run_dual() instead.")

    def _workflow_for(
        self,
        extraction_profile: ExtractionProfile | str | None,
        extraction_mode: str | None = None,
        enable_review_validation: bool | None = None,
        enable_target_guard: bool | None = None,
        enable_source_grounding: bool | None = None,
        review_reject_policy: str | None = None,
    ) -> EvidenceExtractionWorkflow:
        """Return the workflow for the given profile/mode/ablation override.

        Returns the cached default workflow when no overrides are active.
        Creates a fresh workflow otherwise.
        """
        mode = extraction_mode or self._extraction_mode
        erv = self._enable_review_validation if enable_review_validation is None else enable_review_validation
        etg = self._enable_target_guard if enable_target_guard is None else enable_target_guard
        esg = self._enable_source_grounding if enable_source_grounding is None else enable_source_grounding
        rrp = (
            self._review_reject_policy
            if review_reject_policy is None
            else resolve_review_reject_policy(review_reject_policy)
        )
        if (
            extraction_profile is None
            and mode == self._extraction_mode
            and erv == self._enable_review_validation
            and etg == self._enable_target_guard
            and esg == self._enable_source_grounding
            and rrp == self._review_reject_policy
        ):
            return self._workflow
        profile_fields = resolve_profile_fields(extraction_profile)
        return EvidenceExtractionWorkflow(
            provider=self._provider,
            field_profile=profile_fields,
            extraction_mode=mode,
            enable_review_validation=erv,
            enable_target_guard=etg,
            enable_source_grounding=esg,
            review_reject_policy=rrp,
            graph_rag_service=self._graph_rag_service,
            graph_rag_config=self._graph_rag_config,
        )

    @staticmethod
    def build_dual_documents_from_output_dir(
        output_dir: str | Path,
        extraction_target: ExtractionTarget | None = None,
    ) -> DualTrackDocuments:
        base = Path(output_dir)
        original = _build_track_document_from_json(base / "original.json", Track.ORIGINAL, extraction_target)
        translated = _build_track_document_from_json(base / "translated.json", Track.TRANSLATED, extraction_target)
        return DualTrackDocuments(
            document_id=original.document_id,
            original=original,
            translated=translated,
        )

