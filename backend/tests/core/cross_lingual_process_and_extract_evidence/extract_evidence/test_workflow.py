import pytest
from unittest.mock import MagicMock

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import EvidenceExtractionService
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DocumentEvidenceMap,
    EvidenceExtractionStatus,
    PageSpan,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.workflow import EvidenceExtractionWorkflow


@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.evidence_extraction.api_key = "key"
    cfg.evidence_extraction.base_url = "http://localhost:8001/v1"
    cfg.evidence_extraction.fast_model = "fast"
    cfg.evidence_extraction.standard_model = "standard"
    cfg.evidence_extraction.strong_model = "strong"
    cfg.evidence_extraction.temperature = 0.0
    cfg.evidence_extraction.timeout = 60
    cfg.evidence_extraction.max_retries = 3
    return cfg


@pytest.mark.asyncio
async def test_workflow_returns_not_relevant():
    provider = MagicMock()
    emap = DocumentEvidenceMap(relevant=False)
    provider.invoke_structured.return_value = emap

    workflow = EvidenceExtractionWorkflow(provider=provider)

    state = await workflow.run(
        TrackDocument(
            document_id="doc-1",
            track=Track.ORIGINAL,
            formatted_text="unrelated paper",
            page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=15)],
        )
    )

    assert state.status == EvidenceExtractionStatus.NOT_RELEVANT
    assert state.evidence_items == []


@pytest.mark.asyncio
async def test_service_facade_builds_result(mock_config):
    provider = MagicMock()
    emap = DocumentEvidenceMap(relevant=False)
    provider.invoke_structured.return_value = emap

    service = EvidenceExtractionService(cfg=mock_config)
    service._workflow = EvidenceExtractionWorkflow(provider=provider)

    result = await service.run(
        TrackDocument(
            document_id="doc-1",
            track=Track.ORIGINAL,
            formatted_text="unrelated paper",
            page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=15)],
        )
    )

    assert result.status == EvidenceExtractionStatus.NOT_RELEVANT
    assert result.document_id == "doc-1"
    assert result.evidence_items == []
