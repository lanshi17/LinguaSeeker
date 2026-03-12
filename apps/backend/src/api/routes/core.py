import asyncio
import base64
import hashlib
import io
import itertools
import mimetypes
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, cast
from uuid import UUID, uuid4
from loguru import logger
from src.health import check_all_connections
from src.config import settings as cfg
from fastapi import APIRouter, File, Request, Response, HTTPException, UploadFile, Query, Path
from pydantic import BaseModel, Field, HttpUrl
from src.infrastructure.redis import (
    check_pdf_hash as redis_check_pdf_hash,
    get_cached_pdf_result,
    delete_cached_pdf_result,
    redis_client,
)
from src.infrastructure.postgres import get_postgres_client
from src.services.task_manager import process_pdf_task
from src.infrastructure.minio import MinIOClient
from src.infrastructure.enum import MinioBucketNameEnum
from src.infrastructure.models import MinioObjectRefModel
from src.api.dependencies import build_log_link, contract_http_exception
from src.utils.sanitizers import sanitize_filename

router = APIRouter()


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall health status.")
    details: Dict[str, bool] = Field(..., description="Dependency status map.")
    timestamp: str = Field(..., description="UTC timestamp in ISO-8601 format.")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "details": {"postgres": True, "redis": True, "minio": True},
                "timestamp": "2026-02-10T08:00:00+00:00",
            }
        }


class PDFHashCheckResponse(BaseModel):
    exists: bool = Field(..., description="Whether the hash is present in cache or index.")
    result: Optional[Dict[str, Any]] = Field(
        None, description="Cached processing result, if available."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "exists": True,
                "result": {"document_id": "9f2b2a1c-8f55-4e24-8ad8-45ad1354edcb"},
            }
        }


class UploadQueuedResponse(BaseModel):
    status: str = Field("queued", description="Upload processing status.")
    task_id: str = Field(..., description="Celery task id for background processing.")
    filename: Optional[str] = Field(None, description="Original file name.")
    document_id: Optional[str] = Field(None, description="Document id in database, if available.")
    upload_key: str = Field(..., description="Object storage key for the uploaded PDF.")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "queued",
                "task_id": "1f6a8b7a-1b87-4d75-8c72-6f2f6a1a9c2e",
                "filename": "sample.pdf",
                "document_id": "9f2b2a1c-8f55-4e24-8ad8-45ad1354edcb",
                "upload_key": "9f2b2a1c-8f55-4e24-8ad8-45ad1354edcb/5ec66f4ab80f4f96abfce394c5a8f47a.pdf",
            }
        }


class UploadCachedResponse(BaseModel):
    status: str = Field("cached", description="Upload was found in cache.")
    filename: Optional[str] = Field(None, description="Original file name.")
    document_id: Optional[str] = Field(None, description="Document id in database, if available.")
    result: Dict[str, Any] = Field(..., description="Cached processing result.")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "cached",
                "filename": "sample.pdf",
                "document_id": "9f2b2a1c-8f55-4e24-8ad8-45ad1354edcb",
                "result": {"summary": "cached result payload"},
            }
        }


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error details.")

    class Config:
        json_schema_extra = {"example": {"detail": "Invalid input."}}


class LogLinkReissueResponse(BaseModel):
    request_id: str = Field(..., description="Request id used for log link reissue")
    log_link: str = Field(..., description="Reissued signed log link")
    expires_in_seconds: int = Field(24 * 60 * 60, description="Link validity window")


@router.get(
    "/health",
    tags=["Health"],
    summary="Check service health",
    description="Check database/queue/storage connectivity and report a combined status.",
    response_model=HealthResponse,
)
async def health_check():
    """Return aggregated status for core dependencies."""
    # 检查数据库连接等
    checks = check_all_connections()
    overall_status = "ok" if all(checks.values()) else "error"
    return {
        "status": overall_status,
        "details": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
    hash: str = Query(..., min_length=32, description="SHA-256 hash of the PDF content."),
):
    """Check whether a PDF hash exists and return cached result if available."""
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
    files: Optional[List[UploadFile]] = File(
        None, description="Alternative multi-file field; only one is allowed."
    ),
):
    """Upload a single PDF and return either cached result or async task info."""
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
    safe_filename = sanitize_filename(file.filename or f"{pdf_hash}.pdf")
    try:
        postgres_client = get_postgres_client()
    except Exception as exc:
        logger.exception("PostgreSQL client init failed: {}", exc)
        raise HTTPException(status_code=503, detail="PostgreSQL unavailable")
    existing_document = None
    try:
        cached = get_cached_pdf_result(pdf_hash)
        if cached is not None:
            cached_document_id = None
            try:
                cached_document = postgres_client.find_document_by_hash(pdf_hash)
                if cached_document is not None:
                    cached_document_id = str(cached_document.document_id)
            except Exception as exc:
                logger.warning("PostgreSQL hash lookup failed for cached {}: {}", pdf_hash, exc)
            if cached_document_id is None:
                logger.warning(
                    "Cached result missing document_id for hash {}. Removing cache entry.",
                    pdf_hash,
                )
                try:
                    delete_cached_pdf_result(pdf_hash)
                except Exception as exc:
                    logger.warning("Failed to delete cached result for {}: {}", pdf_hash, exc)
            else:
                return {
                    "status": "cached",
                    "filename": safe_filename,
                    "document_id": cached_document_id,
                    "result": cached,
                }
    except Exception as exc:
        logger.warning("Redis lookup failed, continue processing: {}", exc)

    try:
        existing_document = postgres_client.find_document_by_hash(pdf_hash)
    except Exception as exc:
        logger.warning("PostgreSQL hash lookup failed for {}: {}", pdf_hash, exc)

    try:
        minio_client = MinIOClient()
    except Exception as exc:
        logger.exception("MinIO client init failed: {}", exc)
        raise HTTPException(status_code=503, detail="Object storage unavailable")
    upload_ref: Optional[MinioObjectRefModel] = None
    existing_local_path = (
        cast(Optional[str], cast(object, existing_document.local_path))
        if existing_document is not None
        else None
    )
    existing_document_id = (
        cast(Optional[UUID], cast(object, existing_document.document_id))
        if existing_document is not None
        else None
    )
    if existing_document is not None and existing_local_path:
        try:
            if await minio_client.file_exists(
                MinioBucketNameEnum.LITERATURE_UPLOADS.value,
                existing_local_path,
            ):
                upload_ref = MinioObjectRefModel(
                    bucket=MinioBucketNameEnum.LITERATURE_UPLOADS,
                    object_key=existing_local_path,
                    content_type=file.content_type or "application/pdf",
                )
        except Exception as exc:
            logger.warning(
                "MinIO existence check failed for {}: {}. Will re-upload.",
                existing_local_path,
                exc,
            )

    if upload_ref is None:
        try:
            storage_key = MinIOClient.build_literature_object_key(
                file_hash=pdf_hash,
                original_filename=safe_filename,
            )
            upload_ref = await minio_client.upload_literature_upload(
                storage_key=storage_key,
                payload=pdf_data,
                content_type=file.content_type or "application/pdf",
                metadata={
                    "hash": pdf_hash,
                    "uploaded_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as exc:
            logger.exception("Failed to upload PDF to MinIO: {}", exc)
            raise HTTPException(status_code=503, detail="Failed to store PDF in object storage")

    document_id = None
    if existing_document is None:
        try:
            new_document_id = uuid4()
            created_document = postgres_client.create_document(
                title=safe_filename,
                document_id=new_document_id,
                original_filename=safe_filename,
                pmid=None,
                local_path=upload_ref.object_key,
                file_hash=pdf_hash,
                status="uploaded",
                summary=None,
            )
            document_id = str(created_document.document_id)
        except Exception as exc:
            logger.exception("Failed to insert document record for hash {}: {}", pdf_hash, exc)
            raise HTTPException(status_code=503, detail="PostgreSQL insert failed")
    elif (
        upload_ref is not None
        and existing_document_id is not None
        and existing_local_path != upload_ref.object_key
    ):
        try:
            postgres_client.update_document(
                existing_document_id,
                local_path=upload_ref.object_key,
                status="uploaded",
            )
            document_id = str(existing_document_id)
        except Exception as exc:
            logger.exception("Failed to update document record for hash {}: {}", pdf_hash, exc)
            raise HTTPException(status_code=503, detail="PostgreSQL update failed")
    else:
        if existing_document is not None and existing_document_id is not None:
            document_id = str(existing_document_id)
            if not getattr(existing_document, "original_filename", None):
                try:
                    postgres_client.update_document(
                        existing_document_id,
                        original_filename=safe_filename,
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to update original filename for document {}: {}",
                        existing_document_id,
                        exc,
                    )

    # 处理解析文件,调用service进行处理
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(pdf_data)
        tmp_file_path = tmp_file.name

    try:
        logger.debug("Enqueueing Celery task for tmp path: {}", tmp_file_path)
        async_result = cast(Any, process_pdf_task).apply_async(
            args=[[tmp_file_path]],
            kwargs={"file_hash": pdf_hash, "document_id": document_id},
        )
    except Exception as exc:
        logger.exception("Failed to enqueue Celery task: {}", exc)
        raise HTTPException(status_code=503, detail="Task queue unavailable")
    logger.debug("Celery task queued: {}", async_result.id)
    return {
        "status": "queued",
        "task_id": async_result.id,
        "filename": safe_filename,
        "document_id": document_id,
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
    document_id: str = Path(..., description="Document UUID."),
    object_path: str = Path(..., description="Relative path within the result bucket."),
):
    """Download a processed file from object storage as raw bytes."""
    if not object_path:
        raise contract_http_exception(400, "INPUT_INVALID", "object_path is required")

    object_key = f"{document_id}/{object_path}"
    minio_client = MinIOClient()
    try:
        payload = await minio_client.download_processed_result(object_key)
    except FileNotFoundError:
        raise contract_http_exception(404, "RESOURCE_NOT_FOUND", "Result file not found")
    except Exception as exc:
        logger.exception("Failed to download result file {}: {}", object_key, exc)
        raise HTTPException(status_code=503, detail="Failed to fetch result file")

    content_type = mimetypes.guess_type(object_path)[0] or "application/octet-stream"
    return Response(content=payload, media_type=content_type)


@router.get(
    "/logs/reissue",
    tags=["File"],
    summary="Reissue log link",
    description="Reissue signed log link with 1 request/minute rate limit per request_id.",
    response_model=LogLinkReissueResponse,
    responses={
        429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
        503: {"model": ErrorResponse, "description": "Rate limiter unavailable."},
    },
)
async def reissue_log_link(
    request_id: str = Query(
        ..., min_length=8, description="Request id used to regenerate log link."
    ),
):
    rate_key = f"log_reissue:{request_id}"
    try:
        redis_conn = redis_client.get_connection()
        hit_count = int(cast(Any, redis_conn.incr(rate_key)))
        if hit_count == 1:
            redis_conn.expire(rate_key, 60)
    except Exception as exc:
        logger.warning("Failed to apply reissue rate limit for {}: {}", request_id, exc)
        raise HTTPException(status_code=503, detail="Rate limiter unavailable")

    if hit_count > 1:
        raise HTTPException(status_code=429, detail="Reissue rate limit exceeded")

    return LogLinkReissueResponse(
        request_id=request_id,
        log_link=build_log_link(request_id),
        expires_in_seconds=24 * 60 * 60,
    )
