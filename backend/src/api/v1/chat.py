"""Chat routes for evidence review conversations."""
from __future__ import annotations

import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from src.api.auth import require_api_key
from src.api.deps import get_db_session, get_phase4_factory
from src.api.rate_limit import limiter
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    ChatMessageResponse,
    ChatSessionResponse,
)

router = APIRouter()


class CreateSessionRequest(BaseModel):
    processing_run_id: UUID | None = None
    user_id: UUID | None = None


class AppendMessageRequest(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    evidence_id: UUID | None = None
    entity_id: UUID | None = None
    auto_reply: bool = False


@router.post("/sessions", response_model=ChatSessionResponse)
@limiter.limit("30/minute")
async def create_session(
    request: Request,
    body: CreateSessionRequest,
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> ChatSessionResponse:
    """Create a new chat session."""
    factory = get_phase4_factory()
    service = factory.create_chat_service(session)
    return await service.create_session(
        processing_run_id=body.processing_run_id,
        user_id=body.user_id,
    )


@router.get("/sessions/{processing_run_id}", response_model=list[ChatSessionResponse])
async def list_sessions(
    processing_run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[ChatSessionResponse]:
    """List all chat sessions for a processing run."""
    factory = get_phase4_factory()
    service = factory.create_chat_service(session)
    return await service.list_sessions(processing_run_id=processing_run_id)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def list_messages(
    session_id: UUID,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
) -> list[ChatMessageResponse]:
    """List messages in a chat session."""
    factory = get_phase4_factory()
    service = factory.create_chat_service(session)
    return await service.list_messages(session_id=session_id, limit=limit)


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
@limiter.limit("60/minute")
async def append_message(
    request: Request,
    session_id: UUID,
    body: AppendMessageRequest,
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> ChatMessageResponse:
    """Append a message to a chat session."""
    factory = get_phase4_factory()
    service = factory.create_chat_service(session)
    msg = await service.append_message(
        session_id=session_id,
        role=body.role,
        content=body.content,
        evidence_id=body.evidence_id,
        entity_id=body.entity_id,
    )

    if body.role == "user" and body.auto_reply:
        reply = await service.generate_reply(
            session_id=session_id,
            user_message=body.content,
            evidence_id=body.evidence_id,
        )
        if reply:
            await service.append_message(
                session_id=session_id,
                role="assistant",
                content=reply,
                evidence_id=body.evidence_id,
                entity_id=body.entity_id,
            )

    return msg


@router.get("/sessions/{session_id}/stream")
@limiter.limit("10/minute")
async def stream_reply(
    request: Request,
    session_id: UUID,
    user_message: str,
    evidence_id: UUID | None = None,
    session: AsyncSession = Depends(get_db_session),
    _api_key: str | None = Depends(require_api_key),
) -> StreamingResponse:
    """Stream AI reply as SSE events with 15-second keepalive heartbeat.

    Note: if the client disconnects mid-stream, the generator is closed
    before the assistant reply is appended. The user message (flushed by
    append_message) commits during dependency cleanup, but the assistant
    reply is lost. This is a known FastAPI StreamingResponse limitation.
    """
    factory = get_phase4_factory()
    service = factory.create_chat_service(session)

    async def event_generator():
        async def _stream_with_heartbeat():
            async for event in service.stream_reply(
                session_id=session_id,
                user_message=user_message,
                evidence_id=evidence_id,
            ):
                yield f"data: {json.dumps(event)}\n\n"

            yield ": keepalive\n\n"

        async for chunk in _stream_with_heartbeat():
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
