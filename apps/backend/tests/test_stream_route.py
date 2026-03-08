from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from src.service.dtos import PaperTaskItemResponse, TaskRequestStatusResponse, TaskStatusResponse
from src.service.enum import TaskStatus, WorkflowStatus


def test_stream_route_emits_terminal_status(monkeypatch) -> None:
    from src.api.routes import stream as stream_route

    monkeypatch.setattr(
        stream_route,
        "get_task_status",
        lambda task_id: TaskStatusResponse(
            task_id=task_id,
            status=TaskStatus.success,
            workflow_status=WorkflowStatus.completed,
            workflow_status_description="done",
            progress_percentage=None,
            processing_steps=None,
            parsing_metadata=None,
            paper_task_id=None,
            document_id=None,
            file_size_bytes=None,
            processing_duration_seconds=None,
            created_at=None,
            updated_at=None,
            error=None,
            error_details=None,
        ),
    )

    client = TestClient(app)
    with client.websocket_connect("/api/v1/stream/task-1") as websocket:
        payload = websocket.receive_json()

    assert payload["task_id"] == "task-1"
    assert payload["status"] == TaskStatus.success.value
    assert payload["workflow_status"] == WorkflowStatus.completed.value


def test_stream_route_emits_progress_then_terminal(monkeypatch) -> None:
    from src.api.routes import stream as stream_route

    statuses = iter(
        [
            TaskStatusResponse(
                task_id="task-2",
                status=TaskStatus.started,
                workflow_status=WorkflowStatus.processing_pdf,
                workflow_status_description="processing",
                progress_percentage=25.0,
                processing_steps=None,
                parsing_metadata=None,
                paper_task_id=None,
                document_id=None,
                file_size_bytes=None,
                processing_duration_seconds=None,
                created_at=None,
                updated_at=None,
                error=None,
                error_details=None,
            ),
            TaskStatusResponse(
                task_id="task-2",
                status=TaskStatus.success,
                workflow_status=WorkflowStatus.completed,
                workflow_status_description="done",
                progress_percentage=100.0,
                processing_steps=None,
                parsing_metadata=None,
                paper_task_id=None,
                document_id=None,
                file_size_bytes=None,
                processing_duration_seconds=None,
                created_at=None,
                updated_at=None,
                error=None,
                error_details=None,
            ),
        ]
    )

    async def fast_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(stream_route, "STREAM_POLL_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(stream_route.asyncio, "sleep", fast_sleep)
    monkeypatch.setattr(stream_route, "get_task_status", lambda task_id: next(statuses))

    client = TestClient(app)
    with client.websocket_connect("/api/v1/stream/task-2") as websocket:
        first = websocket.receive_json()
        second = websocket.receive_json()

    assert first["status"] == TaskStatus.started.value
    assert first["progress_percentage"] == 25.0
    assert second["status"] == TaskStatus.success.value
    assert second["progress_percentage"] == 100.0


def test_request_stream_route_emits_terminal_status(monkeypatch) -> None:
    from src.api.routes import stream as stream_route

    monkeypatch.setattr(
        stream_route,
        "get_task_request_status",
        lambda request_id: TaskRequestStatusResponse(
            request_id=request_id,
            status="completed",
            papers=[
                PaperTaskItemResponse(
                    paper_task_id="paper-1",
                    filename="paper.pdf",
                    status="completed",
                    error_code=None,
                    duplicate_of=None,
                    document_id="doc-1",
                    celery_task_id="task-1",
                )
            ],
        ),
    )

    client = TestClient(app)
    with client.websocket_connect("/api/v1/stream/requests/request-1") as websocket:
        payload = websocket.receive_json()

    assert payload["request_id"] == "request-1"
    assert payload["status"] == "completed"
    assert payload["papers"][0]["paper_task_id"] == "paper-1"


def test_request_stream_route_emits_progress_then_terminal(monkeypatch) -> None:
    from src.api.routes import stream as stream_route

    statuses = iter(
        [
            TaskRequestStatusResponse(
                request_id="request-2",
                status="processing",
                papers=[
                    PaperTaskItemResponse(
                        paper_task_id="paper-2",
                        filename="paper.pdf",
                        status="running",
                        error_code=None,
                        duplicate_of=None,
                        document_id=None,
                        celery_task_id="task-2",
                    )
                ],
            ),
            TaskRequestStatusResponse(
                request_id="request-2",
                status="completed",
                papers=[
                    PaperTaskItemResponse(
                        paper_task_id="paper-2",
                        filename="paper.pdf",
                        status="completed",
                        error_code=None,
                        duplicate_of=None,
                        document_id="doc-2",
                        celery_task_id="task-2",
                    )
                ],
            ),
        ]
    )

    async def fast_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(stream_route, "STREAM_POLL_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(stream_route.asyncio, "sleep", fast_sleep)
    monkeypatch.setattr(stream_route, "get_task_request_status", lambda request_id: next(statuses))

    client = TestClient(app)
    with client.websocket_connect("/api/v1/stream/requests/request-2") as websocket:
        first = websocket.receive_json()
        second = websocket.receive_json()

    assert first["status"] == "processing"
    assert first["papers"][0]["status"] == "running"
    assert second["status"] == "completed"
    assert second["papers"][0]["document_id"] == "doc-2"
