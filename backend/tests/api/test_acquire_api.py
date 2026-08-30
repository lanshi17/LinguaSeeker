"""Tests for the standalone literature acquisition endpoint (POST /pipeline/acquire)."""

from __future__ import annotations

import asyncio

from dataclasses import dataclass

import pytest
from httpx import AsyncClient

from src.core.ingest_and_digitize_data.document_acquisition.contracts import (
    AcquisitionSource,
    DocumentAcquisitionResult,
    DocumentDownloadEntry,
)

_SERVICE_MOD = "src.core.ingest_and_digitize_data.document_acquisition.service.DocumentAcquisitionService.acquire"


@dataclass
class _FakeItem:
    """Minimal stand-in for lit_acquisition OnlineAcquisitionItem."""

    title: str = "Some paper"
    doi: str = "10.1234/example"


def _make_service_patch(monkeypatch, result: DocumentAcquisitionResult, capture: dict):
    """Patch DocumentAcquisitionService.acquire; record the request in ``capture``."""

    async def _fake_acquire(self, request):
        capture["request"] = request
        return result

    monkeypatch.setattr(_SERVICE_MOD, _fake_acquire)


@pytest.mark.asyncio
async def test_acquire_download_success(async_client: AsyncClient, monkeypatch):
    """Successful download returns typed download entries."""
    capture: dict = {}
    result = DocumentAcquisitionResult(
        success=True,
        source=AcquisitionSource.ONLINE,
        warnings=["provider x slow"],
        items=[_FakeItem()],
        downloads=[
            DocumentDownloadEntry(
                file_path="/data/acquire/paper.pdf",
                pdf_url="https://example.org/paper.pdf",
                resolved_url="https://oa.example.org/paper.pdf",
                pre_parsed_markdown=None,
            ),
            DocumentDownloadEntry(file_path="/data/acquire/pre.pdf", pre_parsed_markdown="# Title"),
        ],
        elapsed_time=1.23,
    )
    _make_service_patch(monkeypatch, result, capture)

    resp = await async_client.post(
        "/api/v1/pipeline/acquire",
        json={"query": "MECP2 Rett syndrome", "limit": 3},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["items_count"] == 1
    assert body["elapsed_seconds"] == 1.23
    assert body["warnings"] == ["provider x slow"]
    assert len(body["downloads"]) == 2
    first, second = body["downloads"]
    assert first["file_path"] == "/data/acquire/paper.pdf"
    assert first["pre_parsed"] is False
    assert second["pre_parsed"] is True

    req = capture["request"]
    assert req.action == "download"
    assert req.limit == 3
    assert req.query == "MECP2 Rett syndrome"
    assert req.download_path.endswith("data/acquire")


@pytest.mark.asyncio
async def test_acquire_search_action_and_identifiers(async_client: AsyncClient, monkeypatch):
    """Identifiers are passed through and action=search works."""
    capture: dict = {}
    result = DocumentAcquisitionResult(
        success=True,
        source=AcquisitionSource.ONLINE,
        items=[_FakeItem(), _FakeItem()],
        downloads=[],
        elapsed_time=0.5,
    )
    _make_service_patch(monkeypatch, result, capture)

    resp = await async_client.post(
        "/api/v1/pipeline/acquire",
        json={"identifiers": ["PMID:12345678", "10.1234/x"], "action": "search"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["downloads"] == []
    assert body["items_count"] == 2

    req = capture["request"]
    assert req.action == "search"
    assert req.identifiers == ["PMID:12345678", "10.1234/x"]
    assert req.query is None


@pytest.mark.asyncio
async def test_acquire_requires_query_or_identifiers(async_client: AsyncClient):
    """Missing both query and identifiers is rejected with 422."""
    resp = await async_client.post("/api/v1/pipeline/acquire", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_acquire_limit_out_of_range(async_client: AsyncClient):
    """limit outside 1-50 is rejected with 422."""
    resp = await async_client.post(
        "/api/v1/pipeline/acquire",
        json={"identifiers": ["10.1234/x"], "limit": 100},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_acquire_not_success_returns_payload_with_error(async_client: AsyncClient, monkeypatch):
    """A failed acquisition still returns 200 with success=false and error text."""
    capture: dict = {}
    result = DocumentAcquisitionResult(
        success=False,
        source=AcquisitionSource.ONLINE,
        warnings=["No OA copy"],
        error="Full-text PDF unavailable",
    )
    _make_service_patch(monkeypatch, result, capture)

    resp = await async_client.post(
        "/api/v1/pipeline/acquire",
        json={"identifiers": ["10.1234/paywalled"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"] == "Full-text PDF unavailable"
    assert body["downloads"] == []


@pytest.mark.asyncio
async def test_acquire_unexpected_service_error_returns_502(async_client: AsyncClient, monkeypatch):
    """An unexpected exception from the service maps to 502."""

    async def _boom(self, request):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(_SERVICE_MOD, _boom)

    resp = await async_client.post(
        "/api/v1/pipeline/acquire",
        json={"identifiers": ["10.1234/x"]},
    )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_acquire_truncates_downloads_to_limit(async_client: AsyncClient, monkeypatch):
    """More downloads than ``limit`` are truncated, with a warning appended."""
    result = DocumentAcquisitionResult(
        success=True,
        source=AcquisitionSource.ONLINE,
        items=[_FakeItem() for _ in range(4)],
        downloads=[
            DocumentDownloadEntry(file_path=f"/data/acquire/paper_{i}.pdf") for i in range(4)
        ],
        elapsed_time=2.0,
    )
    capture: dict = {}
    _make_service_patch(monkeypatch, result, capture)

    resp = await async_client.post(
        "/api/v1/pipeline/acquire",
        json={"identifiers": ["10.1234/x"], "limit": 2},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["downloads"]) == 2
    assert body["downloads"][0]["file_path"] == "/data/acquire/paper_0.pdf"
    assert any(w.startswith("DOWNLOADS_TRUNCATED") for w in body["warnings"])


@pytest.mark.asyncio
async def test_acquire_timeout_returns_504(async_client: AsyncClient, monkeypatch):
    """A hung acquisition is aborted at the request budget with 504."""

    async def _hang(self, request):
        await asyncio.sleep(60)

    monkeypatch.setattr(_SERVICE_MOD, _hang)

    resp = await async_client.post(
        "/api/v1/pipeline/acquire",
        json={"identifiers": ["10.1234/slow"], "timeout_seconds": 10},
    )
    assert resp.status_code == 504
    body = resp.json()
    assert "timed out after 10s" in body["error"]["message"]
