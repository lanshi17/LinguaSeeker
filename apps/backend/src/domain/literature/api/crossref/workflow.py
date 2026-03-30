# src/domain/literature/api/crossref_http/workflow.py
from typing import Any, Dict

from .models import CrossrefPayload
from .service import CrossrefHttpService


async def crossref_http_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = CrossrefPayload.model_validate(payload)
    async with CrossrefHttpService(req) as svc:
        if req.action == "search":
            return (await svc.search(req)).model_dump()
    return {"success": False, "warnings": ["unknown_action"]}
