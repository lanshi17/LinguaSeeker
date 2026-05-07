"""Tests for literature acquisition contracts."""

from src.core.ingest_and_digitize_data.literature_acquisition.contracts import (
    GatewayRequest,
    GatewayResult,
    LiteratureItem,
    LiteratureRequest,
    LiteratureResponse,
    RouteInfo,
    SourceTraceEntry,
)


class TestLiteratureRequest:
    def test_default_values(self):
        req = LiteratureRequest()
        assert req.action == "search"
        assert req.limit == 20
        assert req.prefer == "auto"
        assert req.identifiers == []

    def test_identifier_alias(self):
        req = LiteratureRequest(identifier="10.1234/test")
        assert req.identifiers == ["10.1234/test"]

    def test_text_alias(self):
        req = LiteratureRequest(text="cancer therapy")
        assert req.query == "cancer therapy"

    def test_limit_clamped(self):
        req = LiteratureRequest(limit=500)
        assert req.limit == 200
        req = LiteratureRequest(limit=0)
        assert req.limit == 1

    def test_identifiers_normalized(self):
        req = LiteratureRequest(identifiers="single-id")
        assert req.identifiers == ["single-id"]
        req = LiteratureRequest(identifiers=["a", "b"])
        assert req.identifiers == ["a", "b"]


class TestLiteratureItem:
    def test_construction(self):
        item = LiteratureItem(source="crossref", title="Test Paper")
        assert item.source == "crossref"
        assert item.title == "Test Paper"
        assert item.authors == []
        assert item.identifiers == {}


class TestRouteInfo:
    def test_defaults(self):
        route = RouteInfo(prefer="auto")
        assert route.used is None
        assert route.fallback_used is False


class TestLiteratureResponse:
    def test_success_response(self):
        route = RouteInfo(prefer="auto", used="api", reason="api_provider:crossref")
        resp = LiteratureResponse(success=True, items=[], route=route)
        assert resp.success is True
        assert resp.warnings == []

    def test_model_dump(self):
        route = RouteInfo(prefer="auto")
        resp = LiteratureResponse(success=False, route=route)
        data = resp.model_dump()
        assert "success" in data
        assert "route" in data


class TestSourceTraceEntry:
    def test_construction(self):
        trace = SourceTraceEntry(
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


class TestGatewayResult:
    def test_defaults(self):
        result = GatewayResult(
            provider="crossref",
            success=True,
            items=[],
            warnings=[],
        )
        assert result.downloads == []
        assert result.source_trace == []
