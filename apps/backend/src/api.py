import asyncio
import base64
import itertools
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, HttpUrl

router = APIRouter()


class UploadPdfPayload(BaseModel):
    filename: Optional[str] = None
    content_base64: Optional[str] = None
    file_url: Optional[HttpUrl] = None


class FetchByPmidPayload(BaseModel):
    pmid: str


class FetchByDoiPayload(BaseModel):
    doi: str


class TaskResponse(BaseModel):
    task_id: int
    task_type: str
    status: str
    progress: int
    retries: int
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]


_task_id_seq = itertools.count(1)
_tasks: Dict[int, Dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _create_task(task_type: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    task_id = next(_task_id_seq)
    now = _now_iso()
    task = {
        "task_id": task_id,
        "task_type": task_type,
        "status": "queued",
        "progress": 0,
        "retries": 0,
        "created_at": now,
        "updated_at": now,
        "metadata": metadata,
    }
    _tasks[task_id] = task
    return task


def _get_task_or_404(task_id: int) -> Dict[str, Any]:
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("/api/v1/pdf/upload", response_model=TaskResponse)
async def upload_pdf(payload: UploadPdfPayload):
    if not (payload.content_base64 or payload.file_url):
        raise HTTPException(status_code=400, detail="content_base64 or file_url is required")

    size_bytes = None
    if payload.content_base64:
        try:
            size_bytes = len(base64.b64decode(payload.content_base64, validate=True))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid base64 content") from exc

    metadata = {
        "filename": payload.filename,
        "file_url": str(payload.file_url) if payload.file_url else None,
        "size_bytes": size_bytes,
    }
    task = _create_task("pdf_upload", metadata)
    return TaskResponse(**task)

@router.post("/api/v1/pdf/upload/form", response_model=TaskResponse)
async def upload_pdf_form(file: UploadFile = File(...)):
    content = await file.read()
    metadata = {
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": len(content),
    }
    task = _create_task("pdf_upload_form", metadata)
    return TaskResponse(**task)

@router.post("/api/v1/pdf/fetch-by-pmid", response_model=TaskResponse)
async def fetch_pdf_by_pmid(payload: FetchByPmidPayload):
    metadata = {"pmid": payload.pmid}
    task = _create_task("pdf_fetch_pmid", metadata)
    return TaskResponse(**task)

@router.post("/api/v1/pdf/fetch-by-doi", response_model=TaskResponse)
async def fetch_pdf_by_doi(payload: FetchByDoiPayload):
    metadata = {"doi": payload.doi}
    task = _create_task("pdf_fetch_doi", metadata)
    return TaskResponse(**task)

@router.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int):
    task = _get_task_or_404(task_id)
    return TaskResponse(**task)

@router.delete("/api/v1/tasks/{task_id}")
async def delete_task(task_id: int):
    task = _get_task_or_404(task_id)
    _tasks.pop(task_id, None)
    return {"deleted": True, "task_id": task_id, "task_type": task["task_type"]}

@router.get("/api/v1/tasks/{task_id}/progress")
async def get_task_progress(task_id: int):
    task = _get_task_or_404(task_id)
    return {
        "task_id": task_id,
        "status": task["status"],
        "progress": task["progress"],
        "updated_at": task["updated_at"],
    }

@router.post("/api/v1/tasks/{task_id}/retry", response_model=TaskResponse)
async def retry_task(task_id: int):
    task = _get_task_or_404(task_id)
    task["retries"] += 1
    task["status"] = "queued"
    task["progress"] = 0
    task["updated_at"] = _now_iso()
    return TaskResponse(**task)

@router.websocket("/ws/task/{task_id}/progress")
async def websocket_task_progress(websocket: WebSocket, task_id: int):
    await websocket.accept()
    try:
        task = _get_task_or_404(task_id)
        for progress in (0, 30, 60, 90, 100):
            task["progress"] = progress
            task["status"] = "running" if progress < 100 else "completed"
            task["updated_at"] = _now_iso()
            await websocket.send_json(
                {
                    "task_id": task_id,
                    "status": task["status"],
                    "progress": task["progress"],
                    "updated_at": task["updated_at"],
                }
            )
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return