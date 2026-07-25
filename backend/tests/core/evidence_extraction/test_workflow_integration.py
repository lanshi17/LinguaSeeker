import pytest

from src.core.evidence_extraction.contracts import (
    ContentBlock,
    DocumentEvidenceMap,
    EvidenceStatus,
    EvidenceReviewResponse,
    EvidenceItem,
    PageSpan,
    PrimaryBroadEvidenceCandidate,
    PrimaryBroadExtractionResponse,
    SourceLocation,
    SpecialEvidenceResponse,
    Track,
    TrackDocument,
)
from src.core.evidence_extraction.workflow import EvidenceExtractionWorkflow


class FakeProvider:
    def __init__(self):
        self.stages: list[str] = []

    def invoke_structured(self, prompt, output_schema, tier, stage, response_method="json_schema"):
        del prompt, output_schema, tier, response_method
        self.stages.append(stage)
        if stage == "relevance_scan":
            return DocumentEvidenceMap(relevant=True)
        if stage == "primary_broad_extraction":
            return PrimaryBroadExtractionResponse(
                evidence_items=[
                    PrimaryBroadEvidenceCandidate(
                        field_id="A.gene_symbol",
                        status=EvidenceStatus.FOUND,
                        value="BRCA1",
                        confidence=0.9,
                        source_quote="BRCA1",
                    ),
                    PrimaryBroadEvidenceCandidate(
                        field_id="A.variant_hgvs_c",
                        status=EvidenceStatus.FOUND,
                        value="c.5266dupC",
                        confidence=0.9,
                        source_quote="c.5266dupC",
                    ),
                    PrimaryBroadEvidenceCandidate(
                        field_id="B.disease_diagnosis",
                        status=EvidenceStatus.FOUND,
                        value="Breast cancer",
                        confidence=0.9,
                        source_quote="Breast cancer",
                    ),
                ]
            )
        if stage.startswith("catalog_extraction"):
            return [
                EvidenceItem(
                    field_id="A.gene_symbol",
                    category="A",
                    field_name="Gene symbol",
                    status=EvidenceStatus.FOUND,
                    value="BRCA1",
                    confidence=0.9,
                    raw_source=SourceLocation(block_index=0, context_type="text", context_ref="", text_snippet="BRCA1"),
                ),
                EvidenceItem(
                    field_id="A.variant_hgvs_c",
                    category="A",
                    field_name="HGVS coding variant",
                    status=EvidenceStatus.FOUND,
                    value="c.5266dupC",
                    confidence=0.9,
                    raw_source=SourceLocation(
                        block_index=0, context_type="text", context_ref="", text_snippet="c.5266dupC"
                    ),
                ),
                EvidenceItem(
                    field_id="B.disease_diagnosis",
                    category="B",
                    field_name="Disease diagnosis",
                    status=EvidenceStatus.FOUND,
                    value="Breast cancer",
                    confidence=0.9,
                    raw_source=SourceLocation(
                        block_index=0, context_type="text", context_ref="", text_snippet="Breast cancer"
                    ),
                ),
            ]
        if stage == "special_evidence":
            return SpecialEvidenceResponse(records=[])
        if stage == "clinical_context":
            return []
        if stage == "review_validation":
            return EvidenceReviewResponse()
        raise AssertionError(stage)


@pytest.mark.asyncio
async def test_workflow_catalog_rollback_uses_catalog_special_clinical_order():
    """Explicit extraction_mode="catalog" keeps the catalog -> special -> clinical path."""
    provider = FakeProvider()
    text = "BRCA1\nc.5266dupC\nBreast cancer"
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[],
        blocks=[ContentBlock(type="text", page_idx=0, text=text, bbox=[1, 2, 3, 4])],
    )

    state = await EvidenceExtractionWorkflow(provider=provider, extraction_mode="catalog").run(document)

    assert provider.stages[0] == "relevance_scan"
    assert provider.stages[-2:] == ["special_evidence", "clinical_context"]
    catalog_stages = provider.stages[1:-2]
    assert catalog_stages == ["catalog_extraction/high_signal", "catalog_extraction/supporting"]
    assert all(stage.startswith("catalog_extraction/") for stage in catalog_stages)
    assert "primary_broad_extraction" not in provider.stages
    assert "review_validation" not in provider.stages
    assert "catalog_backfill" not in provider.stages
    assert state.evidence_items
    assert [item.group_id for item in state.evidence_items]
    assert state.evidence_chains == []
    assert all(item.group_id for item in state.evidence_items)
    assert state.quality_report is not None
    assert state.quality_report.human_review_required is True


class ChunkingProvider:
    def __init__(self):
        self.stages: list[str] = []

    def invoke_structured(self, prompt, output_schema, tier, stage, response_method="json_schema"):
        del prompt, output_schema, tier, response_method
        self.stages.append(stage)
        if stage.startswith("relevance_scan"):
            return DocumentEvidenceMap(relevant=True, gene_terms=["GLA"])
        if stage == "primary_broad_extraction":
            return PrimaryBroadExtractionResponse(
                evidence_items=[
                    PrimaryBroadEvidenceCandidate(
                        field_id="A.gene_symbol",
                        status=EvidenceStatus.FOUND,
                        value="GLA",
                        confidence=0.9,
                        source_quote="GLA",
                    ),
                ]
            )
        if stage.startswith("catalog_extraction"):
            return [
                EvidenceItem(
                    field_id="A.gene_symbol",
                    category="A",
                    field_name="Gene symbol",
                    status=EvidenceStatus.FOUND,
                    value="GLA",
                    confidence=0.9,
                    raw_source=SourceLocation(
                        block_index=0,
                        context_type="text",
                        context_ref="",
                        text_snippet="GLA",
                    ),
                )
            ]
        if stage.startswith("special_evidence"):
            return SpecialEvidenceResponse(records=[])
        if stage.startswith("clinical_context"):
            return []
        if stage.startswith("review_validation"):
            return EvidenceReviewResponse()
        raise AssertionError(stage)


@pytest.mark.asyncio
async def test_workflow_accepts_chunking_budget_override_for_regression():
    provider = ChunkingProvider()
    text = "GLA " + ("A" * 200) + "\n\n" + ("B" * 200)
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[],
        blocks=[
            ContentBlock(type="text", page_idx=0, text="GLA " + ("A" * 200)),
            ContentBlock(type="text", page_idx=1, text="B" * 200),
        ],
    )

    workflow = EvidenceExtractionWorkflow(
        provider=provider,
        input_budget_tokens=90,
        extraction_mode="catalog",
    )
    state = await workflow.run(document)

    assert state.evidence_map is not None
    assert state.evidence_map.relevant is True
    assert any(stage.startswith("relevance_scan/") for stage in provider.stages)
    assert any(stage.startswith("catalog_extraction/") for stage in provider.stages)
    assert any(stage.startswith("special_evidence/") for stage in provider.stages)
    assert "primary_broad_extraction" not in provider.stages


@pytest.mark.asyncio
async def test_workflow_default_uses_primary_broad_review_track() -> None:
    """Default workflow (business default broad) uses primary_broad + review, not catalog."""
    provider = FakeProvider()
    text = "BRCA1\nc.5266dupC\nBreast cancer"
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[],
        blocks=[ContentBlock(type="text", page_idx=0, text=text, bbox=[1, 2, 3, 4])],
    )

    state = await EvidenceExtractionWorkflow(provider=provider).run(document)

    assert provider.stages[:3] == ["relevance_scan", "primary_broad_extraction", "review_validation"]
    assert not any(stage.startswith("catalog_extraction") for stage in provider.stages)
    assert "special_evidence" not in provider.stages
    assert "clinical_context" not in provider.stages
    assert state.evidence_items


class ReviewFailOpenProvider(FakeProvider):
    def invoke_structured(self, prompt, output_schema, tier, stage, response_method="json_schema"):
        if stage == "review_validation":
            self.stages.append(stage)
            raise RuntimeError("review unavailable")
        return super().invoke_structured(prompt, output_schema, tier, stage, response_method)


@pytest.mark.asyncio
async def test_workflow_review_validation_fails_open() -> None:
    provider = ReviewFailOpenProvider()
    text = "BRCA1\nc.5266dupC\nBreast cancer"
    document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=text,
        page_spans=[PageSpan(span_id="p1", page=1, start_offset=0, end_offset=len(text))],
        blocks=[ContentBlock(type="text", page_idx=0, text=text, bbox=[1, 2, 3, 4])],
    )

    state = await EvidenceExtractionWorkflow(provider=provider, extraction_mode="broad").run(document)

    assert "review_validation" in provider.stages
    assert any(
        item.field_id == "A.gene_symbol" and item.status == EvidenceStatus.FOUND and item.value == "BRCA1"
        for item in state.evidence_items
    )
