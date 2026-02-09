# celery_app.py
from celery import Celery
from urllib.parse import quote
from src.config import settings as cfg


def _build_redis_url() -> str:
    if cfg.redis_host.startswith("redis://") or cfg.redis_host.startswith("rediss://"):
        return cfg.redis_host

    password_segment = (
        f":{quote(cfg.redis_password, safe='')}@" if cfg.redis_password else ""
    )
    return f"redis://{password_segment}{cfg.redis_host}:{cfg.redis_port}/{cfg.redis_db}"


redis_url = _build_redis_url()

celery_app = Celery(
    "acmg_tasks",
    broker=redis_url,
    backend=redis_url,
    include=["src.service.tasks"],
)

# 可选: 配置序列化器等
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    task_track_started=True,
    timezone='UTC'
)