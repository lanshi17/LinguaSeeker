from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

from src.infrastructure.models import KGEvent
from src.infrastructure.postgres import PostgresClient
from src.services.kg_events import KGEventService


class _FakeExecuteResult:
    def __init__(self, event: KGEvent | None) -> None:
        self._event = event

    def scalar_one_or_none(self) -> KGEvent | None:
        return self._event


class _FakeQuery:
    def __init__(self, store: dict[str, KGEvent]) -> None:
        self._store = store

    def filter(self, *_args, **_kwargs) -> "_FakeQuery":
        return self

    def one(self) -> KGEvent:
        return next(iter(self._store.values()))


class _FakeSession:
    def __init__(self) -> None:
        self.store: dict[str, KGEvent] = {}

    def execute(self, statement) -> _FakeExecuteResult:
        params = statement.compile().params
        key = params["idempotency_key"]
        existing = self.store.get(key)
        if existing is not None:
            return _FakeExecuteResult(None)

        event = KGEvent(
            event_id=params["event_id"] or uuid4(),
            request_id=params["request_id"],
            paper_task_id=params["paper_task_id"],
            document_id=params["document_id"],
            event_type=params["event_type"],
            idempotency_key=key,
            status=params["status"],
            payload=params["payload"],
            attempt_count=params["attempt_count"],
            last_error=params["last_error"],
        )
        self.store[key] = event
        return _FakeExecuteResult(event)

    def query(self, _model) -> _FakeQuery:
        return _FakeQuery(self.store)


def _service_with_fake_session() -> KGEventService:
    client = PostgresClient.__new__(PostgresClient)
    fake_session = _FakeSession()

    @contextmanager
    def _session_scope():
        yield fake_session

    client.session_scope = _session_scope  # type: ignore[method-assign]
    return KGEventService(client)


def test_create_kg_event_persists_minimal_outbox_payload() -> None:
    service = _service_with_fake_session()

    event = service.create_kg_event(
        request_id=uuid4(),
        paper_task_id=uuid4(),
        document_id=uuid4(),
        event_type="paper_completed",
        idempotency_key="kg:v1.0:paper_completed:paper-1",
        payload={"release_no": "v1.0"},
    )

    assert event.status == "pending"
    assert event.payload["release_no"] == "v1.0"
    assert event.attempt_count == 0


def test_create_kg_event_is_idempotent_by_key() -> None:
    service = _service_with_fake_session()

    first = service.create_kg_event(
        request_id=uuid4(),
        paper_task_id=uuid4(),
        document_id=uuid4(),
        event_type="paper_completed",
        idempotency_key="same-key",
        payload={"release_no": "v1.0"},
    )
    second = service.create_kg_event(
        request_id=uuid4(),
        paper_task_id=uuid4(),
        document_id=uuid4(),
        event_type="paper_completed",
        idempotency_key="same-key",
        payload={"release_no": "v2.0"},
    )

    assert second.event_id == first.event_id
    assert second.payload["release_no"] == "v1.0"
