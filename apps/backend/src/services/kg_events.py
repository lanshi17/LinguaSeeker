# pyright: reportAny=false, reportExplicitAny=false, reportDeprecated=false, reportUnannotatedClassAttribute=false

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from src.infrastructure.models import KGEvent
from src.infrastructure.postgres import PostgresClient, get_postgres_client


class KGEventService:
    def __init__(self, postgres_client: Optional[PostgresClient] = None) -> None:
        self.postgres_client = postgres_client or get_postgres_client()

    def create_kg_event(
        self,
        *,
        request_id: Optional[Union[UUID, str]] = None,
        paper_task_id: Optional[Union[UUID, str]] = None,
        document_id: Optional[Union[UUID, str]] = None,
        event_type: str,
        idempotency_key: str,
        payload: Optional[Dict[str, Any]] = None,
        status: str = "pending",
        attempt_count: int = 0,
        last_error: Optional[str] = None,
    ) -> KGEvent:
        return self.postgres_client.create_kg_event(
            request_id=request_id,
            paper_task_id=paper_task_id,
            document_id=document_id,
            event_type=event_type,
            idempotency_key=idempotency_key,
            payload=payload,
            status=status,
            attempt_count=attempt_count,
            last_error=last_error,
        )

    def get_kg_event(self, event_id: Union[UUID, str]) -> Optional[KGEvent]:
        return self.postgres_client.get_kg_event(event_id)

    def get_kg_event_by_idempotency_key(self, idempotency_key: str) -> Optional[KGEvent]:
        return self.postgres_client.get_kg_event_by_idempotency_key(idempotency_key)

    def list_pending_kg_events(self, limit: int = 100) -> List[KGEvent]:
        return self.postgres_client.list_pending_kg_events(limit=limit)

    def update_kg_event_status(
        self,
        event_id: Union[UUID, str],
        *,
        status: str,
        attempt_count: Optional[int] = None,
        last_error: Any = None,
        payload: Any = None,
    ) -> Optional[KGEvent]:
        update_kwargs: Dict[str, Any] = {
            "status": status,
            "attempt_count": attempt_count,
        }
        if last_error is not None:
            update_kwargs["last_error"] = last_error
        if payload is not None:
            update_kwargs["payload"] = payload
        return self.postgres_client.update_kg_event_status(event_id, **update_kwargs)


_kg_event_service: Optional[KGEventService] = None


def get_kg_event_service() -> KGEventService:
    global _kg_event_service
    if _kg_event_service is None:
        _kg_event_service = KGEventService()
    return _kg_event_service
