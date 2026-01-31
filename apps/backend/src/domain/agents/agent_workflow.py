"""Agent Workflow State Machine.

Orchestrates the multi-agent pipeline for document processing using
a state machine pattern with the transitions library.
"""

from enum import Enum
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from uuid import UUID
import hashlib
import json

from transitions import Machine


class AgentState(str, Enum):
    """Agent workflow states."""

    PENDING = "PENDING"
    LAYOUT = "LAYOUT"
    TRANSLATION = "TRANSLATION"
    EVIDENCE = "EVIDENCE"
    ARBITRATION = "ARBITRATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class WorkflowContext:
    """Context passed through agent workflow."""

    task_id: UUID
    document_id: UUID
    pdf_path: str
    parsed_markdown: str = ""
    translated_text: Dict[str, Any] = field(default_factory=dict)
    evidence_items: list = field(default_factory=list)
    confidence_scores: list = field(default_factory=list)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": str(self.task_id),
            "document_id": str(self.document_id),
            "pdf_path": self.pdf_path,
            "parsed_markdown": self.parsed_markdown,
            "translated_text": self.translated_text,
            "evidence_items": self.evidence_items,
            "confidence_scores": self.confidence_scores,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    def get_input_hash(self) -> str:
        """Generate hash of current state for caching."""
        state_data = {
            "parsed_markdown": self.parsed_markdown,
            "translated_text": self.translated_text,
            "evidence_items": self.evidence_items,
        }
        content = json.dumps(state_data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


class AgentWorkflow:
    """State machine for agent workflow orchestration.

    Manages the document processing pipeline:
    PENDING → LAYOUT → TRANSLATION → EVIDENCE → ARBITRATION → COMPLETED
    """

    def __init__(
        self,
        context: WorkflowContext,
        on_state_change: Optional[Callable] = None,
    ):
        """Initialize agent workflow.

        Args:
            context: Workflow context with document data
            on_state_change: Callback for state transitions
        """
        self.context = context
        self.on_state_change = on_state_change

        # Define states
        states = [state.value for state in AgentState]

        # Define transitions
        transitions = [
            # Forward transitions
            {
                "trigger": "start_layout",
                "source": AgentState.PENDING.value,
                "dest": AgentState.LAYOUT.value,
                "before": "log_transition",
            },
            {
                "trigger": "complete_layout",
                "source": AgentState.LAYOUT.value,
                "dest": AgentState.TRANSLATION.value,
                "before": "log_transition",
            },
            {
                "trigger": "complete_translation",
                "source": AgentState.TRANSLATION.value,
                "dest": AgentState.EVIDENCE.value,
                "before": "log_transition",
            },
            {
                "trigger": "complete_evidence",
                "source": AgentState.EVIDENCE.value,
                "dest": AgentState.ARBITRATION.value,
                "before": "log_transition",
            },
            {
                "trigger": "complete_arbitration",
                "source": AgentState.ARBITRATION.value,
                "dest": AgentState.COMPLETED.value,
                "before": "log_transition",
            },
            # Error transitions from any state
            {
                "trigger": "fail",
                "source": "*",
                "dest": AgentState.FAILED.value,
                "before": "log_failure",
            },
        ]

        # Initialize state machine
        self.machine = Machine(
            model=self,
            states=states,
            transitions=transitions,
            initial=AgentState.PENDING.value,
            auto_transitions=False,
        )

    def log_transition(self) -> None:
        """Log state transition."""
        if self.on_state_change:
            self.on_state_change(self.state, self.context)

    def log_failure(self) -> None:
        """Log failure transition."""
        if self.on_state_change:
            self.on_state_change(AgentState.FAILED.value, self.context)

    def can_progress(self) -> bool:
        """Check if workflow can progress to next state."""
        return self.state != AgentState.COMPLETED.value and self.state != AgentState.FAILED.value

    def get_progress_percentage(self) -> int:
        """Get workflow progress percentage."""
        progress_map = {
            AgentState.PENDING.value: 0,
            AgentState.LAYOUT.value: 20,
            AgentState.TRANSLATION.value: 40,
            AgentState.EVIDENCE.value: 60,
            AgentState.ARBITRATION.value: 80,
            AgentState.COMPLETED.value: 100,
            AgentState.FAILED.value: 0,
        }
        return progress_map.get(self.state, 0)

    def get_next_agent(self) -> Optional[str]:
        """Get the next agent to execute.

        Returns:
            Agent name or None if workflow is complete/failed
        """
        agent_map = {
            AgentState.PENDING.value: "layout",
            AgentState.LAYOUT.value: "translation",
            AgentState.TRANSLATION.value: "evidence",
            AgentState.EVIDENCE.value: "arbitration",
        }
        return agent_map.get(self.state)

    def is_terminal(self) -> bool:
        """Check if workflow is in terminal state."""
        return self.state in [AgentState.COMPLETED.value, AgentState.FAILED.value]

    def set_error(self, error_message: str) -> None:
        """Set error message and transition to failed state.

        Args:
            error_message: Error description
        """
        self.context.error_message = error_message
        self.fail()

    def update_context(self, **kwargs) -> None:
        """Update workflow context with new data.

        Args:
            **kwargs: Context fields to update
        """
        for key, value in kwargs.items():
            if hasattr(self.context, key):
                setattr(self.context, key, value)

    def get_state_summary(self) -> Dict[str, Any]:
        """Get current state summary.

        Returns:
            Dictionary with state information
        """
        return {
            "current_state": self.state,
            "progress": self.get_progress_percentage(),
            "next_agent": self.get_next_agent(),
            "is_terminal": self.is_terminal(),
            "has_error": self.context.error_message is not None,
            "task_id": str(self.context.task_id),
        }

    async def execute_next_agent(self, agent_executor: Callable) -> bool:
        """Execute the next agent in workflow.

        Args:
            agent_executor: Async function to execute agent

        Returns:
            True if agent executed successfully, False otherwise
        """
        if self.is_terminal():
            return False

        next_agent = self.get_next_agent()
        if not next_agent:
            return False

        try:
            # Execute agent
            result = await agent_executor(next_agent, self.context)

            # Update context with result
            if result:
                self.update_context(**result)

            # Advance state machine
            if self.state == AgentState.PENDING.value:
                self.start_layout()
            elif self.state == AgentState.LAYOUT.value:
                self.complete_layout()
            elif self.state == AgentState.TRANSLATION.value:
                self.complete_translation()
            elif self.state == AgentState.EVIDENCE.value:
                self.complete_evidence()
            elif self.state == AgentState.ARBITRATION.value:
                self.complete_arbitration()

            return True

        except Exception as e:
            self.set_error(str(e))
            return False

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"AgentWorkflow(state={self.state}, "
            f"task_id={self.context.task_id}, "
            f"progress={self.get_progress_percentage()}%)"
        )
