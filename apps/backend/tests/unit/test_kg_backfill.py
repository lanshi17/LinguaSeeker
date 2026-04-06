from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import src.services.kg_backfill as kg_backfill


class _FakePostgres:
    def __init__(self, rows: List[Any]) -> None:
        self.rows = rows

    def list_completed_paper_tasks_for_kg_backfill(
        self,
        *,
        after_paper_task_id: str | None = None,
        limit: int = 100,
    ) -> List[Any]:
        filtered = [
            row
            for row in self.rows
            if after_paper_task_id is None
            or str(row.paper_task_id) > str(after_paper_task_id)
        ]
        return filtered[:limit]


class _FakeKGEvents:
    def __init__(self) -> None:
        self.created: List[Dict[str, Any]] = []

    def create_kg_event(self, **kwargs: Any) -> Any:
        self.created.append(kwargs)
        return SimpleNamespace(event_id=f"evt-{kwargs['paper_task_id']}")


def test_backfill_runs_from_checkpoint_and_updates_checkpoint_file(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "kg-backfill.json"
    postgres = _FakePostgres(
        [
            SimpleNamespace(paper_task_id="paper-1", request_id="req-1", document_id="doc-1"),
            SimpleNamespace(paper_task_id="paper-2", request_id="req-2", document_id="doc-2"),
            SimpleNamespace(paper_task_id="paper-3", request_id="req-3", document_id="doc-3"),
        ]
    )
    fake_events = _FakeKGEvents()
    processed: List[str] = []

    def fake_process_event(event_id: str) -> Dict[str, Any]:
        processed.append(event_id)
        return {"status": "success"}

    report = kg_backfill.run_kg_backfill(
        checkpoint_path=checkpoint,
        batch_size=2,
        postgres_client=postgres,
        kg_event_service=fake_events,
        process_event_fn=fake_process_event,
    )

    assert report["processed"] == 2
    assert json.loads(checkpoint.read_text())["last_paper_task_id"] == "paper-2"
    assert processed == ["evt-paper-1", "evt-paper-2"]


def test_backfill_resume_skips_completed_prefix(tmp_path: Path) -> None:
    checkpoint = tmp_path / "kg-backfill.json"
    checkpoint.write_text(json.dumps({"last_paper_task_id": "paper-2"}), encoding="utf-8")
    postgres = _FakePostgres(
        [
            SimpleNamespace(paper_task_id="paper-1", request_id="req-1", document_id="doc-1"),
            SimpleNamespace(paper_task_id="paper-2", request_id="req-2", document_id="doc-2"),
            SimpleNamespace(paper_task_id="paper-3", request_id="req-3", document_id="doc-3"),
        ]
    )
    fake_events = _FakeKGEvents()

    report = kg_backfill.run_kg_backfill(
        checkpoint_path=checkpoint,
        batch_size=10,
        postgres_client=postgres,
        kg_event_service=fake_events,
        process_event_fn=lambda event_id: {"event_id": event_id, "status": "success"},
    )

    assert report["processed_paper_task_ids"] == ["paper-3"]


def test_backfill_reuses_same_resync_path_as_incremental_consumer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    checkpoint = tmp_path / "kg-backfill.json"
    postgres = _FakePostgres(
        [
            SimpleNamespace(paper_task_id="paper-1", request_id="req-1", document_id="doc-1"),
            SimpleNamespace(paper_task_id="paper-2", request_id="req-2", document_id="doc-2"),
        ]
    )
    fake_events = _FakeKGEvents()
    calls: List[str] = []

    def fake_process_event(event_id: str) -> Dict[str, Any]:
        calls.append(event_id.replace("evt-paper-", "doc-"))
        return {"status": "success"}

    report = kg_backfill.run_kg_backfill(
        checkpoint_path=checkpoint,
        batch_size=10,
        postgres_client=postgres,
        kg_event_service=fake_events,
        process_event_fn=fake_process_event,
    )

    assert report["processed"] == 2
    assert calls == ["doc-1", "doc-2"]
