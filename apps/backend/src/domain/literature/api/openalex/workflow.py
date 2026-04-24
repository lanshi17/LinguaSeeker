# src/domain/literature/api/openalex/workflow.py
"""Workflow entry point for OpenAlex operations."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from .models import OpenAlexPayload
from .service import OpenAlexService


async def run_openalex_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute OpenAlex workflow based on payload action.

    Args:
        payload: Dictionary containing action type and parameters.

    Returns:
        Dictionary with operation results.
    """
    req = OpenAlexPayload.model_validate(payload)
    service = OpenAlexService()

    if req.action == "doi":
        if req.doi_list:
            result = service.fetch_by_dois(req.doi_list, req)
        elif req.doi:
            result = service.query(req)
        else:
            return {"success": False, "warnings": ["no doi or doi list provided for doi action"]}
        result = await asyncio.to_thread(lambda: result)
        return result.model_dump()

    if req.action == "query":
        result = await asyncio.to_thread(service.query, req)
        return result.model_dump()

    if req.action == "download":
        result = await asyncio.to_thread(service.download, req)
        return result.model_dump()

    return {"success": False, "warnings": ["unknown_action"]}
