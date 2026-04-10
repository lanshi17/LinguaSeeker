# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportDeprecated=false

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.infrastructure.postgres import get_postgres_client
from src.services.release_reporting import (
    AcceptanceManifest,
    AcceptancePaperRecord,
    calculate_release_gate_summary,
    load_acceptance_manifest,
    normalize_manifest_notes,
    save_acceptance_manifest,
)


def _as_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    return None


def _as_iso_datetime(value: Any) -> Optional[str]:
    parsed = _as_datetime(value)
    if parsed is not None:
        return parsed.isoformat()
    if isinstance(value, str):
        return value
    return None


def _derive_latest_attempt_window(
    postgres: Any,
    paper_task_id: Any,
    *,
    fallback_completed_at: Any,
) -> tuple[Optional[datetime], Optional[datetime]]:
    if paper_task_id is None:
        return (None, None)

    get_latest_log = getattr(postgres, 'get_latest_paper_task_log', None)
    if not callable(get_latest_log):
        return (None, None)

    latest_pipeline_log = get_latest_log(str(paper_task_id), node='pipeline')
    started_at = _as_datetime(getattr(latest_pipeline_log, 'created_at', None))

    completed_at = _as_datetime(fallback_completed_at)
    if completed_at is None:
        latest_log = get_latest_log(str(paper_task_id))
        completed_at = _as_datetime(getattr(latest_log, 'created_at', None))

    if started_at is None or completed_at is None:
        return (None, None)
    if completed_at < started_at:
        return (None, None)
    return (started_at, completed_at)


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


def _paper_needs_postgres_refresh(paper: AcceptancePaperRecord) -> bool:
    if paper.status not in {'success', 'failed'}:
        return True
    if not paper.paper_task_id:
        return True
    if paper.duration_seconds is not None:
        return False
    return not (paper.worker_started_at and paper.completed_at)


def sync_manifest_from_postgres(
    manifest_path: str | Path,
    *,
    postgres: Any = None,
    write: bool = False,
) -> AcceptanceManifest:
    manifest = load_acceptance_manifest(manifest_path)
    pg = postgres

    for paper in manifest.papers:
        if not _paper_needs_postgres_refresh(paper):
            continue
        if pg is None:
            pg = get_postgres_client()
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
        worker_started_at = getattr(row, 'worker_started_at', None) or getattr(row, 'created_at', None)
        completed_at = getattr(row, 'completed_at', None) or getattr(row, 'updated_at', None)
        if duration_seconds is not None:
            paper.duration_seconds = float(duration_seconds)
        else:
            latest_started_at, latest_completed_at = _derive_latest_attempt_window(
                pg,
                paper_task_id or paper.paper_task_id,
                fallback_completed_at=completed_at,
            )
            if latest_started_at is not None and latest_completed_at is not None:
                worker_started_at = latest_started_at
                completed_at = latest_completed_at
                paper.duration_seconds = max(
                    (latest_completed_at - latest_started_at).total_seconds(),
                    0.0,
                )
        title = getattr(row, 'title', None) or getattr(row, 'original_filename', None)
        if title is not None:
            paper.title = str(title)
        paper.worker_started_at = _as_iso_datetime(worker_started_at)
        paper.completed_at = _as_iso_datetime(completed_at)

    summary = calculate_release_gate_summary(manifest)
    manifest.notes = normalize_manifest_notes(manifest, summary)

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
            request_id = enqueue_result.get('request_id')
            paper_task_id = enqueue_result.get('paper_task_id')
        else:
            request_id = getattr(enqueue_result, 'request_id', None)
            paper_task_id = getattr(enqueue_result, 'paper_task_id', enqueue_result)
        if request_id:
            paper.request_id = str(request_id)
        if paper_task_id:
            paper.paper_task_id = str(paper_task_id)
        paper.status = 'queued'
        queued_count += 1
        queued_paper_ids.append(paper.paper_id)

    return {
        'queued_count': queued_count,
        'queued_paper_ids': queued_paper_ids,
    }
