# src/domain/literature/api/biorxiv_http/workflow.py
from typing import Any, Dict

from .schemas import BiorxivPayload
from .service import BiorxivHttpService


async def biorxiv_http_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = BiorxivPayload.model_validate(payload)
    async with BiorxivHttpService(req) as svc:
        return (await svc.execute(req)).model_dump()
