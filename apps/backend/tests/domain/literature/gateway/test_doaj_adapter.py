import pytest

from src.domain.literature.gateway.contracts import ApiGatewayRequest, ApiGatewayResult
from src.domain.literature.gateway.adapters.doaj_adapter import DoajAdapter


@pytest.mark.asyncio
async def test_doaj_adapter_routes_download_through_existing_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_call_doaj_download(
        query: str | None,
        limit: int,
        raw: bool,
        download_path: str,
        selected_index: int,
        selected_title: str | None,
        detail_link: str | None,
        api_params: dict[str, object] | None,
    ) -> ApiGatewayResult:
        assert query == "cardiovascular genetics"
        assert limit == 5
        assert raw is True
        assert download_path == "/tmp/doaj-downloads"
        assert selected_index == 1
        assert selected_title == "Chosen DOAJ paper"
        assert detail_link == "https://example.org/doaj-paper"
        assert api_params == {"institution": "tests"}
        return ApiGatewayResult(
            provider="doaj",
            success=True,
            items=[],
            downloads=[
                {
                    "pdf_url": "https://example.org/paper.pdf",
                    "file_path": "/tmp/doaj-downloads/doaj-paper.pdf",
                }
            ],
            warnings=["doaj-warning"],
            meta={"total": 1},
        )

    monkeypatch.setattr(
        "src.domain.literature.gateway.adapters.doaj_adapter.call_doaj_download",
        fake_call_doaj_download,
    )

    adapter = DoajAdapter()
    result = await adapter.execute(
        ApiGatewayRequest(
            provider="doaj",
            action="download",
            query="cardiovascular genetics",
            limit=5,
            raw=True,
            download_path="/tmp/doaj-downloads",
            selected_index=1,
            selected_title="Chosen DOAJ paper",
            detail_link="https://example.org/doaj-paper",
            params={"institution": "tests"},
        )
    )

    assert result.provider == "doaj"
    assert result.success is True
    assert result.downloads == [
        {
            "pdf_url": "https://example.org/paper.pdf",
            "file_path": "/tmp/doaj-downloads/doaj-paper.pdf",
        }
    ]
    assert result.warnings == ["doaj-warning"]
    assert result.meta == {"total": 1}
