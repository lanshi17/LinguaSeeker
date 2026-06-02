"""FastAPI application entry point."""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Any, TypedDict
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from src.api.v1.router import router as v1_router
from src.core.config import get_config
from src.utils.exceptions import ACMGException, error_code_from_exception, status_code_from_error_code
from src.utils.logger import get_logger, setup_logging
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api.rate_limit import limiter
from src.utils.middleware import add_request_monitoring


class ErrorDetail(TypedDict, total=False):
    """Error detail structure."""
    code: str
    message: str
    details: list[dict[str, Any]]


class ErrorResponseBody(TypedDict):
    """Error response envelope."""
    error: ErrorDetail
    request_id: str


def _error_response(
    *,
    code: str,
    message: str,
    request_id: str,
    status: int,
    errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    """Build a structured error response envelope with X-Request-ID header."""
    error_detail: ErrorDetail = {
        "code": code,
        "message": message,
    }
    if errors is not None:
        error_detail["details"] = errors

    body: ErrorResponseBody = {
        "error": error_detail,
        "request_id": request_id,
    }
    return JSONResponse(status_code=status, content=body, headers={"X-Request-ID": request_id})


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown application resources."""
    # Bypass system-wide SOCKS5/HTTP proxy for all outbound connections.
    # httpx and reqwest (Rust) pick up ALL_PROXY from the environment, which
    # breaks TLS handshakes to MinerU CDN and other services.  Clearing these
    # vars ensures direct connections — the intended production behaviour.
    for var in ("ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        os.environ.pop(var, None)

    cfg = get_config()
    setup_logging(environment=cfg.environment, debug=cfg.debug)
    logger = get_logger()
    logger.info("Starting ACMG Lingua backend (env={})", cfg.environment)

    from src.api.wiring import wire_dependencies, dispose_engine
    from src.utils.health import check_all_connections

    wire_dependencies()
    logger.info("Pipeline orchestrator initialized")

    # Startup health checks (non-blocking — warn but don't crash)
    try:
        checks = await check_all_connections()
        failed = checks.failed_services()
        if failed:
            logger.warning("Startup connectivity check failed: {}", ", ".join(failed))
        else:
            logger.info("Startup connectivity check passed")
    except Exception as exc:
        logger.error("Health check system failed: {}", exc)

    yield

    from src.api.deps import get_phase4_factory

    try:
        phase4_factory = get_phase4_factory()
        await phase4_factory.close()
    except Exception:
        logger.warning("Phase4ServiceFactory close failed during shutdown")
    finally:
        await dispose_engine()
        logger.info("ACMG Lingua backend stopped")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Exported as a factory so that test collection does not trigger
    ``get_config()`` — tests mock config before calling ``create_app()``
    inside a fixture.  For deployment, use the ``app`` alias below or
    ``uvicorn app.main:create_app --factory``.
    """
    cfg = get_config()

    _app = FastAPI(
        title="ACMG Lingua Backend",
        description="Multi-Agent infrastructure for medical genetics literature automation",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── Middleware (applied in reverse registration order) ──
    # Request monitor is outermost (logs all requests including CORS preflight).
    # CORS adds headers after route handling — this is correct.
    allow_all = cfg.cors_origins_list == ["*"]
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins_list,
        # Browsers reject Access-Control-Allow-Origin: * with credentials=true
        allow_credentials=not allow_all,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    add_request_monitoring(_app)

    # ── Rate limiting ───────────────────────────────────────────────────
    _app.state.limiter = limiter
    _app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── Routes ───────────────────────────────────────────────────────────
    _app.include_router(v1_router)

    # ── Health (outside v1 router for liveness probes) ──────────────────
    @_app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Health check endpoint."""
        return HealthResponse(status="ok")

    # ── Global error handlers ──────────────────────────────────────────
    @_app.exception_handler(ACMGException)
    async def handle_acmg_exception(request: Request, exc: ACMGException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        status = status_code_from_error_code(exc.code)
        return _error_response(code=exc.code, message=exc.message, request_id=request_id, status=status)

    @_app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        code = error_code_from_exception(exc, status_code=exc.status_code)
        message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return _error_response(code=code, message=message, request_id=request_id, status=exc.status_code)

    @_app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        # Pydantic errors may contain non-serializable types (e.g. Python type objects).
        # Round-trip through JSON with a default str fallback to ensure serializability.
        errors = json.loads(json.dumps(exc.errors(), default=str))
        return _error_response(
            code="VALIDATION_ERROR",
            message="Invalid request payload",
            request_id=request_id,
            status=422,
            errors=errors,
        )

    return _app


# Backward-compatible alias for uvicorn app.main:app and existing launch scripts.
# Prefer ``create_app()`` for programmatic use (tests, custom entrypoints).
app: FastAPI = create_app()
