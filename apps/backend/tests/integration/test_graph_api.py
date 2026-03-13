from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

import main
from src.config import settings as cfg
from src.infrastructure.minio import MinIOClient
import src.api.routes.evidence as graph_api


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    async def _ensure_buckets(self) -> None:
        return None

    monkeypatch.setattr(main, "check_all_connections", lambda: {"redis": True})
    monkeypatch.setattr(MinIOClient, "ensure_buckets", _ensure_buckets, raising=True)

    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture()
def evidence_prefix() -> str:
    return f"{cfg.api_prefix}/evidence"


class DummyReport:
    def __init__(self, payload: Dict[str, Any]) -> None:
        self._payload = payload
        self.total_evidence = payload.get("total_evidence", 0)
        self.links = payload.get("links", [])
        self.variants = payload.get("variants", [])

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._payload)


class DummySearchEngine:
    def search_multi(self, **kwargs: Any) -> DummyReport:
        return DummyReport({"total_evidence": 2, "items": [{"id": 1}, {"id": 2}]})

    def search_by_gene(self, gene_symbol: str) -> DummyReport:
        return DummyReport({"total_evidence": 1, "gene": gene_symbol})

    def search_by_variant(self, variant: str) -> DummyReport:
        return DummyReport({"total_evidence": 1, "variant": variant})

    def get_document_evidence(self, document_id: int) -> DummyReport:
        return DummyReport({"total_evidence": 1, "document_id": document_id})


class DummyAnalyzer:
    def analyze_gene_associations(self, gene_symbol: str) -> DummyReport:
        return DummyReport({"links": [{"gene": gene_symbol}]})

    def analyze_variant_associations(self, variant: str) -> DummyReport:
        return DummyReport({"links": [{"variant": variant}]})

    def build_co_occurrence_matrix(self, gene_symbol: str) -> Dict[str, Any]:
        return {gene_symbol: {"BRCA1": 2}}

    def find_evidence_chains(self, gene_symbol: str, min_documents: int) -> list[dict]:
        return [{"gene": gene_symbol, "min_documents": min_documents}]


class DummyAggregationEngine:
    def aggregate_multi(self, **kwargs: Any) -> DummyReport:
        return DummyReport({"variants": [{"id": "v1"}]})

    def aggregate_by_gene(self, gene_symbol: str) -> DummyReport:
        return DummyReport({"variants": [{"gene": gene_symbol}]})

    def aggregate_by_variant(self, variant: str | None, protein_change: str | None) -> DummyReport:
        return DummyReport({"variants": [{"variant": variant, "protein_change": protein_change}]})

    def quality_overview(self, gene_symbol: str | None) -> Dict[str, Any]:
        return {"total_evidence": 3, "gene_symbol": gene_symbol}


class DummyNeo4jClient:
    def get_graph_statistics(self) -> list[dict]:
        return [{"label": "Gene", "count": 10}]


class DummySyncService:
    def resync_document(self, document_id: int) -> Dict[str, Any]:
        return {"document_id": document_id, "status": "ok"}


def _patch_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph_api, "get_graph_search_engine", lambda: DummySearchEngine())
    monkeypatch.setattr(graph_api, "get_entity_association_analyzer", lambda: DummyAnalyzer())
    monkeypatch.setattr(
        graph_api, "get_evidence_aggregation_engine", lambda: DummyAggregationEngine()
    )
    monkeypatch.setattr(graph_api, "get_neo4j_client", lambda: DummyNeo4jClient())
    monkeypatch.setattr(graph_api, "get_graph_sync_service", lambda: DummySyncService())


def test_search_evidence_requires_params(client: TestClient, evidence_prefix: str) -> None:
    response = client.post(f"{evidence_prefix}/search", json={})
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INPUT_INVALID"
    assert "log_link" in payload


def test_search_evidence_success(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, evidence_prefix: str
) -> None:
    _patch_dependencies(monkeypatch)
    response = client.post(f"{evidence_prefix}/search", json={"gene_symbol": "BRCA1"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["total_evidence"] == 2


def test_search_by_gene(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, evidence_prefix: str
) -> None:
    _patch_dependencies(monkeypatch)
    response = client.get(f"{evidence_prefix}/search/gene/BRCA1")
    assert response.status_code == 200
    assert response.json()["data"]["gene"] == "BRCA1"


def test_search_by_variant(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, evidence_prefix: str
) -> None:
    _patch_dependencies(monkeypatch)
    response = client.get(f"{evidence_prefix}/search/variant/BRCA1:c.68_69del")
    assert response.status_code == 200
    assert response.json()["data"]["variant"] == "BRCA1:c.68_69del"


def test_get_document_evidence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, evidence_prefix: str
) -> None:
    _patch_dependencies(monkeypatch)
    response = client.get(f"{evidence_prefix}/document/12")
    assert response.status_code == 200
    assert response.json()["data"]["document_id"] == 12


def test_association_gene(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, evidence_prefix: str
) -> None:
    _patch_dependencies(monkeypatch)
    response = client.get(f"{evidence_prefix}/association/gene/TP53")
    assert response.status_code == 200
    assert response.json()["data"]["links"][0]["gene"] == "TP53"


def test_association_variant(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, evidence_prefix: str
) -> None:
    _patch_dependencies(monkeypatch)
    response = client.get(f"{evidence_prefix}/association/variant/TP53:c.123A>G")
    assert response.status_code == 200
    assert response.json()["data"]["links"][0]["variant"] == "TP53:c.123A>G"


def test_co_occurrence_matrix(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, evidence_prefix: str
) -> None:
    _patch_dependencies(monkeypatch)
    response = client.get(f"{evidence_prefix}/co-occurrence/BRCA1")
    assert response.status_code == 200
    assert response.json()["data"]["gene_symbol"] == "BRCA1"


def test_evidence_chains(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, evidence_prefix: str
) -> None:
    _patch_dependencies(monkeypatch)
    response = client.get(f"{evidence_prefix}/evidence-chains/BRCA1?min_documents=3")
    assert response.status_code == 200
    assert response.json()["data"]["chains"][0]["min_documents"] == 3


def test_aggregate_evidence(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, evidence_prefix: str
) -> None:
    _patch_dependencies(monkeypatch)
    response = client.post(f"{evidence_prefix}/aggregate", json={"gene_symbol": "BRCA1"})
    assert response.status_code == 200
    assert response.json()["data"]["variants"][0]["id"] == "v1"


def test_aggregate_by_gene(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, evidence_prefix: str
) -> None:
    _patch_dependencies(monkeypatch)
    response = client.get(f"{evidence_prefix}/aggregate/gene/BRCA1")
    assert response.status_code == 200
    assert response.json()["data"]["variants"][0]["gene"] == "BRCA1"


def test_aggregate_by_variant_requires_params(client: TestClient, evidence_prefix: str) -> None:
    response = client.get(f"{evidence_prefix}/aggregate/variant")
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "INPUT_INVALID"
    assert "log_link" in payload


def test_aggregate_by_variant(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, evidence_prefix: str
) -> None:
    _patch_dependencies(monkeypatch)
    response = client.get(f"{evidence_prefix}/aggregate/variant?variant=BRCA1:c.68_69del")
    assert response.status_code == 200
    assert response.json()["data"]["variants"][0]["variant"] == "BRCA1:c.68_69del"


def test_quality_overview(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, evidence_prefix: str
) -> None:
    _patch_dependencies(monkeypatch)
    response = client.get(f"{evidence_prefix}/quality?gene_symbol=BRCA1")
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "RESOURCE_NOT_FOUND"
    assert payload["detail"] == "Quality API removed in MVP"
    assert "log_link" in payload


def test_graph_statistics(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, evidence_prefix: str
) -> None:
    _patch_dependencies(monkeypatch)
    response = client.get(f"{evidence_prefix}/graph/stats")
    assert response.status_code == 200
    assert response.json()["data"]["statistics"][0]["label"] == "Gene"


def test_resync_document(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, evidence_prefix: str
) -> None:
    _patch_dependencies(monkeypatch)
    response = client.post(f"{evidence_prefix}/sync/document/42")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"
