import pytest
from unittest.mock import MagicMock

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import EvidenceExtractionService
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceExtractionStatus,
    EvidenceStatus,
    PageSpan,
    SourceLocation,
    SourcePrecision,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import EvidenceChainBuilder
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


def _found_item(field_id: str, value: str) -> EvidenceItem:
    category, field_name = field_id.split(".", maxsplit=1)
    return EvidenceItem(
        field_id=field_id,
        category=category,
        field_name=field_name,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.9,
        source=SourceLocation(
            span_id="p1",
            page=1,
            start_offset=0,
            end_offset=len(value),
            context_type="text",
            context_ref="",
            text_snippet=value,
        ),
    )


def test_evidence_chain_builder_creates_identity_chain_from_grounded_fields():
    items = [
        _found_item("A.gene_symbol", "GLA"),
        _found_item("B.disease_diagnosis", "Fabry disease"),
        _found_item("A.variant_hgvs_p", "p.R227X"),
    ]

    chains = EvidenceChainBuilder().build(items)

    assert len(chains) == 1
    assert chains[0].gene_text == "GLA"
    assert chains[0].disease_text == "Fabry disease"
    assert chains[0].variant_text == "p.R227X"
    assert chains[0].evidence_field_ids == ["A.gene_symbol", "B.disease_diagnosis", "A.variant_hgvs_p"]
    assert chains[0].chain_id == "A.gene_symbol-B.disease_diagnosis-A.variant_hgvs_p"


def test_evidence_chain_builder_skips_ambiguous_sources():
    items = [
        EvidenceItem(
            field_id="A.gene_symbol",
            category="A",
            field_name="Gene symbol",
            status=EvidenceStatus.FOUND,
            value="GLA",
            confidence=0.9,
            source=SourceLocation(
                span_id="p1",
                page=1,
                start_offset=0,
                end_offset=3,
                context_type="text",
                context_ref="",
                text_snippet="GLA",
                source_precision=SourcePrecision.AMBIGUOUS,
            ),
        ),
        _found_item("B.disease_diagnosis", "Fabry disease"),
        _found_item("A.variant_hgvs_p", "p.R227X"),
    ]

    chains = EvidenceChainBuilder().build(items)

    assert chains == []
