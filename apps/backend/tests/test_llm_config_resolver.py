"""Test LLM configuration resolver functionality.

This test module verifies the LLM triplet resolver that consolidates
(api_key, base_url, model) for each LLM role.
"""

import pytest


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set all required environment variables for Settings instantiation."""
    # Set 8 LLM triplets (required fields)
    llm_roles = [
        "retrieval",
        "parsing",
        "mt",
        "format",
        "vlm",
        "evidence",
        "classification",
        "arbitration",
    ]
    for role in llm_roles:
        monkeypatch.setenv(f"{role.upper()}_API_KEY", f"test-{role}-key")
        monkeypatch.setenv(f"{role.upper()}_BASE_URL", f"https://test-{role}.example.com")
        monkeypatch.setenv(f"{role.upper()}_MODEL", f"test-{role}-model")

    # Set required database credentials
    monkeypatch.setenv("POSTGRES_PASSWORD", "test-postgres-password")
    monkeypatch.setenv("NEO4J_PASSWORD", "test-neo4j-password")

    # Set required MinIO credentials (Task 1.1 requirement)
    monkeypatch.setenv("MINIO_ACCESS_KEY", "test-minio-access-key")
    monkeypatch.setenv("MINIO_SECRET_KEY", "test-minio-secret-key")


def test_llm_triplet_dataclass_exists(mock_env_vars):
    """Test that LLMTriplet dataclass is defined."""
    from src.config import LLMTriplet

    triplet = LLMTriplet(
        api_key="test-key", base_url="https://test.example.com", model="test-model"
    )

    assert triplet.api_key == "test-key"
    assert triplet.base_url == "https://test.example.com"
    assert triplet.model == "test-model"


def test_resolve_llm_triplet_function_exists(mock_env_vars):
    """Test that resolve_llm_triplet function is defined."""
    from src.config import resolve_llm_triplet

    # Function should exist and be callable
    assert callable(resolve_llm_triplet)


def test_resolve_evidence_llm(mock_env_vars):
    """Test resolving evidence LLM configuration."""
    from src.config import resolve_llm_triplet, Settings

    settings = Settings()
    triplet = resolve_llm_triplet(settings, "evidence")

    assert triplet.api_key == "test-evidence-key"
    assert triplet.base_url == "https://test-evidence.example.com"
    assert triplet.model == "test-evidence-model"


def test_resolve_mt_llm(mock_env_vars):
    """Test resolving multi-language translation LLM configuration."""
    from src.config import resolve_llm_triplet, Settings

    settings = Settings()
    triplet = resolve_llm_triplet(settings, "mt")

    assert triplet.api_key == "test-mt-key"
    assert triplet.base_url == "https://test-mt.example.com"
    assert triplet.model == "test-mt-model"


def test_resolve_all_llm_roles(mock_env_vars):
    """Test resolving all 8 LLM role configurations."""
    from src.config import resolve_llm_triplet, Settings

    settings = Settings()
    roles = [
        "retrieval",
        "parsing",
        "mt",
        "format",
        "vlm",
        "evidence",
        "classification",
        "arbitration",
    ]

    for role in roles:
        triplet = resolve_llm_triplet(settings, role)

        assert triplet.api_key == f"test-{role}-key"
        assert triplet.base_url == f"https://test-{role}.example.com"
        assert triplet.model == f"test-{role}-model"


def test_backward_compatibility_existing_fields(mock_env_vars):
    """Test that existing Settings fields still work (backward compatibility)."""
    from src.config import Settings

    settings = Settings()

    # Existing code should still be able to access fields directly
    assert settings.evidence_api_key == "test-evidence-key"
    assert settings.evidence_base_url == "https://test-evidence.example.com"
    assert settings.evidence_model == "test-evidence-model"

    assert settings.mt_api_key == "test-mt-key"
    assert settings.mt_base_url == "https://test-mt.example.com"
    assert settings.mt_model == "test-mt-model"


def test_invalid_role_raises_error(mock_env_vars):
    """Test that resolving invalid role raises appropriate error."""
    from src.config import resolve_llm_triplet, Settings

    settings = Settings()

    with pytest.raises((ValueError, KeyError)):
        resolve_llm_triplet(settings, "invalid_role")
