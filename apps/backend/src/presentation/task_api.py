import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, Path, Query
from loguru import logger
from pydantic import BaseModel, Field

from src.celery_app import celery_app
from src.database.redis_client import list_celery_task_meta
from src.service.tasks import process_pdf_task
from src.service.dtos import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskListItem,
    TaskListResponse,
    TaskStatusResponse,
)
from src.service.enum import TaskStatus

router = APIRouter(prefix="/tasks", tags=["Task"])


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error details.")


def _extract_task_id(meta: Dict[str, Any]) -> str:
    task_id = meta.get("task_id") or meta.get("id")
    if task_id:
        return str(task_id)
    key = meta.get("_key", "")
    if isinstance(key, str) and key.startswith("celery-task-meta-"):
        return key.replace("celery-task-meta-", "", 1)
    return ""


def _parse_date_done(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _build_task_list_item(meta: Dict[str, Any], include_result: bool) -> TaskListItem:
    task_id = _extract_task_id(meta)
    status = TaskStatus.from_celery(str(meta.get("status", "PENDING")))
    date_done = meta.get("date_done")
    result = None
    error = None

    if status == TaskStatus.success and include_result:
        if isinstance(meta.get("result"), dict):
            result = meta.get("result")

    if status == TaskStatus.failure:
        raw_error = meta.get("result")
        if isinstance(raw_error, str):
            error = raw_error
        elif raw_error is not None:
            try:
                error = json.dumps(raw_error, ensure_ascii=False)
            except TypeError:
                error = str(raw_error)

    return TaskListItem(
        task_id=task_id,
        status=status,
        date_done=date_done,
        result=result,
        error=error,
    )


def _task_sort_key(item: TaskListItem) -> datetime:
    parsed = _parse_date_done(item.date_done)
    return parsed or datetime.min.replace(tzinfo=timezone.utc)


@router.post(
    "",
    summary="Create a task",
    description="Create a background processing task for one or more PDF file paths.",
    response_model=TaskCreateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input."},
        503: {"model": ErrorResponse, "description": "Task queue unavailable."},
    },
)
def create_task(payload: TaskCreateRequest) -> TaskCreateResponse:
    if not payload.file_paths:
        raise HTTPException(status_code=400, detail="file_paths is required")

    try:
        logger.debug("Queueing task for file_paths: {} output_root: {}", payload.file_paths, payload.output_root)
        async_result = process_pdf_task.delay(payload.file_paths, payload.output_root)
    except Exception as exc:
        logger.exception("Failed to queue task: {}", exc)
        raise HTTPException(status_code=503, detail="Task queue unavailable")
    logger.debug("Task queued: {} status: {}", async_result.id, async_result.status)
    return TaskCreateResponse(
        task_id=async_result.id,
        status=TaskStatus.from_celery(async_result.status),
    )


@router.get(
    "/{task_id}",
    summary="Get task status",
    description="Fetch task status and result by task id.",
    response_model=TaskStatusResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Task not found."},
    },
)
def get_task_status(
    task_id: str = Path(..., description="Celery task id."),
) -> TaskStatusResponse:
    logger.debug("Fetching task status for task_id: {}", task_id)
    async_result = AsyncResult(task_id, app=celery_app)

    if async_result is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    response = TaskStatusResponse(
        task_id=task_id,
        status=TaskStatus.from_celery(async_result.status),
    )
    if async_result.failed():
        response.error = str(async_result.result)
        logger.debug("Task failed: {} error: {}", task_id, response.error)
    elif async_result.successful():
        response.result = async_result.result
        logger.debug("Task succeeded: {}", task_id)
    else:
        logger.debug("Task status: {} status: {}", task_id, async_result.status)

    return response


@router.get(
    "",
    summary="List tasks",
    description="List recent tasks with optional filtering and pagination.",
    response_model=TaskListResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid query parameters."},
    },
)
def list_tasks(
    limit: int = Query(50, ge=1, le=200, description="Max number of items to return."),
    cursor: int = Query(0, ge=0, description="Scan cursor for pagination."),
    status: Optional[TaskStatus] = Query(None, description="Filter by task status."),
    include_result: bool = Query(False, description="Include result payloads in list items."),
) -> TaskListResponse:
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")

    items: list[TaskListItem] = []
    next_cursor = cursor
    scan_count = min(200, limit)

    while len(items) < limit:
        next_cursor, metas = list_celery_task_meta(cursor=next_cursor, count=scan_count)
        if not metas and next_cursor == 0:
            break

        for meta in metas:
            item = _build_task_list_item(meta, include_result)
            if not item.task_id:
                continue
            if status and item.status != status:
                continue
            items.append(item)
            if len(items) >= limit:
                break

        if next_cursor == 0:
            break

    items.sort(key=_task_sort_key, reverse=True)
    return TaskListResponse(items=items, next_cursor=next_cursor, count=len(items))
