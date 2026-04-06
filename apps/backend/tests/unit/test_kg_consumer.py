from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

import src.services.kg_consumer as kg_consumer


class _FakeKGEvents:
    def __init__(self, event: Any) -> None:
        self.event = event
        self.updated: List[Dict[str, Any]] = []

    def get_kg_event(self, event_id: str) -> Any:
        assert event_id == self.event.event_id
        return self.event

    def update_kg_event_status(self, event_id: str, **kwargs: Any) -> Any:
        self.updated.append({"event_id": event_id, **kwargs})
        for key, value in kwargs.items():
            setattr(self.event, key, value)
        return self.event


class _FakeSync:
    def __init__(self, *, should_fail: bool = False, variant_count: int = 1) -> None:
        self.should_fail = should_fail
        self.calls: List[str] = []
        self.variant_count = variant_count
        self.received_pg_variant_count = 0

    def resync_document(self, document_id: str) -> Dict[str, Any]:
        self.calls.append(document_id)
        if self.should_fail:
            raise RuntimeError("neo4j unavailable")
        self.received_pg_variant_count = self.variant_count
        return {"total": self.variant_count, "synced": self.variant_count, "failed": 0}


def test_process_kg_event_loads_event_and_resyncs_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = SimpleNamespace(
        event_id="event-1",
        document_id="doc-1",
        attempt_count=0,
        status="pending",
        last_error=None,
    )
    fake_events = _FakeKGEvents(event)
    fake_sync = _FakeSync()
    monkeypatch.setattr(kg_consumer, "get_kg_event_service", lambda: fake_events)
    monkeypatch.setattr(kg_consumer, "get_graph_sync_service", lambda: fake_sync)

    result = kg_consumer.process_kg_event("event-1")

    assert result["status"] == "success"
    assert fake_sync.calls == ["doc-1"]
    assert fake_events.updated[-1]["status"] == "success"
    assert fake_events.updated[-1]["attempt_count"] == 1


def test_process_kg_event_marks_failure_and_preserves_attempt_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = SimpleNamespace(
        event_id="event-1",
        document_id="doc-1",
        attempt_count=0,
        status="pending",
        last_error=None,
    )
    fake_events = _FakeKGEvents(event)
    fake_sync = _FakeSync(should_fail=True)
    monkeypatch.setattr(kg_consumer, "get_kg_event_service", lambda: fake_events)
    monkeypatch.setattr(kg_consumer, "get_graph_sync_service", lambda: fake_sync)

    with pytest.raises(RuntimeError):
        kg_consumer.process_kg_event("event-1")

    assert fake_events.updated[-1]["status"] == "failed"
    assert fake_events.updated[-1]["attempt_count"] == 1


def test_process_kg_event_resyncs_document_after_pg_fanout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = SimpleNamespace(
        event_id="event-1",
        document_id="doc-1",
        attempt_count=0,
        status="pending",
        last_error=None,
    )
    fake_events = _FakeKGEvents(event)
    fake_sync = _FakeSync(variant_count=3)
    monkeypatch.setattr(kg_consumer, "get_kg_event_service", lambda: fake_events)
    monkeypatch.setattr(kg_consumer, "get_graph_sync_service", lambda: fake_sync)

    result = kg_consumer.process_kg_event("event-1")

    assert result["status"] == "success"
    assert fake_sync.calls == ["doc-1"]
    assert fake_sync.received_pg_variant_count == 3
