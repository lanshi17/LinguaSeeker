# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUntypedFunctionDecorator=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnusedParameter=false, reportDeprecated=false

from __future__ import annotations

from typing import Any, Dict

from src.celery_app import celery_app
from src.services.kg_consumer import process_kg_event


@celery_app.task(
    name="tasks.process_kg_event",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 1, "countdown": 180, "queue": "kg"},
    retry_jitter=True,
)
def process_kg_event_task(self, event_id: str) -> Dict[str, Any]:
    return process_kg_event(event_id)
