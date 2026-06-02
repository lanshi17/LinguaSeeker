# Unified Backend Configuration & Monitoring Completion Report

**Status:** completed
**Created:** 2026-05-30
**Completed:** 2026-05-30
**Archived:** 2026-06-02
**PR:** not recorded

## Summary

The unified backend configuration and monitoring work has been implemented. The original document was still under `docs/planned/`, but the codebase and `progress.txt` both show this work completed on 2026-05-30. This document is now an archive record of the actual implementation state rather than an executable plan.

Original goal: unify backend observability primitives for the main FastAPI app, including structured logging, centralized exceptions, request monitoring, dependency health checks, global error responses, CORS, async node tracing, and startup smoke coverage.

## Actual Implementation Status

| Area | Status | Actual state | Evidence |
|---|---|---|---|
| Structured logging | completed | `setup_logging()` configures loguru stderr and file sinks, intercepts stdlib logging, and is idempotent. Current file sink level is `INFO`, not the original plan's `DEBUG`. | `backend/src/utils/logger.py`, `backend/app/main.py`, `backend/tests/utils/test_logger.py` |
| Centralized exceptions | completed | `ACMGException` plus domain subclasses and HTTP/error-code mapping helpers are implemented. | `backend/src/utils/exceptions.py`, `backend/tests/utils/test_exceptions.py` |
| Request monitoring | completed with design correction | Implemented as raw ASGI middleware, not `BaseHTTPMiddleware`, so SSE/chunked responses are not buffered. It adds or preserves `X-Request-ID` and logs method/path/status/timing. | `backend/src/utils/middleware.py`, `backend/tests/utils/test_middleware.py` |
| Dependency health checks | completed | Startup checks cover PostgreSQL and Redis through `HealthResult`; checks are non-blocking and log failures without crashing startup. | `backend/src/utils/health.py`, `backend/src/api/wiring.py`, `backend/tests/utils/test_health.py` |
| Global error handlers | completed | `ACMGException`, Starlette HTTP exceptions, and request validation errors return structured error envelopes with request IDs. | `backend/app/main.py`, `backend/tests/api/test_error_handlers.py` |
| CORS | completed | `Settings.cors_origins` and `cors_origins_list` drive `CORSMiddleware`; wildcard origins disable credentials to satisfy browser rules. | `backend/src/core/config.py`, `backend/app/main.py` |
| `/health` response model | completed | `/health` returns `HealthResponse` instead of a bare dict. The endpoint remains a liveness endpoint; dependency readiness is checked at startup and logged. | `backend/app/main.py`, `backend/tests/api/test_health_endpoint.py` |
| Async `traced_node` | completed | `traced_node()` supports both sync and async functions while preserving LangSmith tracing and loguru start/done/error logs. | `backend/src/utils/observability.py`, `backend/tests/utils/test_observability.py` |
| Dead import cleanup | completed | The broken `from src.config import ...` path described in the original plan is gone; `web/base.py` now resolves crawl4ai LLM config from environment variables directly. | `backend/src/core/ingest_and_digitize_data/document_acquisition/online_acquisition/web/base.py` |
| Integration smoke coverage | completed | App startup and `/health` request-ID behavior are covered with mocked config and health checks. | `backend/tests/integration/test_app_startup.py` |

## Current Architecture Notes

`backend/app/main.py` now exposes `create_app()` and a backward-compatible module-level `app: FastAPI = create_app()` alias. Tests that need config isolation import `create_app()` only after patching `src.core.config.get_config`.

Middleware registration order currently includes CORS, request monitoring, body size limiting, and rate limiting. The body size and rate limiting additions were introduced by later security work, but they now share the same app factory surface.

The request monitor is intentionally raw ASGI middleware. This differs from the earliest plan text and from the model server's factory pattern, but it avoids the streaming-response problems caused by `BaseHTTPMiddleware`.

## Remaining Follow-Up Work

These items were intentionally deferred or remain true after implementation:

| Item | Current state | Suggested follow-up |
|---|---|---|
| Model server logger duplication | `backend/services/model-server/app/utils/logger.py` still owns its own logger setup. | Keep standalone until the model server dependency path is intentionally unified. |
| Model server request monitor API | Model server still uses its own middleware factory pattern. | Unify only if the service is moved onto shared backend utilities. |
| Feature-specific exceptions | `ParseDocumentError`, `TranslationError`, `PhaseError`, and `SemanticMatchServiceError` still do not inherit from `ACMGException`. | Migrate in a focused exception-normalization task with regression tests. |
| `/health` readiness detail | `/health` returns only `{"status": "ok"}`. Startup dependency checks are logged but not exposed as readiness details. | Add a separate readiness endpoint if operational tooling needs per-service state. |

## Verification

Current focused verification was run on 2026-06-02:

```bash
cd backend
uv run pytest tests/utils/test_logger.py tests/utils/test_exceptions.py tests/utils/test_middleware.py tests/utils/test_health.py tests/utils/test_observability.py tests/api/test_error_handlers.py tests/api/test_health_endpoint.py tests/integration/test_app_startup.py -q
```

Result:

```text
40 passed in 50.61s
```

Historical progress record also marks the implementation complete:

```text
[2026-05-30] Unified backend config & monitoring: structured logging, centralized exceptions, request monitoring middleware, dependency health checks, global error handlers + CORS, async traced_node, dead code cleanup, integration smoke test [done]
```
