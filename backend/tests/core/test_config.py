"""Tests for model server config in Settings."""
from pathlib import Path

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
    """Settings no longer uses env_file; config comes from config-dev.yaml."""
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


def test_evidence_extraction_falls_back_to_llm_config() -> None:
    """When EVIDENCE_EXTRACTION_* vars are unset, evidence_extraction uses LLM config."""
    import os

    # Save originals
    saved = {}
    keys = [
        "EVIDENCE_EXTRACTION_API_KEY", "EVIDENCE_EXTRACTION_BASE_URL",
        "EVIDENCE_EXTRACTION_FAST_MODEL", "EVIDENCE_EXTRACTION_STANDARD_MODEL",
        "EVIDENCE_EXTRACTION_STRONG_MODEL",
        "FAST_LLM_API_KEY", "FAST_LLM_BASE_URL", "FAST_LLM_MODEL",
    ]
    for k in keys:
        saved[k] = os.environ.pop(k, None)

    try:
        os.environ["FAST_LLM_API_KEY"] = "test-key-123"
        os.environ["FAST_LLM_BASE_URL"] = "https://test.example.com/v1"
        os.environ["FAST_LLM_MODEL"] = "test-model"
        settings = Settings(_env_file=None)
        assert settings.evidence_extraction.api_key == "test-key-123"
        assert settings.evidence_extraction.base_url == "https://test.example.com/v1"
        assert settings.evidence_extraction.fast_model == "test-model"
        assert settings.evidence_extraction.standard_model == "test-model"
        assert settings.evidence_extraction.strong_model == "test-model"
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def test_evidence_extraction_explicit_overrides_fallback() -> None:
    """Explicit EVIDENCE_EXTRACTION_* vars take precedence over LLM fallback."""
    import os

    saved = {}
    keys = [
        "EVIDENCE_EXTRACTION_API_KEY", "EVIDENCE_EXTRACTION_BASE_URL",
        "EVIDENCE_EXTRACTION_FAST_MODEL", "EVIDENCE_EXTRACTION_STANDARD_MODEL",
        "EVIDENCE_EXTRACTION_STRONG_MODEL",
        "FAST_LLM_API_KEY", "FAST_LLM_BASE_URL", "FAST_LLM_MODEL",
    ]
    for k in keys:
        saved[k] = os.environ.pop(k, None)

    try:
        os.environ["FAST_LLM_API_KEY"] = "fallback-key"
        os.environ["FAST_LLM_BASE_URL"] = "https://fallback.example.com/v1"
        os.environ["FAST_LLM_MODEL"] = "fallback-model"
        os.environ["EVIDENCE_EXTRACTION_API_KEY"] = "explicit-key"
        os.environ["EVIDENCE_EXTRACTION_FAST_MODEL"] = "explicit-fast"
        settings = Settings(_env_file=None)
        assert settings.evidence_extraction.api_key == "explicit-key"
        assert settings.evidence_extraction.fast_model == "explicit-fast"
        # Fields without explicit override fall back
        assert settings.evidence_extraction.base_url == "https://fallback.example.com/v1"
        assert settings.evidence_extraction.standard_model == "fallback-model"
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)
