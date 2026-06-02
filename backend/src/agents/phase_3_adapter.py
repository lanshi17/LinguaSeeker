"""Phase 3 adapter: entity standardization and knowledge alignment.

Raises classified errors for orchestrator-level retry decisions.
Sets skip_phase_3_reason when standardized_count == 0.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

import aiofiles
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.agents.contracts import (
    Phase3Output,
    PhaseStatus,
    PhaseStatusDetail,
    PipelineGraphState,
    PermanentPhaseError,
    RetryablePhaseError,
    SkipPhase3Reason,
    build_retryable_errors,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
)

if TYPE_CHECKING:
    from src.core.standardize_entities_and_align_knowledge.api import (
        EntityStandardizationService,
    )

_RETRYABLE_ERRORS = build_retryable_errors()


class Phase3Adapter:
    """Thin adapter wrapping EntityStandardizationService.

    Standardizes extracted entities against terminology databases,
    skipping when Phase 2 marked the document as not relevant.
    """

    def __init__(
        self,
        standardization_service: EntityStandardizationService,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        self._standardization = standardization_service
        self._session_factory = session_factory

    async def run(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 3: standardize entities.

        Returns updated state with phase_3_output set on success.
        Returns state with SKIPPED status if skip_phase_3_reason is set.
        Sets skip_phase_3_reason=NO_CANDIDATES if standardized_count == 0.
        Raises RetryablePhaseError or PermanentPhaseError on failure.
        """
        logger.info("Phase 3 started: run={}", state.processing_run_id)

        # Skip if Phase 2 set a skip reason
        if state.skip_phase_3_reason is not None:
            logger.info(
                "Phase 3 skipped: reason={}", state.skip_phase_3_reason.value
            )
            state.phase_3_status = PhaseStatusDetail(
                status=PhaseStatus.SKIPPED,
                started_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat(),
                summary={"reason": state.skip_phase_3_reason.value},
            )
            return state

        state.phase_3_status = PhaseStatusDetail(
            status=PhaseStatus.RUNNING,
            started_at=datetime.now().isoformat(),
        )

        try:
            # Load extraction result from Phase 2 output
            if state.phase_2_output is None:
                raise PermanentPhaseError(
                    "Phase 2 output not found in state",
                    phase=3,
                )

            # Read the original extraction JSON
            extraction_path = state.phase_2_output.extraction_result_path
            async with aiofiles.open(extraction_path, "r") as f:
                extraction_data = json.loads(await f.read())

            dual_result = DualEvidenceExtractionResult.model_validate(extraction_data)

            # Run standardization with a fresh session
            async with self._session_factory() as session:
                standardization_result = await self._standardization.run_dual_result(
                    session,
                    dual_result,
                    source_document_id=state.source_document_id,
                    processing_run_id=state.processing_run_id,
                )
                await session.commit()

            state.phase_3_output = Phase3Output(
                match_count=standardization_result.match_count,
                standardized_count=standardization_result.standardized_count,
                ambiguous_count=standardization_result.ambiguous_count,
                unmapped_count=standardization_result.unmapped_count,
            )

            # D4 fix: Set skip reason if no candidates were standardized
            if standardization_result.standardized_count == 0:
                state.skip_phase_3_reason = SkipPhase3Reason.NO_CANDIDATES
                state.phase_3_status = PhaseStatusDetail(
                    status=PhaseStatus.COMPLETED,
                    started_at=state.phase_3_status.started_at,
                    completed_at=datetime.now().isoformat(),
                    duration_seconds=(
                        datetime.now() - datetime.fromisoformat(state.phase_3_status.started_at)
                    ).total_seconds()
                    if state.phase_3_status.started_at
                    else None,
                    summary={
                        "match_count": 0,
                        "standardized_count": 0,
                        "skip_reason": "no_candidates",
                    },
                )
                logger.info(
                    "Phase 3 completed but no candidates: run={}",
                    state.processing_run_id,
                )
                return state

            state.phase_3_status = PhaseStatusDetail(
                status=PhaseStatus.COMPLETED,
                started_at=state.phase_3_status.started_at,
                completed_at=datetime.now().isoformat(),
                duration_seconds=(
                    datetime.now() - datetime.fromisoformat(state.phase_3_status.started_at)
                ).total_seconds()
                if state.phase_3_status.started_at
                else None,
                summary={
                    "match_count": standardization_result.match_count,
                    "standardized_count": standardization_result.standardized_count,
                },
            )

            logger.info(
                "Phase 3 completed: run={}, matches={}",
                state.processing_run_id,
                standardization_result.match_count,
            )
            return state

        except _RETRYABLE_ERRORS as e:
            raise RetryablePhaseError(
                f"Phase 3 transient error: {e}",
                phase=3,
            ) from e

        except (PermanentPhaseError, RetryablePhaseError):
            raise  # Already classified, pass through

        except Exception as e:
            raise PermanentPhaseError(
                f"Phase 3 unexpected error: {e}",
                phase=3,
            ) from e
