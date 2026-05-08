"""Tests for online acquisition contracts."""

from src.core.ingest_and_digitize_data.document_acquisition.online_acquisition.contracts import (
    OnlineAcquisitionGatewayRequest,
    OnlineAcquisitionGatewayResult,
    OnlineAcquisitionItem,
    OnlineAcquisitionRequest,
    OnlineAcquisitionResponse,
    OnlineAcquisitionRouteInfo,
    OnlineAcquisitionSourceTraceEntry,
)


class TestOnlineAcquisitionRequest:
    def test_default_values(self):
        req = OnlineAcquisitionRequest()
        assert req.action == "search"
        assert req.limit == 20
        assert req.prefer == "auto"
        assert req.identifiers == []

    def test_identifier_alias(self):
        req = OnlineAcquisitionRequest(identifier="10.1234/test")
        assert req.identifiers == ["10.1234/test"]

    def test_text_alias(self):
        req = OnlineAcquisitionRequest(text="cancer therapy")
        assert req.query == "cancer therapy"

    def test_limit_clamped(self):
        req = OnlineAcquisitionRequest(limit=500)
        assert req.limit == 200
        req = OnlineAcquisitionRequest(limit=0)
        assert req.limit == 1

    def test_identifiers_normalized(self):
        req = OnlineAcquisitionRequest(identifiers="single-id")
        assert req.identifiers == ["single-id"]
        req = OnlineAcquisitionRequest(identifiers=["a", "b"])
        assert req.identifiers == ["a", "b"]


class TestOnlineAcquisitionItem:
    def test_construction(self):
        item = OnlineAcquisitionItem(source="crossref", title="Test Paper")
        assert item.source == "crossref"
        assert item.title == "Test Paper"
        assert item.authors == []
        assert item.identifiers == {}


class TestOnlineAcquisitionRouteInfo:
    def test_defaults(self):
        route = OnlineAcquisitionRouteInfo(prefer="auto")
        assert route.used is None
        assert route.fallback_used is False


class TestOnlineAcquisitionResponse:
    def test_success_response(self):
        route = OnlineAcquisitionRouteInfo(prefer="auto", used="api", reason="api_provider:crossref")
        resp = OnlineAcquisitionResponse(success=True, items=[], route=route)
        assert resp.success is True
        assert resp.warnings == []

    def test_model_dump(self):
        route = OnlineAcquisitionRouteInfo(prefer="auto")
        resp = OnlineAcquisitionResponse(success=False, route=route)
        data = resp.model_dump()
        assert "success" in data
        assert "route" in data


class TestOnlineAcquisitionSourceTraceEntry:
    def test_construction(self):
        trace = OnlineAcquisitionSourceTraceEntry(
            provider="crossref",
            attempt=1,
            action="search",
            success=True,
            items_count=5,
            downloads_count=0,
            warnings=[],
        )
        assert trace.provider == "crossref"
        assert trace.error is None


class TestOnlineAcquisitionGatewayResult:
    def test_defaults(self):
        result = OnlineAcquisitionGatewayResult(
            provider="crossref",
            success=True,
            items=[],
            warnings=[],
        )
        assert result.downloads == []
        assert result.source_trace == []
