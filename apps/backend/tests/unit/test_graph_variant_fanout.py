from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from src.domain.graph import sync as sync_module


class _NoopNeo4j:
    def __getattr__(self, _: str) -> Any:
        return lambda *args, **kwargs: None


class _CapturePostgres:
    def __init__(self) -> None:
        self.rows: List[Dict[str, Any]] = []

    def create_evidence_record(self, **kwargs: Any) -> Any:
        self.rows.append(kwargs)
        return SimpleNamespace(evidence_id=len(self.rows))

    def create_evidence_records(self, rows: List[Dict[str, Any]]) -> List[Any]:
        records = []
        for row in rows:
            self.rows.append(row)
            records.append(SimpleNamespace(evidence_id=len(self.rows)))
        return records

    def get_evidence_for_document(self, *_: Any, **__: Any) -> List[Any]:
        return []


class _NoopVariationService:
    def resolve_variation(self, *_: Any, **__: Any) -> Any:
        return None

    def record_internal_citation(self, *_: Any, **__: Any) -> None:
        return None


def _multi_variant_output() -> Dict[str, Any]:
    return {
        "extracted_fields": {
            "gene": {"symbol": "GENE"},
            "variant": {
                "hgvs_c": "c.1972C>T; c.1935_1954dup; c.1526T>C",
                "hgvs_p": "p.Arg658Cys; p.Glu652fs; p.Ile509Thr",
            },
            "transcript_id": {"transcript_id": "NM_1"},
            "disease_chpo": {"disease_name": "D1"},
        },
        "ps3_evidence": {},
        "evidence_classification": "Pathogenic",
        "overall_confidence": 90.0,
        "acmg_evidence_levels": ["PS3"],
        "final_evidence_strength": "PS3",
        "arbitration_score": 88.0,
    }


def test_sync_evidence_fans_out_multiple_variants_into_multiple_pg_rows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    pg = _CapturePostgres()
    monkeypatch.setattr(sync_module, "get_neo4j_client", lambda: _NoopNeo4j())
    monkeypatch.setattr(sync_module, "get_postgres_client", lambda: pg)
    monkeypatch.setattr(
        sync_module,
        "get_variation_data_service",
        lambda: _NoopVariationService(),
    )
    monkeypatch.setattr(
        sync_module.GraphSyncService,
        "_FAILURE_ARCHIVE_PATH",
        tmp_path / "failures.jsonl",
    )

    service = sync_module.GraphSyncService()
    result = service.sync_evidence("00000000-0000-0000-0000-000000000001", _multi_variant_output())

    assert result["pg_evidence_ids"] == [1, 2, 3]
    assert [row["variant_hgvs_c"] for row in pg.rows] == [
        "c.1972C>T",
        "c.1935_1954dup",
        "c.1526T>C",
    ]
    assert [row["variant_hgvs_p"] for row in pg.rows] == [
        "p.Arg658Cys",
        "p.Glu652fs",
        "p.Ile509Thr",
    ]


def test_sync_evidence_keeps_paper_level_success_shape_when_fanout_occurs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    pg = _CapturePostgres()
    monkeypatch.setattr(sync_module, "get_neo4j_client", lambda: _NoopNeo4j())
    monkeypatch.setattr(sync_module, "get_postgres_client", lambda: pg)
    monkeypatch.setattr(
        sync_module,
        "get_variation_data_service",
        lambda: _NoopVariationService(),
    )
    monkeypatch.setattr(
        sync_module.GraphSyncService,
        "_FAILURE_ARCHIVE_PATH",
        tmp_path / "failures.jsonl",
    )

    service = sync_module.GraphSyncService()
    result = service.sync_evidence("00000000-0000-0000-0000-000000000001", _multi_variant_output())

    assert result["neo4j_synced"] is True
    assert result["skipped"] is False
    assert result["pg_evidence_id"] == 1
