"""Chat / LLM API route — VLM-backed extraction endpoint."""

from __future__ import annotations

import base64
import io
import re
import uuid
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException
from PIL import Image

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


def _extract_first_image(messages: list[ChatMessage]) -> Image.Image | None:
    """Extract first image from multimodal-style messages."""
    for msg in messages:
        # Content is a string in ChatRequest, check for inline base64
        if msg.content and msg.content.startswith("data:image/"):
            match = re.match(r"data:image/\w+;base64,(.+)", msg.content)
            if match:
                img_bytes = base64.b64decode(match.group(1))
                return Image.open(io.BytesIO(img_bytes))
    return None


@router.post("/v1/chat/completions_legacy", response_model=ChatResponse)
def chat_completions(req: ChatRequest):
    if _service is None or not _service.ready:
        raise HTTPException(status_code=503, detail="VLM service not available")

    image = _extract_first_image(req.messages)
    if image is None:
        raise HTTPException(status_code=400, detail="No image found in messages. Use the /v1/chat/completions VLM endpoint with multimodal content.")

    result = _service.infer(image=image)
    reply = result.get("full_markdown", "")

    return ChatResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
        model=req.model or _service.model_id,
        choices=[ChatChoice(message=ChatMessage(role="assistant", content=reply))],
        usage=ChatUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
    )
