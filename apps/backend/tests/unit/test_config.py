from __future__ import annotations

from src.config import AppConfig, Settings


def test_app_config_loads_postgres_schema_from_env(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_SCHEMA", "acmg_app")

    cfg = AppConfig.from_env()

    assert cfg.postgresql.schema == "acmg_app"


def test_settings_exposes_firecrawl_compat_fields(monkeypatch) -> None:
    monkeypatch.setenv("RETRIEVAL_BASE_URL", "https://example.firecrawl.test")
    monkeypatch.setenv("RETRIEVAL_API_KEY", "test-firecrawl-key")
    monkeypatch.setenv("RETRIEVAL_MODEL", "qwen-test")
    monkeypatch.setenv("PARSING_API_KEY", "x")
    monkeypatch.setenv("PARSING_BASE_URL", "x")
    monkeypatch.setenv("PARSING_MODEL", "x")
    monkeypatch.setenv("MT_API_KEY", "x")
    monkeypatch.setenv("MT_BASE_URL", "x")
    monkeypatch.setenv("MT_MODEL", "x")
    monkeypatch.setenv("FORMAT_API_KEY", "x")
    monkeypatch.setenv("FORMAT_BASE_URL", "x")
    monkeypatch.setenv("FORMAT_MODEL", "x")
    monkeypatch.setenv("VLM_API_KEY", "x")
    monkeypatch.setenv("VLM_BASE_URL", "x")
    monkeypatch.setenv("VLM_MODEL", "x")
    monkeypatch.setenv("EVIDENCE_API_KEY", "x")
    monkeypatch.setenv("EVIDENCE_BASE_URL", "x")
    monkeypatch.setenv("EVIDENCE_MODEL", "x")
    monkeypatch.setenv("CLASSIFICATION_API_KEY", "x")
    monkeypatch.setenv("CLASSIFICATION_BASE_URL", "x")
    monkeypatch.setenv("CLASSIFICATION_MODEL", "x")
    monkeypatch.setenv("ARBITRATION_API_KEY", "x")
    monkeypatch.setenv("ARBITRATION_BASE_URL", "x")
    monkeypatch.setenv("ARBITRATION_MODEL", "x")
    monkeypatch.setenv("POSTGRES_PASSWORD", "x")
    monkeypatch.setenv("NEO4J_PASSWORD", "x")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "x")
    monkeypatch.setenv("MINIO_SECRET_KEY", "y")

    settings = Settings()

    assert settings.firecrawl_base_url == "https://example.firecrawl.test"
    assert settings.firecrawl_api_key == "test-firecrawl-key"
