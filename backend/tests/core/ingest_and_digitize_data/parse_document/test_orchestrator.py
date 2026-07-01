"""Tests for orchestrator module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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
from src.core.ingest_and_digitize_data.parse_document.orchestrator import (
    DocumentParseOrchestrator,
    _validate_url_safe,
)


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


@pytest.mark.asyncio
async def test_parse_local_files_delegates_to_remote(mock_remote, mock_local):
    """Regression: factory-created orchestrator.parse_local_files() works."""
    from src.core.ingest_and_digitize_data.parse_document.contracts import (
        MinerUBatchStatus,
        MinerULocalBatchParseResult,
    )

    expected = MinerULocalBatchParseResult(
        batch_id="b1",
        status=MinerUBatchStatus(batch_id="b1"),
        results={},
    )
    mock_remote.parse_local_files = AsyncMock(return_value=expected)

    orchestrator = DocumentParseOrchestrator(remote=mock_remote, local=mock_local)
    result = await orchestrator.parse_local_files(["/tmp/a.pdf"], data_ids=["a"])

    assert result is expected
    mock_remote.parse_local_files.assert_awaited_once_with(["/tmp/a.pdf"], data_ids=["a"])


@pytest.mark.asyncio
async def test_parse_local_files_raises_if_remote_lacks_method(mock_remote, mock_local):
    """Regression: clear error when remote parser doesn't support batch."""
    if hasattr(mock_remote, "parse_local_files"):
        del mock_remote.parse_local_files

    orchestrator = DocumentParseOrchestrator(remote=mock_remote, local=mock_local)

    with pytest.raises(AttributeError, match="does not support parse_local_files"):
        await orchestrator.parse_local_files(["/tmp/a.pdf"])


class _FakeStreamCM:
    """Fake async context manager for httpx client.stream()."""

    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *args):
        return False


def _make_pdf_response(pdf_bytes: bytes = b"%PDF-1.4 fake", url: str = "https://example.com/paper.pdf"):
    """Build a mock httpx response for a successful PDF stream.

    ``raise_for_status`` and ``headers`` are synchronous in httpx, so the
    mock must be a ``MagicMock`` (not ``AsyncMock``).  Only ``aiter_bytes``
    needs to be an async generator.
    """
    mock_response = MagicMock()
    mock_response.headers = {"content-type": "application/pdf"}
    mock_response.url = url
    mock_response.raise_for_status = MagicMock()

    async def _aiter_bytes():
        yield pdf_bytes

    mock_response.aiter_bytes = _aiter_bytes
    return mock_response


@pytest.mark.asyncio
async def test_url_fallback_downloads_to_temp_and_cleans_up(mock_remote, mock_local):
    """Regression: URL input downloads to temp file, passes path to local, cleans up."""
    local_result = ParseResult(
        metadata=DocumentMetadata(total_pages=1),
        pages=[PageContent(page_number=1, markdown="parsed")],
        parser_used="mineru-local",
    )
    mock_remote.parse.side_effect = MinerUAPIError("Remote failed")
    mock_local.parse.return_value = local_result

    mock_response = _make_pdf_response()
    mock_client = MagicMock()
    mock_client.stream.return_value = _FakeStreamCM(mock_response)

    orchestrator = DocumentParseOrchestrator(remote=mock_remote, local=mock_local)

    with (
        patch("src.core.ingest_and_digitize_data.parse_document.orchestrator.httpx.AsyncClient") as mock_cls,
        patch("src.core.ingest_and_digitize_data.parse_document.orchestrator._validate_url_safe"),
    ):
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await orchestrator.parse("https://example.com/paper.pdf")

    assert result.parser_used == "mineru-local"
    called_path = mock_local.parse.call_args[0][0]
    assert called_path != "https://example.com/paper.pdf"
    assert not __import__("pathlib").Path(called_path).exists(), "temp file should be cleaned up"


@pytest.mark.asyncio
async def test_url_fallback_rejects_non_pdf_content_type(mock_remote, mock_local):
    """Regression: non-PDF content-type is rejected before writing to disk."""
    mock_remote.parse.side_effect = MinerUAPIError("Remote failed")

    mock_response = _make_pdf_response()
    mock_response.headers = {"content-type": "text/html"}
    mock_client = MagicMock()
    mock_client.stream.return_value = _FakeStreamCM(mock_response)

    orchestrator = DocumentParseOrchestrator(remote=mock_remote, local=mock_local)

    with (
        patch("src.core.ingest_and_digitize_data.parse_document.orchestrator.httpx.AsyncClient") as mock_cls,
        patch("src.core.ingest_and_digitize_data.parse_document.orchestrator._validate_url_safe"),
    ):
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(ParserExhaustedError) as exc_info:
            await orchestrator.parse("https://example.com/fake.pdf")

    assert "url-download" in exc_info.value.errors


@pytest.mark.asyncio
async def test_url_fallback_rejects_non_pdf_signature(mock_remote, mock_local):
    """Regression: downloaded file without %PDF magic is rejected."""
    mock_remote.parse.side_effect = MinerUAPIError("Remote failed")

    mock_response = _make_pdf_response(pdf_bytes=b"<html>not a pdf</html>")
    mock_client = MagicMock()
    mock_client.stream.return_value = _FakeStreamCM(mock_response)

    orchestrator = DocumentParseOrchestrator(remote=mock_remote, local=mock_local)

    with (
        patch("src.core.ingest_and_digitize_data.parse_document.orchestrator.httpx.AsyncClient") as mock_cls,
        patch("src.core.ingest_and_digitize_data.parse_document.orchestrator._validate_url_safe"),
    ):
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(ParserExhaustedError) as exc_info:
            await orchestrator.parse("https://example.com/fake.pdf")

    assert "url-download" in exc_info.value.errors


@pytest.mark.asyncio
async def test_url_fallback_rejects_http_error(mock_remote, mock_local):
    """Regression: HTTP 4xx/5xx raises via raise_for_status and triggers fallback error."""
    mock_remote.parse.side_effect = MinerUAPIError("Remote failed")

    mock_response = MagicMock()
    mock_response.headers = {"content-type": "application/pdf"}
    mock_response.url = "https://example.com/paper.pdf"
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "403 Forbidden",
            request=httpx.Request("GET", "https://example.com/paper.pdf"),
            response=httpx.Response(403),
        )
    )
    mock_client = MagicMock()
    mock_client.stream.return_value = _FakeStreamCM(mock_response)

    orchestrator = DocumentParseOrchestrator(remote=mock_remote, local=mock_local)

    with (
        patch("src.core.ingest_and_digitize_data.parse_document.orchestrator.httpx.AsyncClient") as mock_cls,
        patch("src.core.ingest_and_digitize_data.parse_document.orchestrator._validate_url_safe"),
    ):
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(ParserExhaustedError) as exc_info:
            await orchestrator.parse("https://example.com/paper.pdf")

    assert "url-download" in exc_info.value.errors


# --- SSRF protection tests ---


def test_validate_url_safe_rejects_loopback():
    with pytest.raises(MinerUAPIError, match="private/reserved"):
        _validate_url_safe("http://127.0.0.1/admin")


def test_validate_url_safe_rejects_private_10():
    with pytest.raises(MinerUAPIError, match="private/reserved"):
        _validate_url_safe("http://10.0.0.1/file.pdf")


def test_validate_url_safe_rejects_private_192():
    with pytest.raises(MinerUAPIError, match="private/reserved"):
        _validate_url_safe("http://192.168.1.1/file.pdf")


def test_validate_url_safe_rejects_private_172():
    with pytest.raises(MinerUAPIError, match="private/reserved"):
        _validate_url_safe("http://172.16.0.1/file.pdf")


def test_validate_url_safe_rejects_link_local():
    with pytest.raises(MinerUAPIError, match="private/reserved"):
        _validate_url_safe("http://169.254.169.254/latest/meta-data/")


def test_validate_url_safe_rejects_ipv6_loopback():
    with pytest.raises(MinerUAPIError, match="private/reserved"):
        _validate_url_safe("http://[::1]/file.pdf")


def test_validate_url_safe_rejects_unsupported_scheme():
    with pytest.raises(MinerUAPIError, match="Unsupported URL scheme"):
        _validate_url_safe("ftp://example.com/file.pdf")


def test_validate_url_safe_allows_public_url():
    """Public URLs should not raise."""
    _validate_url_safe("https://example.com/paper.pdf")
