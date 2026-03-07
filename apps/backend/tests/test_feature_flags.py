from __future__ import annotations

from src.config import Settings


def _make_settings() -> Settings:
    return Settings(
        retrieval_api_key="test-key",
        retrieval_base_url="https://example.com/retrieval",
        retrieval_model="retrieval-model",
        parsing_api_key="test-key",
        parsing_base_url="https://example.com/parsing",
        parsing_model="parsing-model",
        mt_api_key="test-key",
        mt_base_url="https://example.com/mt",
        mt_model="mt-model",
        format_api_key="test-key",
        format_base_url="https://example.com/format",
        format_model="format-model",
        vlm_api_key="test-key",
        vlm_base_url="https://example.com/vlm",
        vlm_model="vlm-model",
        evidence_api_key="test-key",
        evidence_base_url="https://example.com/evidence",
        evidence_model="evidence-model",
        classification_api_key="test-key",
        classification_base_url="https://example.com/classification",
        classification_model="classification-model",
        arbitration_api_key="test-key",
        arbitration_model="arbitration-model",
        arbitration_base_url="https://example.com/arbitration",
        embedding_provider="nomic",
        embedding_base_url="https://example.com/embedding",
        embedding_api_key="test-key",
        embedding_model="embedding-model",
        embedding_dimension=1536,
        postgres_port=5432,
        postgres_password="postgres-password",
        neo4j_password="neo4j-password",
    )


def test_agent_workflow_flags_default_false(monkeypatch) -> None:
    for name in (
        "USE_AGENT_WORKFLOW_PDF",
        "USE_AGENT_WORKFLOW_PUBMED",
        "USE_AGENT_WORKFLOW_WEB",
    ):
        monkeypatch.delenv(name, raising=False)

    cfg = _make_settings()

    assert cfg.use_agent_workflow_pdf is False
    assert cfg.use_agent_workflow_pubmed is False
    assert cfg.use_agent_workflow_web is False
    assert cfg.use_agent_workflow("pdf") is False
    assert cfg.use_agent_workflow("pubmed") is False
    assert cfg.use_agent_workflow("web") is False
    assert cfg.use_agent_workflow("unknown") is False


def test_agent_workflow_pdf_env_override(monkeypatch) -> None:
    monkeypatch.setenv("USE_AGENT_WORKFLOW_PDF", "true")
    monkeypatch.delenv("USE_AGENT_WORKFLOW_PUBMED", raising=False)
    monkeypatch.delenv("USE_AGENT_WORKFLOW_WEB", raising=False)

    cfg = _make_settings()

    assert cfg.use_agent_workflow_pdf is True
    assert cfg.use_agent_workflow_pubmed is False
    assert cfg.use_agent_workflow_web is False
    assert cfg.use_agent_workflow("pdf") is True
    assert cfg.use_agent_workflow("pubmed") is False
