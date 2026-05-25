"""Tests for model server config in Settings."""
from src.core.config import Settings


def test_model_server_url_default():
    settings = Settings()
    assert settings.model_server_url == "http://localhost:8001"


def test_standardization_similarity_model_defaults_match_model_server() -> None:
    """Backend semantic matching defaults align with model-server defaults."""
    from src.core.config import Settings

    settings = Settings()

    assert settings.embedding.base_url == ""
    assert settings.embedding.model == "Qwen/Qwen3-Embedding-0.6B"
    assert settings.embedding.dimension == 1024
    assert settings.rerank.model == "BAAI/bge-reranker-v2-m3"
