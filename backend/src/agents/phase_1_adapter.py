"""Phase 1 adapter: document acquisition and parsing.

Raises classified errors for orchestrator-level retry decisions.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import aiofiles
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
# FileNotFoundError/PermissionError are OSError subclasses but are permanent,
# not transient — must not be retried.
_PERMANENT_OS_ERRORS = (FileNotFoundError, PermissionError, IsADirectoryError)

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

    When ``state.pre_parsed_markdown`` is set, skips MinerU entirely and
    constructs Phase1Output directly from the provided markdown text.
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
            # Fast path: pre-parsed markdown bypasses MinerU entirely
            if state.pre_parsed_markdown:
                state = await self._build_from_pre_parsed(state)
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
                detail = (
                    f" ({'; '.join(reasons[:3])})" if reasons else ""
                )
                raise PermanentPhaseError(
                    f"Full-text PDF unavailable for the given identifier{detail}. "
                    f"The article may be paywalled or no OA copy is indexed.",
                    phase=1,
                )

            # If the acquisition pipeline already parsed the PDF (multilingual
            # workflow's early MinerU batch), reuse that markdown and bypass
            # the local re-parse. Falls back to ``_build_from_pre_parsed``
            # which writes the canonical metadata.json layout Phase 2 expects.
            pre_parsed = getattr(entry, "pre_parsed_markdown", None) if entry else None
            if pre_parsed:
                state.pre_parsed_markdown = pre_parsed
                state = await self._build_from_pre_parsed(state)
                # Surface the original PDF for downstream provenance.
                if state.phase_1_output and pdf_path:
                    state.phase_1_output.pdf_path = pdf_path
                return state

            # Parse document — use absolute path to survive CWD changes
            from pathlib import Path as _Path
            _backend_root = _Path(__file__).resolve().parent.parent.parent
            output_dir = str(_backend_root / "data" / "pipeline" / state.processing_run_id / "phase_1")
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

        except _PERMANENT_OS_ERRORS as e:
            raise PermanentPhaseError(
                f"Phase 1 permanent file error: {e}",
                phase=1,
            ) from e

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

    async def _build_from_pre_parsed(
        self, state: PipelineGraphState,
    ) -> PipelineGraphState:
        """Construct Phase1Output from pre-parsed markdown, skipping MinerU."""
        assert state.pre_parsed_markdown is not None  # noqa: S101
        markdown_text = state.pre_parsed_markdown

        backend_root = Path(__file__).resolve().parent.parent.parent
        output_dir = backend_root / "data" / "pipeline" / state.processing_run_id / "phase_1"
        output_dir.mkdir(parents=True, exist_ok=True)

        md_path = output_dir / "output.md"
        meta_path = output_dir / "metadata.json"

        # Write markdown
        async with aiofiles.open(str(md_path), "w") as f:
            await f.write(markdown_text)

        # Extract title from first markdown heading (# Title)
        title: str | None = None
        for line in markdown_text.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                title = line[2:].strip() or None
                break

        # Construct metadata JSON compatible with Phase 2 expectations
        metadata = {
            "total_pages": 1,
            "title": title,
            "authors": [],
            "abstract_text": None,
            "pages": [
                {
                    "page_number": 1,
                    "markdown": markdown_text,
                    "figures": [],
                    "tables": [],
                }
            ],
            "content_blocks": [],
        }
        async with aiofiles.open(str(meta_path), "w") as f:
            await f.write(json.dumps(metadata, indent=2))

        state.phase_1_output = Phase1Output(
            pdf_path="",
            md_path=str(md_path),
            metadata_path=str(meta_path),
            output_dir=str(output_dir),
            images_dir=None,
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
            summary={"source": "pre_parsed_markdown"},
        )

        logger.info(
            "Phase 1 completed (pre-parsed): run={}, {} chars",
            state.processing_run_id,
            len(markdown_text),
        )
        return state
