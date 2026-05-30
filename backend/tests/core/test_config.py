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


def test_settings_default_env_files_include_repo_and_backend_locations() -> None:
    """Default env-file search paths are absolute and independent of cwd."""
    backend_root = Path(__file__).resolve().parents[2]
    env_files = Settings.model_config.get("env_file")

    assert isinstance(env_files, tuple)
    assert str(backend_root / ".env.local") in env_files


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
