"""Celery configuration utilities with Redis authentication support."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional, Sequence
from urllib.parse import quote

from celery import Celery
from kombu import Exchange, Queue

from src.config.app_config import AppConfig
from src.config.database_config import DatabaseConfig

# Ensure .env files are loaded before we hydrate DatabaseConfig
AppConfig._load_dotenv()
_db_config = DatabaseConfig.from_env()
_redis_cfg = _db_config.redis


def _safe_int(value: Optional[str], default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _resolve_db_number(env_keys: Sequence[str], default: int) -> int:
    for key in env_keys:
        if not key:
            continue
        candidate = os.getenv(key)
        if candidate is not None:
            return _safe_int(candidate, default)
    return default


def _build_auth_segment() -> str:
    """Compose the redis auth string with URL-safe encoding."""
    username = os.getenv("REDIS_USERNAME") or None
    password = _redis_cfg.password or os.getenv("REDIS_PASSWORD") or None

    if username and password:
        return f"{quote(username, safe='')}:{quote(password, safe='')}@"
    if username:
        return f"{quote(username, safe='')}@"
    if password:
        return f":{quote(password, safe='')}@"
    return ""


def _build_redis_url(url_env: str, db_envs: Sequence[str], default_db: int) -> str:
    """Return a redis:// URL honoring per-component overrides."""
    if url := os.getenv(url_env):
        return url

    db_number = _resolve_db_number(db_envs, default_db)
    host = _redis_cfg.host
    port = _redis_cfg.port
    auth_segment = _build_auth_segment()
    return f"redis://{auth_segment}{host}:{port}/{db_number}"


def _create_celery_app() -> Celery:
    """Instantiate and configure a Celery application."""
    broker_url = _build_redis_url(
        "REDIS_BROKER_URL",
        ("REDIS_BROKER_DB", "CELERY_BROKER_DB", "REDIS_DB"),
        default_db=0,
    )
    result_backend = _build_redis_url(
        "REDIS_RESULT_BACKEND",
        ("REDIS_RESULT_DB", "CELERY_RESULT_DB", "REDIS_DB"),
        default_db=1,
    )

    app = Celery("document_processing", broker=broker_url, backend=result_backend)

    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        result_expires=3600 * 24,  # persist results for 24h
        result_extended=True,
        task_routes={
            "src.infrastructure.tasks.celery_tasks.*": {
                "queue": "document_processing",
                "routing_key": "document.processing",
            },
        },
        task_queues=(
            Queue("default", Exchange("default"), routing_key="default"),
            Queue(
                "document_processing",
                Exchange("document_processing"),
                routing_key="document.processing",
            ),
        ),
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=100,
        task_soft_time_limit=600,
        task_time_limit=900,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        broker_connection_retry_on_startup=True,
    )

    return app


@lru_cache(maxsize=1)
def get_celery_app() -> Celery:
    """Return a singleton Celery app for both workers and API clients."""
    return _create_celery_app()


__all__ = ["get_celery_app"]
