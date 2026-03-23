import pytest

from src.domain.literature.gateway.api_gateway import (
    ApiGatewayRequest,
    ApiGatewayResult,
    call_api_gateway,
)


@pytest.mark.asyncio
async def test_jstage_download_supported_with_detail_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_download(candidates, download_path, filename_stem):  # type: ignore[no-untyped-def]
        assert candidates
        assert "jstage.jst.go.jp" in candidates[0]
        assert download_path == "/tmp/jstage-downloads"
        return (
            "/tmp/jstage-downloads/jstage-paper.pdf",
            "https://www.jstage.jst.go.jp/article/test/_pdf",
            [],
        )

    monkeypatch.setattr(
        "src.domain.literature.gateway.api_gateway._download_pdf_from_candidates",
        fake_download,
    )

    result = await call_api_gateway(
        ApiGatewayRequest(
            provider="jstage",
            action="download",
            detail_link="https://www.jstage.jst.go.jp/article/test/_article",
            download_path="/tmp/jstage-downloads",
        )
    )

    assert result.success is True
    assert len(result.downloads) == 1
    assert result.downloads[0]["file_path"] == "/tmp/jstage-downloads/jstage-paper.pdf"


@pytest.mark.asyncio
async def test_doaj_download_supported_from_search_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_doaj_workflow(payload):  # type: ignore[no-untyped-def]
        assert payload["action"] == "search"
        return {
            "success": True,
            "items": [
                {
                    "bibjson": {
                        "title": "DOAJ Example Paper",
                        "link": [
                            {
                                "type": "fulltext",
                                "content_type": "application/pdf",
                                "url": "https://example.org/paper.pdf",
                            }
                        ],
                    }
                }
            ],
            "warnings": [],
            "meta": {"total": 1},
        }

    async def fake_download(candidates, download_path, filename_stem):  # type: ignore[no-untyped-def]
        assert candidates[0] == "https://example.org/paper.pdf"
        assert download_path == "/tmp/doaj-downloads"
        assert filename_stem == "DOAJ Example Paper"
        return (
            "/tmp/doaj-downloads/doaj-paper.pdf",
            "https://example.org/paper.pdf",
            [],
        )

    monkeypatch.setattr(
        "src.domain.literature.gateway.api_gateway.doaj_http_workflow",
        fake_doaj_workflow,
    )
    monkeypatch.setattr(
        "src.domain.literature.gateway.api_gateway._download_pdf_from_candidates",
        fake_download,
    )

    result = await call_api_gateway(
        ApiGatewayRequest(
            provider="doaj",
            action="download",
            query="cardiovascular genetics",
            limit=5,
            download_path="/tmp/doaj-downloads",
        )
    )

    assert result.success is True
    assert len(result.downloads) == 1
    assert result.downloads[0]["pdf_url"] == "https://example.org/paper.pdf"


@pytest.mark.asyncio
async def test_crossref_download_still_unsupported() -> None:
    result = await call_api_gateway(
        ApiGatewayRequest(
            provider="crossref",
            action="download",
            query="ldlr",
        )
    )
    assert result.success is False
    assert "crossref_download_unsupported" in result.warnings


@pytest.mark.asyncio
async def test_pmc_search_with_pmcid_delegates_to_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_metadata(pmcids, raw, api_params):  # type: ignore[no-untyped-def]
        assert pmcids == ["PMC7777777"]
        assert raw is True
        assert api_params == {"source": "freeze-test"}
        return ApiGatewayResult(
            provider="pmc",
            success=True,
            items=[{"pmcid": "PMC7777777", "title": "PMC direct metadata"}],
            warnings=[],
        )

    monkeypatch.setattr(
        "src.domain.literature.gateway.api_gateway.call_pmc_metadata",
        fake_metadata,
    )

    result = await call_api_gateway(
        ApiGatewayRequest(
            provider="pmc",
            action="search",
            identifiers={"pmcid": "PMC7777777"},
            raw=True,
            params={"source": "freeze-test"},
        )
    )

    assert result.provider == "pmc"
    assert result.success is True
    assert result.items == [{"pmcid": "PMC7777777", "title": "PMC direct metadata"}]
    assert result.warnings == []


@pytest.mark.asyncio
async def test_pmc_search_with_pmid_delegates_to_pmid_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_for_pmid(pmid, limit, raw, api_params):  # type: ignore[no-untyped-def]
        assert pmid == "12345678"
        assert limit == 7
        assert raw is False
        assert api_params == {"source": "pmid-freeze"}
        return ApiGatewayResult(
            provider="pmc",
            success=True,
            items=[{"pmcid": "PMC1234567", "title": "PMID metadata"}],
            warnings=["pmc_search_warning"],
        )

    monkeypatch.setattr(
        "src.domain.literature.gateway.api_gateway.call_pmc_for_pmid",
        fake_for_pmid,
    )

    result = await call_api_gateway(
        ApiGatewayRequest(
            provider="pmc",
            action="search",
            identifiers={"pmid": "12345678"},
            limit=7,
            params={"source": "pmid-freeze"},
        )
    )

    assert result.provider == "pmc"
    assert result.success is True
    assert result.items == [{"pmcid": "PMC1234567", "title": "PMID metadata"}]
    assert result.warnings == ["pmc_search_warning"]


@pytest.mark.asyncio
async def test_default_search_falls_back_to_crossref_with_identifier_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_crossref(query, limit, raw, filter_expr, api_params):  # type: ignore[no-untyped-def]
        assert query == "familial hypercholesterolemia"
        assert limit == 9
        assert raw is True
        assert filter_expr == "doi:10.1000/xyz-123"
        assert api_params == {"source": "crossref-freeze"}
        return ApiGatewayResult(
            provider="crossref",
            success=True,
            items=[{"doi": "10.1000/xyz-123", "title": "Crossref fallback"}],
            warnings=[],
        )

    monkeypatch.setattr(
        "src.domain.literature.gateway.api_gateway.call_crossref",
        fake_crossref,
    )

    result = await call_api_gateway(
        ApiGatewayRequest(
            provider="crossref",
            action="search",
            query="familial hypercholesterolemia",
            identifiers={"doi": "10.1000/xyz-123", "issn": "1234-5678"},
            limit=9,
            raw=True,
            params={"source": "crossref-freeze"},
        )
    )

    assert result.provider == "crossref"
    assert result.success is True
    assert result.items == [{"doi": "10.1000/xyz-123", "title": "Crossref fallback"}]
    assert result.warnings == []
