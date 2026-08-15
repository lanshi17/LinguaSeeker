"""Tests for the shared logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from loguru import logger as _logger


@pytest.fixture(autouse=True)
def _isolate_loguru():
    """Save and restore loguru handler state around each test."""
    import src.utils.logger as _mod

    _logger.remove()
    _mod._configured = False  # reset idempotency guard
    yield
    _logger.remove()  # leave clean state after each test


def test_setup_logging_installs_stderr_sink():
    """setup_logging() should configure loguru with a stderr sink."""
    import sys
    from src.utils.logger import setup_logging

    setup_logging()
    handlers = _logger._core.handlers
    # Verify at least one handler writes to stderr
    stderr_sinks = [
        h for h in handlers.values() if hasattr(h, "_sink") and getattr(h._sink, "_stream", None) is sys.stderr
    ]
    assert len(stderr_sinks) >= 1, "Expected at least one stderr handler"


def test_setup_logging_intercepts_stdlib():
    """setup_logging() should redirect stdlib logging through loguru."""
    from src.utils.logger import setup_logging

    setup_logging()

    root = logging.getLogger()
    assert any(isinstance(h, logging.Handler) for h in root.handlers)


def test_setup_logging_silences_noisy_third_party_loggers():
    """Noisy HTTP/driver loggers are raised to WARNING to avoid log floods."""
    from src.utils.logger import setup_logging

    setup_logging()

    for name in ("openai", "httpcore", "httpx", "neo4j"):
        assert logging.getLogger(name).level == logging.WARNING, (
            f"Expected {name} logger at WARNING, got {logging.getLogger(name).level}"
        )


def test_log_dir_created(tmp_path: Path):
    """setup_logging() should create the logs directory and add a file sink."""
    from src.utils.logger import setup_logging

    test_dir = tmp_path / "test_logs"
    with patch("src.utils.logger.LOG_DIR", test_dir):
        setup_logging()
        assert test_dir.exists()
        # Verify at least one file sink was registered
        file_sinks = [
            h
            for h in _logger._core.handlers.values()
            if hasattr(h, "_sink") and getattr(h._sink, "_path", None) is not None
        ]
        assert len(file_sinks) >= 1, "Expected at least one file sink after setup_logging()"
