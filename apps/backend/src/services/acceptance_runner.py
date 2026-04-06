# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportDeprecated=false

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.infrastructure.postgres import get_postgres_client
from src.services.release_reporting import (
    AcceptanceManifest,
    AcceptancePaperRecord,
    load_acceptance_manifest,
    save_acceptance_manifest,
)


def _as_iso_datetime(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, str):
        return value
    return None


def _lookup_acceptance_row(postgres: Any, paper: AcceptancePaperRecord) -> Any:
    lookup_by_paper_id = getattr(postgres, 'get_acceptance_result_by_paper_id', None)
    if callable(lookup_by_paper_id):
        row = lookup_by_paper_id(paper.paper_id)
        if row is not None:
            return row

    if paper.paper_task_id:
        get_paper_task = getattr(postgres, 'get_paper_task', None)
        if callable(get_paper_task):
            return get_paper_task(paper.paper_task_id)

    return None


def sync_manifest_from_postgres(
    manifest_path: str | Path,
    *,
    postgres: Any = None,
    write: bool = False,
) -> AcceptanceManifest:
    manifest = load_acceptance_manifest(manifest_path)
    pg = postgres or get_postgres_client()

    for paper in manifest.papers:
        row = _lookup_acceptance_row(pg, paper)
        if row is None:
            continue
        paper_task_id = getattr(row, 'paper_task_id', None)
        if paper_task_id is not None:
            paper.paper_task_id = str(paper_task_id)
        status = getattr(row, 'status', None)
        if status:
            paper.status = str(status)
        error_code = getattr(row, 'error_code', None)
        paper.error_code = str(error_code) if error_code is not None else None
        duration_seconds = getattr(row, 'processing_duration_seconds', None)
        if duration_seconds is not None:
            paper.duration_seconds = float(duration_seconds)
        title = getattr(row, 'title', None) or getattr(row, 'original_filename', None)
        if title is not None:
            paper.title = str(title)
        worker_started_at = getattr(row, 'worker_started_at', None) or getattr(row, 'created_at', None)
        completed_at = getattr(row, 'completed_at', None) or getattr(row, 'updated_at', None)
        paper.worker_started_at = _as_iso_datetime(worker_started_at)
        paper.completed_at = _as_iso_datetime(completed_at)

    if write:
        save_acceptance_manifest(manifest_path, manifest)
    return manifest


def run_acceptance_set(
    manifest: AcceptanceManifest,
    *,
    enqueue: Callable[[AcceptancePaperRecord], Any],
) -> Dict[str, Any]:
    queued_count = 0
    queued_paper_ids: list[str] = []

    for paper in manifest.papers:
        if paper.paper_task_id or paper.status in {'success', 'failed'}:
            continue
        enqueue_result = enqueue(paper)
        if isinstance(enqueue_result, dict):
            paper_task_id = enqueue_result.get('paper_task_id')
        else:
            paper_task_id = getattr(enqueue_result, 'paper_task_id', enqueue_result)
        if paper_task_id:
            paper.paper_task_id = str(paper_task_id)
        paper.status = 'queued'
        queued_count += 1
        queued_paper_ids.append(paper.paper_id)

    return {
        'queued_count': queued_count,
        'queued_paper_ids': queued_paper_ids,
    }
