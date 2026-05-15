from unittest.mock import MagicMock

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.config_context import (
    EvidenceExtractionConfigContext,
)


def test_evidence_extraction_config_context_from_config():
    cfg = MagicMock()
    cfg.evidence_extraction.api_key = "key"
    cfg.evidence_extraction.base_url = "http://localhost:8001/v1"
    cfg.evidence_extraction.fast_model = "qwen-flash"
    cfg.evidence_extraction.standard_model = "qwen-plus"
    cfg.evidence_extraction.strong_model = "qwen-max"
    cfg.evidence_extraction.temperature = 0.0
    cfg.evidence_extraction.timeout = 60
    cfg.evidence_extraction.max_retries = 3

    ctx = EvidenceExtractionConfigContext.from_config(cfg)

    assert ctx.fast_model == "qwen-flash"
    assert ctx.standard_model == "qwen-plus"
    assert ctx.strong_model == "qwen-max"
    assert ctx.timeout == 60
    assert ctx.max_retries == 3
