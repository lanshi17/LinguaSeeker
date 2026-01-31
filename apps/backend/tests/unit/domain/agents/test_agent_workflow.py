"""
Unit tests for Agent Workflow.
"""

import pytest
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from src.domain.agents.agent_workflow import AgentWorkflow, WorkflowContext, AgentState


@pytest.fixture
def workflow_context():
    """Create a workflow context."""
    return WorkflowContext(
        task_id=uuid4(),
        document_id=uuid4(),
        pdf_path="/test/document.pdf",
        parsed_markdown="# Test Document\n\nContent here.",
    )


@pytest.fixture
def agent_workflow(workflow_context):
    """Create an agent workflow instance."""
    return AgentWorkflow(workflow_context)


def test_agent_workflow_initialization(agent_workflow, workflow_context):
    """Test agent workflow initialization."""
    assert agent_workflow.context == workflow_context
    assert agent_workflow.state == AgentState.PENDING.value


def test_agent_workflow_get_progress_percentage(agent_workflow):
    """Test progress percentage calculation."""
    # Initial state should be 0%
    assert agent_workflow.get_progress_percentage() == 0

    # Set to LAYOUT state
    agent_workflow.machine.set_state(AgentState.LAYOUT.value)
    assert agent_workflow.get_progress_percentage() == 20

    # Set to TRANSLATION state
    agent_workflow.machine.set_state(AgentState.TRANSLATION.value)
    assert agent_workflow.get_progress_percentage() == 40

    # Set to COMPLETED state
    agent_workflow.machine.set_state(AgentState.COMPLETED.value)
    assert agent_workflow.get_progress_percentage() == 100

    # Set to FAILED state
    agent_workflow.machine.set_state(AgentState.FAILED.value)
    assert agent_workflow.get_progress_percentage() == 0


def test_agent_workflow_get_next_agent(agent_workflow):
    """Test next agent determination."""
    # PENDING -> layout
    assert agent_workflow.get_next_agent() == "layout"

    # LAYOUT -> translation
    agent_workflow.machine.set_state(AgentState.LAYOUT.value)
    assert agent_workflow.get_next_agent() == "translation"

    # TRANSLATION -> evidence
    agent_workflow.machine.set_state(AgentState.TRANSLATION.value)
    assert agent_workflow.get_next_agent() == "evidence"

    # EVIDENCE -> arbitration
    agent_workflow.machine.set_state(AgentState.EVIDENCE.value)
    assert agent_workflow.get_next_agent() == "arbitration"

    # COMPLETED -> None
    agent_workflow.machine.set_state(AgentState.COMPLETED.value)
    assert agent_workflow.get_next_agent() is None

    # FAILED -> None
    agent_workflow.machine.set_state(AgentState.FAILED.value)
    assert agent_workflow.get_next_agent() is None


def test_agent_workflow_is_terminal(agent_workflow):
    """Test terminal state detection."""
    # PENDING is not terminal
    assert agent_workflow.is_terminal() is False

    # COMPLETED is terminal
    agent_workflow.machine.set_state(AgentState.COMPLETED.value)
    assert agent_workflow.is_terminal() is True

    # FAILED is terminal
    agent_workflow.machine.set_state(AgentState.FAILED.value)
    assert agent_workflow.is_terminal() is True


def test_agent_workflow_update_context(agent_workflow):
    """Test context updates."""
    initial_markdown = agent_workflow.context.parsed_markdown
    new_markdown = "# Updated Document\n\nNew content."

    agent_workflow.update_context(parsed_markdown=new_markdown)
    assert agent_workflow.context.parsed_markdown == new_markdown

    # Other fields should remain unchanged
    assert agent_workflow.context.task_id == agent_workflow.context.task_id


def test_agent_workflow_set_error(agent_workflow):
    """Test error setting and failure transition."""
    error_message = "Test error occurred"
    agent_workflow.set_error(error_message)

    assert agent_workflow.context.error_message == error_message
    assert agent_workflow.state == AgentState.FAILED.value


def test_agent_workflow_get_state_summary(agent_workflow):
    """Test state summary generation."""
    summary = agent_workflow.get_state_summary()

    assert summary["current_state"] == AgentState.PENDING.value
    assert summary["progress"] == 0
    assert summary["next_agent"] == "layout"
    assert summary["is_terminal"] is False
    assert summary["has_error"] is False
    assert summary["task_id"] == str(agent_workflow.context.task_id)


@pytest.mark.asyncio
async def test_agent_workflow_execute_next_agent_success(agent_workflow):
    """Test successful agent execution."""
    # Mock agent executor
    async def mock_executor(agent_name, context):
        return {"parsed_markdown": f"Processed by {agent_name}"}

    # Execute first agent (layout)
    success = await agent_workflow.execute_next_agent(mock_executor)
    assert success is True
    assert agent_workflow.state == AgentState.LAYOUT.value
    assert "Processed by layout" in agent_workflow.context.parsed_markdown

    # Execute second agent (translation)
    success = await agent_workflow.execute_next_agent(mock_executor)
    assert success is True
    assert agent_workflow.state == AgentState.TRANSLATION.value


@pytest.mark.asyncio
async def test_agent_workflow_execute_next_agent_failure(agent_workflow):
    """Test agent execution with failure."""
    # Mock agent executor that raises exception
    async def failing_executor(agent_name, context):
        raise ValueError("Agent failed")

    success = await agent_workflow.execute_next_agent(failing_executor)
    assert success is False
    assert agent_workflow.state == AgentState.FAILED.value
    assert "Agent failed" in agent_workflow.context.error_message


def test_workflow_context_to_dict(workflow_context):
    """Test workflow context serialization."""
    context_dict = workflow_context.to_dict()

    assert context_dict["task_id"] == str(workflow_context.task_id)
    assert context_dict["document_id"] == str(workflow_context.document_id)
    assert context_dict["pdf_path"] == workflow_context.pdf_path
    assert context_dict["parsed_markdown"] == workflow_context.parsed_markdown


def test_workflow_context_get_input_hash(workflow_context):
    """Test input hash generation."""
    hash1 = workflow_context.get_input_hash()
    hash2 = workflow_context.get_input_hash()

    # Same context should produce same hash
    assert hash1 == hash2

    # Different context should produce different hash
    workflow_context.parsed_markdown = "Different content"
    hash3 = workflow_context.get_input_hash()
    assert hash1 != hash3