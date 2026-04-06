# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportCallIssue=false, reportGeneralTypeIssues=false, reportMissingImports=false, reportRedeclaration=false, reportFunctionMemberAccess=false, reportPossiblyUnboundVariable=false, reportReturnType=false

import json
from typing import Any, Dict, List, Optional, Tuple

import redis

from src.config import app_config as cfg

DEFAULT_CACHE_TTL_SECONDS = 86400
PDF_HASH_KEY_PREFIX = "pdf:hash:"
PDF_RESULT_KEY_PREFIX = "pdf:result:"


class RedisClient:
    """Redis client wrapper with proper authentication handling."""

    def __init__(self):
        self._connection = None

    def get_connection(self) -> redis.Redis:
        """Get Redis connection with proper authentication."""
        # Create connection with authentication
        connection = redis.Redis(
            host=cfg.redis.host,
            port=cfg.redis.port,
            db=cfg.redis.db,
            password=cfg.redis.password,  # This handles authentication
            max_connections=cfg.redis.max_connections,
            decode_responses=False,  # Keep responses as bytes to handle all types
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )

        return connection

    def get_async_connection(self) -> redis.Redis:
        """Deprecated alias for compatibility; returns a sync Redis connection."""
        return self.get_connection()


# Global Redis client instance
redis_client = RedisClient()


def _hash_key(pdf_hash: str) -> str:
    return f"{PDF_HASH_KEY_PREFIX}{pdf_hash}"


def _result_key(pdf_hash: str) -> str:
    return f"{PDF_RESULT_KEY_PREFIX}{pdf_hash}"


def store_pdf_hash(
    pdf_hash: str, expiration: Optional[int] = DEFAULT_CACHE_TTL_SECONDS
) -> None:
    """Store the PDF hash in Redis with an optional expiration time (default 1 day)."""
    redis_conn = redis_client.get_connection()
    redis_conn.set(_hash_key(pdf_hash), "processed", ex=expiration)


def check_pdf_hash(pdf_hash: str) -> bool:
    """Check if the PDF hash exists in Redis."""
    redis_conn = redis_client.get_connection()
    exists = redis_conn.exists(_hash_key(pdf_hash))
    return exists == 1


def get_cached_pdf_result(pdf_hash: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached result payload for a PDF hash if available."""
    redis_conn = redis_client.get_connection()
    raw = redis_conn.get(_result_key(pdf_hash))
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw)


def cache_pdf_result(
    pdf_hash: str,
    result: Dict[str, Any],
    expiration: Optional[int] = DEFAULT_CACHE_TTL_SECONDS,
) -> None:
    """Cache PDF processing result and mark hash as processed."""
    redis_conn = redis_client.get_connection()
    payload = json.dumps(result, ensure_ascii=False)
    pipe = redis_conn.pipeline()
    pipe.set(_result_key(pdf_hash), payload, ex=expiration)
    pipe.set(_hash_key(pdf_hash), "processed", ex=expiration)
    pipe.execute()


def delete_cached_pdf_result(pdf_hash: str) -> None:
    """Delete cached result payload and hash marker for a PDF hash."""
    redis_conn = redis_client.get_connection()
    redis_conn.delete(_result_key(pdf_hash), _hash_key(pdf_hash))


def list_celery_task_meta(
    cursor: int = 0,
    count: int = 100,
    pattern: str = "celery-task-meta-*",
) -> Tuple[int, List[Dict[str, Any]]]:
    """Scan celery task meta keys and return parsed metadata payloads."""
    redis_conn = redis_client.get_connection()
    next_cursor, keys = redis_conn.scan(cursor=cursor, match=pattern, count=count)
    if not keys:
        return int(next_cursor), []

    raw_values = redis_conn.mget(keys)
    items: List[Dict[str, Any]] = []
    for key, raw in zip(keys, raw_values):
        if not raw:
            continue
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if isinstance(key, bytes):
            key = key.decode("utf-8")
        payload["_key"] = key
        items.append(payload)

    return int(next_cursor), items
