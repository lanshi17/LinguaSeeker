"""Tests for parse document configuration."""
from __future__ import annotations


def test_parse_document_config_defaults():
    """Test that ParseDocumentConfig has correct defaults."""
    from src.core.config import ParseDocumentConfig

    config = ParseDocumentConfig()
    assert config.mineru_remote_poll_interval == 2.0
    assert config.mineru_remote_max_poll_attempts == 150
    assert config.mineru_local_api_url == "http://localhost:8001"
    assert config.mineru_local_timeout == 600.0
    assert config.mineru_local_backend == "vlm"


def test_parse_document_config_from_settings(monkeypatch):
    """Test that Settings loads env vars and builds ParseDocumentConfig."""
    from src.core.config import Settings

    monkeypatch.setenv("MINERU_REMOTE_POLL_INTERVAL", "3.0")
    monkeypatch.setenv("MINERU_LOCAL_API_URL", "http://mineru:30000")

    settings = Settings()
    assert settings.parse_document.mineru_remote_poll_interval == 3.0
    assert settings.parse_document.mineru_local_api_url == "http://mineru:30000"
