from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import scripts.e2e_extract_evidence as runner
from scripts.e2e_extract_evidence import run_extract_evidence
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DualEvidenceExtractionResult,
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    Track,
)


class FakeEvidenceExtractionService:
    def __init__(self) -> None:
        self.document_ids: list[str] = []

    async def run_dual(self, documents):
        self.document_ids.append(documents.document_id)
        return DualEvidenceExtractionResult(
            document_id=documents.document_id,
            original_result=_result(documents.document_id, Track.ORIGINAL, "法布雷病"),
            translated_result=_result(documents.document_id, Track.TRANSLATED, "Fabry disease"),
        )


def _result(document_id: str, track: Track, value: str) -> EvidenceExtractionResult:
    return EvidenceExtractionResult(
        status=EvidenceExtractionStatus.COMPLETED,
        document_id=document_id,
        track=track,
        evidence_items=[
            EvidenceItem(
                field_id="A.disease_name",
                category="A",
                field_name="Disease name",
                status=EvidenceStatus.FOUND,
                value=value,
                source=SourceLocation(
                    span_id=f"{track.value}-p1",
                    page=1,
                    start_offset=0,
                    end_offset=len(value),
                    context_type="text",
                    context_ref="fixture",
                    text_snippet=value,
                ),
                confidence=0.95,
            )
        ],
    )


@pytest.mark.asyncio
async def test_run_extract_evidence_writes_dual_track_outputs(tmp_path: Path):
    input_dir = tmp_path / "input" / "法布雷病1例"
    _write_fixture(input_dir)
    output_dir = tmp_path / "extract_evidence"
    service = FakeEvidenceExtractionService()

    saved_dir = await run_extract_evidence(
        input_dir=input_dir,
        output_dir=output_dir,
        service=service,
        run_id="test-run",
    )

    assert saved_dir == output_dir / "法布雷病1例" / "test-run"
    assert service.document_ids == ["法布雷病1例"]

    result_data = json.loads((saved_dir / "result.json").read_text(encoding="utf-8"))
    summary_data = json.loads((saved_dir / "summary.json").read_text(encoding="utf-8"))
    original_data = json.loads((saved_dir / "original_result.json").read_text(encoding="utf-8"))
    translated_data = json.loads((saved_dir / "translated_result.json").read_text(encoding="utf-8"))

    assert result_data["document_id"] == "法布雷病1例"
    assert original_data["track"] == "original"
    assert translated_data["track"] == "translated"
    assert summary_data["original"]["found_count"] == 1
    assert summary_data["translated"]["found_count"] == 1


def test_ensure_evidence_env_falls_back_to_loaded_llm_config(monkeypatch: pytest.MonkeyPatch):
    class FakeLlm:
        api_key = "key"
        base_url = "http://localhost:8001/v1"
        model = "model"

    class FakeConfig:
        llm = FakeLlm()

    for name in (
        "EVIDENCE_EXTRACTION_API_KEY",
        "EVIDENCE_EXTRACTION_BASE_URL",
        "EVIDENCE_EXTRACTION_FAST_MODEL",
        "EVIDENCE_EXTRACTION_STANDARD_MODEL",
        "EVIDENCE_EXTRACTION_STRONG_MODEL",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(runner, "get_config", lambda: FakeConfig())

    runner._ensure_evidence_env_from_llm()

    assert os.environ["EVIDENCE_EXTRACTION_API_KEY"] == "key"
    assert os.environ["EVIDENCE_EXTRACTION_BASE_URL"] == "http://localhost:8001/v1"
    assert os.environ["EVIDENCE_EXTRACTION_STRONG_MODEL"] == "model"


def _write_fixture(input_dir: Path) -> None:
    input_dir.mkdir(parents=True)
    original = {
        "metadata": {"doc_id": "法布雷病1例", "source_language": "zh"},
        "blocks": [
            {"type": "text", "page_idx": 0, "text": "法布雷病1例"},
            {"type": "text", "page_idx": 1, "text": "患者男性。"},
        ],
    }
    translated = {
        "metadata": {"doc_id": "法布雷病1例", "source_language": "zh"},
        "blocks": [
            {"type": "text", "page_idx": 0, "text": "A case of Fabry disease"},
            {"type": "text", "page_idx": 1, "text": "The patient was male."},
        ],
    }
    (input_dir / "original.json").write_text(
        json.dumps(original, ensure_ascii=False),
        encoding="utf-8",
    )
    (input_dir / "translated.json").write_text(
        json.dumps(translated, ensure_ascii=False),
        encoding="utf-8",
    )
