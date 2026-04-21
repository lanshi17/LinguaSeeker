from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import json
import pytest

from src.services import task_manager as tasks_module


def _make_fake_recovery(result: Dict[str, Any]):
    def _fake_recovery(url: str) -> Dict[str, Any]:
        return result

    return _fake_recovery


def _make_fake_minio_client(metadata_sink: Dict[str, Any] | None = None) -> type:
    class _FakeMinioClient:
        @staticmethod
        def build_literature_object_key(file_hash: str, original_filename: str) -> str:
            return f"literature/{file_hash[:8]}/{original_filename}"

        async def ensure_buckets(self) -> None:
            return None

        async def upload_literature_upload(self, **kwargs: Any) -> Any:
            if metadata_sink is not None:
                metadata_sink["metadata"] = kwargs.get("metadata")
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
async def test_try_download_and_store_literature_pdf_persists_source_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "source_trace.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\nsource-trace")

    source_trace = [
        {
            "provider": "pmc",
            "attempt": 1,
            "success": True,
            "items_count": 0,
            "downloads_count": 1,
            "warnings": [],
            "error": None,
        }
    ]

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
            "raw": {"api": {"source_trace": source_trace}},
        }

    metadata_sink: Dict[str, Any] = {}
    monkeypatch.setattr(tasks_module, "literature_unified_workflow", fake_unified)
    monkeypatch.setattr(
        tasks_module,
        "MinIOClient",
        _make_fake_minio_client(metadata_sink),
    )

    result = await tasks_module._try_download_and_store_literature_pdf(
        document_id="doc-trace",
        source="pubmed",
        query="PMID:123456",
        identifiers=["123456"],
        selected_title="paper",
    )

    assert result["downloaded"] is True
    assert result["object_key"] == "literature/mock/object.pdf"
    assert result["provider"] == "pmc"
    assert result["size_bytes"] > 0
    assert result["source_trace"] == source_trace

    metadata = metadata_sink["metadata"]
    assert metadata["source_trace"] == json.dumps(source_trace, ensure_ascii=False)


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


@pytest.mark.asyncio
async def test_try_download_and_store_literature_pdf_persists_web_source_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "web_source_trace.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\nweb-source-trace")

    source_trace = [
        {
            "provider": "cyberleninka",
            "attempt": 1,
            "success": True,
            "items_count": 0,
            "downloads_count": 1,
            "warnings": [],
            "error": None,
        }
    ]

    async def fake_unified(payload: Dict[str, Any]) -> Dict[str, Any]:
        assert payload["raw"] is True
        return {
            "success": True,
            "downloads": [{"file_path": str(pdf_path)}],
            "warnings": [],
            "route": {
                "used": "web",
                "web_provider": "cyberleninka",
                "reason": "web_provider:cyberleninka",
            },
            "raw": {"web": {"source_trace": source_trace}},
        }

    metadata_sink: Dict[str, Any] = {}
    monkeypatch.setattr(tasks_module, "literature_unified_workflow", fake_unified)
    monkeypatch.setattr(
        tasks_module,
        "MinIOClient",
        _make_fake_minio_client(metadata_sink),
    )

    result = await tasks_module._try_download_and_store_literature_pdf(
        document_id="doc-web-trace",
        source="web",
        query="https://cyberleninka.ru/article/n/test",
        identifiers=["https://cyberleninka.ru/article/n/test"],
        selected_title="paper",
    )

    assert result["downloaded"] is True
    assert result["provider"] == "cyberleninka"
    assert result["source_trace"] == source_trace

    metadata = metadata_sink["metadata"]
    assert metadata["source_trace"] == json.dumps(source_trace, ensure_ascii=False)


@pytest.mark.asyncio
async def test_try_download_invalid_pdf_signature_uses_html_fallback_for_known_chinese_provider_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    txt_path = tmp_path / "ANK1.pdf"
    txt_path.write_text("not-a-pdf", encoding="utf-8")

    async def fake_unified(_: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": True,
            "downloads": [{"file_path": str(txt_path)}],
            "warnings": [],
            "route": {"used": "web", "web_provider": "hans_publishers"},
            "raw": {"web": {"source_trace": []}},
        }

    recovery_called: list[str] = []

    def fake_recovery(url: str) -> Dict[str, Any]:
        recovery_called.append(url)
        return {
            "success": True,
            "normalized_markdown": "# 标题\n\n正文",
            "provider": "chinese_fulltext_recovery",
            "warnings": ["fallback:html_body"],
        }

    monkeypatch.setattr(tasks_module, "literature_unified_workflow", fake_unified)
    monkeypatch.setattr(tasks_module, "run_chinese_fulltext_recovery", fake_recovery)

    result = await tasks_module._try_download_and_store_literature_pdf(
        document_id="doc-hans",
        source="web",
        query="https://image.hanspub.org/Html/77-1577845_75032.htm",
        identifiers=["https://image.hanspub.org/Html/77-1577845_75032.htm"],
        detail_link="https://image.hanspub.org/Html/77-1577845_75032.htm",
    )

    assert result["downloaded"] is False
    assert result["normalized_markdown"] == "# 标题\n\n正文"
    assert result["provider"] == "chinese_fulltext_recovery"
    assert recovery_called == ["https://image.hanspub.org/Html/77-1577845_75032.htm"]


@pytest.mark.asyncio
async def test_try_download_returns_normalized_markdown_when_chinese_pdf_fallbacks_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_unified(_: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": False,
            "downloads": [],
            "warnings": [],
            "route": {"used": "web", "web_provider": "pubscholar"},
            "raw": {"web": {"source_trace": []}},
        }

    recovery_called: list[str] = []

    def fake_recovery(url: str) -> Dict[str, Any]:
        recovery_called.append(url)
        return {
            "success": True,
            "normalized_markdown": "# 标题\n\n正文",
            "provider": "chinese_fulltext_recovery",
            "warnings": ["fallback:html_body"],
        }

    monkeypatch.setattr(tasks_module, "literature_unified_workflow", fake_unified)
    monkeypatch.setattr(tasks_module, "run_chinese_fulltext_recovery", fake_recovery)

    result = await tasks_module._try_download_and_store_literature_pdf(
        document_id="doc-zh",
        source="web",
        query="DNAJB2复合杂合突变相关腓骨肌萎缩症2型家系病例1例",
        identifiers=["https://example.cn/paper"],
        detail_link="https://example.cn/paper",
        selected_title="DNAJB2复合杂合突变相关腓骨肌萎缩症2型家系病例1例",
    )

    assert result["downloaded"] is False
    assert result["normalized_markdown"] == "# 标题\n\n正文"
    assert result["provider"] == "chinese_fulltext_recovery"
    assert recovery_called == ["https://example.cn/paper"]


@pytest.mark.asyncio
async def test_try_download_does_not_trigger_recovery_for_non_chinese_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_unified(_: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": False,
            "downloads": [],
            "warnings": [],
            "route": {"used": "web", "web_provider": "pubscholar"},
            "raw": {"web": {"source_trace": []}},
        }

    recovery_called: list[str] = []

    def fake_recovery(url: str) -> Dict[str, Any]:
        recovery_called.append(url)
        return {
            "success": True,
            "normalized_markdown": "# Title\n\nBody",
            "provider": "chinese_fulltext_recovery",
            "warnings": ["fallback:html_body"],
        }

    monkeypatch.setattr(tasks_module, "literature_unified_workflow", fake_unified)
    monkeypatch.setattr(tasks_module, "run_chinese_fulltext_recovery", fake_recovery)

    result = await tasks_module._try_download_and_store_literature_pdf(
        document_id="doc-en",
        source="web",
        query="Fabry case report",
        identifiers=["https://example.org/paper"],
        detail_link="https://example.org/paper",
        selected_title="Fabry case report",
    )

    assert result["downloaded"] is False
    assert result["reason"] == "pdf_not_found"
    assert recovery_called == []
