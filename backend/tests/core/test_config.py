"""Tests for model server and LLM config in Settings."""
from src.core.config import Settings


def test_model_server_url_default():
    settings = Settings()
    assert settings.model_server_url == "http://localhost:8001"


def test_fast_llm_env_populates_llm_nested_config(monkeypatch) -> None:
    monkeypatch.setenv("FAST_LLM_API_KEY", "fast-key")
    monkeypatch.setenv("FAST_LLM_BASE_URL", "https://fast.example/v1")
    monkeypatch.setenv("FAST_LLM_MODEL", "fast-model")
    monkeypatch.setenv("FAST_LLM_TEMPERATURE", "0.2")
    monkeypatch.setenv("FAST_LLM_MAX_TOKENS", "4096")
    monkeypatch.setenv("FAST_LLM_TIMEOUT", "30")
    monkeypatch.setenv("FAST_LLM_MAX_RETRIES", "5")

    settings = Settings(_env_file=None)

    assert settings.llm.api_key == "fast-key"
    assert settings.llm.base_url == "https://fast.example/v1"
    assert settings.llm.model == "fast-model"
    assert settings.llm.temperature == 0.2
    assert settings.llm.max_tokens == 4096
    assert settings.llm.timeout == 30
    assert settings.llm.max_retries == 5


def test_reasoning_llm_env_populates_reasoning_nested_config(monkeypatch) -> None:
    monkeypatch.setenv("REASONING_LLM_API_KEY", "reason-key")
    monkeypatch.setenv("REASONING_LLM_BASE_URL", "https://reason.example/v1")
    monkeypatch.setenv("REASONING_LLM_MODEL", "reason-model")
    monkeypatch.setenv("REASONING_LLM_REASONING_EFFORT", "xhigh")

    settings = Settings(_env_file=None)

    assert settings.reasoning.api_key == "reason-key"
    assert settings.reasoning.base_url == "https://reason.example/v1"
    assert settings.reasoning.model == "reason-model"
    assert settings.reasoning.reasoning_effort == "xhigh"
