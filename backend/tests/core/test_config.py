"""Tests for model server config in Settings."""

from src.core.config import Settings


def test_model_server_url_default():
    settings = Settings()
    assert settings.model_server_url == "http://localhost:8001"


def test_standardization_similarity_model_defaults_match_model_server() -> None:
    """Backend semantic matching defaults align with model-server defaults."""
    from src.core.config import EmbeddingConfig, RerankConfig

    # Test pure defaults by instantiating the config models directly
    embedding = EmbeddingConfig()
    rerank = RerankConfig()

    assert embedding.base_url == ""
    assert embedding.model == "Qwen/Qwen3-Embedding-0.6B"
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

    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.config_context import (
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


def test_production_accepts_api_key() -> None:
    """Settings accepts production with a valid API_KEY."""
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
