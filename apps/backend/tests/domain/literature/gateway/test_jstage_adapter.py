import pytest

from src.domain.literature.gateway.contracts import ApiGatewayRequest, ApiGatewayResult
from src.domain.literature.gateway.adapters.jstage_adapter import JStageAdapter


@pytest.mark.asyncio
async def test_jstage_adapter_routes_download_through_existing_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_jstage_download(
        query,
        limit,
        raw,
        download_path,
        selected_index,
        selected_title,
        detail_link,
        api_params,
    ):  # type: ignore[no-untyped-def]
        assert query == "lung cancer"
        assert limit == 5
        assert raw is True
        assert download_path == "/tmp/jstage-downloads"
        assert selected_index == 1
        assert selected_title == "Chosen JStage paper"
        assert detail_link == "https://www.jstage.jst.go.jp/article/test/_article"
        assert api_params == {"institution": "tests"}
        return ApiGatewayResult(
            provider="jstage",
            success=True,
            items=[],
            downloads=[
                {
                    "pdf_url": "https://www.jstage.jst.go.jp/article/test/_pdf",
                    "file_path": "/tmp/jstage-downloads/jstage-paper.pdf",
                }
            ],
            warnings=["jstage-warning"],
            meta={"total": 1},
        )

    monkeypatch.setattr(
        "src.domain.literature.gateway.adapters.jstage_adapter.call_jstage_download",
        fake_jstage_download,
    )

    adapter = JStageAdapter()
    result = await adapter.execute(
        ApiGatewayRequest(
            provider="jstage",
            action="download",
            query="lung cancer",
            limit=5,
            raw=True,
            download_path="/tmp/jstage-downloads",
            selected_index=1,
            selected_title="Chosen JStage paper",
            detail_link="https://www.jstage.jst.go.jp/article/test/_article",
            params={"institution": "tests"},
        )
    )

    assert result.provider == "jstage"
    assert result.success is True
    assert result.downloads == [
        {
            "pdf_url": "https://www.jstage.jst.go.jp/article/test/_pdf",
            "file_path": "/tmp/jstage-downloads/jstage-paper.pdf",
        }
    ]
    assert result.warnings == ["jstage-warning"]
    assert result.meta == {"total": 1}
