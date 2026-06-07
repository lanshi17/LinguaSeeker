"""API v1 router for ACMG Lingua backend."""
from __future__ import annotations

from fastapi import APIRouter

from src.api.v1 import chat, dashboard, delta_audit, evidence, pipeline, source_link

router = APIRouter(prefix="/api/v1")

# Pipeline orchestrator routes
router.include_router(pipeline.router, prefix="/pipeline", tags=["pipeline"])

# Phase 4 routes (expert review — independent of orchestrator)
router.include_router(evidence.router, prefix="/evidence", tags=["evidence"])
router.include_router(delta_audit.router, prefix="/delta-audit", tags=["delta-audit"])
router.include_router(source_link.router, prefix="/source-link", tags=["source-link"])
router.include_router(chat.router, prefix="/chat", tags=["chat"])

# Dashboard aggregation routes
router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
