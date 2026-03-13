from __future__ import annotations

from typing import Generator

import pytest
from fastapi.testclient import TestClient

import main
import src.api.routes.evidence as evidence_module
from src.config import settings as cfg
from src.infrastructure.minio import MinIOClient


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    async def _ensure_buckets(self) -> None:
        return None

    monkeypatch.setattr(main, "check_all_connections", lambda: {"redis": True})
    monkeypatch.setattr(MinIOClient, "ensure_buckets", _ensure_buckets, raising=True)

    with TestClient(main.app) as test_client:
        yield test_client


def test_search_evidence_missing_params_returns_input_invalid(
    client: TestClient,
) -> None:
    """Test that search without required params returns INPUT_INVALID error."""
    response = client.post(
        f"{cfg.api_prefix}/evidence/search",
        json={},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INPUT_INVALID"
    assert "log_link" in payload


def test_aggregate_by_variant_missing_params_returns_input_invalid(
    client: TestClient,
) -> None:
    """Test that aggregate_by_variant without params returns INPUT_INVALID error."""
    response = client.get(f"{cfg.api_prefix}/evidence/aggregate/variant")
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INPUT_INVALID"
    assert "log_link" in payload


def test_quality_overview_returns_resource_not_found(
    client: TestClient,
) -> None:
    """Test that quality API returns RESOURCE_NOT_FOUND (MVP disabled)."""
    response = client.get(f"{cfg.api_prefix}/evidence/quality")
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "RESOURCE_NOT_FOUND"
    assert "log_link" in payload


def test_search_by_gene_engine_failure_returns_internal_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that engine failures return INTERNAL_ERROR."""

    class DummyEngine:
        def search_by_gene(self, gene_symbol: str) -> None:
            raise RuntimeError("Graph engine unavailable")

    monkeypatch.setattr(evidence_module, "get_graph_search_engine", lambda: DummyEngine())

    response = client.get(f"{cfg.api_prefix}/evidence/search/gene/BRCA1")
    assert response.status_code == 500
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INTERNAL_ERROR"
    assert "log_link" in payload


def test_graph_statistics_neo4j_failure_returns_internal_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that Neo4j failures return INTERNAL_ERROR."""

    class DummyNeo4jClient:
        def get_graph_statistics(self) -> None:
            raise ConnectionError("Neo4j unavailable")

    monkeypatch.setattr(evidence_module, "get_neo4j_client", lambda: DummyNeo4jClient())

    response = client.get(f"{cfg.api_prefix}/evidence/graph/stats")
    assert response.status_code == 500
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INTERNAL_ERROR"
    assert "log_link" in payload
