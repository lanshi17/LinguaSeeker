"""Tests for orchestrator module."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.core.ingest_and_digitize_data.parse_document.base import ParserStrategy
from src.core.ingest_and_digitize_data.parse_document.contracts import (
    DocumentMetadata,
    PageContent,
    ParseResult,
)
from src.core.ingest_and_digitize_data.parse_document.exceptions import (
    MinerUAPIError,
    ParserExhaustedError,
)
from src.core.ingest_and_digitize_data.parse_document.orchestrator import DocumentParseOrchestrator


@pytest.fixture
def mock_remote():
    """Create mock remote parser."""
    parser = AsyncMock(spec=ParserStrategy)
    parser.name = "mineru-remote"
    return parser


@pytest.fixture
def mock_local():
    """Create mock local parser."""
    parser = AsyncMock(spec=ParserStrategy)
    parser.name = "mineru-local"
    return parser


@pytest.fixture
def sample_result():
    """Create sample parse result."""
    return ParseResult(
        metadata=DocumentMetadata(total_pages=1),
        pages=[PageContent(page_number=1, markdown="test")],
        parser_used="mineru-remote",
    )


@pytest.mark.asyncio
async def test_orchestrator_uses_remote_first(mock_remote, mock_local, sample_result):
    """Test that orchestrator tries remote first."""
    mock_remote.parse.return_value = sample_result

    orchestrator = DocumentParseOrchestrator(remote=mock_remote, local=mock_local)
    result = await orchestrator.parse("test.pdf")

    mock_remote.parse.assert_called_once_with("test.pdf")
    mock_local.parse.assert_not_called()
    assert result.parser_used == "mineru-remote"


@pytest.mark.asyncio
async def test_orchestrator_fallback_to_local(mock_remote, mock_local):
    """Test that orchestrator falls back to local on remote failure."""
    local_result = ParseResult(
        metadata=DocumentMetadata(total_pages=1),
        pages=[PageContent(page_number=1, markdown="test")],
        parser_used="mineru-local",
    )
    mock_remote.parse.side_effect = MinerUAPIError("Remote failed")
    mock_local.parse.return_value = local_result

    orchestrator = DocumentParseOrchestrator(remote=mock_remote, local=mock_local)
    result = await orchestrator.parse("test.pdf")

    mock_remote.parse.assert_called_once_with("test.pdf")
    mock_local.parse.assert_called_once_with("test.pdf")
    assert result.parser_used == "mineru-local"


@pytest.mark.asyncio
async def test_orchestrator_raises_on_both_failure(mock_remote, mock_local):
    """Test that orchestrator raises ParserExhaustedError when both fail."""
    mock_remote.parse.side_effect = MinerUAPIError("Remote failed")
    mock_local.parse.side_effect = MinerUAPIError("Local failed")

    orchestrator = DocumentParseOrchestrator(remote=mock_remote, local=mock_local)

    with pytest.raises(ParserExhaustedError) as exc_info:
        await orchestrator.parse("test.pdf")

    assert "mineru-remote" in exc_info.value.errors
    assert "mineru-local" in exc_info.value.errors


@pytest.mark.asyncio
async def test_orchestrator_name(mock_remote, mock_local):
    """Test orchestrator name property."""
    orchestrator = DocumentParseOrchestrator(remote=mock_remote, local=mock_local)
    assert orchestrator.name == "orchestrator"
