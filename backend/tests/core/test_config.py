"""Tests for PaddleOCR config in Settings."""
from src.core.config import Settings


def test_paddle_config_defaults():
    settings = Settings()
    assert hasattr(settings, "paddle")
    assert settings.paddle.model_path == ""
    assert settings.paddle.use_gpu is False
    assert settings.paddle.lang == "en"
