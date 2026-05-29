"""Main pipeline orchestrator using LangGraph.

Architecture:
- 3 phase adapter nodes (Phase 1, 2, 3)
- Phase 4 is NOT a graph node — it operates via its own HTTP API
- After Phase 3 completes, pipeline_status is set to AWAITING_REVIEW
- State persisted to PostgreSQL after each phase for crash recovery
- Upstream dependency validation for single-phase mode
- Adapters raise classified errors; orchestrator catches and decides
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from langgraph.graph import END, StateGraph
from loguru import logger

from src.agents.concurrency import RetryablePhaseExecutor
from src.agents.contracts import (
    PhaseErrorDetail,
    PhaseStatus,
    PhaseStatusDetail,
    PermanentPhaseError,
    PipelineGraphState,
    PipelineMode,
    PipelineStatus,
    RetryablePhaseError,
)
from src.agents.state_persistence import StatePersistenceService

# Upstream dependencies for single-phase mode validation
REQUIRED_UPSTREAM: dict[int, list[int]] = {
    1: [],
    2: [1],
    3: [1, 2],
}


class PipelineOrchestrator:
    """LangGraph-based orchestrator coordinating 3 phases of evidence processing.

    Flow: Phase 1 -> Phase 2 -> (skip Phase 3 if not relevant) -> AWAITING_REVIEW
    Phase 4 operates independently via its own HTTP API.
    """

    def __init__(
        self,
        phase_adapters: dict[str, Any],
        state_persistence: StatePersistenceService,
        retry_executor: RetryablePhaseExecutor,
    ):
        self._adapters = phase_adapters
        self._persistence = state_persistence
        self._retry = retry_executor
        self._graph = self._build_graph()

    async def _handle_phase_failure(
        self,
        state: PipelineGraphState,
        error: Exception,
        phase: int,
        retryable: bool,
        attempt: int,
        max_retries: int,
    ) -> PipelineGraphState:
        """Mark a phase as FAILED, persist state, and return it."""
        error_detail = PhaseErrorDetail(
            message=str(error),
            retryable=retryable,
            attempt=attempt,
            max_retries=max_retries,
        )
        phase_attr = f"phase_{phase}_status"
        current = getattr(state, phase_attr)
        setattr(
            state,
            phase_attr,
            PhaseStatusDetail(
                status=PhaseStatus.FAILED,
                started_at=current.started_at if current else None,
                completed_at=datetime.now().isoformat(),
                error=error_detail,
            ),
        )
        state.error_message = str(error)
        state.error_phase = phase
        state.pipeline_status = PipelineStatus.FAILED
        state.completed_at = datetime.now().isoformat()
        await self._persistence.save(state)
        return state

    async def _execute_phase(
        self,
        adapter: Any,
        state: PipelineGraphState,
        phase_name: str,
    ) -> PipelineGraphState:
        """Execute a phase adapter with retry logic.

        Adapters raise classified errors:
        - RetryablePhaseError: retried by RetryablePhaseExecutor
        - PermanentPhaseError: caught here, marks phase as FAILED

        State is persisted after each phase (success or failure).
        """
        try:
            result = await self._retry.execute_with_retry(
                operation=adapter.run,
                state=state,
                phase_name=phase_name,
            )
            await self._persistence.save(result)
            return result

        except RetryablePhaseError as e:
            logger.error("Phase {} failed after retries: {}", e.phase, str(e))
            return await self._handle_phase_failure(
                state, e, e.phase, retryable=True,
                attempt=e.attempt, max_retries=self._retry.max_retries,
            )

        except PermanentPhaseError as e:
            logger.error("Phase {} failed permanently: {}", e.phase, str(e))
            return await self._handle_phase_failure(
                state, e, e.phase, retryable=False, attempt=0, max_retries=0,
            )

    async def _node_phase_1(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 1: acquisition + parsing."""
        return await self._execute_phase(
            self._adapters["phase_1"], state, "phase_1"
        )

    async def _node_phase_2(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 2: translation + evidence extraction."""
        return await self._execute_phase(
            self._adapters["phase_2"], state, "phase_2"
        )

    async def _node_phase_3(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 3: entity standardization."""
        return await self._execute_phase(
            self._adapters["phase_3"], state, "phase_3"
        )

    def _route_after_phase_1(self, state: PipelineGraphState) -> str:
        """Route after Phase 1: continue or stop on failure."""
        if state.phase_1_status.status == PhaseStatus.FAILED:
            logger.error("Phase 1 failed, stopping pipeline")
            return "end"
        return "phase_2"

    def _route_after_phase_2(self, state: PipelineGraphState) -> str:
        """Route after Phase 2: continue to Phase 3 or stop on failure."""
        if state.phase_2_status.status == PhaseStatus.FAILED:
            logger.error("Phase 2 failed, stopping pipeline")
            return "end"
        return "phase_3"

    def _route_after_phase_3(self, state: PipelineGraphState) -> str:
        """Route after Phase 3: always end (finalize sets AWAITING_REVIEW)."""
        if state.phase_3_status.status == PhaseStatus.FAILED:
            logger.error("Phase 3 failed, stopping pipeline")
        return "end"

    def _build_graph(self) -> Any:
        """Build the LangGraph state machine with 3 phase nodes."""
        graph = StateGraph(PipelineGraphState)

        graph.add_node("phase_1", self._node_phase_1)
        graph.add_node("phase_2", self._node_phase_2)
        graph.add_node("phase_3", self._node_phase_3)

        graph.set_entry_point("phase_1")

        graph.add_conditional_edges(
            "phase_1",
            self._route_after_phase_1,
            {"phase_2": "phase_2", "end": END},
        )
        graph.add_conditional_edges(
            "phase_2",
            self._route_after_phase_2,
            {"phase_3": "phase_3", "end": END},
        )
        graph.add_conditional_edges(
            "phase_3",
            self._route_after_phase_3,
            {"end": END},
        )

        return graph.compile()

    async def _validate_upstream(
        self, state: PipelineGraphState
    ) -> PipelineGraphState | None:
        """Validate upstream phases have completed for single-phase mode.

        Returns updated state with error if validation fails, None if OK.
        """
        target = state.target_phase
        if target is None:
            return None

        required = REQUIRED_UPSTREAM.get(target, [])
        for upstream_phase in required:
            phase_attr = f"phase_{upstream_phase}_status"
            phase_status = getattr(state, phase_attr)
            if phase_status.status != PhaseStatus.COMPLETED:
                state.pipeline_status = PipelineStatus.FAILED
                state.error_message = (
                    f"Upstream phase {upstream_phase} has not completed "
                    f"(status={phase_status.status.value}). "
                    f"Phase {target} requires phases {required} to be completed first."
                )
                state.error_phase = target
                state.completed_at = datetime.now().isoformat()
                await self._persistence.save(state)
                return state

        return None

    async def run(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute the pipeline.

        For mode=FULL: runs all phases in sequence.
        For mode=PHASE: validates upstream, runs target phase only.
        After Phase 3 completes (or is skipped), sets pipeline_status=AWAITING_REVIEW.
        """
        logger.info(
            "Pipeline orchestrator started: run={}, mode={}",
            state.processing_run_id,
            state.mode.value,
        )

        state.pipeline_status = PipelineStatus.RUNNING
        state.started_at = datetime.now().isoformat()

        # Validate upstream for single-phase mode
        if state.mode == PipelineMode.PHASE:
            error_state = await self._validate_upstream(state)
            if error_state is not None:
                return error_state

        final_state = await self._graph.ainvoke(state)

        if isinstance(final_state, dict):
            final_state = PipelineGraphState.model_validate(final_state)

        # If pipeline didn't fail, mark as AWAITING_REVIEW (Phase 4 is external)
        if final_state.pipeline_status != PipelineStatus.FAILED:
            final_state.pipeline_status = PipelineStatus.AWAITING_REVIEW
            final_state.completed_at = datetime.now().isoformat()
            await self._persistence.save(final_state)

        logger.info(
            "Pipeline orchestrator completed: run={}, pipeline_status={}",
            final_state.processing_run_id,
            final_state.pipeline_status.value,
        )

        return final_state
