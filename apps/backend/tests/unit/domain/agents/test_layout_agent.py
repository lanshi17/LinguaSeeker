"""
Unit tests for Layout Agent.
"""

import pytest
from unittest.mock import Mock, AsyncMock

from src.domain.agents.layout_agent import LayoutAgent, LayoutResult
from src.domain.agents.agent_workflow import WorkflowContext
from src.infrastructure.adapters.llm_adapter import LLMAdapter


@pytest.fixture
def mock_llm_adapter():
    """Create a mock LLM adapter."""
    adapter = Mock(spec=LLMAdapter)
    adapter.generate = AsyncMock()
    return adapter


@pytest.fixture
def layout_agent(mock_llm_adapter):
    """Create a layout agent instance."""
    return LayoutAgent(mock_llm_adapter)


@pytest.fixture
def workflow_context():
    """Create a workflow context."""
    from uuid import uuid4
    return WorkflowContext(
        task_id=uuid4(),
        document_id=uuid4(),
        pdf_path="/test/document.pdf",
        parsed_markdown="# Test Document\n\nThis is a test paragraph.",
    )


def test_layout_agent_initialization(layout_agent, mock_llm_adapter):
    """Test layout agent initialization."""
    assert layout_agent.llm == mock_llm_adapter


@pytest.mark.asyncio
async def test_layout_agent_process(layout_agent, workflow_context):
    """Test layout agent processing."""
    # Mock the internal methods
    layout_agent._analyze_structure = AsyncMock(return_value={
        "sections": [{"title": "Test", "content": "Content", "level": 2}],
        "tables": [],
        "figures": [],
        "references": []
    })
    layout_agent._generate_markdown = AsyncMock(return_value="# Test\n\nContent\n\n")
    layout_agent._extract_metadata = Mock(return_value={"section_count": 1})

    result = await layout_agent.process(workflow_context)

    assert isinstance(result, LayoutResult)
    assert result.markdown == "# Test\n\nContent\n\n"
    assert result.metadata["section_count"] == 1


def test_layout_agent_sanitize_markdown(layout_agent):
    """Test markdown sanitization."""
    dirty_markdown = "Line 1\n\n\n\nLine 2\n\n\nLine 3"
    clean_markdown = layout_agent.sanitize_markdown(dirty_markdown)

    # Should remove excessive blank lines
    assert clean_markdown == "Line 1\n\nLine 2\n\nLine 3"


def test_layout_agent_sanitize_markdown_empty():
    """Test markdown sanitization with empty input."""
    layout_agent = LayoutAgent(Mock())
    result = layout_agent.sanitize_markdown("")
    assert result == ""


def test_layout_agent_sanitize_markdown_single_line():
    """Test markdown sanitization with single line."""
    layout_agent = LayoutAgent(Mock())
    result = layout_agent.sanitize_markdown("Single line")
    assert result == "Single line"