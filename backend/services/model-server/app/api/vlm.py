"""VLM / MinerU extraction API route — OpenAI-compatible multimodal endpoint."""

from __future__ import annotations

import base64
import io
import re
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException
from PIL import Image
from pydantic import ValidationError

from app.models import (
    VLMExtractRequest,
    VLMExtractResponse,
    VLMMessage,
    VLMPageContent,
    VLMDocumentMetadata,
    VLMUsage,
    VLMFigurePosition,
    VLMTableStructure,
)
from app.utils.logger import get_logger

from app.domain.vlm import VLMInferenceError

if TYPE_CHECKING:
    from app.domain.vlm import VLMService

logger = get_logger()
router = APIRouter(tags=["vlm"])

_service: VLMService | None = None


def bind(service: VLMService) -> None:
    global _service
    _service = service


def _extract_images_from_messages(messages: list[VLMMessage]) -> list[Image.Image]:
    """Extract PIL Images from OpenAI multimodal message format."""
    images = []
    for msg in messages:
        if not isinstance(msg.content, list):
            continue
        for part in msg.content:
            if part.type != "image_url" or part.image_url is None:
                continue
            url = part.image_url.url
            if url.startswith("data:"):
                match = re.match(r"data:image/\w+;base64,(.+)", url)
                if match:
                    img_bytes = base64.b64decode(match.group(1))
                    images.append(Image.open(io.BytesIO(img_bytes)))
            else:
                raise HTTPException(status_code=400, detail="Only base64 data URIs are supported for image input.")
    return images


def _parse_figure(raw: dict) -> VLMFigurePosition:
    """Parse a raw dict into VLMFigurePosition with validation."""
    try:
        return VLMFigurePosition.model_validate(raw)
    except ValidationError as exc:
        logger.warning("Malformed figure data: {raw} — {exc}", raw=raw, exc=exc)
        raise HTTPException(status_code=502, detail=f"Upstream returned malformed figure data: {exc}") from exc


def _parse_table(raw: dict) -> VLMTableStructure:
    """Parse a raw dict into VLMTableStructure with validation."""
    try:
        return VLMTableStructure.model_validate(raw)
    except ValidationError as exc:
        logger.warning("Malformed table data: {raw} — {exc}", raw=raw, exc=exc)
        raise HTTPException(status_code=502, detail=f"Upstream returned malformed table data: {exc}") from exc


def _build_pages(pages_data: list[dict]) -> list[VLMPageContent]:
    """Convert raw page dicts to VLMPageContent list with explicit validation."""
    pages = []
    for i, page in enumerate(pages_data, start=1):
        page_number = page.get("page_number", i)
        figures = [_parse_figure(f) for f in page.get("figures", [])]
        tables = [_parse_table(t) for t in page.get("tables", [])]
        pages.append(VLMPageContent(
            page_number=page_number,
            markdown=page.get("markdown", ""),
            figures=figures,
            tables=tables,
        ))
    return pages


@router.post("/v1/chat/completions", response_model=VLMExtractResponse)
def chat_completions(req: VLMExtractRequest):
    """OpenAI-compatible multimodal extraction endpoint."""
    if _service is None:
        raise HTTPException(status_code=503, detail="VLM service not available. Configure VLM_MODEL_ID to enable.")

    images = _extract_images_from_messages(req.messages)
    if not images:
        raise HTTPException(status_code=400, detail="No image found in messages. Provide an image via image_url content part.")
    if len(images) > 1:
        raise HTTPException(status_code=400, detail="Multiple images not supported. Provide exactly one image.")

    try:
        result = _service.infer(image=images[0])
    except VLMInferenceError as exc:
        logger.error("VLM inference failed (upstream): {exc}", exc=exc)
        raise HTTPException(status_code=502, detail=f"VLM upstream failure: {exc}") from exc
    except Exception as exc:
        logger.error("VLM inference failed: {exc}", exc=exc)
        raise HTTPException(status_code=500, detail=f"VLM inference failed: {exc}") from exc

    return VLMExtractResponse(
        id=result.id,
        model=req.model or _service.model_id,
        metadata=VLMDocumentMetadata(
            total_pages=result.metadata.get("total_pages", len(result.pages)),
            title=result.metadata.get("title"),
            authors=result.metadata.get("authors", []),
            abstract_text=result.metadata.get("abstract_text"),
        ),
        pages=_build_pages(result.pages),
        full_markdown=result.full_markdown,
        usage=VLMUsage(),
    )
