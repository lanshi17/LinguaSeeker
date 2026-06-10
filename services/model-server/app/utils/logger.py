"""Logging configuration — loguru + request monitoring middleware."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from loguru import logger as _logger

# ── Defaults ─────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

_logger.remove()
_logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}")
_logger.add(LOG_DIR / "model-server_{time:YYYY-MM-DD}.log", rotation="00:00", retention="14 days", level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | {name}:{function}:{line} | {message}")

# ── Public API ───────────────────────────────────────────────────────────

def get_logger() -> type[_logger]:
    return _logger


def setup_logging() -> None:
    """Install loguru as the stdlib logging handler."""
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)


class _InterceptHandler(logging.Handler):
    """Redirect stdlib logging → loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = _logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        _logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


# ── Request monitoring middleware (to be added in main.py) ───────────────

def request_monitor_middleware_factory():
    """Return an ASGI middleware that logs request duration and status."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    class RequestMonitorMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            start = time.perf_counter()
            response: Response = await call_next(request)
            elapsed = (time.perf_counter() - start) * 1000
            _logger.info("{method} {path} → {status} ({elapsed:.1f}ms)",
                         method=request.method, path=request.url.path,
                         status=response.status_code, elapsed=elapsed)
            return response

    return RequestMonitorMiddleware
