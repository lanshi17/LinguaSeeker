import os
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.service import tasks as tasks_module
from src.domain.models import EvidenceOutput, MinerUResponse, PipelineFiles, PipelineResult


def _make_mineru_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "mineru_output"
    folder.mkdir()
    (folder / "full.md").write_text("hello world", encoding="utf-8")
    image_path = folder / "image1.jpg"
    image_path.write_bytes(b"fake")
    return folder


def _make_evidence_output(ps3_evidence: Dict[str, Any] | None = None) -> EvidenceOutput:
    return EvidenceOutput(
        ps3_evidence=ps3_evidence or {},
        arbitration_score=0.0,
        image_descriptions=[],
        final_evidence_strength="",
        status="success",
        origin_format_md="",
        en_format_md="",
        extracted_fields={},
        field_confidence_scores={},
        overall_confidence=0.0,
        evidence_classification="",
        acmg_evidence_levels=[],
    )


@pytest.fixture()
def mineru_folder(tmp_path: Path) -> Path:
    return _make_mineru_folder(tmp_path)


def test_disable_proxies() -> None:
    os.environ["http_proxy"] = "1"
    os.environ["https_proxy"] = "1"
    os.environ["all_proxy"] = "1"
    tasks_module._disable_proxies()
    assert "http_proxy" not in os.environ
    assert "https_proxy" not in os.environ
    assert "all_proxy" not in os.environ


def test_collect_mineru_assets(mineru_folder: Path) -> None:
    content, images = tasks_module._collect_mineru_assets(str(mineru_folder))
    assert "hello world" in content
    assert any(Path(p).name == "image1.jpg" for p in images)


@pytest.mark.asyncio
async def test_init_knowledge_base_if_needed_skips_when_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_check(_: str) -> bool:
        return True

    monkeypatch.setattr(tasks_module._qdrant_manager, "check_collection_exists", fake_check)
    called: Dict[str, Any] = {"init": False}

    async def fake_init(_: str) -> None:
        called["init"] = True

    monkeypatch.setattr(tasks_module, "initialize_knowledge_base", fake_init)
    result = await tasks_module.init_knowledge_base_if_needed()
    assert result is True
    assert called["init"] is False


@pytest.mark.asyncio
async def test_init_knowledge_base_if_needed_runs_init(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_check(_: str) -> bool:
        return False

    monkeypatch.setattr(tasks_module._qdrant_manager, "check_collection_exists", fake_check)
    called: Dict[str, Any] = {"init": False}

    async def fake_init(_: str) -> None:
        called["init"] = True

    monkeypatch.setattr(tasks_module, "initialize_knowledge_base", fake_init)
    result = await tasks_module.init_knowledge_base_if_needed()
    assert result is True
    assert called["init"] is True


@pytest.mark.asyncio
async def test_run_fastapi_pipeline_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mineru_folder: Path) -> None:

    async def fake_init() -> bool:
        return True

    monkeypatch.setattr(tasks_module, "init_knowledge_base_if_needed", fake_init)

    class FakeMinerU:
        def minerU_pipeline(self, _: Any) -> MinerUResponse:
            return MinerUResponse(
                task_id="t1",
                status="done",
                message="ok",
                folder_path=str(mineru_folder),
            )

    class FakeAgent:
        def process_medical_evidence(self, markdown_content: str, image_paths: List[str]) -> EvidenceOutput:
            return _make_evidence_output()

    monkeypatch.setattr(tasks_module, "_mineru", FakeMinerU())
    monkeypatch.setattr(tasks_module, "_agents", FakeAgent())
    monkeypatch.setattr(
        tasks_module.file_utils,
        "cleanup_old_temp_folders",
        lambda *_, **__: None,
    )

    result = await tasks_module.run_fastapi_pipeline(["file.pdf"], output_root=tmp_path)
    assert result.output_dir
    assert result.mineru_folder
    assert result.files
    assert result.evidence


@pytest.mark.asyncio
async def test_run_fastapi_pipeline_empty_paths() -> None:
    with pytest.raises(tasks_module.exc.ValidationException):
        await tasks_module.run_fastapi_pipeline([])


def test_process_pdf_task(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(_: List[str], output_root: Path | None = None) -> PipelineResult:
        return PipelineResult(
            document_id="doc-1",
            output_dir="/tmp/out",
            mineru_folder="/tmp/mineru",
            files=PipelineFiles(
                origin_md_path="/tmp/orig.md",
                en_md_path="/tmp/en.md",
                image_desc_path="/tmp/image_desc.txt",
                ps3_evidence_path="/tmp/ps3.json",
                image_dir="/tmp/images",
                origin_md_url="",
                en_md_url="",
                image_desc_url="",
                ps3_evidence_url="",
                image_urls=[],
            ),
            evidence=_make_evidence_output(ps3_evidence={"ok": True}),
        )

    monkeypatch.setattr(tasks_module, "run_fastapi_pipeline", fake_run)
    result = tasks_module.process_pdf_task(["file.pdf"])
    assert result["document_id"] == "doc-1"
