"""FastAPI application entry point."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from src.api.v1.router import router as v1_router
from src.core.config import get_config
from src.utils.exceptions import ACMGException, error_code_from_exception
from src.utils.logger import get_logger, setup_logging
from src.utils.middleware import add_request_monitoring

# Stable mapping from ACMGException error codes to HTTP status codes
_CODE_TO_STATUS: dict[str, int] = {
    "NOT_FOUND": 404,
    "VALIDATION_ERROR": 422,
    "DATABASE_ERROR": 500,
    "LLM_ERROR": 502,
    "SERVICE_ERROR": 503,
    "TRANSLATION_ERROR": 502,
    "PARSING_ERROR": 500,
    "PHASE_ERROR": 500,
    "INTERNAL_ERROR": 500,
}


def _error_response(
    *, code: str, message: str, request_id: str, status: int, errors: list | None = None,
) -> JSONResponse:
    """Build a structured error response envelope with X-Request-ID header."""
    body: dict = {
        "error": {"code": code, "message": message},
        "request_id": request_id,
    }
    if errors is not None:
        body["error"]["details"] = errors
    return JSONResponse(status_code=status, content=body, headers={"X-Request-ID": request_id})


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown application resources."""
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
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            logger.warning("Startup connectivity check failed: {}", ", ".join(failed))
        else:
            logger.info("Startup connectivity check passed")
    except Exception as exc:
        logger.error("Health check system failed: {}", exc)

    yield

    await dispose_engine()
    logger.info("ACMG Lingua backend stopped")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Exported as a factory (not called at module level) so that test
    collection does not trigger get_config() — tests mock config before
    calling create_app() inside a fixture.
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

    # ── Routes ───────────────────────────────────────────────────────────
    _app.include_router(v1_router)

    # ── Health (outside v1 router for liveness probes) ──────────────────
    @_app.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok"}

    # ── Global error handlers ──────────────────────────────────────────
    @_app.exception_handler(ACMGException)
    async def handle_acmg_exception(request: Request, exc: ACMGException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        status = _CODE_TO_STATUS.get(exc.code, 500)
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


# NOTE: do NOT call create_app() at module level.
# Tests import create_app and call it inside a fixture after mocking config.
# Production uses create_app() in the ASGI entrypoint (uvicorn app.main:create_app).
