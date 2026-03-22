from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from src.domain.mineru.component import MinerUComponent
from src.domain.models import BatchStatusData, FileExtractResult, MinerURequest


def test_mineru_pipeline_downloads_from_full_zip_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mineru = MinerUComponent(token="test-token")
    mineru.download_dir = str(tmp_path / "mineru_downloads")

    final_status = BatchStatusData(
        batch_id="batch-1",
        extract_result=[
            FileExtractResult(
                file_name="paper.pdf",
                state="done",
                err_msg="",
                full_zip_url="https://example.com/mineru-result.zip",
            )
        ],
        download_url=None,
    )

    monkeypatch.setattr(
        mineru,
        "upload_local_files_batch",
        lambda _token, _file_paths, common_params=None: (  # noqa: ARG005
            True,
            "batch-1",
            None,
        ),
    )
    monkeypatch.setattr(
        mineru,
        "query_batch_status",
        lambda token, batch_id: (True, final_status, None),  # noqa: ARG005
    )
    monkeypatch.setattr(
        mineru,
        "poll_batch_status_until_done",
        lambda token, batch_id: final_status,  # noqa: ARG005
    )

    download_calls: list[tuple[str, str, int]] = []

    def _fake_download(url: str, destination: str, timeout: int = 300) -> str:
        download_calls.append((url, destination, timeout))
        zip_path = Path(destination)
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w") as zip_file:
            zip_file.writestr("full.md", "parsed markdown")
        return destination

    from src.domain.mineru import component as mineru_component

    monkeypatch.setattr(mineru_component.file_utils, "download_file", _fake_download)

    response = mineru.minerU_pipeline(MinerURequest(file_paths=["paper.pdf"]))

    assert response is not None
    assert response.status == "done"
    assert response.folder_path is not None
    assert Path(response.folder_path, "full.md").exists()
    assert download_calls[0][0] == "https://example.com/mineru-result.zip"
