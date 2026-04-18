from __future__ import annotations

from typing import Any

from src.services.neo4j_disease_icd10_backfill import run_disease_icd10_backfill


def test_run_disease_icd10_backfill_upserts_distinct_nonempty_pairs() -> None:
    class FakePostgres:
        def list_distinct_disease_icd10_pairs(self, *, limit: int, offset: int):
            assert limit == 10
            assert offset == 0
            return [
                {'disease_name': 'D1', 'icd10_code': 'Q87.8'},
                {'disease_name': 'D2', 'icd10_code': 'E11.9'},
                {'disease_name': 'D3', 'icd10_code': None},
                {'disease_name': 'D4', 'icd10_code': ''},
                {'disease_name': '', 'icd10_code': 'A00.0'},
            ]

    class FakeNeo4j:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def upsert_disease(self, name: str, **props: Any) -> None:
            self.calls.append({'name': name, **props})

    fake_pg = FakePostgres()
    fake_neo = FakeNeo4j()

    report = run_disease_icd10_backfill(
        limit=10,
        offset=0,
        postgres_client=fake_pg,
        neo4j_client=fake_neo,
    )

    assert fake_neo.calls == [
        {'name': 'D1', 'icd10_code': 'Q87.8'},
        {'name': 'D2', 'icd10_code': 'E11.9'},
    ]
    assert report == {
        'processed': 2,
        'diseases': ['D1', 'D2'],
    }


def test_disease_icd10_backfill_cli_invokes_service(monkeypatch) -> None:
    calls = {}

    def fake_run_disease_icd10_backfill(*, limit: int, offset: int):
        calls['limit'] = limit
        calls['offset'] = offset
        return {'processed': 5, 'diseases': []}

    from src.services import neo4j_disease_icd10_backfill_cli as cli_module

    monkeypatch.setattr(cli_module, 'run_disease_icd10_backfill', fake_run_disease_icd10_backfill)

    assert cli_module.main(['--limit', '5', '--offset', '10']) == 0
    assert calls == {'limit': 5, 'offset': 10}
