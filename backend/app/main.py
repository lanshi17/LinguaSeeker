"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from src.api.v1.router import router as v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown application resources."""
    logger.info("Starting ACMG Lingua backend")

    from src.api.wiring import wire_dependencies, dispose_engine

    wire_dependencies(app)
    logger.info("Pipeline orchestrator initialized")

    yield

    await dispose_engine()
    logger.info("ACMG Lingua backend stopped")


app = FastAPI(
    title="ACMG Lingua Backend",
    description="Multi-Agent infrastructure for medical genetics literature automation",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(v1_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
