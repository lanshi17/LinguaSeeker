"""Tests for ClinGen layer-3 value matching."""
from __future__ import annotations

import asyncio

import pytest

from benchmark.layer3.evaluate import (
    compare_evidence,
    evaluate_one,
    fuzzy_match_value,
    preflight_database_connection,
    submit_and_poll,
)


def test_fuzzy_match_value_treats_dash_variants_as_equivalent() -> None:
    assert fuzzy_match_value(
        "Charcot-Marie-Tooth disease axonal type 2N",
        "Charcot–Marie–Tooth disease axonal type 2N",
    )


def test_fuzzy_match_value_normalizes_curly_quotes_and_spacing() -> None:
    assert fuzzy_match_value("AARS2-related disease", "AARS2‑related  disease")


def test_fuzzy_match_value_normalizes_cjk_fullwidth_hyphen() -> None:
    assert fuzzy_match_value("AARS2-related disease", "AARS2－related disease")


def test_compare_evidence_counts_extra_found_candidate_as_over_extraction() -> None:
    expected = [{"field_id": "A.gene_symbol", "value": "AARS2"}]
    extracted = [
        {"field_id": "A.gene_symbol", "status": "found", "value": "AARS2", "confidence": 0.9},
        {"field_id": "A.gene_symbol", "status": "found", "value": "BRCA1", "confidence": 0.6},
    ]

    matches = compare_evidence(expected, extracted)

    assert matches[0].matched
    assert matches[0].match_type == "exact"
    assert matches[0].extra_found_values == ["BRCA1"]


def test_compare_evidence_deduplicates_extra_found_values() -> None:
    expected = [{"field_id": "A.gene_symbol", "value": "AARS2"}]
    extracted = [
        {"field_id": "A.gene_symbol", "status": "found", "value": "AARS2", "confidence": 0.9},
        {"field_id": "A.gene_symbol", "status": "found", "value": "BRCA1", "confidence": 0.6},
        {"field_id": "A.gene_symbol", "status": "found", "value": "BRCA1", "confidence": 0.5},
    ]

    matches = compare_evidence(expected, extracted)

    assert matches[0].extra_found_values == ["BRCA1"]


def test_compare_evidence_preserves_source_span_for_matched_candidate() -> None:
    expected = [{"field_id": "A.gene_symbol", "value": "AARS2"}]
    source_span = {"text_snippet": "AARS2 variant evidence", "start_offset": 10, "end_offset": 31}
    extracted = [
        {
            "field_id": "A.gene_symbol",
            "status": "found",
            "value": "AARS2",
            "confidence": 0.9,
            "source_span": source_span,
        }
    ]

    matches = compare_evidence(expected, extracted)

    assert matches[0].matched
    assert matches[0].source_span == source_span


def test_compare_evidence_preserves_contextual_score_components() -> None:
    expected = [{"field_id": "A.gene_symbol", "value": "AARS2"}]
    extracted = [
        {
            "field_id": "A.gene_symbol",
            "status": "found",
            "value": "AARS2",
            "confidence": 0.9,
            "best_score": 0.91,
            "source_score": 1.0,
            "confidence_score": 0.9,
            "agreement_score": 0.0,
            "status_score": 1.0,
            "verifier_support_score": 0.8,
            "target_specificity_score": 1.0,
            "contradiction_penalty": 0.0,
            "accepted_track": "original",
            "normalized_value": "aars2",
        }
    ]

    matches = compare_evidence(expected, extracted)

    assert matches[0].matched
    assert matches[0].best_score == 0.91
    assert matches[0].source_score == 1.0
    assert matches[0].confidence_score == 0.9
    assert matches[0].agreement_score == 0.0
    assert matches[0].status_score == 1.0
    assert matches[0].verifier_support_score == 0.8
    assert matches[0].target_specificity_score == 1.0
    assert matches[0].contradiction_penalty == 0.0
    assert matches[0].accepted_track == "original"
    assert matches[0].normalized_value == "aars2"


def test_compare_evidence_preserves_source_span_for_wrong_value_candidate() -> None:
    expected = [{"field_id": "A.gene_symbol", "value": "AARS2"}]
    source_span = {"text_snippet": "BRCA1 distractor", "start_offset": 40, "end_offset": 55}
    extracted = [
        {
            "field_id": "A.gene_symbol",
            "status": "found",
            "value": "BRCA1",
            "confidence": 0.6,
            "source_span": source_span,
        }
    ]

    matches = compare_evidence(expected, extracted)

    assert not matches[0].matched
    assert matches[0].match_type == "wrong_value"
    assert matches[0].source_span == source_span


def test_compare_evidence_treats_disease_punctuation_only_variants_as_exact() -> None:
    expected = [{"field_id": "B.disease_diagnosis", "value": "Charcot-Marie-Tooth disease axonal type 2N"}]
    extracted = [
        {
            "field_id": "B.disease_diagnosis",
            "status": "found",
            "value": "Charcot-Marie-Tooth disease, axonal type 2N",
            "confidence": 0.9,
        }
    ]

    matches = compare_evidence(expected, extracted)

    assert matches[0].matched
    assert matches[0].match_type == "exact"


class FakePipelineClient:
    def __init__(self) -> None:
        self.post_payloads = []

    async def post(self, url: str, json: dict, timeout: float):  # noqa: ANN001
        self.post_payloads.append(json)
        return FakeResponse(202, {"status_url": "/status"})

    async def get(self, url: str, timeout: float):  # noqa: ANN001
        return FakeResponse(200, {"pipeline_status": "completed"})


class FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class NonTerminalPipelineClient:
    def __init__(self) -> None:
        self.post_payloads = []

    async def post(self, url: str, json: dict, timeout: float):  # noqa: ANN001
        self.post_payloads.append(json)
        return FakeResponse(
            202,
            {
                "processing_run_id": "run-123",
                "source_document_id": "source-123",
                "status_url": "/api/v1/pipeline/runs/run-123/status",
            },
        )

    async def get(self, url: str, timeout: float):  # noqa: ANN001
        return FakeResponse(
            200,
            {
                "processing_run_id": "run-123",
                "pipeline_status": "running",
                "current_phase": "phase_2",
            },
        )


@pytest.mark.asyncio
async def test_submit_and_poll_sends_extraction_target(monkeypatch) -> None:
    monkeypatch.setattr("benchmark.layer3.evaluate.POLL_INTERVAL_S", 0)
    client = FakePipelineClient()

    await submit_and_poll(
        client,
        "http://test",
        pdf_bytes=None,
        filename="clingen_002.md",
        pre_parsed_markdown="ABCA3 text",
        extraction_target={
            "gene_symbol": "ABCA3",
            "disease_name": "interstitial lung disease due to ABCA3 deficiency",
            "clingen_entry_id": "clingen_002",
        },
    )

    assert client.post_payloads[0]["target"]["gene_symbol"] == "ABCA3"


@pytest.mark.asyncio
async def test_submit_and_poll_timeout_preserves_run_diagnostics(monkeypatch) -> None:
    monkeypatch.setattr("benchmark.layer3.evaluate.POLL_INTERVAL_S", 0)
    monkeypatch.setattr("benchmark.layer3.evaluate.MAX_POLL_ATTEMPTS", 1)
    client = NonTerminalPipelineClient()

    result = await submit_and_poll(
        client,
        "http://test",
        pdf_bytes=None,
        filename="clingen_001.md",
        pre_parsed_markdown="AARS2 text",
    )

    assert result["pipeline_status"] == "timeout"
    assert result["processing_run_id"] == "run-123"
    assert result["status_url"] == "/api/v1/pipeline/runs/run-123/status"
    assert result["last_status"]["pipeline_status"] == "running"
    assert result["last_status"]["current_phase"] == "phase_2"


@pytest.mark.asyncio
async def test_evaluate_one_timeout_keeps_run_diagnostics(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("benchmark.layer3.evaluate.GROUND_TRUTH_DIR", tmp_path)
    monkeypatch.setattr("benchmark.layer3.evaluate.POLL_INTERVAL_S", 0)
    monkeypatch.setattr("benchmark.layer3.evaluate.MAX_POLL_ATTEMPTS", 1)
    entry_dir = tmp_path / "clingen_001"
    entry_dir.mkdir()
    (entry_dir / "source.md").write_text("AARS2 evidence text. " * 10, encoding="utf-8")

    metrics = await evaluate_one(
        NonTerminalPipelineClient(),
        "http://test",
        {
            "entry_id": "clingen_001",
            "gene_symbol": "AARS2",
            "disease_label": "combined oxidative phosphorylation deficiency",
            "classification": "Definitive",
            "moi": "AR",
            "expected_evidence": [
                {"field_id": "A.gene_symbol", "value": "AARS2"},
                {
                    "field_id": "B.disease_diagnosis",
                    "value": "combined oxidative phosphorylation deficiency",
                },
                {"field_id": "A.gene_disease_relationship", "value": "causative"},
            ],
        },
        sf=lambda: None,
        semaphore=asyncio.Semaphore(1),
    )

    assert metrics.pipeline_status == "timeout"
    assert metrics.run_id == "run-123"
    assert metrics.status_url == "/api/v1/pipeline/runs/run-123/status"
    assert metrics.last_pipeline_status == "running"
    assert metrics.last_current_phase == "phase_2"
    assert metrics.error_message == "Poll timed out"
    assert [field.match_type for field in metrics.field_matches] == ["missing", "missing", "missing"]


@pytest.mark.asyncio
async def test_preflight_database_connection_raises_clear_error_before_pipeline_submission() -> None:
    class FailingSession:
        async def __aenter__(self):  # noqa: ANN204
            raise RuntimeError('password authentication failed for user "[redacted-user]"')

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            return None

    def failing_session_factory() -> FailingSession:
        return FailingSession()

    with pytest.raises(RuntimeError, match="Layer 3 database preflight failed"):
        await preflight_database_connection(failing_session_factory)
