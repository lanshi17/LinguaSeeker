import pytest

from src.domain.literature.gateway.api_gateway import (
    ApiGatewayRequest,
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
