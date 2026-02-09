import asyncio
import base64
import hashlib
import io
import itertools
import mimetypes
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from loguru import logger
from src.health import check_all_connections 
from src.config  import settings as cfg
from fastapi import APIRouter, File, Request, Response, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, Query, Path
from pydantic import BaseModel, Field, HttpUrl
from src.database.redis_client import check_pdf_hash as redis_check_pdf_hash, get_cached_pdf_result
from src.database.postgre_client import get_postgres_client
from src.service.tasks import process_pdf_task
from src.database.minio_client import MinIOClient
from src.database.enum import MinioBucketNameEnum
from src.database.models import MinioObjectRefModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall health status.")
    details: Dict[str, bool] = Field(..., description="Dependency status map.")
    timestamp: str = Field(..., description="UTC timestamp in ISO-8601 format.")


class PDFHashCheckResponse(BaseModel):
    exists: bool = Field(..., description="Whether the hash is present in cache or index.")
    result: Optional[Dict[str, Any]] = Field(None, description="Cached processing result, if available.")


class UploadQueuedResponse(BaseModel):
    status: str = Field("queued", description="Upload processing status.")
    task_id: str = Field(..., description="Celery task id for background processing.")
    filename: Optional[str] = Field(None, description="Original file name.")
    hash: str = Field(..., description="SHA-256 hash of the PDF content.")
    upload_key: str = Field(..., description="Object storage key for the uploaded PDF.")


class UploadCachedResponse(BaseModel):
    status: str = Field("cached", description="Upload was found in cache.")
    hash: str = Field(..., description="SHA-256 hash of the PDF content.")
    filename: Optional[str] = Field(None, description="Original file name.")
    result: Dict[str, Any] = Field(..., description="Cached processing result.")


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error details.")


@router.get(
    "/health",
    tags=["Health"],
    summary="Check service health",
    description="Check database/queue/storage connectivity and report a combined status.",
    response_model=HealthResponse,
)
async def health_check():
    """Health check endpoint."""
    #检查数据库连接等
    checks = check_all_connections()
    overall_status = "ok" if all(checks.values()) else "error"
    return {
        "status": overall_status,
        "details": checks,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.get(
    "/pdf/check_hash",
    tags=["File"],
    summary="Check PDF hash",
    description="Check whether a PDF hash exists and return cached result if present.",
    response_model=PDFHashCheckResponse,
    responses={
        200: {"description": "Hash lookup completed."},
        503: {"model": ErrorResponse, "description": "Cache backend unavailable."},
    },
)
async def check_pdf_hash(
    hash: str = Query(..., min_length=32, description="SHA-256 hash of the PDF content.")
):
    """检查PDF哈希值是否存在"""
    try:
        cached = get_cached_pdf_result(hash)
        if cached is not None:
            return {"exists": True, "result": cached}
        return {"exists": redis_check_pdf_hash(hash)}
    except Exception as exc:
        logger.warning("Redis check failed for hash {}: {}", hash, exc)
        return {"exists": False}
 
@router.post(
    "/pdf/upload",
    tags=["File"],
    summary="Upload a PDF",
    description=(
        "Upload a single PDF file via multipart/form-data. If the hash is cached, return the cached result. "
        "Otherwise enqueue background processing and return a task id."
    ),
    response_model=Union[UploadQueuedResponse, UploadCachedResponse],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input or missing file."},
        415: {"model": ErrorResponse, "description": "Unsupported Content-Type."},
        503: {"model": ErrorResponse, "description": "Storage or queue unavailable."},
    },
)
async def upload_pdf(
    request: Request,
    file: Optional[UploadFile] = File(None, description="Single PDF file field named 'file'."),
    files: Optional[List[UploadFile]] = File(None, description="Alternative multi-file field; only one is allowed."),
):
    """PDF上传接口"""
    if file is None and files:
        if len(files) != 1:
            raise HTTPException(status_code=400, detail="Exactly one PDF file is required.")
        file = files[0]

    if file is None:
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" not in content_type:
            raise HTTPException(
                status_code=415,
                detail="Content-Type must be multipart/form-data with a 'file' field.",
            )
        raise HTTPException(status_code=400, detail="Missing required file field.")

    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Invalid PDF file.")
    
    pdf_data = await file.read()
    logger.debug(
        "Received PDF upload filename: {} content_type: {} size: {} bytes",
        file.filename,
        file.content_type,
        len(pdf_data),
    )
    pdf_hash = hashlib.sha256(pdf_data).hexdigest()
    postgres_client = get_postgres_client()
    existing_document = None
    try:
        cached = get_cached_pdf_result(pdf_hash)
        if cached is not None:
            return {
                "status": "cached",
                "hash": pdf_hash,
                "filename": file.filename,
                "result": cached,
            }
    except Exception as exc:
        logger.warning("Redis lookup failed, continue processing: {}", exc)

    try:
        existing_document = postgres_client.find_document_by_hash(pdf_hash)
    except Exception as exc:
        logger.warning("PostgreSQL hash lookup failed for {}: {}", pdf_hash, exc)

    minio_client = MinIOClient()
    upload_ref = None
    if existing_document and existing_document.local_path:
        try:
            if await minio_client.file_exists(
                MinioBucketNameEnum.LITERATURE_UPLOADS.value,
                existing_document.local_path,
            ):
                upload_ref = MinioObjectRefModel(
                    bucket=MinioBucketNameEnum.LITERATURE_UPLOADS,
                    object_key=existing_document.local_path,
                    content_type=file.content_type or "application/pdf",
                )
        except Exception as exc:
            logger.warning(
                "MinIO existence check failed for {}: {}. Will re-upload.",
                existing_document.local_path,
                exc,
            )

    if upload_ref is None:
        try:
            upload_ref = await minio_client.upload_literature_upload(
                filename=file.filename or f"{pdf_hash}.pdf",
                payload=pdf_data,
                content_type=file.content_type or "application/pdf",
                object_prefix=pdf_hash,
                metadata={
                    "hash": pdf_hash,
                    "filename": file.filename or "",
                },
            )
        except Exception as exc:
            logger.exception("Failed to upload PDF to MinIO: {}", exc)
            raise HTTPException(status_code=503, detail="Failed to store PDF in object storage")

    if existing_document is None:
        try:
            postgres_client.create_document(
                title=file.filename or pdf_hash,
                pmid=None,
                local_path=upload_ref.object_key,
                file_hash=pdf_hash,
                status="uploaded",
                summary=None,
            )
        except Exception as exc:
            logger.warning("Failed to insert document record for hash {}: {}", pdf_hash, exc)
    elif upload_ref and existing_document.local_path != upload_ref.object_key:
        try:
            postgres_client.update_document(
                existing_document.document_id,
                local_path=upload_ref.object_key,
                status="uploaded",
            )
        except Exception as exc:
            logger.warning("Failed to update document record for hash {}: {}", pdf_hash, exc)
    
    # 处理解析文件,调用service进行处理
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(pdf_data)
        tmp_file_path = tmp_file.name

    try:
        logger.debug("Enqueueing Celery task for tmp path: {}", tmp_file_path)
        async_result = process_pdf_task.apply_async(args=[[tmp_file_path]], kwargs={"file_hash": pdf_hash})
    except Exception as exc:
        logger.exception("Failed to enqueue Celery task: {}", exc)
        raise HTTPException(status_code=503, detail="Task queue unavailable")
    logger.debug("Celery task queued: {}", async_result.id)
    return {
        "status": "queued",
        "task_id": async_result.id,
        "filename": file.filename,
        "hash": pdf_hash,
        "upload_key": upload_ref.object_key,
    }


@router.get(
    "/results/{document_id}/{object_path:path}",
    tags=["File"],
    summary="Download processed result",
    description="Fetch a processed result file from object storage by document id and path.",
    responses={
        200: {"description": "File content"},
        400: {"model": ErrorResponse, "description": "Missing object path."},
        404: {"model": ErrorResponse, "description": "Result file not found."},
        503: {"model": ErrorResponse, "description": "Object storage unavailable."},
    },
)
async def download_processed_result_file(
    document_id: str = Path(..., description="Document id or hash prefix."),
    object_path: str = Path(..., description="Relative path within the result bucket."),
):
    if not object_path:
        raise HTTPException(status_code=400, detail="object_path is required")

    object_key = f"{document_id}/{object_path}"
    minio_client = MinIOClient()
    try:
        payload = await minio_client.download_processed_result(object_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Result file not found")
    except Exception as exc:
        logger.exception("Failed to download result file {}: {}", object_key, exc)
        raise HTTPException(status_code=503, detail="Failed to fetch result file")

    content_type = mimetypes.guess_type(object_path)[0] or "application/octet-stream"
    return Response(content=payload, media_type=content_type)
    
    
    