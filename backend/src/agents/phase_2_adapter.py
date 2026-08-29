"""Phase 2 adapter: document parsing (MinerU).

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
    ParseOutput,
    PhaseStatus,
    PhaseStatusDetail,
    PipelineGraphState,
    PermanentPhaseError,
    build_retryable_errors,
    classify_phase_error,
)

if TYPE_CHECKING:
    from src.core.ingest_and_digitize_data.parse_document.service import (
        ParseDocumentService,
    )

_RETRYABLE_ERRORS = build_retryable_errors()


class Phase2Adapter:
    """Thin adapter wrapping ParseDocumentService.

    When ``state.pre_parsed_markdown`` is set (uploaded directly or produced
    by Phase 1 acquisition), skips MinerU entirely and constructs ParseOutput
    from the provided markdown text.
    """

    def __init__(
        self,
        parse_service: ParseDocumentService,
    ):
        self._parse = parse_service

    async def run(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 2: parse document into markdown + metadata.

        Returns updated state with phase_2_output set on success.
        Raises RetryablePhaseError or PermanentPhaseError on failure.
        """
        logger.info(
            "Phase 2 started: run={}, pre_parsed={}",
            state.processing_run_id,
            state.pre_parsed_markdown is not None,
        )

        state.phase_2_status = PhaseStatusDetail(
            status=PhaseStatus.RUNNING,
            started_at=datetime.now().isoformat(),
        )

        try:
            # Fast path: pre-parsed markdown bypasses MinerU entirely
            if state.pre_parsed_markdown:
                state = await self._build_from_pre_parsed(state)
                return state

            if state.phase_1_output is None or not state.phase_1_output.pdf_path:
                raise PermanentPhaseError(
                    "Phase 1 output with a PDF path not found in state",
                    phase=2,
                )
            pdf_path = state.phase_1_output.pdf_path

            # Parse document — use absolute path to survive CWD changes
            _backend_root = Path(__file__).resolve().parent.parent.parent.parent
            output_dir = str(_backend_root / "data" / "pipeline" / state.processing_run_id / "phase_2")
            parse_result = await self._parse.parse_local_files_and_save(
                file_paths=[pdf_path],
                output_dir=output_dir,
            )

            # Extract parsed output paths (B4 fix: correct field names)
            if not parse_result.saved_files:
                raise PermanentPhaseError(
                    "Phase 2 parsing produced no output files (document may have been "
                    "rejected by the parser, e.g. page-limit exceeded)",
                    phase=2,
                )
            first_file = list(parse_result.saved_files.values())[0]

            state.phase_2_output = ParseOutput(
                md_path=str(first_file.md_path),
                metadata_path=str(first_file.metadata_path),
                output_dir=str(first_file.output_dir),
                images_dir=str(first_file.images_dir) if first_file.images_dir else None,
            )

            state.phase_2_status = PhaseStatusDetail.complete(
                started_at=state.phase_2_status.started_at,
            )

            logger.info("Phase 2 completed: run={}", state.processing_run_id)
            return state

        except Exception as e:
            classify_phase_error(2, e, _RETRYABLE_ERRORS)

    async def _build_from_pre_parsed(
        self,
        state: PipelineGraphState,
    ) -> PipelineGraphState:
        """Construct ParseOutput from pre-parsed markdown, skipping MinerU."""
        assert state.pre_parsed_markdown is not None  # noqa: S101
        markdown_text = state.pre_parsed_markdown

        backend_root = Path(__file__).resolve().parent.parent.parent.parent
        output_dir = backend_root / "data" / "pipeline" / state.processing_run_id / "phase_2"
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

        # Construct metadata JSON compatible with Phase 3 expectations
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

        state.phase_2_output = ParseOutput(
            md_path=str(md_path),
            metadata_path=str(meta_path),
            output_dir=str(output_dir),
            images_dir=None,
        )

        state.phase_2_status = PhaseStatusDetail.complete(
            started_at=state.phase_2_status.started_at,
            summary={"source": "pre_parsed_markdown"},
        )

        logger.info(
            "Phase 2 completed (pre-parsed): run={}, {} chars",
            state.processing_run_id,
            len(markdown_text),
        )
        return state
