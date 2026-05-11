"""VLM / MinerU extraction API route — OpenAI-compatible multimodal endpoint."""

from __future__ import annotations

import base64
import io
import re
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException
from PIL import Image

from app.models import (
    VLMExtractRequest,
    VLMExtractResponse,
    VLMPageContent,
    VLMDocumentMetadata,
    VLMUsage,
)
from app.utils.logger import get_logger

if TYPE_CHECKING:
    from app.domain.llm import LLMService

logger = get_logger()
router = APIRouter(tags=["vlm"])

_service: LLMService | None = None


def bind(service: LLMService) -> None:
    global _service
    _service = service


def _extract_images_from_messages(messages: list[dict]) -> list[Image.Image]:
    """Extract PIL Images from OpenAI multimodal message format."""
    images = []
    for msg in messages:
        content = msg.get("content", "")
        if not isinstance(content, list):
            continue
        for part in content:
            if part.get("type") != "image_url":
                continue
            url = part["image_url"]["url"]
            if url.startswith("data:"):
                match = re.match(r"data:image/\w+;base64,(.+)", url)
                if match:
                    img_bytes = base64.b64decode(match.group(1))
                    images.append(Image.open(io.BytesIO(img_bytes)))
            else:
                raise HTTPException(status_code=400, detail="Only base64 data URIs are supported for image input.")
    return images


def _build_pages(pages_data: list[dict]) -> list[VLMPageContent]:
    """Convert raw page dicts to VLMPageContent list."""
    pages = []
    for i, page in enumerate(pages_data, start=1):
        page_number = page.get("page_number", i)
        pages.append(VLMPageContent(
            page_number=page_number,
            markdown=page.get("markdown", ""),
            figures=page.get("figures", []),
            tables=page.get("tables", []),
        ))
    return pages


@router.post("/v1/chat/completions", response_model=VLMExtractResponse)
def chat_completions(req: VLMExtractRequest):
    """OpenAI-compatible multimodal extraction endpoint."""
    if _service is None or not _service.ready:
        raise HTTPException(status_code=503, detail="VLM service not available. Configure VLM_MODEL_ID to enable.")

    images = _extract_images_from_messages(req.messages)
    if not images:
        raise HTTPException(status_code=400, detail="No image found in messages. Provide an image via image_url content part.")

    result = _service.infer(image=images[0])

    metadata = result.get("metadata", {})
    pages_data = result.get("pages", [])

    return VLMExtractResponse(
        id=result.get("id", ""),
        model=req.model or _service.model_id,
        metadata=VLMDocumentMetadata(
            total_pages=metadata.get("total_pages", len(pages_data)),
            title=metadata.get("title"),
            authors=metadata.get("authors", []),
            abstract_text=metadata.get("abstract_text"),
        ),
        pages=_build_pages(pages_data),
        full_markdown=result.get("full_markdown", ""),
        usage=VLMUsage(),
    )
