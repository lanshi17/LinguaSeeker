from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import scripts.e2e_extract_evidence as runner
from scripts.e2e_extract_evidence import run_extract_evidence
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceChain,
    DualEvidenceExtractionResult,
    EvidenceExtractionResult,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    QualityReport,
    SourceLocation,
    SourcePrecision,
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
                group_id="gene=GLA|variant=__missing__",
                source=SourceLocation(
                    span_id=f"{track.value}-p1",
                    page=1,
                    start_offset=0,
                    end_offset=len(value),
                    context_type="text",
                    context_ref="fixture",
                    text_snippet=value,
                    block_index=0,
                    source_precision=SourcePrecision.CORRECTED,
                ),
                raw_source=SourceLocation(
                    span_id=f"{track.value}-p1",
                    page=1,
                    start_offset=0,
                    end_offset=len(value),
                    context_type="text",
                    context_ref="fixture",
                    text_snippet=value,
                    block_index=1,
                ),
                confidence=0.95,
                assigned_acmg_codes=["PP4"],
                assigned_clingen_modules=["phenotype_consistency"],
            ),
            EvidenceItem(
                field_id="D.allele_frequency",
                category="D",
                field_name="Allele frequency",
                status=EvidenceStatus.NOT_FOUND,
                value=None,
                confidence=0.0,
                group_id="gene=GLA|variant=__missing__",
                requires_external_completion=True,
                external_completion_note="Population frequency must be completed externally.",
            )
        ],
        evidence_chains=[
            EvidenceChain(
                chain_id="gene=GLA|variant=__missing__",
                chain_level="singleton",
                case_ids=["case-1"],
                special_evidence_ids=["special-0"],
            )
        ],
        quality_report=QualityReport(
            passed=True,
            scorable=False,
            found_count=1,
            score_gate_passed=False,
            human_review_required=True,
            human_review_reasons=["No grounded evidence chain was produced"],
            human_review_by_category={"workflow": ["No grounded evidence chain was produced"]},
        ),
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
    assert summary_data["original"]["not_found_count"] == 0
    assert summary_data["original"]["ocr_gap_count"] == 0
    assert summary_data["original"]["score_gate_passed"] is False
    assert summary_data["original"]["human_review_required"] is True
    assert summary_data["original"]["group_count"] == 1
    assert summary_data["original"]["chain_levels"] == {"singleton": 1}
    assert summary_data["original"]["case_ids"] == ["case-1"]
    assert summary_data["original"]["special_evidence_ids"] == ["special-0"]
    assert summary_data["original"]["grounded_source_count"] == 1
    assert summary_data["original"]["raw_source_count"] == 1
    assert summary_data["original"]["block_grounded_source_count"] == 1
    assert summary_data["original"]["source_precision_counts"] == {"corrected": 1}
    assert summary_data["original"]["external_completion_required_count"] == 1
    assert summary_data["original"]["assigned_acmg_codes"] == ["PP4"]
    assert summary_data["original"]["assigned_clingen_modules"] == ["phenotype_consistency"]
    assert summary_data["original"]["human_review_by_category"]["workflow"] == [
        "No grounded evidence chain was produced",
    ]


def test_ensure_evidence_env_falls_back_to_loaded_llm_config(monkeypatch: pytest.MonkeyPatch):
    class FakeLlm:
        api_key = "fast-key"
        base_url = "http://localhost:8001/v1"
        model = "fast-model"

    class FakeReasoning:
        api_key = "reason-key"
        base_url = "http://localhost:8002/v1"
        model = "reason-model"

    class FakeConfig:
        llm = FakeLlm()
        reasoning = FakeReasoning()

    for name in (
        "EVIDENCE_EXTRACTION_API_KEY",
        "EVIDENCE_EXTRACTION_BASE_URL",
        "EVIDENCE_EXTRACTION_FAST_MODEL",
        "EVIDENCE_EXTRACTION_STANDARD_MODEL",
        "EVIDENCE_EXTRACTION_STRONG_MODEL",
        "FAST_LLM_API_KEY",
        "FAST_LLM_BASE_URL",
        "FAST_LLM_MODEL",
        "REASONING_LLM_API_KEY",
        "REASONING_LLM_BASE_URL",
        "REASONING_LLM_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(runner, "get_config", lambda: FakeConfig())

    runner._ensure_evidence_env_from_llm()

    assert os.environ["EVIDENCE_EXTRACTION_API_KEY"] == "fast-key"
    assert os.environ["EVIDENCE_EXTRACTION_BASE_URL"] == "http://localhost:8001/v1"
    assert os.environ["EVIDENCE_EXTRACTION_FAST_MODEL"] == "fast-model"
    assert os.environ["EVIDENCE_EXTRACTION_STANDARD_MODEL"] == "fast-model"
    assert os.environ["EVIDENCE_EXTRACTION_STRONG_MODEL"] == "reason-model"


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
