"""File parse API route -- MinerU PDF parsing endpoint."""

from __future__ import annotations

import asyncio
import base64
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.auth import require_api_key
from app.utils.logger import get_logger

logger = get_logger()

router = APIRouter(tags=["file_parse"])

_service = None


def bind(service) -> None:
    """Inject the DocParseService."""
    global _service
    _service = service


class FileParseResponse(BaseModel):
    """Response model for /file_parse."""

    task_id: str = ""
    status: str = "completed"
    backend: str = "vlm"
    version: str = ""
    results: dict[str, dict[str, Any]] = {}


@router.post("/file_parse", response_model=FileParseResponse)
async def file_parse(
    file: UploadFile = File(...),
    return_content_list: str = Form(default="true"),
    return_images: str = Form(default="true"),
    return_md: str = Form(default="true"),
    _api_key: str | None = Depends(require_api_key),
):
    """Parse an uploaded PDF file using MinerU."""
    if _service is None:
        raise HTTPException(status_code=503, detail="DocParse service not available.")

    if not _service.is_available():
        raise HTTPException(
            status_code=503,
            detail="MinerU is not installed on the model-server. Install with: pip install 'mineru[vlm]'",
        )

    file_name = file.filename or "document.pdf"
    backend = _service.backend
    logger.info("Received file_parse request: {name} (backend={backend})", name=file_name, backend=backend)

    pdf_bytes = await file.read()

    try:
        result = await asyncio.to_thread(_service.parse, pdf_bytes, file_name)
    except Exception as exc:
        logger.error("MinerU parsing failed for {name}: {exc}", name=file_name, exc=exc)
        raise HTTPException(status_code=500, detail=f"MinerU parsing failed: {exc}") from exc

    file_result: dict[str, Any] = {}

    if return_md.lower() == "true":
        file_result["md_content"] = result.md_content

    if return_content_list.lower() == "true":
        file_result["content_list"] = result.content_list

    if return_images.lower() == "true":
        encoded_images = {}
        for img_name, img_bytes in result.images.items():
            suffix = img_name.rsplit(".", 1)[-1].lower() if "." in img_name else "png"
            mime = f"image/{'jpeg' if suffix in ('jpg', 'jpeg') else suffix}"
            encoded_images[img_name] = f"data:{mime};base64,{base64.b64encode(img_bytes).decode()}"
        file_result["images"] = encoded_images

    return FileParseResponse(
        status="completed",
        backend=backend,
        results={file_name: file_result},
    )
