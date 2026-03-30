# src/domain/literature/api/jstage_http/workflow.py
from typing import Any, Dict

from .models import JStagePayload
from .service import JStageHttpService


async def jstage_http_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = JStagePayload.model_validate(payload)
    async with JStageHttpService(req) as svc:
        if req.action == "volumes":
            return (await svc.fetch_volumes(req)).model_dump()
        if req.action == "articles":
            return (await svc.fetch_articles(req)).model_dump()
    return {"success": False, "warnings": ["unknown_action"]}
