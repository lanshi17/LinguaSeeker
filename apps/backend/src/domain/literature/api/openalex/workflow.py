# src/domain/literature/api/openalex/workflow.py
# OpenAlex workflow entry point

from typing import Any, Dict

from .models import OpenAlexPayload
from .service import OpenAlexService


async def openalex_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Workflow entry point for OpenAlex API."""
    req = OpenAlexPayload.model_validate(payload)
    async with OpenAlexService() as svc:
        if req.action == "query":
            return (await svc.search(req)).model_dump()
        if req.action == "doi":
            return (await svc.query_by_doi(req)).model_dump()
        if req.action == "download":
            return (await svc.download(req, req.download_path)).model_dump()
    return {"success": False, "warnings": ["unknown action"]}
