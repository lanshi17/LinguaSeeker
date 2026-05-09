"""Regression tests for the rust_io Python facade."""

import hashlib

import pytest

import rust_io.files as files
import rust_io.http as http_io


def test_http_io_facade_exports_provider_functions():
    for name in (
        "fetch_one",
        "fetch_multi",
        "scrape_web",
        "scrape_html",
        "extract_pdf_links",
        "mineru_create_task",
        "mineru_get_result",
        "mineru_batch_submit",
        "mineru_batch_result",
    ):
        assert hasattr(http_io, name)


def test_files_facade_preserves_legacy_helpers(tmp_path):
    path = tmp_path / "sample.bin"

    files.write_file(str(path), b"abc")

    assert path.read_bytes() == b"abc"
    assert files.compute_sha256(str(path)) == hashlib.sha256(b"abc").hexdigest()
    assert files.validate_pdf_magic(b"%PDF-1.7") is True
    assert files.validate_pdf_magic(b"not a pdf") is False


def test_files_facade_exports_files_io_functions():
    for name in (
        "File",
        "batch_copy",
        "batch_compress",
        "batch_copy_async",
        "check_duplicate",
        "batch_hash",
    ):
        assert hasattr(files, name)


@pytest.mark.asyncio
async def test_http_io_fetch_multi_returns_failure_per_unknown_provider():
    results = await http_io.fetch_multi(["missing_a", "missing_b"], "search", {})

    assert [result["provider"] for result in results] == ["missing_a", "missing_b"]
    assert [result["success"] for result in results] == [False, False]
    assert all(result["warnings"] for result in results)


@pytest.mark.asyncio
async def test_unpaywall_requires_configured_email(monkeypatch):
    monkeypatch.delenv("UNPAYWALL_EMAIL", raising=False)

    result = await http_io.fetch_one(
        "unpaywall",
        "search",
        {"identifiers": {"doi": "10.1234/example"}},
        timeout_ms=100,
        max_retries=0,
        proxy="http://127.0.0.1:1",
    )

    assert result["success"] is False
    assert result["warnings"] == ["unpaywall_requires_email"]
