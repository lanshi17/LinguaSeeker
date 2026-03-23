from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.domain.literature.gateway.adapters.pmc_adapter import PmcGatewayAdapter
from src.domain.literature.gateway.api_gateway import (
    ApiGatewayRequest,
    ApiGatewayResult,
)


@dataclass
class _RecordedCall:
    args: tuple[Any, ...]
    kwargs: dict[str, Any]


def _unexpected_result(label: str) -> None:
    raise AssertionError(f"Unexpected PMC adapter helper call: {label}")


async def _unexpected_metadata(
    pmcids: list[str], raw: bool = False, api_params: dict[str, Any] | None = None
) -> ApiGatewayResult:
    raise AssertionError("Unexpected PMC adapter helper call: metadata")


async def _unexpected_pmid(
    pmid: str,
    limit: int = 20,
    raw: bool = False,
    api_params: dict[str, Any] | None = None,
) -> ApiGatewayResult:
    raise AssertionError("Unexpected PMC adapter helper call: pmid")


async def _unexpected_search(
    term: str,
    limit: int = 20,
    raw: bool = False,
    api_params: dict[str, Any] | None = None,
) -> ApiGatewayResult:
    raise AssertionError("Unexpected PMC adapter helper call: search")


async def _unexpected_download(
    query: str | None,
    identifiers: dict[str, str | None],
    limit: int,
    raw: bool,
    download_path: str,
    api_params: dict[str, Any] | None = None,
) -> ApiGatewayResult:
    raise AssertionError("Unexpected PMC adapter helper call: download")


@pytest.mark.asyncio
async def test_pmc_adapter_uses_metadata_for_pmcid_requests() -> None:
    recorded: dict[str, _RecordedCall] = {}

    async def fake_metadata(
        pmcids: list[str], raw: bool = False, api_params: dict[str, Any] | None = None
    ) -> ApiGatewayResult:
        recorded["metadata"] = _RecordedCall(
            (pmcids,), {"raw": raw, "api_params": api_params}
        )
        return ApiGatewayResult(
            provider="pmc", success=True, items=[{"pmcid": pmcids[0]}], warnings=[]
        )

    adapter = PmcGatewayAdapter(
        metadata_fn=fake_metadata,
        pmid_fn=_unexpected_pmid,
        search_fn=_unexpected_search,
        download_fn=_unexpected_download,
    )

    result = await adapter.execute(
        ApiGatewayRequest(
            provider="pmc",
            action="search",
            identifiers={"pmcid": "PMC7777777"},
            raw=True,
            params={"source": "pmcid-freeze"},
        )
    )

    assert result.success is True
    assert result.items == [{"pmcid": "PMC7777777"}]
    assert recorded["metadata"].args == (["PMC7777777"],)
    assert recorded["metadata"].kwargs == {
        "raw": True,
        "api_params": {"source": "pmcid-freeze"},
    }


@pytest.mark.asyncio
async def test_pmc_adapter_uses_pmid_helper_for_pmid_requests() -> None:
    recorded: dict[str, _RecordedCall] = {}

    async def fake_for_pmid(
        pmid: str,
        limit: int = 20,
        raw: bool = False,
        api_params: dict[str, Any] | None = None,
    ) -> ApiGatewayResult:
        recorded["pmid"] = _RecordedCall(
            (pmid,), {"limit": limit, "raw": raw, "api_params": api_params}
        )
        return ApiGatewayResult(
            provider="pmc", success=True, items=[{"pmid": pmid}], warnings=[]
        )

    adapter = PmcGatewayAdapter(
        metadata_fn=_unexpected_metadata,
        pmid_fn=fake_for_pmid,
        search_fn=_unexpected_search,
        download_fn=_unexpected_download,
    )

    result = await adapter.execute(
        ApiGatewayRequest(
            provider="pmc",
            action="search",
            identifiers={"pmid": "12345678"},
            limit=7,
            params={"source": "pmid-freeze"},
        )
    )

    assert result.success is True
    assert result.items == [{"pmid": "12345678"}]
    assert recorded["pmid"].args == ("12345678",)
    assert recorded["pmid"].kwargs == {
        "limit": 7,
        "raw": False,
        "api_params": {"source": "pmid-freeze"},
    }


@pytest.mark.asyncio
async def test_pmc_adapter_searches_and_hydrates_for_generic_queries() -> None:
    recorded: dict[str, _RecordedCall] = {}

    async def fake_search(
        term: str,
        limit: int = 20,
        raw: bool = False,
        api_params: dict[str, Any] | None = None,
    ) -> ApiGatewayResult:
        recorded["search"] = _RecordedCall(
            (term,), {"limit": limit, "raw": raw, "api_params": api_params}
        )
        return ApiGatewayResult(
            provider="pmc",
            success=True,
            items=[{"pmcid": "PMC101"}, {"pmcid": "PMC202"}],
            warnings=["pmc_search_warning"],
        )

    async def fake_metadata(
        pmcids: list[str], raw: bool = False, api_params: dict[str, Any] | None = None
    ) -> ApiGatewayResult:
        recorded["metadata"] = _RecordedCall(
            (pmcids,), {"raw": raw, "api_params": api_params}
        )
        return ApiGatewayResult(
            provider="pmc",
            success=True,
            items=[
                {"pmcid": "PMC101", "title": "A"},
                {"pmcid": "PMC202", "title": "B"},
            ],
            warnings=["pmc_metadata_warning"],
        )

    adapter = PmcGatewayAdapter(
        metadata_fn=fake_metadata,
        pmid_fn=_unexpected_pmid,
        search_fn=fake_search,
        download_fn=_unexpected_download,
    )

    result = await adapter.execute(
        ApiGatewayRequest(
            provider="pmc",
            action="search",
            query="familial hypercholesterolemia",
            limit=3,
            raw=True,
            params={"source": "generic-freeze"},
        )
    )

    assert result.success is True
    assert result.items == [
        {"pmcid": "PMC101", "title": "A"},
        {"pmcid": "PMC202", "title": "B"},
    ]
    assert result.warnings == ["pmc_search_warning", "pmc_metadata_warning"]
    assert recorded["search"].args == ("familial hypercholesterolemia",)
    assert recorded["search"].kwargs == {
        "limit": 3,
        "raw": True,
        "api_params": {"source": "generic-freeze"},
    }
    assert recorded["metadata"].args == (["PMC101", "PMC202"],)
    assert recorded["metadata"].kwargs == {
        "raw": True,
        "api_params": {"source": "generic-freeze"},
    }


@pytest.mark.asyncio
async def test_pmc_adapter_delegates_download_requests() -> None:
    recorded: dict[str, _RecordedCall] = {}

    async def fake_download(
        query: str | None,
        identifiers: dict[str, str | None],
        limit: int,
        raw: bool,
        download_path: str,
        api_params: dict[str, Any] | None = None,
    ) -> ApiGatewayResult:
        recorded["download"] = _RecordedCall(
            (query, identifiers, limit, raw, download_path, api_params),
            {},
        )
        return ApiGatewayResult(
            provider="pmc",
            success=True,
            items=[],
            downloads=[{"file_path": "/tmp/pmc/paper.pdf"}],
            warnings=[],
        )

    adapter = PmcGatewayAdapter(
        metadata_fn=_unexpected_metadata,
        pmid_fn=_unexpected_pmid,
        search_fn=_unexpected_search,
        download_fn=fake_download,
    )

    result = await adapter.execute(
        ApiGatewayRequest(
            provider="pmc",
            action="download",
            identifiers={"pmcid": "PMC7777777"},
            query="PMC Article",
            selected_title="PMC Article",
            download_path="/tmp/pmc",
            params={"source": "download-freeze"},
        )
    )

    assert result.success is True
    assert result.downloads == [{"file_path": "/tmp/pmc/paper.pdf"}]
    assert recorded["download"].args == (
        "PMC Article",
        {"pmcid": "PMC7777777"},
        20,
        False,
        "/tmp/pmc",
        {"source": "download-freeze"},
    )
