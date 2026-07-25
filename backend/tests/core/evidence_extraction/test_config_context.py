from unittest.mock import MagicMock

from src.core.evidence_extraction.config_context import (
    EvidenceExtractionConfigContext,
)


def test_evidence_extraction_config_context_from_config():
    cfg = MagicMock()
    cfg.llm.api_key = "fast-key"
    cfg.llm.base_url = "https://fast.example.com/v1"
    cfg.llm.model = "qwen-flash"
    cfg.llm.timeout = 60
    cfg.reasoning.api_key = "reasoning-key"
    cfg.reasoning.base_url = "https://reasoning.example.com/v1"
    cfg.reasoning.model = "qwen-max"
    cfg.reasoning.reasoning_effort = "high"
    cfg.reasoning.max_tokens = 8192
    cfg.reasoning.timeout = 180

    ctx = EvidenceExtractionConfigContext.from_config(cfg)

    assert ctx.api_key == "fast-key"
    assert ctx.base_url == "https://fast.example.com/v1"
    assert ctx.fast_model == "qwen-flash"
    assert ctx.reasoning_api_key == "reasoning-key"
    assert ctx.reasoning_base_url == "https://reasoning.example.com/v1"
    assert ctx.strong_model == "qwen-max"
    assert ctx.standard_model == "qwen-max"
    assert ctx.timeout == 180
    assert ctx.strong_effort == "high"
