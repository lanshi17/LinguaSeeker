import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    DocumentEvidenceMap,
    EvidenceStatus,
    EvidenceReviewResponse,
    PageSpan,
    PrimaryBroadEvidenceCandidate,
    PrimaryBroadExtractionResponse,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.workflow import EvidenceExtractionWorkflow


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
            raise AssertionError("full B8 workflow must not call catalog_extraction")
        if stage == "special_evidence":
            raise AssertionError("full B8 workflow must not call special_evidence")
        if stage == "clinical_context":
            raise AssertionError("full B8 workflow must not call clinical_context")
        if stage == "review_validation":
            return EvidenceReviewResponse()
        raise AssertionError(stage)


@pytest.mark.asyncio
async def test_workflow_runs_block_group_ground_chain_quality_order():
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

    assert provider.stages[0] == "relevance_scan"
    assert provider.stages[:3] == ["relevance_scan", "primary_broad_extraction", "review_validation"]
    assert not any(stage.startswith("catalog_extraction") for stage in provider.stages)
    assert "special_evidence" not in provider.stages
    assert "clinical_context" not in provider.stages
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
            raise AssertionError("full B8 workflow must not call catalog_extraction")
        if stage.startswith("special_evidence"):
            raise AssertionError("full B8 workflow must not call special_evidence")
        if stage.startswith("clinical_context"):
            raise AssertionError("full B8 workflow must not call clinical_context")
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

    workflow = EvidenceExtractionWorkflow(provider=provider, input_budget_tokens=90)
    state = await workflow.run(document)

    assert state.evidence_map is not None
    assert state.evidence_map.relevant is True
    assert any(stage.startswith("relevance_scan/") for stage in provider.stages)
    assert "primary_broad_extraction" in provider.stages
    assert not any(stage.startswith("catalog_extraction") for stage in provider.stages)
    assert not any(stage.startswith("special_evidence") for stage in provider.stages)


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

    state = await EvidenceExtractionWorkflow(provider=provider).run(document)

    assert "review_validation" in provider.stages
    assert any(
        item.field_id == "A.gene_symbol"
        and item.status == EvidenceStatus.FOUND
        and item.value == "BRCA1"
        for item in state.evidence_items
    )
