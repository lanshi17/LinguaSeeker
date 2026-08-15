"""Shared logging configuration — loguru sinks + stdlib interception."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from loguru import logger as _logger

# ── Defaults ─────────────────────────────────────────────────────────────

# backend/src/utils/logger.py → up 4 levels → project root
LOG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "logs"

_configured: bool = False

# Third-party stdlib loggers that emit per-request DEBUG/INFO spam (including
# full request/response bodies). Raised to WARNING in setup_logging() so the
# loguru sinks aren't flooded during LLM-heavy pipeline runs.
_NOISY_LOGGERS = ("openai", "httpcore", "httpx", "neo4j")

# ── Public API ───────────────────────────────────────────────────────────


def get_logger():
    """Return the loguru logger instance."""
    return _logger


def setup_logging(
    *,
    environment: str = "development",
    debug: bool = False,
    file_level: str = "INFO",
) -> None:
    """Configure loguru sinks and intercept stdlib logging.

    Call once during application startup (lifespan). All parameters are
    keyword-only with defaults so that callers that don't pass them (e.g.
    external services' ``setup_logging()``) remain backward-compatible.

    ``file_level`` sets the minimum level written to the file sink
    (backend/logs/YYYY-MM-DD/HHmmss.log). The app passes the configured
    ``logging.file_level`` from YAML / ``LOGGING_FILE_LEVEL`` env var.

    Idempotent: subsequent calls are no-ops. Tests bypass this by calling
    ``_logger.remove()`` directly via the ``_isolate_loguru`` fixture.
    """
    global _configured
    if _configured:
        return

    LOG_DIR.mkdir(exist_ok=True)
    _logger.remove()
    _configured = True

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

    # File sink — WARNING+, daily rotation into date subdirectories, 14-day retention
    # Path uses loguru's {time:...} interpolation evaluated per rotation:
    #   logs/2026-06-30/143000.log
    #   logs/2026-07-01/093000.log
    _logger.add(
        str(LOG_DIR / "{time:YYYY-MM-DD}" / "{time:HHmmss}.log"),
        rotation="1 day",
        retention="14 days",
        compression="gz",
        level=file_level,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} | {message}",
        enqueue=True,
    )

    # Intercept stdlib logging → loguru
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)

    # Silence verbose third-party HTTP/driver loggers. With the root logger at
    # level 0 (above), these libraries emit DEBUG/INFO records for every request
    # — including full request/response bodies — flooding the sinks and driving
    # heavy disk I/O during LLM-heavy pipeline runs (e.g. a 108 MB batch log
    # where ~48% of lines were httpcore/openai/httpx/neo4j DEBUG noise).
    for _name in _NOISY_LOGGERS:
        logging.getLogger(_name).setLevel(logging.WARNING)


class _InterceptHandler(logging.Handler):
    """Redirect stdlib ``logging`` output through loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = _logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        # depth=6 skips: emit → handle → callHandlers → _log → log → user_code
        # If log messages show wrong file/line, adjust this value.
        _logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())
