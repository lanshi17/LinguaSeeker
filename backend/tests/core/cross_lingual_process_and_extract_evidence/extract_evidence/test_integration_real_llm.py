"""Integration test with real LLM. Skipped unless env vars are present."""
from __future__ import annotations

import os

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import EvidenceExtractionService
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceExtractionStatus,
    PageSpan,
    Track,
    TrackDocument,
)

_REQUIRED_ENV = [
    "EVIDENCE_EXTRACTION_API_KEY",
    "EVIDENCE_EXTRACTION_BASE_URL",
    "EVIDENCE_EXTRACTION_FAST_MODEL",
    "EVIDENCE_EXTRACTION_STANDARD_MODEL",
    "EVIDENCE_EXTRACTION_STRONG_MODEL",
]

_skip_reason = "Evidence extraction env vars not configured"
_skip = not all(os.environ.get(v) for v in _REQUIRED_ENV)


@pytest.mark.integration
@pytest.mark.skipif(_skip, reason=_skip_reason)
@pytest.mark.asyncio
async def test_evidence_extraction_with_real_llm():
    from src.core.config import get_config

    cfg = get_config()
    service = EvidenceExtractionService(cfg=cfg)

    document = TrackDocument(
        document_id="integration-test-1",
        track=Track.ORIGINAL,
        formatted_text=(
            "Patient 1 had Fabry disease and carried a hemizygous GLA c.1000G>A "
            "(p.Gly334Ser) variant. The variant was absent from population databases. "
            "No functional assay was reported."
        ),
        page_spans=[
            PageSpan(span_id="p1", page=1, start_offset=0, end_offset=167),
        ],
    )

    result = await service.run(document)

    assert result.status in (EvidenceExtractionStatus.COMPLETED, EvidenceExtractionStatus.NOT_RELEVANT)
    if result.status == EvidenceExtractionStatus.COMPLETED:
        found_items = [i for i in result.evidence_items if i.status.value == "found"]
        assert len(found_items) > 0
        assert any(i.source is not None for i in found_items)
        assert result.quality_report is not None
