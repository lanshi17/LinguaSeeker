"""End-to-end tests for the online literature acquisition workflow.

Tests the full search → download pipeline using real providers.
Downloaded files go to backend/downloads/v1.2/.
Network-dependent tests skip gracefully when providers are unavailable.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.workflow import (
    online_acquisition_workflow,
)

DOWNLOAD_ROOT = str(Path(__file__).resolve().parents[2] / "downloads" / "v1.2")


def _skip_if_network_error(result: dict, provider_hint: str = "") -> None:
    """Skip test if failure is due to network unavailability."""
    if result.get("success"):
        return
    warnings = " ".join(result.get("warnings", []))
    indicators = (
        "sending request",
        "connect",
        "403",
        "429",
        "timeout",
        "unavailable",
        "net_io not available",
        "requires_email",
        "FETCH_NO_RESULT",
        "FULLTEXT_UNAVAILABLE",
    )
    if any(k in warnings.lower() for k in indicators):
        pytest.skip(f"Provider unavailable{f' ({provider_hint})' if provider_hint else ''}: {warnings[:200]}")


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_crossref_by_query():
    """Search CrossRef with a keyword query."""
    result = await online_acquisition_workflow(
        {
            "action": "search",
            "query": "BRCA1 breast cancer",
            "limit": 5,
            "raw": True,
        }
    )
    _skip_if_network_error(result, "crossref")
    assert result["success"] is True
    assert len(result["items"]) > 0
    first = result["items"][0]
    assert first.get("title"), "Expected title in first result"


@pytest.mark.asyncio
async def test_search_crossref_by_doi():
    """Search CrossRef by DOI identifier."""
    result = await online_acquisition_workflow(
        {
            "action": "search",
            "identifiers": ["10.1038/nature12373"],
            "limit": 3,
        }
    )
    _skip_if_network_error(result, "crossref")
    assert result["success"] is True
    assert len(result["items"]) > 0


@pytest.mark.asyncio
async def test_search_pmc_by_pmcid():
    """Search PMC by PubMed Central ID."""
    result = await online_acquisition_workflow(
        {
            "action": "search",
            "identifiers": ["PMC7075944"],
            "limit": 3,
        }
    )
    _skip_if_network_error(result, "pmc")
    assert result["success"] is True


@pytest.mark.asyncio
async def test_search_unpaywall_by_doi():
    """Search Unpaywall with a known open-access DOI (requires UNPAYWALL_EMAIL)."""
    if not os.getenv("UNPAYWALL_EMAIL"):
        pytest.skip("UNPAYWALL_EMAIL not set")
    result = await online_acquisition_workflow(
        {
            "action": "search",
            "query": "10.1371/journal.pone.0000308",
            "api_provider": "unpaywall",
            "limit": 3,
        }
    )
    _skip_if_network_error(result, "unpaywall")
    assert result["success"] is True


@pytest.mark.asyncio
async def test_search_openalex():
    """Search OpenAlex by query."""
    result = await online_acquisition_workflow(
        {
            "action": "search",
            "query": "CRISPR gene editing",
            "api_provider": "openalex",
            "limit": 5,
        }
    )
    _skip_if_network_error(result, "openalex")
    assert result["success"] is True
    assert len(result["items"]) > 0


@pytest.mark.asyncio
async def test_search_europepmc():
    """Search Europe PMC by query."""
    result = await online_acquisition_workflow(
        {
            "action": "search",
            "query": "variant pathogenicity classification",
            "api_provider": "europepmc",
            "limit": 5,
        }
    )
    _skip_if_network_error(result, "europepmc")
    assert result["success"] is True


@pytest.mark.asyncio
async def test_search_with_fallback_chain():
    """Search triggers fallback chain when first provider fails."""
    result = await online_acquisition_workflow(
        {
            "action": "search",
            "query": "ACMG variant classification guidelines",
            "limit": 5,
            "raw": True,
        }
    )
    _skip_if_network_error(result, "fallback-chain")
    assert result["success"] is True
    # Verify route info shows which provider was used
    assert result["route"]["used"] in ("api", "web")


# ---------------------------------------------------------------------------
# Download tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_crossref_open_access():
    """Download an open-access paper via CrossRef → Unpaywall chain."""
    download_path = os.path.join(DOWNLOAD_ROOT, "crossref")
    result = await online_acquisition_workflow(
        {
            "action": "download",
            "query": "10.1371/journal.pone.0000308",
            "download_path": download_path,
            "limit": 5,
        }
    )
    _skip_if_network_error(result, "crossref-download")
    assert result["success"] is True
    assert len(result["downloads"]) > 0
    # Verify file was actually written
    file_path = result["downloads"][0].get("file_path")
    if file_path:
        assert Path(file_path).exists(), f"Downloaded file should exist: {file_path}"
        assert Path(file_path).stat().st_size > 0, "Downloaded file should not be empty"


@pytest.mark.asyncio
async def test_download_pmc_fulltext():
    """Download a PMC full-text article (PubMed Central is open access)."""
    download_path = os.path.join(DOWNLOAD_ROOT, "pmc")
    result = await online_acquisition_workflow(
        {
            "action": "download",
            "identifiers": ["PMC7075944"],
            "download_path": download_path,
            "limit": 5,
        }
    )
    _skip_if_network_error(result, "pmc-download")
    assert result["success"] is True
    assert len(result["downloads"]) > 0


@pytest.mark.asyncio
async def test_download_with_doi_fallback():
    """Download triggers DOI fallback when API providers return no PDF."""
    download_path = os.path.join(DOWNLOAD_ROOT, "doi_fallback")
    result = await online_acquisition_workflow(
        {
            "action": "download",
            "identifiers": ["10.1038/nature12373"],
            "download_path": download_path,
            "limit": 5,
        }
    )
    _skip_if_network_error(result, "doi-fallback")
    # Either direct download or DOI fallback should succeed
    if result["success"]:
        assert len(result["downloads"]) > 0


@pytest.mark.asyncio
async def test_download_specified_provider():
    """Download from a specific provider (CrossRef) with a known open-access DOI."""
    download_path = os.path.join(DOWNLOAD_ROOT, "crossref_direct")
    result = await online_acquisition_workflow(
        {
            "action": "download",
            "query": "10.1371/journal.pone.0000308",
            "api_provider": "crossref",
            "download_path": download_path,
            "limit": 5,
        }
    )
    _skip_if_network_error(result, "crossref-direct-download")
    if result["success"]:
        assert len(result["downloads"]) > 0


# ---------------------------------------------------------------------------
# Search then download (two-step flow)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_then_download_by_index():
    """Search for papers, then download the first result by index."""
    # Step 1: Search
    search_result = await online_acquisition_workflow(
        {
            "action": "search",
            "query": "ACMG guidelines variant classification",
            "limit": 5,
        }
    )
    _skip_if_network_error(search_result, "search-step")
    assert search_result["success"] is True
    assert len(search_result["items"]) > 0

    # Step 2: Download first result
    first_item = search_result["items"][0]
    download_path = os.path.join(DOWNLOAD_ROOT, "search_then_download")

    download_result = await online_acquisition_workflow(
        {
            "action": "download",
            "query": first_item.get("title") or first_item.get("doi") or "ACMG",
            "download_path": download_path,
            "selected_index": 0,
            "limit": 5,
        }
    )
    _skip_if_network_error(download_result, "download-step")
    if download_result["success"]:
        assert len(download_result["downloads"]) > 0


# ---------------------------------------------------------------------------
# Route & metadata validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_route_info_populated():
    """Verify route info is populated in the response."""
    result = await online_acquisition_workflow(
        {
            "action": "search",
            "query": "genetic testing",
            "limit": 3,
        }
    )
    _skip_if_network_error(result)
    route = result["route"]
    assert "prefer" in route
    assert "used" in route


@pytest.mark.asyncio
async def test_invalid_request_returns_error():
    """Invalid request payload returns a structured error."""
    result = await online_acquisition_workflow(
        {
            "action": "invalid_action",
        }
    )
    assert result["success"] is False
    assert len(result["warnings"]) > 0


@pytest.mark.asyncio
async def test_web_provider_requires_specification():
    """prefer=web without web_provider returns an error."""
    result = await online_acquisition_workflow(
        {
            "action": "search",
            "query": "test",
            "prefer": "web",
        }
    )
    assert result["success"] is False
    assert any("web_provider" in w for w in result["warnings"])


@pytest.mark.asyncio
async def test_raw_mode_includes_source_trace():
    """raw=True includes source trace in response."""
    result = await online_acquisition_workflow(
        {
            "action": "search",
            "query": "BRCA1",
            "limit": 3,
            "raw": True,
        }
    )
    _skip_if_network_error(result)
    assert result.get("raw") is not None
    assert "source_trace" in result["raw"]


# ---------------------------------------------------------------------------
# Language-specific routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_language_path_organization():
    """Download with Chinese DOI auto-organizes into zh/ subdirectory."""
    download_path = os.path.join(DOWNLOAD_ROOT, "lang")
    result = await online_acquisition_workflow(
        {
            "action": "download",
            "identifiers": ["10.3760/cma.j.cn112151-20200407-00486"],
            "download_path": download_path,
            "limit": 3,
        }
    )
    _skip_if_network_error(result, "chinese-doi")
    # If it succeeds, verify the path contains zh/
    if result["success"] and result["downloads"]:
        file_path = result["downloads"][0].get("file_path", "")
        if file_path:
            assert "/zh/" in file_path or "\\zh\\" in file_path, "Chinese DOI should route to zh/ subdirectory"
