"""Phase 1 adapter: document acquisition and parsing.

Raises classified errors for orchestrator-level retry decisions.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from src.agents.contracts import (
    Phase1Output,
    PhaseStatus,
    PhaseStatusDetail,
    PipelineGraphState,
    PermanentPhaseError,
    RetryablePhaseError,
    build_retryable_errors,
)
from src.core.ingest_and_digitize_data.document_acquisition.contracts import (
    AcquisitionSource,
    DocumentAcquisitionRequest,
)

if TYPE_CHECKING:
    from src.core.ingest_and_digitize_data.document_acquisition.service import (
        DocumentAcquisitionService,
    )
    from src.core.ingest_and_digitize_data.parse_document.service import (
        ParseDocumentService,
    )

_RETRYABLE_ERRORS = build_retryable_errors()

# Permanent errors that should NOT be retried
try:
    from src.core.ingest_and_digitize_data.parse_document.exceptions import (
        ParserExhaustedError,
    )
except ImportError:
    ParserExhaustedError = None  # type: ignore[assignment,misc]


class Phase1Adapter:
    """Thin adapter wrapping DocumentAcquisitionService + ParseDocumentService.

    Raises RetryablePhaseError for transient failures (timeouts, rate limits).
    Raises PermanentPhaseError for permanent failures (file not found, invalid input).
    """

    def __init__(
        self,
        acquisition_service: DocumentAcquisitionService,
        parse_service: ParseDocumentService,
    ):
        self._acquisition = acquisition_service
        self._parse = parse_service

    async def run(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 1: acquire and parse document.

        Returns updated state with phase_1_output set on success.
        Raises RetryablePhaseError or PermanentPhaseError on failure.
        """
        logger.info(
            "Phase 1 started: run={}, source={}",
            state.processing_run_id,
            state.source_type.value,
        )

        state.phase_1_status = PhaseStatusDetail(
            status=PhaseStatus.RUNNING,
            started_at=datetime.now().isoformat(),
        )

        try:
            # Build acquisition request from state
            request = DocumentAcquisitionRequest(
                source=AcquisitionSource(state.source_type.value),
                filename=Path(state.upload_file_path).name if state.upload_file_path else None,
                content=state.upload_file_path,  # file path for gateway to read
                upload_dir=None,
            )

            # Acquire document
            acquisition_result = await self._acquisition.acquire(request)

            if not acquisition_result.success:
                raise PermanentPhaseError(
                    f"Acquisition failed: {acquisition_result.error}",
                    phase=1,
                )

            # Extract file path
            if acquisition_result.stored_file:
                pdf_path = acquisition_result.stored_file.file_path
            elif acquisition_result.downloads:
                pdf_path = acquisition_result.downloads[0].file_path
            else:
                raise PermanentPhaseError(
                    "Acquisition succeeded but no file path found",
                    phase=1,
                )

            # Parse document
            output_dir = f"data/pipeline/{state.processing_run_id}/phase_1"
            parse_result = await self._parse.parse_local_files_and_save(
                file_paths=[pdf_path],
                output_dir=output_dir,
            )

            # Extract parsed output paths (B4 fix: correct field names)
            first_file = list(parse_result.saved_files.values())[0]

            state.phase_1_output = Phase1Output(
                pdf_path=pdf_path,
                md_path=str(first_file.md_path),
                metadata_path=str(first_file.metadata_path),
                output_dir=str(first_file.output_dir),
                images_dir=str(first_file.images_dir) if first_file.images_dir else None,
            )

            state.phase_1_status = PhaseStatusDetail(
                status=PhaseStatus.COMPLETED,
                started_at=state.phase_1_status.started_at,
                completed_at=datetime.now().isoformat(),
                duration_seconds=(
                    datetime.now() - datetime.fromisoformat(state.phase_1_status.started_at)
                ).total_seconds()
                if state.phase_1_status.started_at
                else None,
            )

            logger.info("Phase 1 completed: run={}", state.processing_run_id)
            return state

        except _RETRYABLE_ERRORS as e:
            raise RetryablePhaseError(
                f"Phase 1 transient error: {e}",
                phase=1,
            ) from e

        except (PermanentPhaseError, RetryablePhaseError):
            raise  # Already classified, pass through

        except Exception as e:
            # Default to permanent for unknown errors
            if ParserExhaustedError and isinstance(e, ParserExhaustedError):
                raise PermanentPhaseError(
                    f"All parsers failed: {e}",
                    phase=1,
                ) from e
            raise PermanentPhaseError(
                f"Phase 1 unexpected error: {e}",
                phase=1,
            ) from e
