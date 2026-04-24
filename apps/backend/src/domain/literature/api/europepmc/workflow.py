# src/domain/literature/api/europepmc/workflow.py
"""Workflow entry point for Europe PMC API operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import (
    ApiResponse,
    DownloadResponse,
    EuropePmcPayload,
)
from .service import EuropePmcService


def run_europepmc_workflow(payload: EuropePmcPayload) -> ApiResponse | DownloadResponse:
    """Run the Europe PMC workflow based on payload action.

    Args:
        payload: The Europe PMC operation payload containing action and parameters.

    Returns:
        ApiResponse for query/search operations, DownloadResponse for download.
    """
    service = EuropePmcService()

    if payload.action == "query":
        return service.query(payload)
    elif payload.action == "doi":
        if payload.doi_list:
            return service.fetch_by_dois(payload.doi_list, payload)
        elif payload.doi:
            return service.query(payload)
        else:
            return ApiResponse(
                success=False,
                items=[],
                warnings=["no doi or doi list provided for doi action"],
            )
    elif payload.action == "download":
        return service.download(payload)
    else:
        return ApiResponse(
            success=False,
            items=[],
            warnings=[f"unknown action: {payload.action}"],
        )
