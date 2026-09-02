"""Phase 1 adapter: literature/document acquisition.

Raises classified errors for orchestrator-level retry decisions.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
from loguru import logger

from src.agents.contracts import (
    AcquisitionOutput,
    PhaseStatus,
    PhaseStatusDetail,
    PipelineGraphState,
    PermanentPhaseError,
    build_retryable_errors,
    classify_phase_error,
)
from src.core.ingest_and_digitize_data.document_acquisition.contracts import (
    AcquisitionSource,
    DocumentAcquisitionRequest,
)

if TYPE_CHECKING:
    from src.core.ingest_and_digitize_data.document_acquisition.service import (
        DocumentAcquisitionService,
    )

_RETRYABLE_ERRORS = build_retryable_errors()


class Phase1Adapter:
    """Thin adapter wrapping DocumentAcquisitionService.

    Raises RetryablePhaseError for transient failures (timeouts, rate limits).
    Raises PermanentPhaseError for permanent failures (file not found, invalid input).

    When ``state.pre_parsed_markdown`` is set, acquisition is unnecessary and
    the phase is marked SKIPPED; Phase 2 consumes the markdown directly.
    """

    def __init__(
        self,
        acquisition_service: DocumentAcquisitionService,
    ):
        self._acquisition = acquisition_service

    async def run(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 1: acquire document.

        Returns updated state with phase_1_output set on success.
        Raises RetryablePhaseError or PermanentPhaseError on failure.
        """
        logger.info(
            "Phase 1 started: run={}, source={}, pre_parsed={}",
            state.processing_run_id,
            state.source_type.value,
            state.pre_parsed_markdown is not None,
        )

        state.phase_1_status = PhaseStatusDetail(
            status=PhaseStatus.RUNNING,
            started_at=datetime.now().isoformat(),
        )

        try:
            # Fast path: pre-parsed markdown needs no acquisition at all
            if state.pre_parsed_markdown:
                state.phase_1_output = AcquisitionOutput(pdf_path="")
                state.phase_1_status = PhaseStatusDetail(
                    status=PhaseStatus.SKIPPED,
                    started_at=state.phase_1_status.started_at,
                    completed_at=datetime.now().isoformat(),
                    summary={"reason": "pre_parsed_markdown"},
                )
                logger.info("Phase 1 skipped (pre-parsed markdown): run={}", state.processing_run_id)
                return state

            # Read uploaded file bytes if available
            content_bytes: bytes | None = None
            upload_filename: str | None = None
            if state.upload_file_path:
                upload_filename = Path(state.upload_file_path).name
                async with aiofiles.open(state.upload_file_path, "rb") as f:
                    content_bytes = await f.read()

            # Build acquisition request from state
            request = DocumentAcquisitionRequest(
                source=AcquisitionSource(state.source_type.value),
                filename=upload_filename,
                content=content_bytes,
                upload_dir=None,
                # Online acquisition fields
                action=state.action,
                query=state.query,
                identifiers=state.identifiers,
                relevance_gate=state.relevance_gate,
                literature_types=list(state.literature_types) if state.literature_types else None,
            )

            # Acquire document
            acquisition_result = await self._acquisition.acquire(request)

            if not acquisition_result.success:
                raise PermanentPhaseError(
                    f"Acquisition failed: {acquisition_result.error}",
                    phase=1,
                )

            # Extract file path
            entry: object | None = None
            if acquisition_result.stored_file:
                pdf_path = acquisition_result.stored_file.file_path
            elif acquisition_result.downloads:
                entry = acquisition_result.downloads[0]
                pdf_path = entry.file_path
            else:
                # Acquisition returned metadata/items but no downloadable PDF.
                # Most common cause: the article is paywalled or the provider
                # has no OA copy. Not retryable — retrying would hit the same
                # providers and get the same empty result.
                reasons = list(acquisition_result.warnings or [])
                detail = f" ({'; '.join(reasons[:3])})" if reasons else ""
                raise PermanentPhaseError(
                    f"Full-text PDF unavailable for the given identifier{detail}. "
                    f"The article may be paywalled or no OA copy is indexed.",
                    phase=1,
                )

            state.phase_1_output = AcquisitionOutput(pdf_path=pdf_path)

            # If the acquisition pipeline already parsed the PDF (multilingual
            # workflow's early MinerU batch), hand the markdown to Phase 2 so
            # it writes the canonical layout without re-parsing.
            pre_parsed = getattr(entry, "pre_parsed_markdown", None) if entry else None
            if pre_parsed:
                state.pre_parsed_markdown = pre_parsed

            summary: dict = {"pdf_path": pdf_path}
            if pre_parsed:
                summary["pre_parsed_by_acquisition"] = True
            state.phase_1_status = PhaseStatusDetail.complete(
                started_at=state.phase_1_status.started_at,
                summary=summary,
            )

            logger.info("Phase 1 completed: run={}", state.processing_run_id)
            return state

        except Exception as e:
            classify_phase_error(1, e, _RETRYABLE_ERRORS)
