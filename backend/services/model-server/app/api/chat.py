"""Chat / LLM API route — placeholder for future local LLM."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException

from app.models import ChatChoice, ChatMessage, ChatRequest, ChatResponse, ChatUsage
from app.utils.logger import get_logger

if TYPE_CHECKING:
    from app.domain.llm import LLMService

logger = get_logger()
router = APIRouter(tags=["chat"])

_service: LLMService | None = None


def bind(service: LLMService) -> None:
    global _service
    _service = service


@router.post("/v1/chat/completions", response_model=ChatResponse)
def chat_completions(req: ChatRequest):
    if _service is None or not _service.ready:
        raise HTTPException(status_code=503, detail="Local LLM not available")

    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    reply = _service.infer(messages, max_tokens=req.max_tokens, temperature=req.temperature)

    return ChatResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
        model=req.model or _service.model_id,
        choices=[ChatChoice(message=ChatMessage(role="assistant", content=reply))],
        usage=ChatUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
    )
