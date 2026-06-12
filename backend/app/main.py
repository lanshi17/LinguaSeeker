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

from src.api.rate_limit import init_limiter
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


_startup_lock_raw_conn = None


async def _try_startup_lock(engine) -> bool:
    """Acquire a PostgreSQL advisory lock for startup initialization.

    Uses a raw connection (not returned to pool) so the lock persists
    for the duration of the startup phase.  PostgreSQL advisory locks
    are session-scoped: they release automatically when the connection
    closes.

    Returns True if the lock was acquired (this worker should run recovery).
    Returns False if another worker already holds the lock.
    Returns True for non-PostgreSQL engines (SQLite in tests).
    """
    global _startup_lock_raw_conn

    try:
        raw_conn = await engine.raw_connection()
        try:
            result = await raw_conn.exec_driver_sql(
                "SELECT pg_try_advisory_lock(hashtext('cross_evidence_backend_startup'))"
            )
            row = result.fetchone()
            acquired = bool(row[0]) if row else False
        except Exception:
            await raw_conn.close()
            return True

        if acquired:
            _startup_lock_raw_conn = raw_conn
        else:
            await raw_conn.close()
        return acquired
    except Exception:
        # Non-PostgreSQL engines (SQLite in tests) don't have advisory locks
        return True


async def _release_startup_lock() -> None:
    """Release the PostgreSQL advisory lock by closing the raw connection.

    PostgreSQL automatically releases all advisory locks when a connection
    is closed, so explicit pg_advisory_unlock is not required.
    """
    global _startup_lock_raw_conn
    if _startup_lock_raw_conn is not None:
        try:
            await _startup_lock_raw_conn.close()
        except Exception:
            pass
        _startup_lock_raw_conn = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown application resources."""
    # Bypass system-wide SOCKS5/HTTP proxy env vars.  httpx and reqwest pick
    # these up automatically, which breaks TLS handshakes to MinerU CDN and
    # other services.  Our application-level proxy routing (NetworkConfig)
    # handles selective proxying instead.
    for var in ("ALL_PROXY", "all_proxy", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        os.environ.pop(var, None)

    cfg = get_config()
    setup_logging(environment=cfg.environment, debug=cfg.debug)
    logger = get_logger()
    logger.info("Starting Cross Evidence backend (env={})", cfg.environment)

    if cfg.network.proxy:
        logger.info("Network proxy enabled: {} (bypass: {} domains)", cfg.network.proxy, len(cfg.network.no_proxy.split(",")))
    else:
        logger.info("Network proxy disabled — all connections are direct")

    import src.api.wiring as _wiring

    wire_dependencies = _wiring.wire_dependencies
    from src.utils.health import check_all_connections

    wire_dependencies()
    logger.info("Pipeline orchestrator initialized")

    # Ensure standalone tables (independent MetaData, not managed by Alembic) exist
    # Use advisory lock to prevent multi-worker races on table creation and recovery
    from src.dao.postgresql.search_index_repo import search_index_metadata
    _wiring.get_session_factory()  # trigger lazy engine creation
    engine = _wiring.get_engine()

    startup_lock_acquired = False
    if engine is not None:
        startup_lock_acquired = await _try_startup_lock(engine)
    if engine is not None and startup_lock_acquired:
        async with engine.begin() as conn:
            await conn.run_sync(search_index_metadata.create_all)

    # Recover pipeline runs interrupted by server restart (only if we hold the lock)
    from src.api.v1.pipeline import get_pipeline_runner
    if startup_lock_acquired:
        try:
            runner = get_pipeline_runner()
            await runner.recover_orphaned_runs()
        except Exception as exc:
            logger.warning("Orphaned run recovery failed: {}", exc)
        finally:
            await _release_startup_lock()
    else:
        logger.info("Skipping startup recovery — another worker holds the advisory lock")

    # Startup health checks (non-blocking — warn but don't crash)
    try:
        checks = await check_all_connections()
        failed = checks.failed_services()
        if failed:
            for svc in failed:
                logger.log("DEBUG" if svc == "redis" else "WARNING",
                           "Startup connectivity check failed: {}", svc)
        else:
            logger.info("Startup connectivity check passed")
    except Exception as exc:
        logger.error("Health check system failed: {}", exc)

    yield

    # Graceful shutdown: wait for in-flight pipeline tasks to complete so
    # they can persist their state to PostgreSQL before the engine is disposed.
    # This prevents orphaned PENDING/RUNNING rows when uvicorn --reload or
    # SIGTERM interrupts a long-running LLM call.
    try:
        runner = get_pipeline_runner()
        # Timeout must exceed the LLM request timeout (default 60s) to avoid
        # cancelling requests that would have succeeded.
        await runner.shutdown(timeout=90.0)
    except Exception as exc:
        logger.debug("Pipeline runner shutdown skipped: {}", exc)

    from src.api.deps import get_phase4_factory

    try:
        phase4_factory = get_phase4_factory()
        await phase4_factory.close()
    except Exception:
        logger.warning("Phase4ServiceFactory close failed during shutdown")
    finally:
        try:
            await _wiring.dispose_redis()
        except Exception:
            logger.warning("Redis disposal failed during shutdown")
        try:
            await _wiring.dispose_engine()
        except Exception:
            logger.warning("PostgreSQL engine disposal failed during shutdown")
        logger.info("Cross Evidence backend stopped")


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
        title="Cross Evidence Backend",
        description="Variant classification and evidence interpretation platform",
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

    # ── Body size limit (before ASGI reads body into memory) ──────────
    from src.api.body_size_limit import BodySizeLimitMiddleware
    _app.add_middleware(BodySizeLimitMiddleware, max_bytes=cfg.mineru.max_file_size_mb * 1024 * 1024)

    # ── Rate limiting ───────────────────────────────────────────────────
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    configured_limiter = init_limiter()
    _app.state.limiter = configured_limiter
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


# Module-level app instance for uvicorn app.main:app entry point.
# Use ``create_app()`` for programmatic use (tests, custom entrypoints).
app: FastAPI = create_app()
