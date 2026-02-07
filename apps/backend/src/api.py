import asyncio
import base64
import hashlib
import io
import itertools
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from loguru import logger
from src.health import (
    check_redis_connection,
    check_postgres_connection,
    check_minio_connection,
    check_qdrant_connection,
)
from src.config  import settings as cfg
from fastapi import APIRouter, File, Request,Response,HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, HttpUrl

router = APIRouter()
@router.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    #检查数据库连接等
    redis_status = check_redis_connection()
    postgres_status = check_postgres_connection()
    minio_status = check_minio_connection()
    qdrant_status = check_qdrant_connection()

    overall_status = "ok" if all([redis_status, postgres_status, minio_status, qdrant_status]) else "error"
    return {
        "status": overall_status,
        "details": {
            "redis": redis_status,
            "postgres": postgres_status,
            "minio": minio_status,
            "qdrant": qdrant_status,
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
@router.get("/pdf/upload", tags=["File"])
async def upload_pdf(upload_request: Request):
    """PDF上传接口"""
    #检查pdf的合法性
    if not upload_request.headers.get("content-type","").startswith("application/pdf"):
        raise HTTPException(status_code=400, detail="Invalid PDF file.")
    pdf_data = await upload_request.body()
    #处理上传的pdf文件
    logger.debug(f"Received PDF file of size {len(pdf_data)} bytes.")
    #检查pdf的哈希值
    pdf_hash = hashlib.sha256(pdf_data).hexdigest()
    logger.debug(f"PDF SHA-256 hash: {pdf_hash}")
    #调用Redis存储pdf的哈希值
    await store_pdf_hash_in_redis(pdf_hash)
    
    
    