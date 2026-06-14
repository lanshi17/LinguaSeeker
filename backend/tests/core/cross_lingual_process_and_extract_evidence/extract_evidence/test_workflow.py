import pytest
from unittest.mock import AsyncMock, MagicMock

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.api import EvidenceExtractionService
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    DocumentEvidenceMap,
    EvidenceExtractionState,
    EvidenceExtractionStatus,
    EvidenceItem,
    EvidenceStatus,
    PageSpan,
    SourceLocation,
    SourcePrecision,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import EvidenceNormalizationIssueType
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import EvidenceChainBuilder
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.normalization import AcmgEvidenceValueNormalizer
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.workflow import EvidenceExtractionWorkflow


@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.llm.api_key = "key"
    cfg.llm.base_url = "http://localhost:8001/v1"
    cfg.llm.model = "fast"
    cfg.llm.timeout = 60
    cfg.reasoning.api_key = "key"
    cfg.reasoning.base_url = "http://localhost:8001/v1"
    cfg.reasoning.model = "strong"
    cfg.reasoning.reasoning_effort = "high"
    cfg.reasoning.max_tokens = 8192
    cfg.reasoning.timeout = 180
    return cfg


@pytest.mark.asyncio
async def test_workflow_returns_not_relevant():
    provider = MagicMock()
    emap = DocumentEvidenceMap(relevant=False)
    provider.invoke_structured.return_value = emap
    provider.ainvoke_structured = AsyncMock(return_value=emap)

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
    provider.ainvoke_structured = AsyncMock(return_value=emap)

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
        group_id="gene=GLA|variant=p.R227X",
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

    chains = EvidenceChainBuilder().build(items, [])

    assert len(chains) == 1
    assert chains[0].gene_text == "GLA"
    assert chains[0].disease_text == "Fabry disease"
    assert chains[0].variant_text == "p.R227X"
    assert chains[0].chain_level == "full"
    assert chains[0].chain_id == "gene=GLA|variant=p.R227X"
    assert set(chains[0].evidence_field_ids) == {"A.gene_symbol", "B.disease_diagnosis", "A.variant_hgvs_p"}


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

    chains = EvidenceChainBuilder().build(items, [])

    assert len(chains) == 1
    assert chains[0].chain_level == "partial"
    assert chains[0].gene_text == ""
    assert chains[0].disease_text == "Fabry disease"
    assert chains[0].variant_text == "p.R227X"


def test_workflow_normalization_node_rejects_coordinate_only_hgvs() -> None:
    workflow = EvidenceExtractionWorkflow.__new__(EvidenceExtractionWorkflow)
    workflow._value_normalizer = AcmgEvidenceValueNormalizer()
    state = EvidenceExtractionState(
        document=TrackDocument(
            document_id="doc",
            track=Track.ORIGINAL,
            formatted_text="chr6_44270253",
            page_spans=[],
        ),
        evidence_items=[
            EvidenceItem(
                field_id="A.variant_hgvs_g",
                category="A",
                field_name="HGVS genomic variant",
                status=EvidenceStatus.FOUND,
                value="chr6_44270253",
                confidence=0.9,
            )
        ],
    )

    result = workflow._node_value_normalization(state)

    assert result.evidence_items[0].status == EvidenceStatus.NOT_FOUND
    assert result.normalization_issues[0].field_id == "A.variant_hgvs_g"
    assert result.normalization_issues[0].issue_type == EvidenceNormalizationIssueType.INVALID_HGVS
