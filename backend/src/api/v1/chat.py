"""Chat routes for evidence review conversations."""
from __future__ import annotations

import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session, get_phase4_factory
from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    ChatMessageResponse,
    ChatSessionResponse,
)

router = APIRouter()


class CreateSessionRequest(BaseModel):
    processing_run_id: UUID
    user_id: UUID | None = None


class AppendMessageRequest(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    evidence_id: UUID | None = None
    entity_id: UUID | None = None


@router.post("/sessions")
async def create_session(
    req: CreateSessionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ChatSessionResponse:
    """Create a new chat session."""
    factory = get_phase4_factory()
    service = factory.create_chat_service(session)
    return await service.create_session(
        processing_run_id=req.processing_run_id,
        user_id=req.user_id,
    )


@router.get("/sessions/{processing_run_id}")
async def list_sessions(
    processing_run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[ChatSessionResponse]:
    """List all chat sessions for a processing run."""
    factory = get_phase4_factory()
    service = factory.create_chat_service(session)
    return await service.list_sessions(processing_run_id=processing_run_id)


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: UUID,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
) -> list[ChatMessageResponse]:
    """List messages in a chat session."""
    factory = get_phase4_factory()
    service = factory.create_chat_service(session)
    return await service.list_messages(session_id=session_id, limit=limit)


@router.post("/sessions/{session_id}/messages")
async def append_message(
    session_id: UUID,
    req: AppendMessageRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ChatMessageResponse:
    """Append a message to a chat session."""
    factory = get_phase4_factory()
    service = factory.create_chat_service(session)
    msg = await service.append_message(
        session_id=session_id,
        role=req.role,
        content=req.content,
        evidence_id=req.evidence_id,
        entity_id=req.entity_id,
    )

    if req.role == "user":
        reply = await service.generate_reply(
            session_id=session_id,
            user_message=req.content,
            evidence_id=req.evidence_id,
        )
        if reply:
            await service.append_message(
                session_id=session_id,
                role="assistant",
                content=reply,
                evidence_id=req.evidence_id,
                entity_id=req.entity_id,
            )

    return msg


@router.get("/sessions/{session_id}/stream")
async def stream_reply(
    session_id: UUID,
    user_message: str,
    evidence_id: UUID | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Stream AI reply as SSE events with 15-second keepalive heartbeat."""
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
