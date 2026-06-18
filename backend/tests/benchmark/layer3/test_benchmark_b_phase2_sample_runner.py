"""Tests for the Benchmark B Phase 2 sample runner."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
import pytest

from benchmark.runners.benchmark_b_phase2_sample import (
    BenchmarkBPhase2SampleConfig,
    benchmark_b_phase2_sample_report_to_payload,
    build_pipeline_payload,
    load_sample_sources,
    run_benchmark_b_phase2_sample,
)
from benchmark.core import MAX_POLL_ATTEMPTS, POLL_INTERVAL_S


def _write_queue(path: Path, pdf_root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    items = []
    for language in ("ja", "ko", "zh"):
        pdf_path = pdf_root / language / "case_report" / "clingen_000.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(f"%PDF-1.4\n{language}\n".encode("utf-8"))
        items.append(
            {
                "queue_id": f"clingen_000:{language}",
                "entry_id": "clingen_000",
                "article_language": language,
                "target_gene": "AARS1",
                "target_disease": "Charcot-Marie-Tooth disease axonal type 2N",
                "source_id": f"local_pdf:{language}/case_report/clingen_000.pdf",
                "source_database": "local_pdf",
                "source_url": None,
                "local_path": f"{language}/case_report/clingen_000.pdf",
                "source_pdf_path": str(pdf_path),
                "sha256": f"sha-{language}",
                "annotation_status": "unlabeled",
                "access_status": "local_copy",
                "benchmark_layer": "multilingual_pressure_test",
                "literature_type": "case_report",
            }
        )
    path.write_text(json.dumps({"items": items}), encoding="utf-8")


def test_load_sample_sources_limits_manifest_order(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.json"
    _write_queue(queue_path, tmp_path / "pdfs")

    sources = load_sample_sources(BenchmarkBPhase2SampleConfig(queue_path=queue_path, limit=2))

    assert [source.queue_id for source in sources] == ["clingen_000:ja", "clingen_000:ko"]
    assert sources[0].source_pdf_path.exists()
    assert sources[0].target_gene == "AARS1"


def test_load_sample_sources_skips_existing_queue_ids_before_applying_limit(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.json"
    _write_queue(queue_path, tmp_path / "pdfs")

    sources = load_sample_sources(
        BenchmarkBPhase2SampleConfig(
            queue_path=queue_path,
            limit=2,
            skip_queue_ids=("clingen_000:ja",),
        )
    )

    assert [source.queue_id for source in sources] == ["clingen_000:ko", "clingen_000:zh"]


def test_build_pipeline_payload_uses_language_scoped_filename_and_target(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.json"
    _write_queue(queue_path, tmp_path / "pdfs")
    source = load_sample_sources(BenchmarkBPhase2SampleConfig(queue_path=queue_path, limit=1))[0]

    payload = build_pipeline_payload(source)

    assert payload["filename"] == "clingen_000_ja.pdf"
    assert base64.b64decode(payload["content_base64"]).startswith(b"%PDF-1.4")
    assert payload["target"] == {
        "gene_symbol": "AARS1",
        "disease_name": "Charcot-Marie-Tooth disease axonal type 2N",
        "clingen_entry_id": "clingen_000",
    }


def test_sample_runner_defaults_match_layer3_polling_window() -> None:
    config = BenchmarkBPhase2SampleConfig()

    assert config.poll_interval_s == POLL_INTERVAL_S
    assert config.max_poll_attempts == MAX_POLL_ATTEMPTS


@pytest.mark.asyncio
async def test_run_benchmark_b_phase2_sample_polls_until_phase2_completed(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.json"
    pipeline_root = tmp_path / "pipeline"
    artifact_path = pipeline_root / "run-1" / "phase_2" / "extraction_result.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("{}", encoding="utf-8")
    _write_queue(queue_path, tmp_path / "pdfs")
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        if request.method == "POST":
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["filename"] == "clingen_000_ja.pdf"
            return httpx.Response(
                202,
                json={
                    "processing_run_id": "run-1",
                    "source_document_id": "doc-1",
                    "status": "accepted",
                    "status_url": "/api/v1/pipeline/runs/run-1/status",
                },
            )
        return httpx.Response(
            200,
            json={
                "processing_run_id": "run-1",
                "source_document_id": "doc-1",
                "pipeline_status": "running",
                "current_phase": "phase_2",
                "phases": {"phase_2": {"status": "completed"}},
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://pipeline.test",
    ) as client:
        report = await run_benchmark_b_phase2_sample(
            BenchmarkBPhase2SampleConfig(
                queue_path=queue_path,
                pipeline_root=pipeline_root,
                base_url="https://pipeline.test",
                limit=1,
                poll_interval_s=0,
            ),
            client=client,
        )

    payload = benchmark_b_phase2_sample_report_to_payload(report)
    assert report.phase2_completed_count == 1
    assert payload["rows"][0]["status"] == "phase2_completed"
    assert payload["rows"][0]["artifact_exists"] is True
    assert [method for method, _url in calls] == ["POST", "GET"]


@pytest.mark.asyncio
async def test_run_benchmark_b_phase2_sample_accepts_artifact_when_status_lags(tmp_path: Path) -> None:
    queue_path = tmp_path / "queue.json"
    pipeline_root = tmp_path / "pipeline"
    artifact_path = pipeline_root / "run-1" / "phase_2" / "extraction_result.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("{}", encoding="utf-8")
    _write_queue(queue_path, tmp_path / "pdfs")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(
                202,
                json={
                    "processing_run_id": "run-1",
                    "source_document_id": "doc-1",
                    "status": "accepted",
                    "status_url": "/api/v1/pipeline/runs/run-1/status",
                },
            )
        return httpx.Response(
            200,
            json={
                "processing_run_id": "run-1",
                "source_document_id": "doc-1",
                "pipeline_status": "running",
                "current_phase": None,
                "phases": {"phase_2": {"status": "pending"}},
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://pipeline.test",
    ) as client:
        report = await run_benchmark_b_phase2_sample(
            BenchmarkBPhase2SampleConfig(
                queue_path=queue_path,
                pipeline_root=pipeline_root,
                base_url="https://pipeline.test",
                limit=1,
                poll_interval_s=0,
            ),
            client=client,
        )

    payload = benchmark_b_phase2_sample_report_to_payload(report)
    assert report.phase2_completed_count == 1
    assert payload["rows"][0]["status"] == "phase2_completed"
    assert payload["rows"][0]["phase2_status"] == "completed"
    assert payload["rows"][0]["message"] == "Phase 2 artifact materialized; status endpoint may lag."
