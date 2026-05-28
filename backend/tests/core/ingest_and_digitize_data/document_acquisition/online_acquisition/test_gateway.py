"""Tests for gateway module — with mocked net_io."""

from unittest.mock import patch

import pytest

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import OnlineAcquisitionGatewayRequest
from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.gateway import (
    _build_fetch_params,
    _choose_item,
    _rust_result_to_gateway,
    call_provider,
)


class TestBuildFetchParams:
    def test_basic_params(self):
        request = OnlineAcquisitionGatewayRequest(provider="crossref", action="search", query="cancer", limit=10)
        params = _build_fetch_params(request)
        assert params["query"] == "cancer"
        assert params["limit"] == 10
        assert params["raw"] is False

    def test_with_identifiers(self):
        request = OnlineAcquisitionGatewayRequest(
            provider="unpaywall",
            identifiers={"doi": "10.1234/test"},
        )
        params = _build_fetch_params(request)
        assert params["identifiers"] == {"doi": "10.1234/test"}

    def test_none_identifiers_excluded(self):
        request = OnlineAcquisitionGatewayRequest(
            provider="unpaywall",
            identifiers={"doi": "10.1234/test", "pmid": None},
        )
        params = _build_fetch_params(request)
        assert params["identifiers"] == {"doi": "10.1234/test"}


class TestChooseItem:
    def test_by_index(self):
        items = [{"title": "A"}, {"title": "B"}, {"title": "C"}]
        result = _choose_item(items, 1, None, ["title"])
        assert result == {"title": "B"}

    def test_by_title(self):
        items = [{"title": "Alpha"}, {"title": "Beta"}, {"title": "Gamma"}]
        result = _choose_item(items, 0, "beta", ["title"])
        assert result == {"title": "Beta"}

    def test_title_not_found_falls_back_to_index(self):
        items = [{"title": "Alpha"}, {"title": "Beta"}]
        result = _choose_item(items, 1, "missing", ["title"])
        assert result == {"title": "Beta"}

    def test_out_of_range_index(self):
        items = [{"title": "A"}]
        result = _choose_item(items, 5, None, ["title"])
        assert result is None


class TestRustResultToGateway:
    def test_success_result(self):
        raw = {
            "provider": "crossref",
            "success": True,
            "items": [{"title": "Paper"}],
            "downloads": [],
            "warnings": [],
        }
        result = _rust_result_to_gateway("crossref", raw)
        assert result.success is True
        assert len(result.items) == 1

    def test_failure_result(self):
        raw = {
            "provider": "crossref",
            "success": False,
            "items": [],
            "downloads": [],
            "warnings": ["error"],
        }
        result = _rust_result_to_gateway("crossref", raw)
        assert result.success is False


class TestCallProvider:
    @pytest.mark.asyncio
    async def test_net_io_not_available(self):
        with patch("builtins.__import__", side_effect=ImportError("no net_io")):
            result = await call_provider(OnlineAcquisitionGatewayRequest(provider="crossref"))
            assert result.success is False
            assert "not available" in result.warnings[0]
