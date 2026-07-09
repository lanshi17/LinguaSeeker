"""Chat routes for evidence review conversations."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from src.api.auth import get_current_account
from src.api.deps import get_db_session, get_phase4_factory
from src.api.rate_limit import limiter
from src.api.wiring import get_local_parser
from src.core.auth.contracts import AuthContext
from src.core.config import get_config
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
    account: AuthContext = Depends(get_current_account),
) -> ChatSessionResponse:
    """Create a new chat session."""
    factory = get_phase4_factory()
    service = factory.create_chat_service(session)
    chat_session = await service.create_session(
        processing_run_id=body.processing_run_id,
        user_id=account.owner_user_id,
    )
    await session.commit()
    return chat_session


@router.get("/sessions/{processing_run_id}", response_model=list[ChatSessionResponse])
async def list_sessions(
    processing_run_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    account: AuthContext = Depends(get_current_account),
) -> list[ChatSessionResponse]:
    """List all chat sessions for a processing run."""
    factory = get_phase4_factory()
    service = factory.create_chat_service(session)
    return await service.list_sessions(processing_run_id=processing_run_id, owner_user_id=account.owner_user_id)


@router.get("/session-details/{session_id}", response_model=ChatSessionResponse)
async def get_session(
    session_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    account: AuthContext = Depends(get_current_account),
) -> ChatSessionResponse:
    """Fetch a single chat session by id."""
    factory = get_phase4_factory()
    service = factory.create_chat_service(session)
    return await service.get_session(session_id=session_id, owner_user_id=account.owner_user_id)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def list_messages(
    session_id: UUID,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
    account: AuthContext = Depends(get_current_account),
) -> list[ChatMessageResponse]:
    """List messages in a chat session."""
    factory = get_phase4_factory()
    service = factory.create_chat_service(session)
    return await service.list_messages(session_id=session_id, limit=limit, owner_user_id=account.owner_user_id)


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
@limiter.limit("60/minute")
async def append_message(
    request: Request,
    session_id: UUID,
    body: AppendMessageRequest,
    session: AsyncSession = Depends(get_db_session),
    account: AuthContext = Depends(get_current_account),
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
        owner_user_id=account.owner_user_id,
    )

    if body.role == "user" and body.auto_reply:
        reply = await service.generate_reply(
            session_id=session_id,
            user_message=body.content,
            evidence_id=body.evidence_id,
            owner_user_id=account.owner_user_id,
            reviewer_id=account.owner_user_id,
        )
        if reply:
            await service.append_message(
                session_id=session_id,
                role="assistant",
                content=reply,
                evidence_id=body.evidence_id,
                entity_id=body.entity_id,
                owner_user_id=account.owner_user_id,
            )

    await session.commit()
    if body.role == "user":
        factory.schedule_session_title_generation(
            session_id=session_id,
            user_message=body.content,
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
    account: AuthContext = Depends(get_current_account),
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
        async for event in service.stream_reply(
            session_id=session_id,
            user_message=user_message,
            evidence_id=evidence_id,
            owner_user_id=account.owner_user_id,
            reviewer_id=account.owner_user_id,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


class ChatFileParseResponse(BaseModel):
    """Response for PDF file parsing in chat context."""

    ok: bool
    filename: str
    content: str = ""
    page_count: int = 0
    error: str = ""


_PDF_MAGIC = b"%PDF"
_MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/files/parse", response_model=ChatFileParseResponse)
@limiter.limit("10/minute")
async def parse_chat_file(
    request: Request,
    file: UploadFile = File(...),
    _account: AuthContext = Depends(get_current_account),
) -> ChatFileParseResponse:
    """Parse an uploaded PDF for chat context.

    Accepts a PDF file, validates it, and parses it using the MinerU local
    parser. Returns the parsed markdown content ready for insertion into a
    chat message.
    """
    # ── Validate file type ──
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # ── Read and validate magic bytes ──
    content = await file.read()
    if len(content) > _MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {_MAX_UPLOAD_SIZE // (1024 * 1024)} MB",
        )

    if not content.startswith(_PDF_MAGIC):
        raise HTTPException(status_code=400, detail="File is not a valid PDF")

    # ── Use wired parser singleton, fall back to fresh instance ──
    parser = get_local_parser()
    if parser is None:
        from src.core.ingest_and_digitize_data.parse_document.local.parser import (
            MinerULocalParser,
        )

        cfg = get_config()
        parser = MinerULocalParser(
            parse_url=cfg.parse_document.mineru_local_parse_url,
            model_id=cfg.parse_document.mineru_local_model_id,
            timeout=cfg.parse_document.mineru_local_timeout,
            dpi=cfg.parse_document.mineru_local_dpi,
            api_key=cfg.inference_api_key,
        )

    # ── Save to temp file for MinerU parsing ──
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        result = await parser.parse(str(tmp_path))

        return ChatFileParseResponse(
            ok=True,
            filename=file.filename,
            content=result.full_markdown,
            page_count=result.total_pages,
        )

    except Exception as exc:
        logger.warning("Chat file parse failed for {}: {}", file.filename, exc)
        return ChatFileParseResponse(
            ok=False,
            filename=file.filename,
            error=f"Failed to parse PDF: {exc}",
        )

    finally:
        # ── Always clean up the temp file ──
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
