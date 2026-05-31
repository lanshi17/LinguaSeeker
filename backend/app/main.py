"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.v1.router import router as v1_router
from src.core.config import get_config
from src.utils.logger import get_logger, setup_logging
from src.utils.middleware import add_request_monitoring


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown application resources."""
    cfg = get_config()
    setup_logging(environment=cfg.environment, debug=cfg.debug)
    logger = get_logger()
    logger.info("Starting ACMG Lingua backend (env={})", cfg.environment)

    from src.api.wiring import wire_dependencies, dispose_engine

    wire_dependencies()
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

add_request_monitoring(app)
app.include_router(v1_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
