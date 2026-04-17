from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from src.services.neo4j_document_backfill import run_document_metadata_backfill


def test_run_document_metadata_backfill_upserts_document_props() -> None:
    class FakePostgres:
        def list_documents(self, *, limit: int, offset: int) -> list[Any]:
            assert limit == 2
            assert offset == 0
            return [
                SimpleNamespace(
                    document_id='00000000-0000-0000-0000-000000000001',
                    title='Doc One',
                    file_hash='hash-1',
                    status='success',
                    pmid='1001',
                ),
                SimpleNamespace(
                    document_id='00000000-0000-0000-0000-000000000002',
                    title='Doc Two',
                    file_hash='hash-2',
                    status='queued',
                    pmid=None,
                ),
            ]

    class FakeNeo4j:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def upsert_document(self, document_id: str, **props: Any) -> None:
            self.calls.append({'document_id': document_id, **props})

    fake_pg = FakePostgres()
    fake_neo = FakeNeo4j()

    report = run_document_metadata_backfill(
        limit=2,
        offset=0,
        postgres_client=fake_pg,
        neo4j_client=fake_neo,
    )

    assert fake_neo.calls == [
        {
            'document_id': '00000000-0000-0000-0000-000000000001',
            'title': 'Doc One',
            'file_hash': 'hash-1',
            'status': 'success',
            'pmid': '1001',
        },
        {
            'document_id': '00000000-0000-0000-0000-000000000002',
            'title': 'Doc Two',
            'file_hash': 'hash-2',
            'status': 'queued',
        },
    ]
    assert report == {
        'processed': 2,
        'document_ids': [
            '00000000-0000-0000-0000-000000000001',
            '00000000-0000-0000-0000-000000000002',
        ],
    }


def test_document_backfill_cli_invokes_service(monkeypatch) -> None:
    calls = {}

    def fake_run_document_metadata_backfill(*, limit: int, offset: int):
        calls['limit'] = limit
        calls['offset'] = offset
        return {'processed': 5, 'document_ids': []}

    from src.services import neo4j_document_backfill_cli as cli_module

    monkeypatch.setattr(cli_module, 'run_document_metadata_backfill', fake_run_document_metadata_backfill)

    assert cli_module.main(['--limit', '5', '--offset', '10']) == 0
    assert calls == {'limit': 5, 'offset': 10}
