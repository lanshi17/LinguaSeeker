"""Celery configuration for async task processing."""

import os
from kombu import Exchange, Queue


class CeleryConfig:
    """Celery configuration settings."""

    # Broker settings (Redis)
    broker_url = os.getenv("REDIS_BROKER_URL", "redis://localhost:6379/1")
    result_backend = os.getenv("REDIS_RESULT_BACKEND", "redis://localhost:6379/2")

    # Serialization
    task_serializer = "json"
    result_serializer = "json"
    accept_content = ["json"]
    timezone = "UTC"
    enable_utc = True

    # Task execution settings
    task_time_limit = 600  # 10 minutes hard limit
    task_soft_time_limit = 540  # 9 minutes warning
    task_acks_late = True
    task_reject_on_worker_lost = True

    # Retry settings
    task_annotations = {
        "*": {
            "max_retries": 3,
            "retry_backoff": True,
            "retry_backoff_max": 8,  # Max 8 seconds
            "retry_jitter": True,
        }
    }

    # Worker settings
    worker_prefetch_multiplier = 4
    worker_max_tasks_per_child = 100
    worker_disable_rate_limits = False

    # Result backend settings
    result_expires = 3600  # 1 hour
    result_persistent = True

    # Task routing
    task_routes = {
        "src.infrastructure.tasks.celery_tasks.parse_pdf_task": {
            "queue": "pdf_parsing"
        },
        "src.infrastructure.tasks.celery_tasks.extract_evidence_task": {
            "queue": "evidence_extraction"
        },
        "src.infrastructure.tasks.celery_tasks.sync_graph_task": {
            "queue": "graph_sync"
        },
    }

    # Queue definitions
    task_queues = (
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("pdf_parsing", Exchange("pdf_parsing"), routing_key="pdf.#"),
        Queue(
            "evidence_extraction",
            Exchange("evidence_extraction"),
            routing_key="evidence.#",
        ),
        Queue("graph_sync", Exchange("graph_sync"), routing_key="graph.#"),
        Queue(
            "celery_dead_letter",
            Exchange("celery_dead_letter"),
            routing_key="dead_letter.#",
        ),
    )

    # Beat schedule (for periodic tasks)
    beat_schedule = {
        "cleanup-old-logs": {
            "task": "src.infrastructure.tasks.celery_tasks.cleanup_old_logs_task",
            "schedule": 86400.0,  # Daily
        },
        "sync-graph-periodically": {
            "task": "src.infrastructure.tasks.celery_tasks.sync_graph_task",
            "schedule": 3600.0,  # Hourly
        },
    }


# Export configuration
celery_config = CeleryConfig()
