from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from src.services import task_manager as tasks_module


def _make_fake_minio_client() -> type:
    class _FakeMinioClient:
        @staticmethod
        def build_literature_object_key(file_hash: str, original_filename: str) -> str:
            return f"literature/{file_hash[:8]}/{original_filename}"

        async def ensure_buckets(self) -> None:
            return None

        async def upload_literature_upload(self, **_: Any) -> Any:
            return SimpleNamespace(
                bucket=SimpleNamespace(value="literature-uploads"),
                object_key="literature/mock/object.pdf",
                content_type="application/pdf",
            )

    return _FakeMinioClient


@pytest.mark.asyncio
async def test_try_download_and_store_literature_pdf_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\nmock")

    async def fake_unified(_: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": True,
            "downloads": [{"file_path": str(pdf_path)}],
            "warnings": [],
            "route": {
                "used": "api",
                "api_provider": "pmc",
                "reason": "api_provider:pmc",
            },
        }

    monkeypatch.setattr(tasks_module, "literature_unified_workflow", fake_unified)
    monkeypatch.setattr(tasks_module, "MinIOClient", _make_fake_minio_client())

    result = await tasks_module._try_download_and_store_literature_pdf(
        document_id="doc-1",
        source="pubmed",
        query="PMID:123456",
        identifiers=["123456"],
        selected_title="paper",
    )

    assert result["downloaded"] is True
    assert result["object_key"] == "literature/mock/object.pdf"
    assert result["provider"] == "pmc"
    assert result["size_bytes"] > 0


@pytest.mark.asyncio
async def test_try_download_and_store_literature_pdf_invalid_signature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    txt_path = tmp_path / "not_pdf.pdf"
    txt_path.write_bytes(b"not-a-pdf")

    async def fake_unified(_: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": True,
            "downloads": [{"file_path": str(txt_path)}],
            "warnings": [],
            "route": {"used": "web", "web_provider": "hans_publishers"},
        }

    monkeypatch.setattr(tasks_module, "literature_unified_workflow", fake_unified)
    monkeypatch.setattr(tasks_module, "MinIOClient", _make_fake_minio_client())

    result = await tasks_module._try_download_and_store_literature_pdf(
        document_id="doc-2",
        source="web",
        query="test",
        identifiers=["https://example.org/paper"],
    )

    assert result["downloaded"] is False
    assert result["reason"] == "invalid_pdf_signature"
