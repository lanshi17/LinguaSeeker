# src/domain/literature/api/doaj_http/workflow.py
from typing import Any, Dict

from .models import DoajPayload
from .service import DoajHttpService


async def doaj_http_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = DoajPayload.model_validate(payload)
    async with DoajHttpService(req) as svc:
        if req.action == "search":
            return (await svc.search(req)).model_dump()
    return {"success": False, "warnings": ["unknown_action"]}
