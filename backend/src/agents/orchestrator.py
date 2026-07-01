"""Main pipeline orchestrator using LangGraph.

Architecture:
- 3 phase adapter nodes (Phase 1, 2, 3)
- Phase 4 is NOT a graph node — it operates via its own HTTP API
- After Phase 3 completes, pipeline_status is set to COMPLETED
- State persisted to PostgreSQL after each phase for crash recovery
- Upstream dependency validation for single-phase mode
- Adapters raise classified errors; orchestrator catches and decides
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from langgraph.graph import END, StateGraph
from loguru import logger

from src.agents.concurrency import RetryablePhaseExecutor
from src.agents.contracts import (
    InvalidStateTransitionError,
    PhaseErrorDetail,
    PhaseStatus,
    PhaseStatusDetail,
    PermanentPhaseError,
    PipelineGraphState,
    PipelineMode,
    PipelineStatus,
    RetryablePhaseError,
    validate_pipeline_status_transition,
    validate_phase_status_transition,
)
from src.agents.state_persistence import SessionBoundStatePersistence

# Upstream dependencies for single-phase mode validation
REQUIRED_UPSTREAM: dict[int, list[int]] = {
    1: [],
    2: [1],
    3: [1, 2],
}


class PipelineOrchestrator:
    """LangGraph-based orchestrator coordinating 3 phases of evidence processing.

    Flow: Phase 1 -> Phase 2 -> (skip Phase 3 if not relevant) -> COMPLETED
    Phase 4 operates independently via its own HTTP API.
    """

    def __init__(
        self,
        phase_adapters: dict[str, Any],
        state_persistence: SessionBoundStatePersistence,
        retry_executor: RetryablePhaseExecutor,
    ):
        self._adapters = phase_adapters
        self._persistence = state_persistence
        self._retry = retry_executor
        self._graph = self._build_graph()
        # Optional callback invoked after each state persistence so the
        # runner can keep its in-memory cache in sync during execution.
        self.on_state_change: Callable[[str, PipelineGraphState], None] | None = None

    def _notify(self, state: PipelineGraphState) -> None:
        """Push latest state to runner's in-memory cache (if wired)."""
        if self.on_state_change is not None:
            try:
                self.on_state_change(state.processing_run_id, state)
            except Exception:
                logger.exception("on_state_change callback failed for run={}", state.processing_run_id)

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
        new_phase_status = PhaseStatusDetail(
            status=PhaseStatus.FAILED,
            started_at=current.started_at if current else None,
            completed_at=datetime.now().isoformat(),
            error=error_detail,
        )

        # Defense-in-depth: validate transitions before mutating state.
        # These should never fail in practice — the orchestrator logic
        # should always produce valid transitions. If they do fail, it
        # indicates a programming bug rather than a data issue.
        try:
            validate_phase_status_transition(
                current.status,
                PhaseStatus.FAILED,
                context=f"phase_{phase} failure handling",
            )
            validate_pipeline_status_transition(
                state.pipeline_status,
                PipelineStatus.FAILED,
                context=f"pipeline failure handling (phase {phase})",
            )
        except InvalidStateTransitionError:
            logger.exception(
                "State transition guard triggered in _handle_phase_failure — "
                "this indicates an orchestrator bug. run={}, phase={}, "
                "current_pipeline_status={}, current_phase_status={}",
                state.processing_run_id,
                phase,
                state.pipeline_status.value,
                current.status.value,
            )
            # Continue anyway — we need to persist the failure state.
            # The persistence layer guard will also fire, but we log here
            # for better stack traces at the point of the logic error.

        setattr(state, phase_attr, new_phase_status)
        state.error_message = str(error)
        state.error_phase = phase
        state.pipeline_status = PipelineStatus.FAILED
        state.completed_at = datetime.now().isoformat()
        await self._persistence.save(state)
        self._notify(state)
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

        State is persisted at phase entry (PENDING -> RUNNING) and exit
        (RUNNING -> COMPLETED/FAILED/SKIPPED). The entry save is what
        makes the persistence-layer transition guard happy: without it
        the guard would see PENDING -> COMPLETED and reject the save.
        """
        # Phase entry: mark RUNNING and persist so the transition guard
        # observes a legal PENDING -> RUNNING step before the adapter
        # produces a terminal status.
        phase_num = int(phase_name.rsplit("_", 1)[-1])
        phase_attr = f"phase_{phase_num}_status"
        current_detail = getattr(state, phase_attr)
        if current_detail.status == PhaseStatus.PENDING:
            setattr(
                state,
                phase_attr,
                PhaseStatusDetail(
                    status=PhaseStatus.RUNNING,
                    started_at=datetime.now().isoformat(),
                ),
            )
            await self._persistence.save(state)
            self._notify(state)

        try:
            result = await self._retry.execute_with_retry(
                operation=adapter.run,
                state=state,
                phase_name=phase_name,
            )
            await self._persistence.save(result)
            self._notify(result)
            return result

        except RetryablePhaseError as e:
            logger.error("Phase {} failed after retries: {}", e.phase, str(e))
            return await self._handle_phase_failure(
                state,
                e,
                e.phase,
                retryable=True,
                attempt=e.attempt,
                max_retries=self._retry.max_retries,
            )

        except PermanentPhaseError as e:
            logger.error("Phase {} failed permanently: {}", e.phase, str(e))
            return await self._handle_phase_failure(
                state,
                e,
                e.phase,
                retryable=False,
                attempt=0,
                max_retries=0,
            )

    async def _node_phase_1(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 1: acquisition + parsing."""
        return await self._execute_phase(self._adapters["phase_1"], state, "phase_1")

    async def _node_phase_2(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 2: translation + evidence extraction."""
        return await self._execute_phase(self._adapters["phase_2"], state, "phase_2")

    async def _node_phase_3(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute Phase 3: entity standardization."""
        return await self._execute_phase(self._adapters["phase_3"], state, "phase_3")

    def _route_entry(self, state: PipelineGraphState) -> str:
        """Route entry point: start at target phase in phase mode, or phase 1 in full mode."""
        if state.mode == PipelineMode.PHASE and state.target_phase is not None:
            return f"phase_{state.target_phase}"
        return "phase_1"

    def _route_after_phase_1(self, state: PipelineGraphState) -> str:
        """Route after Phase 1: continue or stop on failure/target reached."""
        if state.phase_1_status.status == PhaseStatus.FAILED:
            logger.error("Phase 1 failed, stopping pipeline")
            return "end"
        if state.mode == PipelineMode.PHASE and state.target_phase == 1:
            return "end"
        return "phase_2"

    def _route_after_phase_2(self, state: PipelineGraphState) -> str:
        """Route after Phase 2: continue to Phase 3 or stop on failure/target reached."""
        if state.phase_2_status.status == PhaseStatus.FAILED:
            logger.error("Phase 2 failed, stopping pipeline")
            return "end"
        if state.mode == PipelineMode.PHASE and state.target_phase == 2:
            return "end"
        return "phase_3"

    def _route_after_phase_3(self, state: PipelineGraphState) -> str:
        """Route after Phase 3: always end (orchestrator finalizes to COMPLETED)."""
        if state.phase_3_status.status == PhaseStatus.FAILED:
            logger.error("Phase 3 failed, stopping pipeline")
        return "end"

    def _build_graph(self) -> Any:
        """Build the LangGraph state machine with 3 phase nodes."""
        graph = StateGraph(PipelineGraphState)

        graph.add_node("phase_1", self._node_phase_1)
        graph.add_node("phase_2", self._node_phase_2)
        graph.add_node("phase_3", self._node_phase_3)

        graph.set_conditional_entry_point(
            self._route_entry,
            {"phase_1": "phase_1", "phase_2": "phase_2", "phase_3": "phase_3"},
        )

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

    async def _validate_upstream(self, state: PipelineGraphState) -> PipelineGraphState | None:
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
                self._notify(state)
                return state

        return None

    async def run(self, state: PipelineGraphState) -> PipelineGraphState:
        """Execute the pipeline.

        For mode=FULL: runs all phases in sequence.
        For mode=PHASE: validates upstream, runs target phase only.
        After Phase 3 completes (or is skipped), sets pipeline_status=COMPLETED.
        """
        logger.info(
            "Pipeline orchestrator started: run={}, mode={}",
            state.processing_run_id,
            state.mode.value,
        )

        # Defense-in-depth: validate PENDING → RUNNING transition
        try:
            validate_pipeline_status_transition(
                state.pipeline_status,
                PipelineStatus.RUNNING,
                context="orchestrator.run() start",
            )
        except InvalidStateTransitionError:
            logger.exception(
                "State transition guard triggered at orchestrator start — "
                "this indicates an orchestrator bug. run={}, current_status={}",
                state.processing_run_id,
                state.pipeline_status.value,
            )
            # Continue anyway — persistence layer is the final guard

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

        # If pipeline didn't fail, mark as COMPLETED.
        # Expert review / correction is handled via the chat interface,
        # not as a gating step on the pipeline itself.
        if final_state.pipeline_status != PipelineStatus.FAILED:
            # Defense-in-depth: validate RUNNING → COMPLETED transition
            try:
                validate_pipeline_status_transition(
                    final_state.pipeline_status,
                    PipelineStatus.COMPLETED,
                    context="orchestrator.run() finalization",
                )
            except InvalidStateTransitionError:
                logger.exception(
                    "State transition guard triggered at orchestrator finalization — "
                    "this indicates an orchestrator bug. run={}, current_status={}",
                    final_state.processing_run_id,
                    final_state.pipeline_status.value,
                )
                # Continue anyway — persistence layer is the final guard

            final_state.pipeline_status = PipelineStatus.COMPLETED
            final_state.completed_at = datetime.now().isoformat()
            await self._persistence.save(final_state)
            self._notify(final_state)

        logger.info(
            "Pipeline orchestrator completed: run={}, pipeline_status={}",
            final_state.processing_run_id,
            final_state.pipeline_status.value,
        )

        return final_state
