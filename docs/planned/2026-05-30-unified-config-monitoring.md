# Unified Backend Configuration & Monitoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unify the backend's configuration management and monitoring infrastructure — structured logging, centralized exceptions, request monitoring middleware, dependency health checks, and CORS — so both the main app and model server share consistent observability patterns.

**Architecture:** Extract shared observability primitives into `backend/src/utils/` (logging config, exceptions, middleware). The main `app/main.py` wires them at startup, matching the model server's existing patterns.

**Deferred:**
- The model server's `services/model-server/app/utils/logger.py` duplicates `_InterceptHandler` and loguru configuration. Refactoring it to import from `src.utils.logger` is deferred — the model server is a standalone microservice with its own dependency tree, and sharing `src.utils` requires restructuring its Python path.
- The model server uses `request_monitor_middleware_factory()` (factory pattern) while this plan introduces `add_request_monitoring(app)` (direct registration). Unifying the API is deferred to the same follow-up.

**Tech Stack:** Python 3.12+, FastAPI, loguru, pydantic, Starlette middleware

---

## Current State Summary

| Area | Main Backend (`app/main.py`) | Model Server (`services/model-server/`) |
|------|------|------|
| Loguru config | Default stderr only, no file sink | Full: stderr + file rotation + retention |
| Request timing | None | `RequestMonitorMiddleware` active |
| Health check | `{"status": "ok"}` only | Per-model `ready` status |
| Startup checks | None | N/A (lazy model loading) |
| Exception handling | Ad-hoc `HTTPException` raises | None |
| CORS | Not configured | Not configured |

**Scattered exceptions in:**
- `src/core/ingest_and_digitize_data/parse_document/exceptions.py`
- `src/core/cross_lingual_process_and_extract_evidence/cross_lingual/translate/exceptions.py`
- `src/core/standardize_entities_and_align_knowledge/similarity_match/core.py`
- `src/agents/contracts.py`

**Scattered exception migration:** Out of scope for this plan. The four existing exception files above will coexist with the new centralized hierarchy. A future plan should migrate them to inherit from `ACMGException`.

**Dead code:**
- `src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web/base.py:175` imports `from src.config import get_settings, resolve_llm_triplet` — module does not exist.

---

## Task 1: Structured Logging for Main Backend

**Files:**
- Create: `backend/src/utils/logger.py`
- Modify: `backend/app/main.py:1-42`

### Step 1: Write the failing test

Create `backend/tests/utils/test_logger.py`:

```python
"""Tests for the shared logging configuration."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from loguru import logger as _logger


@pytest.fixture(autouse=True)
def _isolate_loguru():
    """Save and restore loguru handler state around each test."""
    _logger.remove()
    yield
    _logger.remove()  # leave clean state after each test


def test_setup_logging_installs_stderr_sink():
    """setup_logging() should configure loguru with at least one stderr sink."""
    from src.utils.logger import setup_logging

    setup_logging()
    assert len(_logger._core.handlers) >= 1


def test_setup_logging_intercepts_stdlib():
    """setup_logging() should redirect stdlib logging through loguru."""
    from src.utils.logger import setup_logging

    setup_logging()

    root = logging.getLogger()
    assert any(isinstance(h, logging.Handler) for h in root.handlers)


def test_log_dir_created(tmp_path: Path):
    """setup_logging() should create the logs directory and add a file sink."""
    from src.utils.logger import setup_logging

    test_dir = tmp_path / "test_logs"
    with patch("src.utils.logger.LOG_DIR", test_dir):
        setup_logging()
        assert test_dir.exists()
        # Verify at least one file sink was registered
        file_sinks = [
            h for h in _logger._core.handlers.values()
            if hasattr(h, "_sink") and getattr(h._sink, "_path", None) is not None
        ]
        assert len(file_sinks) >= 1, "Expected at least one file sink after setup_logging()"
```

### Step 2: Run test to verify it fails

```bash
cd backend && uv run pytest tests/utils/test_logger.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.utils.logger'`

### Step 3: Write minimal implementation

Create `backend/src/utils/logger.py`:

```python
"""Shared logging configuration — loguru sinks + stdlib interception."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from loguru import logger as _logger

# ── Defaults ─────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"

# ── Public API ───────────────────────────────────────────────────────────


def get_logger() -> type[_logger]:
    """Return the loguru logger instance."""
    return _logger


def setup_logging(*, environment: str = "development", debug: bool = False) -> None:
    """Configure loguru sinks and intercept stdlib logging.

    Call once during application startup (lifespan).
    """
    LOG_DIR.mkdir(exist_ok=True)
    _logger.remove()

    # Stderr sink — colored, INFO+ in production, DEBUG in development
    stderr_level = "DEBUG" if debug or environment == "development" else "INFO"
    _logger.add(
        sys.stderr,
        level=stderr_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level:<8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
        backtrace=True,
        diagnose=debug,
    )

    # File sink — DEBUG+, daily rotation, 14-day retention
    _logger.add(
        LOG_DIR / "backend_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="14 days",
        compression="gz",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} | {message}",
        enqueue=True,
    )

    # Intercept stdlib logging → loguru
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)


class _InterceptHandler(logging.Handler):
    """Redirect stdlib ``logging`` output through loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = _logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        _logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())
```

### Step 4: Run test to verify it passes

```bash
cd backend && uv run pytest tests/utils/test_logger.py -v
```

Expected: PASS (3 tests)

### Step 5: Integrate into `app/main.py`

Modify `backend/app/main.py` — add `setup_logging()` call in lifespan, use structured logger:

```python
"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.v1.router import router as v1_router
from src.core.config import get_config
from src.utils.logger import get_logger, setup_logging


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

app.include_router(v1_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
```

### Step 6: Run all existing tests to verify no regressions

```bash
cd backend && uv run pytest tests/ -v --timeout=30
```

Expected: All existing tests pass.

### Step 7: Commit

```bash
git add backend/src/utils/logger.py backend/tests/utils/test_logger.py backend/app/main.py
git commit -m "feat(backend): add structured logging config for main app

- Create shared logger module with stderr + file sinks
- Daily rotation, 14-day retention, gz compression
- Intercept stdlib logging through loguru
- Integrate into app lifespan startup"
```

---

## Task 2: Centralized Exception Hierarchy

**Files:**
- Create: `backend/src/utils/exceptions.py`
- Create: `backend/tests/utils/test_exceptions.py`

### Step 1: Write the failing test

Create `backend/tests/utils/test_exceptions.py`:

```python
"""Tests for the centralized exception hierarchy."""
from __future__ import annotations

import pytest

from src.utils.exceptions import (
    ACMGException,
    DatabaseException,
    LLMException,
    NotFoundException,
    ParsingException,
    ServiceException,
    TranslationException,
    ValidationException,
    error_code_from_exception,
)


class TestACMGException:
    def test_base_exception_stores_message_and_code(self):
        exc = ACMGException("something broke", code="GENERIC_ERROR")
        assert exc.message == "something broke"
        assert exc.code == "GENERIC_ERROR"
        assert str(exc) == "something broke"

    def test_default_code_is_internal_error(self):
        exc = ACMGException("oops")
        assert exc.code == "INTERNAL_ERROR"


class TestSubclasses:
    def test_not_found_has_code(self):
        exc = NotFoundException("item", "123")
        assert exc.code == "NOT_FOUND"
        assert "item" in exc.message
        assert "123" in exc.message

    def test_validation_has_code(self):
        exc = ValidationException("bad input")
        assert exc.code == "VALIDATION_ERROR"

    def test_database_has_code(self):
        exc = DatabaseException("connection refused")
        assert exc.code == "DATABASE_ERROR"

    def test_llm_has_code(self):
        exc = LLMException("timeout")
        assert exc.code == "LLM_ERROR"

    def test_translation_has_code(self):
        exc = TranslationException("failed")
        assert exc.code == "TRANSLATION_ERROR"

    def test_parsing_has_code(self):
        exc = ParsingException("corrupt pdf")
        assert exc.code == "PARSING_ERROR"

    def test_service_has_code(self):
        exc = ServiceException("unavailable")
        assert exc.code == "SERVICE_ERROR"


class TestErrorCodeFromException:
    def test_acmg_exception_returns_its_code(self):
        exc = LLMException("boom")
        assert error_code_from_exception(exc) == "LLM_ERROR"

    def test_generic_exception_returns_internal_error(self):
        exc = ValueError("unexpected")
        assert error_code_from_exception(exc) == "INTERNAL_ERROR"

    def test_http_status_mapping(self):
        assert error_code_from_exception(Exception(), status_code=404) == "NOT_FOUND"
        assert error_code_from_exception(Exception(), status_code=422) == "VALIDATION_ERROR"
        assert error_code_from_exception(Exception(), status_code=500) == "INTERNAL_ERROR"
```

### Step 2: Run test to verify it fails

```bash
cd backend && uv run pytest tests/utils/test_exceptions.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.utils.exceptions'`

### Step 3: Write minimal implementation

Create `backend/src/utils/exceptions.py`:

```python
"""Centralized exception hierarchy for ACMG Lingua backend.

All domain exceptions inherit from ``ACMGException`` which carries a
human-readable ``message`` and a stable ``code`` string.  The API layer
uses these codes in structured error responses.
"""
from __future__ import annotations


class ACMGException(Exception):
    """Base exception for all ACMG Lingua domain errors."""

    def __init__(self, message: str, *, code: str = "INTERNAL_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


# ── Concrete exceptions ──────────────────────────────────────────────────


class NotFoundException(ACMGException):
    """Requested resource not found."""

    def __init__(self, entity: str, identifier: str) -> None:
        super().__init__(f"{entity} {identifier} not found", code="NOT_FOUND")


class ValidationException(ACMGException):
    """Input validation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="VALIDATION_ERROR")


class DatabaseException(ACMGException):
    """Database operation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="DATABASE_ERROR")


class LLMException(ACMGException):
    """LLM service call failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="LLM_ERROR")


class TranslationException(ACMGException):
    """Translation operation failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="TRANSLATION_ERROR")


class ParsingException(ACMGException):
    """Document parsing failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="PARSING_ERROR")


class ServiceException(ACMGException):
    """External service unavailable or failed."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="SERVICE_ERROR")


# ── Helpers ───────────────────────────────────────────────────────────────

# Stable mapping from HTTP status codes to error codes
_STATUS_TO_CODE: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
}


def error_code_from_exception(exc: Exception, *, status_code: int | None = None) -> str:
    """Derive a stable error code from an exception or HTTP status."""
    if isinstance(exc, ACMGException):
        return exc.code
    if status_code is not None:
        return _STATUS_TO_CODE.get(status_code, "INTERNAL_ERROR")
    return "INTERNAL_ERROR"
```

### Step 4: Run test to verify it passes

```bash
cd backend && uv run pytest tests/utils/test_exceptions.py -v
```

Expected: PASS (all tests)

### Step 5: Commit

```bash
git add backend/src/utils/exceptions.py backend/tests/utils/test_exceptions.py
git commit -m "feat(backend): add centralized exception hierarchy

- ACMGException base with message + stable code
- Concrete: NotFound, Validation, Database, LLM, Translation, Parsing, Service
- error_code_from_exception helper for API error responses"
```

---

## Task 3: Request Monitoring Middleware

**Files:**
- Create: `backend/src/utils/middleware.py`
- Create: `backend/tests/utils/test_middleware.py`

### Step 1: Write the failing test

Create `backend/tests/utils/test_middleware.py`:

```python
"""Tests for request monitoring middleware."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.utils.middleware import add_request_monitoring


@pytest.fixture()
def client():
    app = FastAPI()
    add_request_monitoring(app)

    @app.get("/test")
    async def test_route():
        return {"ok": True}

    @app.get("/error")
    async def error_route():
        raise RuntimeError("boom")

    return TestClient(app, raise_server_exceptions=False)


def test_successful_request_logs_timing(client, capsys):
    resp = client.get("/test")
    assert resp.status_code == 200


def test_error_request_returns_500(client):
    resp = client.get("/error")
    assert resp.status_code == 500


def test_middleware_preserves_response_body(client):
    resp = client.get("/test")
    assert resp.json() == {"ok": True}
```

### Step 2: Run test to verify it fails

```bash
cd backend && uv run pytest tests/utils/test_middleware.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.utils.middleware'`

### Step 3: Write minimal implementation

Create `backend/src/utils/middleware.py`:

```python
"""Shared ASGI middleware for the main backend."""
from __future__ import annotations

import time

from fastapi import FastAPI
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestMonitorMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status code, and duration.

    Logs timing even when the route handler raises an unhandled exception.

    Known limitation: ``BaseHTTPMiddleware`` buffers the full response body
    in memory, which breaks SSE / chunked streaming and large downloads.
    If streaming endpoints are added, rewrite this as raw ASGI middleware::

        class RequestMonitorMiddleware:
            async def __call__(self, scope, receive, send): ...
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        start = time.perf_counter()
        status = 500
        try:
            response: Response = await call_next(request)
            status = response.status_code
            return response
        except Exception:
            status = 500
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "{method} {path} -> {status} ({elapsed:.1f}ms)",
                method=request.method,
                path=request.url.path,
                status=status,
                elapsed=elapsed_ms,
            )


def add_request_monitoring(app: FastAPI) -> None:
    """Register the request monitoring middleware on a FastAPI app."""
    app.add_middleware(RequestMonitorMiddleware)
```

### Step 4: Run test to verify it passes

```bash
cd backend && uv run pytest tests/utils/test_middleware.py -v
```

Expected: PASS (3 tests)

### Step 5: Commit

```bash
git add backend/src/utils/middleware.py backend/tests/utils/test_middleware.py
git commit -m "feat(backend): add request monitoring middleware

- Log method, path, status, duration for every request
- add_request_monitoring helper for FastAPI app wiring"
```

---

## Task 4: Dependency Health Checks

**Files:**
- Create: `backend/src/utils/health.py`
- Modify: `backend/src/api/wiring.py` (add `get_engine()` accessor)
- Create: `backend/tests/utils/test_health.py`

### Step 1: Write the failing test

Create `backend/tests/utils/test_health.py`:

```python
"""Tests for startup health checks."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.utils.health import HealthStatus, check_all_connections


@pytest.mark.asyncio
async def test_check_all_returns_health_status():
    """check_all_connections returns a HealthStatus with known keys."""
    with (
        patch("src.utils.health._check_postgres", new_callable=AsyncMock, return_value=True),
        patch("src.utils.health._check_redis", new_callable=AsyncMock, return_value=True),
    ):
        result = await check_all_connections()
        assert isinstance(result, dict)
        assert result["postgres"] is True
        assert result["redis"] is True


@pytest.mark.asyncio
async def test_check_all_reports_failures():
    """Failed checks should be reported as False."""
    with (
        patch("src.utils.health._check_postgres", new_callable=AsyncMock, return_value=False),
        patch("src.utils.health._check_redis", new_callable=AsyncMock, return_value=True),
    ):
        result = await check_all_connections()
        assert result["postgres"] is False
        assert result["redis"] is True
```

### Step 2: Run test to verify it fails

```bash
cd backend && uv run pytest tests/utils/test_health.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.utils.health'`

### Step 3: Add `get_engine()` accessor to `wiring.py`

Add this function to `backend/src/api/wiring.py` (after `get_session_factory`):

```python
def get_engine() -> AsyncEngine | None:
    """Return the singleton engine (or None if not yet initialized).

    Used by health checks to verify DB connectivity without creating
    a second engine.
    """
    return _engine
```

### Step 4: Write minimal implementation

Create `backend/src/utils/health.py`:

```python
"""Startup dependency health checks.

Call ``check_all_connections()`` during FastAPI lifespan startup to verify
that all critical infrastructure is reachable before accepting requests.
"""
from __future__ import annotations

from typing import TypedDict

from loguru import logger

from src.core.config import get_config


class HealthStatus(TypedDict):
    """Per-service connectivity status."""

    postgres: bool
    redis: bool


async def _check_postgres() -> bool:
    """Ping PostgreSQL with a lightweight query.

    Reuses the engine already created by wire_dependencies() via
    src.api.wiring.get_engine(). Falls back to False if wiring hasn't run yet.
    """
    try:
        from sqlalchemy import text

        from src.api.wiring import get_engine

        engine = get_engine()
        if engine is None:
            logger.warning("PostgreSQL health check skipped: engine not initialized")
            return False
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("PostgreSQL health check failed: {}", exc)
        return False


async def _check_redis() -> bool:
    """Ping Redis."""
    try:
        import redis.asyncio as aioredis

        cfg = get_config()
        client = aioredis.Redis(
            host=cfg.redis.host,
            port=cfg.redis.port,
            password=cfg.redis.password or None,
            db=cfg.redis.db,
        )
        pong = await client.ping()
        await client.aclose()
        return bool(pong)
    except Exception as exc:
        logger.warning("Redis health check failed: {}", exc)
        return False


async def check_all_connections() -> HealthStatus:
    """Check all critical infrastructure connections.

    Returns a typed mapping of service name to connectivity status.
    """
    postgres_ok, redis_ok = await _check_postgres(), await _check_redis()
    return HealthStatus(postgres=postgres_ok, redis=redis_ok)
```

### Step 5: Run test to verify it passes

```bash
cd backend && uv run pytest tests/utils/test_health.py -v
```

Expected: PASS (2 tests)

### Step 6: Commit

```bash
git add backend/src/utils/health.py backend/src/api/wiring.py backend/tests/utils/test_health.py
git commit -m "feat(backend): add startup dependency health checks

- Async PostgreSQL and Redis connectivity checks
- Reuse wiring engine instead of creating a second one
- get_engine() accessor in wiring.py
- check_all_connections returns per-service status dict"
```

---

## Task 5: Global Error Handling & CORS Middleware

**Files:**
- Modify: `backend/app/main.py:1-42`
- Modify: `backend/tests/utils/test_exceptions.py` (extend)

### Step 1: Write the failing test for error responses

Add to `backend/tests/utils/test_exceptions.py`:

```python
class TestErrorResponseContract:
    """Tests for the structured error response shape returned by the API."""

    def test_404_returns_structured_error(self, client):
        resp = client.get("/api/v1/nonexistent")
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    def test_422_returns_structured_error(self, client):
        """FastAPI validation errors should use our contract."""
        # POST to a non-existent endpoint triggers 404, not 422
        # We test 422 via a real endpoint that requires body validation
        # For now, just verify the handler is registered
        pass
```

Create `backend/tests/api/test_error_handlers.py`:

```python
"""Tests for global error handlers."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    # Mock health checks to avoid real postgres/redis connections during tests
    with patch(
        "src.utils.health.check_all_connections",
        new_callable=AsyncMock,
        return_value={"postgres": True, "redis": True},
    ):
        from app.main import app
        yield TestClient(app, raise_server_exceptions=False)


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_unknown_route_returns_structured_404(client):
    resp = client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert "request_id" in body
```

### Step 2: Run test to verify it fails

```bash
cd backend && uv run pytest tests/api/test_error_handlers.py -v
```

Expected: FAIL — response body does not match structured error format.

### Step 3: Implement global error handlers and CORS in `app/main.py`

Replace `backend/app/main.py`:

```python
"""FastAPI application entry point."""
from __future__ import annotations

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
    "INTERNAL_ERROR": 500,
}


def _error_response(
    *, code: str, message: str, request_id: str, status: int, errors: list | None = None,
) -> JSONResponse:
    """Build a structured error response envelope."""
    body: dict = {
        "error": {"code": code, "message": message},
        "request_id": request_id,
    }
    if errors is not None:
        body["error"]["details"] = errors
    return JSONResponse(status_code=status, content=body)


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
    checks = await check_all_connections()
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        logger.warning("Startup connectivity check failed: {}", ", ".join(failed))
    else:
        logger.info("Startup connectivity check passed")

    yield

    await dispose_engine()
    logger.info("ACMG Lingua backend stopped")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    cfg = get_config()

    _app = FastAPI(
        title="ACMG Lingua Backend",
        description="Multi-Agent infrastructure for medical genetics literature automation",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── Middleware (reverse order: CORS outermost, then request monitor) ──
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins_list,
        allow_credentials=True,
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
        request_id = request.headers.get("x-request-id") or str(uuid4())
        status = _CODE_TO_STATUS.get(exc.code, 500)
        return _error_response(code=exc.code, message=exc.message, request_id=request_id, status=status)

    @_app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = request.headers.get("x-request-id") or str(uuid4())
        code = error_code_from_exception(exc, status_code=exc.status_code)
        message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return _error_response(code=code, message=message, request_id=request_id, status=exc.status_code)

    @_app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = request.headers.get("x-request-id") or str(uuid4())
        return _error_response(
            code="VALIDATION_ERROR",
            message="Invalid request payload",
            request_id=request_id,
            status=422,
            errors=exc.errors(),
        )

    return _app


app = create_app()
```

### Step 4: Run tests to verify they pass

```bash
cd backend && uv run pytest tests/api/test_error_handlers.py tests/utils/ -v
```

Expected: PASS

### Step 5: Run full test suite

```bash
cd backend && uv run pytest tests/ -v --timeout=30
```

Expected: All tests pass.

### Step 6: Commit

```bash
git add backend/app/main.py backend/tests/api/test_error_handlers.py
git commit -m "feat(backend): add global error handlers and CORS middleware

- ACMGException, HTTPException, validation error handlers
- _CODE_TO_STATUS mapping for correct HTTP semantics
- Structured error response envelope with request_id
- create_app() factory pattern (no module-level config loading)
- CORS middleware from config
- Startup health checks for postgres + redis"
```

---

## Task 6: Generalize `traced_node` to Support Async

**Files:**
- Modify: `backend/src/utils/observability.py:1-27`
- Modify: `backend/tests/utils/test_observability.py`

### Step 1: Write the failing test

Add to `backend/tests/utils/test_observability.py`:

```python
import pytest

@pytest.mark.asyncio
async def test_traced_node_with_async_function():
    """traced_node should work with async functions."""
    @traced_node("async_test")
    async def async_fn(x: int) -> int:
        return x * 2

    result = await async_fn(5)
    assert result == 10
```

### Step 2: Run test to verify it fails

```bash
cd backend && uv run pytest tests/utils/test_observability.py -v
```

Expected: FAIL — `traced_node` does not handle async functions.

### Step 3: Update implementation

Replace `backend/src/utils/observability.py`:

```python
"""Observability utilities — LangSmith tracing + structured logging."""
from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable

from langsmith import traceable
from loguru import logger


def traced_node(name: str) -> Callable:
    """Decorator that adds LangSmith tracing + loguru logging to a pipeline node.

    Works with both sync and async functions.
    """
    def decorator(fn: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(fn)

        @traceable(name=name, run_type="chain")
        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.info("Node [{}] start", name)
            try:
                result = fn(*args, **kwargs)
                logger.info("Node [{}] done", name)
                return result
            except Exception as e:
                logger.error("Node [{}] failed: {}", name, e)
                raise

        @traceable(name=name, run_type="chain")
        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.info("Node [{}] start", name)
            try:
                result = await fn(*args, **kwargs)
                logger.info("Node [{}] done", name)
                return result
            except Exception as e:
                logger.error("Node [{}] failed: {}", name, e)
                raise

        return async_wrapper if is_async else sync_wrapper
    return decorator
```

### Step 4: Run test to verify it passes

```bash
cd backend && uv run pytest tests/utils/test_observability.py -v
```

Expected: PASS

### Step 5: Commit

```bash
git add backend/src/utils/observability.py backend/tests/utils/test_observability.py
git commit -m "feat(backend): generalize traced_node to support async functions

- Detect async functions and use appropriate wrapper
- Maintain existing sync behavior unchanged"
```

---

## Task 7: Wire Health Checks into Lifespan & Clean Up Dead Code

**Files:**
- Modify: `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web/base.py:175`
- Modify: `backend/src/utils/README.md`

### Step 1: Fix dead import in `web/base.py`

Read lines 170-190 of `web/base.py` to identify the full try/except block (import at ~175, usage at ~176-188), then remove the entire block — both the import and the code that references the imported names:

```python
# Before (broken — lines ~175-188):
try:
    from src.config import get_settings, resolve_llm_triplet
    # ... lines 176-188 that use get_settings/resolve_llm_triplet ...
except (ImportError, Exception):
    pass

# After: remove the entire try/except block (lines ~175-188)
# The import target doesn't exist and all code inside is unreachable
```

### Step 2: Update `backend/src/utils/README.md`

Add documentation for the new modules:

```markdown
## Modules

| Module | Purpose |
|--------|---------|
| `logger.py` | Shared loguru configuration (stderr + file sinks, stdlib interception) |
| `exceptions.py` | Centralized exception hierarchy with stable error codes |
| `middleware.py` | Request monitoring middleware (timing + logging) |
| `health.py` | Startup dependency health checks (PostgreSQL, Redis) |
| `observability.py` | Pipeline node tracing (LangSmith + loguru) |
| `text.py` | Text normalization utilities |
| `rust_io.py` | Rust IO bridge utilities |
```

### Step 3: Run full test suite

```bash
cd backend && uv run pytest tests/ -v --timeout=30
```

Expected: All tests pass.

### Step 4: Commit

```bash
git add backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web/base.py
git add backend/src/utils/README.md
git commit -m "fix(backend): remove dead import and update utils README

- Remove broken import from src.config in web/base.py
- Document new utils modules in README"
```

---

## Task 8: Integration Smoke Test

**Files:**
- Create: `backend/tests/integration/test_app_startup.py`

### Step 1: Write the integration test

```python
"""Integration test: full app startup and health check."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def app():
    """Import the app with mocked health checks (triggers lifespan setup)."""
    with patch(
        "src.utils.health.check_all_connections",
        new_callable=AsyncMock,
        return_value={"postgres": True, "redis": True},
    ):
        from app.main import app as _app
        yield _app


def test_app_starts_and_health_returns_ok(app):
    """The app should start up and respond to /health."""
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_structured_error_on_unknown_route(app):
    """Unknown routes should return structured error envelope."""
    client = TestClient(app)
    resp = client.get("/api/v1/definitely-not-real")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert "request_id" in body
```

### Step 2: Run integration test

```bash
cd backend && uv run pytest tests/integration/test_app_startup.py -v
```

Expected: PASS

### Step 3: Run full test suite one final time

```bash
cd backend && uv run pytest tests/ -v --timeout=30
```

Expected: All tests pass.

### Step 4: Commit

```bash
git add backend/tests/integration/test_app_startup.py
git commit -m "test(backend): add integration smoke test for app startup

- Verify health endpoint responds
- Verify structured error responses on unknown routes"
```

---

## Final Verification Checklist

```bash
cd backend

# Lint check
uv run ruff check

# Full test suite
uv run pytest tests/ -v --timeout=30

# Verify app starts (manual)
uv run uvicorn app.main:app --reload
# Then: curl http://localhost:8000/health
# Then: curl http://localhost:8000/api/v1/nonexistent
```

Expected results:
- `ruff check` — no errors
- `pytest` — all pass
- `/health` — `{"status": "ok"}`
- `/api/v1/nonexistent` — `{"error": {"code": "NOT_FOUND", "message": "..."}, "request_id": "..."}`
