from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pytest

from src.database import neo4j_client as neo4j_module


class FakeRecord:
    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = data

    def data(self) -> Dict[str, Any]:
        return dict(self._data)


class FakeResult:
    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        self._rows = rows

    def __iter__(self):
        return (FakeRecord(row) for row in self._rows)


class FakeSession:
    def __init__(self, responses: List[List[Dict[str, Any]]]) -> None:
        self.responses = list(responses)
        self.calls: List[Tuple[str, Dict[str, Any]]] = []
        self.database: str | None = None

    def run(self, query: str, parameters: Dict[str, Any] | None = None) -> FakeResult:
        self.calls.append((query, parameters or {}))
        if self.responses:
            return FakeResult(self.responses.pop(0))
        return FakeResult([])

    def close(self) -> None:
        return None


class FakeDriver:
    def __init__(self, responses: List[List[Dict[str, Any]]]) -> None:
        self.session_obj = FakeSession(responses)

    def session(self, database: str | None = None) -> FakeSession:
        self.session_obj.database = database
        return self.session_obj

    def close(self) -> None:
        return None


def _make_client(monkeypatch: pytest.MonkeyPatch, responses: List[List[Dict[str, Any]]]) -> Tuple[neo4j_module.Neo4jClient, FakeDriver]:
    fake_driver = FakeDriver(responses)
    monkeypatch.setattr(neo4j_module.GraphDatabase, "driver", lambda *args, **kwargs: fake_driver)
    client = neo4j_module.Neo4jClient(uri="bolt://localhost", user="neo4j", password="pass", database="neo4j")
    return client, fake_driver


def test_run_query_returns_data(monkeypatch: pytest.MonkeyPatch) -> None:
    client, driver = _make_client(monkeypatch, [[{"ok": 1}]])

    result = client.run_query("RETURN 1 AS ok")

    assert result == [{"ok": 1}]
    assert driver.session_obj.calls[0][0].startswith("RETURN 1")


def test_initialize_schema_runs_all_statements(monkeypatch: pytest.MonkeyPatch) -> None:
    client, driver = _make_client(monkeypatch, [])

    client.initialize_schema()

    expected_count = len(neo4j_module._SCHEMA_CONSTRAINTS) + len(neo4j_module._SCHEMA_INDEXES)
    assert len(driver.session_obj.calls) == expected_count
    assert driver.session_obj.calls[0][0].startswith("CREATE CONSTRAINT")


def test_upsert_gene(monkeypatch: pytest.MonkeyPatch) -> None:
    client, driver = _make_client(monkeypatch, [[{"g": {"symbol": "BRCA1"}}]])

    result = client.upsert_gene("BRCA1", foo="bar")

    assert result["g"]["symbol"] == "BRCA1"
    query, params = driver.session_obj.calls[-1]
    assert "MERGE (g:Gene" in query
    assert params == {"symbol": "BRCA1", "props": {"foo": "bar"}}


def test_link_gene_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    client, driver = _make_client(monkeypatch, [])

    client.link_gene_variant("GENE1", "c.1A>T", source="unit")

    query, params = driver.session_obj.calls[-1]
    assert "HAS_VARIANT" in query
    assert params == {"gene_symbol": "GENE1", "variant_hgvs_c": "c.1A>T", "props": {"source": "unit"}}


def test_find_multi_document_evidence_no_conditions(monkeypatch: pytest.MonkeyPatch) -> None:
    client, driver = _make_client(monkeypatch, [])

    result = client.find_multi_document_evidence()

    assert result == []
    assert driver.session_obj.calls == []


def test_find_multi_document_evidence_with_gene(monkeypatch: pytest.MonkeyPatch) -> None:
    client, driver = _make_client(monkeypatch, [[{"gene": "BRCA1"}]])

    result = client.find_multi_document_evidence(gene_symbol="BRCA1")

    assert result == [{"gene": "BRCA1"}]
    query, params = driver.session_obj.calls[-1]
    assert "WHERE g.symbol = $gene" in query
    assert params == {"gene": "BRCA1"}


def test_get_graph_statistics(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _driver = _make_client(
        monkeypatch,
        [[{"label": "Gene", "count": 2}, {"label": "HAS_VARIANT", "count": 3}, {"label": None, "count": 1}]],
    )

    stats = client.get_graph_statistics()

    assert stats == {"Gene": 2, "HAS_VARIANT": 3}


def test_health_check_success(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _driver = _make_client(monkeypatch, [[{"ok": 1}]])

    assert client.health_check() is True


def test_health_check_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _driver = _make_client(monkeypatch, [])

    def _raise(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(client, "run_query", _raise)

    assert client.health_check() is False


def test_get_neo4j_client_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    neo4j_module._neo4j_client = None
    fake_driver = FakeDriver([])
    monkeypatch.setattr(neo4j_module.GraphDatabase, "driver", lambda *args, **kwargs: fake_driver)

    first = neo4j_module.get_neo4j_client()
    second = neo4j_module.get_neo4j_client()

    assert first is second
