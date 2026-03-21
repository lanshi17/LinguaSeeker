# src/domain/literature/api/unpaywall/workflow.py
"""Workflow entry point for Unpaywall operations."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from .models import UnpaywallPayload
from .service import UnpaywallService


async def unpaywall_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute Unpaywall workflow based on payload action.

    Args:
        payload: Dictionary containing action type and parameters.

    Returns:
        Dictionary with operation results.
    """
    req = UnpaywallPayload.model_validate(payload)
    service = UnpaywallService(email=req.email)

    if req.action == "doi":
        result = await asyncio.to_thread(service.doi_query, req)
        return result.model_dump()

    if req.action == "query":
        result = await asyncio.to_thread(service.query, req)
        return result.model_dump()

    if req.action == "download":
        result = await asyncio.to_thread(service.download, req)
        return result.model_dump()

    return {"success": False, "warnings": ["unknown_action"]}
