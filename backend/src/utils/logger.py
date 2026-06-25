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

# ── Public API ───────────────────────────────────────────────────────────


def get_logger():
    """Return the loguru logger instance."""
    return _logger


def setup_logging(*, environment: str = "development", debug: bool = False) -> None:
    """Configure loguru sinks and intercept stdlib logging.

    Call once during application startup (lifespan). Both parameters are
    keyword-only with defaults so that callers that don't pass them (e.g.
    external services' ``setup_logging()``) remain backward-compatible.

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

    # File sink — INFO+, daily rotation, 14-day retention
    # Naming follows AGENTS.md rule 7: YYYY-MM-DD_HHmmss.log
    _logger.add(
        LOG_DIR / "{time:YYYY-MM-DD_HHmmss}.log",
        rotation="1 day",
        retention="14 days",
        compression="gz",
        level="INFO",
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
        # depth=6 skips: emit → handle → callHandlers → _log → log → user_code
        # If log messages show wrong file/line, adjust this value.
        _logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())
