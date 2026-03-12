import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from src.api.routes.task import get_task_request_status, get_task_status
from src.services.enum import TaskStatus

router = APIRouter(prefix="/stream", tags=["Stream"])

STREAM_POLL_INTERVAL_SECONDS = 1.0
TERMINAL_TASK_STATUSES = {
    TaskStatus.success,
    TaskStatus.failure,
    TaskStatus.revoked,
}
TERMINAL_REQUEST_STATUSES = {"completed", "failed", "success", "partial_success"}


@router.websocket("/{task_id}")
async def stream_task_status(websocket: WebSocket, task_id: str) -> None:
    await websocket.accept()
    last_payload = None

    try:
        while True:
            status = get_task_status(task_id)
            payload = status.model_dump(mode="json")

            if payload != last_payload:
                await websocket.send_json(payload)
                last_payload = payload

            if status.status in TERMINAL_TASK_STATUSES:
                break

            await asyncio.sleep(STREAM_POLL_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        return
    except HTTPException as exc:
        await websocket.send_json({"task_id": task_id, "status": "error", "detail": exc.detail})
        await websocket.close(code=1011)


@router.websocket("/requests/{request_id}")
async def stream_request_status(websocket: WebSocket, request_id: str) -> None:
    await websocket.accept()
    last_payload = None

    try:
        while True:
            status = get_task_request_status(request_id)
            payload = status.model_dump(mode="json")

            if payload != last_payload:
                await websocket.send_json(payload)
                last_payload = payload

            if str(status.status).lower() in TERMINAL_REQUEST_STATUSES:
                break

            await asyncio.sleep(STREAM_POLL_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        return
    except HTTPException as exc:
        await websocket.send_json(
            {"request_id": request_id, "status": "error", "detail": exc.detail}
        )
        await websocket.close(code=1011)


__all__ = ["router"]
