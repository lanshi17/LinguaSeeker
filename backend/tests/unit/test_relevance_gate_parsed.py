"""Unit tests for relevance_gate _check_one parsed_markdown bypass."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.relevance_gate import (
    _check_one,
)


@pytest.mark.asyncio
async def test_check_one_uses_parsed_markdown(tmp_path):
    """When download has parsed_markdown, fitz extraction is bypassed."""
    # Create an empty file path that would otherwise fail extraction.
    fake_pdf = tmp_path / "paper.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4\n%fake")

    download = {
        "file_path": str(fake_pdf),
        "title": "Test paper",
        "lang": "en",
        "parsed_markdown": "# Title\n\nThis paper describes BRCA1 c.5266dupC variant in a Rett syndrome cohort.",
    }

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"relevant": True, "reason": "matches"})

    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=mock_response)

    import asyncio as _asyncio

    sem = _asyncio.Semaphore(1)

    # Patch fitz to ensure it's NOT called when parsed_markdown is present.
    with patch(
        "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.relevance_gate.fitz"
    ) as mock_fitz:
        judgment = await _check_one(
            client=client,
            sem=sem,
            model="test-model",
            query="Rett syndrome MECP2",
            download=download,
            max_pages=3,
            max_chars=3000,
            max_tokens=1024,
        )

    assert judgment.relevant is True
    assert judgment.error == ""
    mock_fitz.open.assert_not_called()
    # The user message must include the parsed markdown text.
    call_args = client.chat.completions.create.call_args
    user_msg = call_args.kwargs["messages"][1]["content"]
    assert "BRCA1 c.5266dupC" in user_msg


@pytest.mark.asyncio
async def test_check_one_falls_back_to_fitz_without_markdown(tmp_path):
    """Without parsed_markdown, behavior unchanged: fitz extracts text."""
    fake_pdf = tmp_path / "paper.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4\n")

    download = {
        "file_path": str(fake_pdf),
        "title": "Test paper",
        "lang": "en",
        # NO parsed_markdown
    }

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"relevant": True, "reason": "ok"})

    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=mock_response)

    import asyncio as _asyncio

    sem = _asyncio.Semaphore(1)

    with patch(
        "src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.relevance_gate._extract_text",
        return_value="A long enough body of extracted text that passes the 30-char floor.",
    ) as mock_extract:
        judgment = await _check_one(
            client=client,
            sem=sem,
            model="test-model",
            query="Rett",
            download=download,
            max_pages=3,
            max_chars=3000,
            max_tokens=1024,
        )

    assert judgment.relevant is True
    mock_extract.assert_called_once()


@pytest.mark.asyncio
async def test_check_one_missing_file_without_markdown_returns_error(tmp_path):
    """Missing PDF without parsed_markdown returns file_not_found error."""
    download = {
        "file_path": str(tmp_path / "missing.pdf"),
        "title": "Test",
        "lang": "en",
    }

    client = MagicMock()
    client.chat.completions.create = AsyncMock()

    import asyncio as _asyncio

    sem = _asyncio.Semaphore(1)

    judgment = await _check_one(
        client=client,
        sem=sem,
        model="test-model",
        query="q",
        download=download,
        max_pages=3,
        max_chars=3000,
        max_tokens=1024,
    )

    assert judgment.error == "file_not_found"
    client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_check_one_with_markdown_skips_missing_file_check(tmp_path):
    """parsed_markdown bypass works even if file_path is missing/empty."""
    download = {
        "file_path": str(tmp_path / "missing.pdf"),
        "title": "Test",
        "lang": "en",
        "parsed_markdown": "Substantial markdown body discussing MECP2 variants.",
    }

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps({"relevant": True, "reason": "ok"})

    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=mock_response)

    import asyncio as _asyncio

    sem = _asyncio.Semaphore(1)

    judgment = await _check_one(
        client=client,
        sem=sem,
        model="test-model",
        query="MECP2",
        download=download,
        max_pages=3,
        max_chars=3000,
        max_tokens=1024,
    )

    # No file_not_found — markdown was used.
    assert judgment.error == ""
    assert judgment.relevant is True
