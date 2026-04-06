# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportDeprecated=false, reportUnusedCallResult=false

from __future__ import annotations

from typing import Any, Dict, Optional, Union
from uuid import UUID

from loguru import logger

from src.domain.graph.sync import get_graph_sync_service
from src.services.kg_events import KGEventService, get_kg_event_service


def process_kg_event(
    event_id: Union[UUID, str],
    *,
    kg_event_service: Optional[KGEventService] = None,
    sync_service: Any = None,
) -> Dict[str, Any]:
    events = kg_event_service or get_kg_event_service()
    sync = sync_service or get_graph_sync_service()
    event = events.get_kg_event(event_id)
    if event is None:
        raise ValueError(f"KG event not found: {event_id}")

    document_id = str(getattr(event, "document_id", "") or "").strip()
    if not document_id:
        raise ValueError(f"KG event {event_id} is missing document_id")

    next_attempt = int(getattr(event, "attempt_count", 0) or 0) + 1
    event_id_str = str(getattr(event, "event_id", event_id))
    events.update_kg_event_status(
        event_id_str,
        status="running",
        attempt_count=next_attempt,
        last_error=None,
    )

    try:
        graph_sync_result = sync.resync_document(document_id)
        events.update_kg_event_status(
            event_id_str,
            status="success",
            attempt_count=next_attempt,
            last_error=None,
        )
        return {
            "status": "success",
            "event_id": event_id_str,
            "document_id": document_id,
            "graph_sync_result": graph_sync_result,
        }
    except Exception as exc:
        logger.warning("KG consumer failed for event {}: {}", event_id_str, exc)
        events.update_kg_event_status(
            event_id_str,
            status="failed",
            attempt_count=next_attempt,
            last_error=str(exc),
        )
        raise
