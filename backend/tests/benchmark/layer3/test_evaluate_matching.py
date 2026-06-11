"""Tests for ClinGen layer-3 value matching."""
from __future__ import annotations

import pytest

from benchmark.layer3.evaluate import compare_evidence, fuzzy_match_value, submit_and_poll


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
