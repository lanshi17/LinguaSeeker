"""Tests for inference service config in Settings."""

from src.core.config import Settings


def test_pipeline_runtime_defaults_disabled_for_development(monkeypatch) -> None:
    """Development disables pipeline cache and duplicate-run prevention by default."""
    monkeypatch.delenv("PIPELINE_CACHE_ENABLED", raising=False)
    monkeypatch.delenv("PIPELINE_DEDUP_ENABLED", raising=False)

    settings = Settings(environment="development")

    assert settings.pipeline.cache_enabled is False
    assert settings.pipeline.dedup_enabled is False


def test_pipeline_runtime_defaults_enabled_for_production_like(monkeypatch) -> None:
    """Production-like environments enable pipeline cache and dedup by default."""
    monkeypatch.delenv("PIPELINE_CACHE_ENABLED", raising=False)
    monkeypatch.delenv("PIPELINE_DEDUP_ENABLED", raising=False)

    settings = Settings(environment="production", api_key="secret", redis_password="redis-secret")

    assert settings.pipeline.cache_enabled is True
    assert settings.pipeline.dedup_enabled is True


def test_pipeline_runtime_explicit_overrides_win(monkeypatch) -> None:
    """Explicit pipeline switches override environment-derived defaults."""
    monkeypatch.delenv("PIPELINE_CACHE_ENABLED", raising=False)
    monkeypatch.delenv("PIPELINE_DEDUP_ENABLED", raising=False)

    settings = Settings(
        environment="production",
        api_key="secret",
        redis_password="redis-secret",
        pipeline_cache_enabled=False,
        pipeline_dedup_enabled=False,
    )

    assert settings.pipeline.cache_enabled is False
    assert settings.pipeline.dedup_enabled is False


def test_inference_api_key_field_exists():
    """inference_api_key field exists on Settings with a string default."""
    settings = Settings()
    assert isinstance(settings.inference_api_key, str)


def test_standardization_similarity_model_defaults_match_inference_service() -> None:
    """Backend semantic matching defaults align with inference service defaults."""
    from src.core.config import EmbeddingConfig, RerankConfig

    # Test pure defaults by instantiating the config models directly
    embedding = EmbeddingConfig()
    rerank = RerankConfig()

    assert embedding.base_url == ""
    assert embedding.model == "BAAI/bge-m3"
    assert embedding.dimension == 1024
    assert rerank.model == "BAAI/bge-reranker-v2-m3"


def test_embedding_dimension_must_match_pgvector() -> None:
    """Configuration fails fast if embedding dimension does not match pgvector column."""
    import os

    from src.core.config import Settings

    original = os.environ.get("EMBEDDING_DIMENSION")
    try:
        os.environ["EMBEDDING_DIMENSION"] = "768"
        try:
            Settings()
            raise AssertionError("Expected ValueError for mismatched dimension")
        except ValueError as exc:
            assert "does not match pgvector column dimension" in str(exc)
    finally:
        if original is None:
            os.environ.pop("EMBEDDING_DIMENSION", None)
        else:
            os.environ["EMBEDDING_DIMENSION"] = original


def test_settings_no_env_files() -> None:
    """Settings no longer uses env_file; config comes from backend/config."""
    env_files = Settings.model_config.get("env_file")

    # env_file should not be configured — YAML is the source of truth
    assert env_files is None


def test_reasoning_config_has_timeout() -> None:
    """ReasoningConfig includes timeout field with default 60."""
    from src.core.config import ReasoningConfig

    cfg = ReasoningConfig()
    assert cfg.timeout == 60


def test_reasoning_config_timeout_from_settings() -> None:
    """Settings propagates reasoning_llm_timeout to ReasoningConfig.timeout."""
    import os

    original = os.environ.get("REASONING_LLM_TIMEOUT")
    try:
        os.environ["REASONING_LLM_TIMEOUT"] = "120"
        settings = Settings(_env_file=None)
        assert settings.reasoning.timeout == 120
    finally:
        if original is None:
            os.environ.pop("REASONING_LLM_TIMEOUT", None)
        else:
            os.environ["REASONING_LLM_TIMEOUT"] = original


def test_evidence_extraction_config_context_reads_from_llm_and_reasoning() -> None:
    """EvidenceExtractionConfigContext reads FAST from llm and STRONG from reasoning."""
    from unittest.mock import MagicMock

    from src.core.evidence_extraction.config_context import (
        EvidenceExtractionConfigContext,
    )

    cfg = MagicMock()
    cfg.llm.api_key = "fast-key"
    cfg.llm.base_url = "https://fast.example.com/v1"
    cfg.llm.model = "fast-model"
    cfg.llm.timeout = 60
    cfg.reasoning.api_key = "reasoning-key"
    cfg.reasoning.base_url = "https://reasoning.example.com/v1"
    cfg.reasoning.model = "reasoning-model"
    cfg.reasoning.reasoning_effort = "high"
    cfg.reasoning.max_tokens = 4096
    cfg.reasoning.timeout = 180

    ctx = EvidenceExtractionConfigContext.from_config(cfg)
    assert ctx.api_key == "fast-key"
    assert ctx.base_url == "https://fast.example.com/v1"
    assert ctx.fast_model == "fast-model"
    assert ctx.reasoning_api_key == "reasoning-key"
    assert ctx.reasoning_base_url == "https://reasoning.example.com/v1"
    assert ctx.strong_model == "reasoning-model"


def test_production_requires_api_key() -> None:
    """Settings raises ValueError when ENVIRONMENT=production and API_KEY is empty."""
    import pytest

    with pytest.raises(ValueError, match="API_KEY"):
        Settings(environment="production", api_key="")


def test_production_accepts_api_key(monkeypatch) -> None:
    """Settings accepts production with a valid API_KEY and required secrets."""
    monkeypatch.setenv("REDIS_PASSWORD", "secret-redis")
    settings = Settings(environment="production", api_key="secret")

    assert settings.is_production is True
    assert settings.api_key == "secret"


def test_llm_temperature_and_retries_are_propagated() -> None:
    """Settings propagates temperature and max_retries to nested LLM configs."""
    settings = Settings(
        fast_llm_temperature=0.2,
        fast_llm_max_retries=3,
        reasoning_llm_temperature=0.1,
        reasoning_llm_max_retries=4,
    )

    assert settings.llm.temperature == 0.2
    assert settings.llm.max_retries == 3
    assert settings.reasoning.temperature == 0.1
    assert settings.reasoning.max_retries == 4
