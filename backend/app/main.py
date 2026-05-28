"""FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI

from src.api.v1.router import router as v1_router

app = FastAPI(
    title="ACMG Lingua Backend",
    description="Multi-Agent infrastructure for medical genetics literature automation",
    version="0.1.0",
)

app.include_router(v1_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
