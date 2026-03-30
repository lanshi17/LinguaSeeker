# celery_app.py
from urllib.parse import quote

from celery import Celery
from kombu import Queue

from src.config import app_config as cfg


def _build_redis_url() -> str:
    if cfg.redis.host.startswith("redis://") or cfg.redis.host.startswith("rediss://"):
        return cfg.redis.host

    password_segment = (
        f":{quote(cfg.redis.password, safe='')}@" if cfg.redis.password else ""
    )
    return f"redis://{password_segment}{cfg.redis.host}:{cfg.redis.port}/{cfg.redis.db}"


redis_url = _build_redis_url()

celery_app = Celery(
    "acmg_tasks",
    broker=redis_url,
    backend=redis_url,
    include=["src.services.task_manager"],
)

# 可选: 配置序列化器等
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    timezone="UTC",
    task_default_queue="default",
    task_create_missing_queues=True,
    task_queues=(
        Queue("default", routing_key="default"),
        Queue("retry", routing_key="retry"),
    ),
    task_routes={
        "tasks.process_pdf": {"queue": "default", "routing_key": "default"},
    },
)
