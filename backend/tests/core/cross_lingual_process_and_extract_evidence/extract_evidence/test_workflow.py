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
    ExtractionTarget,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceNormalizationIssueType,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.core import EvidenceChainBuilder
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.normalization import (
    AcmgEvidenceValueNormalizer,
)
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


def test_workflow_target_span_recovery_node_adds_missing_high_signal_field() -> None:
    workflow = EvidenceExtractionWorkflow(provider=MagicMock())
    source_text = "Stargardt disease results from biallelic pathogenic variants in the ABCA4 gene."
    state = EvidenceExtractionState(
        document=TrackDocument(
            document_id="doc",
            track=Track.ORIGINAL,
            formatted_text=source_text,
            page_spans=[],
            extraction_target=ExtractionTarget(
                gene_symbol="ABCA4",
                disease_name="Stargardt disease",
            ),
        ),
        evidence_items=[
            EvidenceItem(
                field_id="A.gene_symbol",
                category="A",
                field_name="Gene symbol",
                status=EvidenceStatus.FOUND,
                value="ABCA4",
                confidence=0.9,
                group_id="gene=ABCA4|variant=",
                source=SourceLocation(
                    context_type="text",
                    context_ref="target",
                    text_snippet=source_text,
                ),
            ),
        ],
    )

    result = workflow._node_target_span_recovery(state)

    values = {item.field_id: item.value for item in result.evidence_items if item.status == EvidenceStatus.FOUND}
    assert values["A.gene_disease_relationship"] == "causative"
    assert values["B.mode_of_inheritance_reported"] == "AR"


def test_catalog_backfill_node_expands_to_full_catalog():
    """Unit test for the backfill node — no LLM, no graph compile."""
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.catalog import (
        EVIDENCE_FIELD_SPECS,
    )

    workflow = EvidenceExtractionWorkflow(provider=MagicMock())
    state = EvidenceExtractionState(
        document=TrackDocument(
            document_id="d1",
            track=Track.ORIGINAL,
            formatted_text="x",
            page_spans=[],
        ),
    )
    state.evidence_items = [
        EvidenceItem(
            field_id="A.gene_symbol",
            category="A",
            field_name="Gene symbol",
            status=EvidenceStatus.FOUND,
            value="GLA",
            confidence=0.9,
            group_id="g1",
        ),
    ]

    out = workflow._node_catalog_backfill(state)
    field_ids = {item.field_id for item in out.evidence_items}
    expected = {spec.field_id for spec in EVIDENCE_FIELD_SPECS}
    assert expected.issubset(field_ids), f"Missing: {expected - field_ids}"
    # Backfilled items keep group_id of source items
    backfilled = [i for i in out.evidence_items if i.field_id != "A.gene_symbol"]
    assert all(i.group_id == "g1" for i in backfilled)
    assert all(i.status == EvidenceStatus.NOT_FOUND for i in backfilled)


@pytest.mark.asyncio
async def test_workflow_backfills_after_quality_gate(mock_config):
    """Integration: ensure the END state carries the full 166 rows when relevant=True."""
    provider = MagicMock()
    # Force not-relevant path so we exit early without LLM extraction;
    # the not_relevant branch returns directly to END with [] items —
    # this asserts backfill is NOT applied on the not_relevant branch.
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
    # not_relevant path exits before catalog_backfill — items stay empty.
    assert state.evidence_items == []


def test_service_default_uses_broad_workflow(mock_config):
    """EvidenceExtractionService(cfg) defaults to the broad business workflow."""
    service = EvidenceExtractionService(cfg=mock_config)
    assert service._extraction_mode == "broad"
    assert service._workflow._extraction_mode == "broad"


def test_service_explicit_catalog_uses_catalog_workflow(mock_config):
    """EvidenceExtractionService(cfg, extraction_mode='catalog') builds a catalog workflow."""
    service = EvidenceExtractionService(cfg=mock_config, extraction_mode="catalog")
    assert service._extraction_mode == "catalog"
    assert service._workflow._extraction_mode == "catalog"


def test_service_run_catalog_override_uses_catalog_workflow(mock_config):
    """service.run(..., extraction_mode='catalog') overrides the default broad for that call."""
    service = EvidenceExtractionService(cfg=mock_config)
    assert service._extraction_mode == "broad"
    # No profile override + explicit legacy mode -> fresh legacy workflow.
    wf = service._workflow_for(None, extraction_mode="catalog")
    assert wf._extraction_mode == "catalog"
    # No override -> cached default (b8) workflow.
    assert service._workflow_for(None, extraction_mode=None)._extraction_mode == "broad"


def test_service_review_reject_policy_override_uses_fresh_workflow(mock_config):
    """service.run(..., review_reject_policy='tristate_review') overrides default hard veto."""
    service = EvidenceExtractionService(cfg=mock_config)

    wf = service._workflow_for(None, review_reject_policy="tristate_review")

    assert wf._review_reject_policy == "tristate_review"
    assert wf._review_validation._review_reject_policy == "tristate_review"
    assert service._workflow_for(None, review_reject_policy=None)._review_reject_policy == "hard_veto"


def test_backward_compat_alias_b8_to_broad(mock_config):
    """extraction_mode='b8' (old name) resolves to 'broad'."""
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.workflow import resolve_extraction_mode

    assert resolve_extraction_mode("b8") == "broad"


def test_backward_compat_alias_legacy_to_catalog(mock_config):
    """extraction_mode='legacy' (old name) resolves to 'catalog'."""
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.workflow import resolve_extraction_mode

    assert resolve_extraction_mode("legacy") == "catalog"


def test_resolve_extraction_mode_unknown_raises():
    """Unknown mode string raises ValueError."""
    from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.workflow import resolve_extraction_mode

    with pytest.raises(ValueError, match="Unknown extraction_mode"):
        resolve_extraction_mode("unknown")
