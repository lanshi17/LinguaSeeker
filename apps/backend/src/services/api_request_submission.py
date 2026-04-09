from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from loguru import logger
from sqlalchemy.exc import IntegrityError

from src.infrastructure.postgres import get_postgres_client


def _normalize_identifiers(raw_identifiers: Any) -> list[str]:
    if isinstance(raw_identifiers, dict):
        items = [f"{key}:{value}" for key, value in raw_identifiers.items()]
    elif isinstance(raw_identifiers, str):
        items = [raw_identifiers]
    elif isinstance(raw_identifiers, list):
        items = raw_identifiers
    else:
        items = []

    identifiers: list[str] = []
    for item in items:
        text = str(item).strip()
        if text:
            identifiers.append(text)
    return identifiers


def _normalize_request_payload(
    request_payload: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    task_form = str(
        request_payload.get("task_form")
        or request_payload.get("task_form_text")
        or ""
    ).strip()
    if not task_form:
        raise ValueError("API acceptance request_payload must include task_form")

    query = str(request_payload.get("query") or "").strip()
    identifiers = _normalize_identifiers(request_payload.get("identifiers"))
    selected_title = str(request_payload.get("selected_title") or "").strip()
    detail_link = str(request_payload.get("detail_link") or "").strip()

    normalized_payload: dict[str, Any] = {
        "query": query,
        "identifiers": identifiers,
    }
    if selected_title:
        normalized_payload["selected_title"] = selected_title
    if detail_link:
        normalized_payload["detail_link"] = detail_link

    return task_form, normalized_payload


def _synthetic_hash_for_api_acceptance(
    source: str,
    request_payload: Mapping[str, Any],
) -> str:
    hash_input = json.dumps(
        {
            "entry": "api",
            "source": str(source).strip().lower(),
            "query": str(request_payload.get("query") or "").strip(),
            "identifiers": list(request_payload.get("identifiers") or []),
            "detail_link": str(request_payload.get("detail_link") or "").strip(),
        },
        sort_keys=True,
    )
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()


def _has_successful_historical_paper(historical_paper: Any) -> bool:
    return (
        historical_paper is not None
        and str(getattr(historical_paper, "status", "")) == "success"
    )


def _create_duplicate_api_paper_entry(
    postgres: Any,
    *,
    request_id: str,
    document_id: str | None,
    original_filename: str,
    file_hash: str,
    historical_paper: Any,
    source: str,
) -> Any:
    paper_entry = postgres.create_paper_task(
        request_id=request_id,
        document_id=document_id,
        original_filename=original_filename,
        file_hash=file_hash,
        status="success",
        error_code="FILE_DUPLICATE",
        duplicate_of=(historical_paper.paper_task_id if historical_paper else None),
    )
    postgres.append_paper_task_log(
        paper_entry.paper_task_id,
        status="success",
        node="dedup",
        error_code="FILE_DUPLICATE",
        message=f"Duplicate api acceptance item detected for {source}",
    )
    return paper_entry


def _get_process_api_paper_task() -> Any:
    from src.services import task_manager as task_manager_module

    task = getattr(task_manager_module, "process_api_paper_task", None)
    if task is None:
        raise NotImplementedError("Task 5 will add process_api_paper_task")
    return task


def submit_api_acceptance_item(
    *,
    source: str,
    request_payload: Mapping[str, Any],
    postgres: Any = None,
    task_handler: Any = None,
) -> dict[str, str]:
    task_form, normalized_payload = _normalize_request_payload(request_payload)
    pg = postgres or get_postgres_client()
    source_name = str(source).strip().lower()
    if not source_name:
        raise ValueError("API acceptance source is required")

    request_entry = pg.create_task_request(
        task_form_text=task_form,
        status="queued",
        metadata={
            "entry": "api",
            "source": source_name,
            "request_payload": normalized_payload,
        },
    )
    request_id = str(request_entry.request_id)

    file_hash = _synthetic_hash_for_api_acceptance(source_name, normalized_payload)
    historical_paper = pg.find_latest_paper_task_by_hash(file_hash)
    existing_document = pg.find_document_by_hash(file_hash)
    original_filename = str(
        normalized_payload.get("selected_title")
        or normalized_payload.get("query")
        or (normalized_payload.get("identifiers") or [f"{source_name}-paper"])[0]
    )

    if existing_document is not None and _has_successful_historical_paper(
        historical_paper
    ):
        paper_entry = _create_duplicate_api_paper_entry(
            pg,
            request_id=request_id,
            document_id=(
                str(getattr(existing_document, "document_id", "")) or None
            ),
            original_filename=original_filename,
            file_hash=file_hash,
            historical_paper=historical_paper,
            source=source_name,
        )
        pg.refresh_task_request_status(request_id)
        return {
            "request_id": request_id,
            "paper_task_id": str(paper_entry.paper_task_id),
        }

    try:
        document = pg.create_document(
            title=original_filename,
            original_filename=original_filename,
            local_path=normalized_payload.get("detail_link"),
            file_hash=file_hash,
            status="queued",
            summary=f"Queued api acceptance source: {source_name}",
        )
    except IntegrityError as exc:
        logger.warning("API acceptance document create conflict for {}: {}", source_name, exc)
        existing_document = pg.find_document_by_hash(file_hash)
        historical_paper = pg.find_latest_paper_task_by_hash(file_hash)
        if existing_document is not None and _has_successful_historical_paper(
            historical_paper
        ):
            paper_entry = _create_duplicate_api_paper_entry(
                pg,
                request_id=request_id,
                document_id=(
                    str(getattr(existing_document, "document_id", "")) or None
                ),
                original_filename=original_filename,
                file_hash=file_hash,
                historical_paper=historical_paper,
                source=source_name,
            )
        else:
            paper_entry = pg.create_paper_task(
                request_id=request_id,
                document_id=(
                    str(getattr(existing_document, "document_id", "")) or None
                ),
                original_filename=original_filename,
                file_hash=file_hash,
                status="failed",
                error_code="INTERNAL_ERROR",
            )
            pg.append_paper_task_log(
                str(paper_entry.paper_task_id),
                status="failed",
                node="document",
                error_code="INTERNAL_ERROR",
                message="Concurrent api document creation conflict",
            )
        pg.refresh_task_request_status(request_id)
        return {
            "request_id": request_id,
            "paper_task_id": str(paper_entry.paper_task_id),
        }

    document_id = str(document.document_id)
    paper_entry = pg.create_paper_task(
        request_id=request_id,
        document_id=document_id,
        original_filename=original_filename,
        file_hash=file_hash,
        status="queued",
    )
    paper_task_id = str(paper_entry.paper_task_id)
    pg.append_paper_task_log(
        paper_task_id,
        status="queued",
        node="acquisition",
        message=f"API acceptance paper queued via {source_name}",
        payload={"source": source_name, **normalized_payload},
    )

    task = task_handler or _get_process_api_paper_task()
    async_result = task.apply_async(
        args=[
            source_name,
            normalized_payload,
            document_id,
            paper_task_id,
            request_id,
        ]
    )
    pg.update_paper_task(paper_task_id, celery_task_id=async_result.id)
    pg.refresh_task_request_status(request_id)

    return {
        "request_id": request_id,
        "paper_task_id": paper_task_id,
    }
