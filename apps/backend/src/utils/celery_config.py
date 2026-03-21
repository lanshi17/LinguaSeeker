# Celery 配置
from celery import Celery
from kombu import Exchange, Queue
from src.configs.app_config import AppConfig

cfg = AppConfig.from_env()

# 创建 Celery 应用
celery_app = Celery(
    "document_processing",
    broker=cfg.redis.broker_url if hasattr(cfg, "redis") else "redis://localhost:6379/0",
    backend=cfg.redis.result_backend if hasattr(cfg, "redis") else "redis://localhost:6379/1",
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # 任务结果配置
    result_expires=3600 * 24,  # 结果保留24小时
    result_extended=True,  # 扩展结果信息
    # 任务路由
    task_routes={
        "src.utils.celery_tasks.*": {"queue": "document_processing"},
    },
    # 队列配置
    task_queues=(
        Queue(
            "document_processing",
            Exchange("document_processing"),
            routing_key="document.processing",
        ),
    ),
    # Worker 配置
    worker_prefetch_multiplier=1,  # 每次只拉取一个任务
    worker_max_tasks_per_child=100,  # 每个worker处理100个任务后重启
    # 任务超时配置
    task_soft_time_limit=600,  # 软超时10分钟
    task_time_limit=900,  # 硬超时15分钟
)
