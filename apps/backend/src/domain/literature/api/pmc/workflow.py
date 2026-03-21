# src/domain/literature/api/pmc_http/workflow.py
from typing import Any, Dict

from .models import PmcPayload
from .service import PmcHttpService


async def pmc_http_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = PmcPayload.model_validate(payload)
    async with PmcHttpService(req) as svc:
        if req.action == "search":
            return (await svc.search(req)).model_dump()
        if req.action == "list_versions":
            return (await svc.list_versions(req)).model_dump()
        if req.action == "metadata":
            return (await svc.fetch_metadata(req)).model_dump()
        if req.action == "download":
            return (await svc.download(req)).model_dump()
    return {"success": False, "warnings": ["unknown_action"]}
