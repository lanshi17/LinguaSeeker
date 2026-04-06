# pyright: reportAny=false, reportExplicitAny=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportDeprecated=false, reportUnusedCallResult=false

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, cast

from src.infrastructure.models import PaperTask
from src.infrastructure.postgres import PostgresClient, get_postgres_client
from src.services.kg_consumer import process_kg_event
from src.services.kg_events import KGEventService, get_kg_event_service

_RELEASE_NO = "v1.0"


def _load_checkpoint(checkpoint_path: Path) -> Dict[str, Any]:
    if not checkpoint_path.exists():
        return {}
    return json.loads(checkpoint_path.read_text(encoding="utf-8"))


def _write_checkpoint(checkpoint_path: Path, *, last_paper_task_id: str) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(
        json.dumps(
            {
                "last_paper_task_id": last_paper_task_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )


def _list_backfill_candidates(
    postgres_client: Any,
    *,
    after_paper_task_id: Optional[str] = None,
    limit: int = 100,
) -> List[Any]:
    explicit_list = getattr(
        postgres_client, "list_completed_paper_tasks_for_kg_backfill", None
    )
    if callable(explicit_list):
        rows = explicit_list(after_paper_task_id=after_paper_task_id, limit=limit)
        if isinstance(rows, list):
            return rows
        return list(cast(Iterable[Any], rows))

    if isinstance(postgres_client, PostgresClient):
        with postgres_client.session_scope() as session:
            rows = (
                session.query(PaperTask)
                .filter(PaperTask.status == "success", PaperTask.document_id.isnot(None))
                .all()
            )
        filtered = [
            row
            for row in rows
            if after_paper_task_id is None
            or str(row.paper_task_id) > str(after_paper_task_id)
        ]
        filtered.sort(key=lambda row: str(row.paper_task_id))
        return filtered[:limit]

    raise TypeError("Unsupported postgres client for KG backfill")


def run_kg_backfill(
    *,
    checkpoint_path: str | Path,
    batch_size: int,
    postgres_client: Optional[Any] = None,
    kg_event_service: Optional[KGEventService] = None,
    process_event_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    checkpoint = Path(checkpoint_path)
    checkpoint_data = _load_checkpoint(checkpoint)
    last_paper_task_id = checkpoint_data.get("last_paper_task_id")
    postgres = postgres_client or get_postgres_client()
    events = kg_event_service or get_kg_event_service()
    process_event = process_event_fn or process_kg_event

    candidates = _list_backfill_candidates(
        postgres,
        after_paper_task_id=last_paper_task_id,
        limit=max(int(batch_size), 0),
    )

    processed_ids: List[str] = []
    results: List[Dict[str, Any]] = []
    for candidate in candidates:
        paper_task_id = str(candidate.paper_task_id)
        event = events.create_kg_event(
            request_id=getattr(candidate, "request_id", None),
            paper_task_id=paper_task_id,
            document_id=str(getattr(candidate, "document_id")),
            event_type="paper_completed",
            idempotency_key=f"kg:{_RELEASE_NO}:backfill:{paper_task_id}",
            payload={"release_no": _RELEASE_NO, "trigger": "backfill"},
        )
        results.append(process_event(str(event.event_id)))
        processed_ids.append(paper_task_id)
        _write_checkpoint(checkpoint, last_paper_task_id=paper_task_id)

    return {
        "processed": len(processed_ids),
        "processed_paper_task_ids": processed_ids,
        "checkpoint_path": str(checkpoint),
        "results": results,
    }
