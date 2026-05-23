import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    DocumentEvidenceMap,
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    SpecialEvidenceResponse,
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
        if stage == "catalog_extraction":
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
                    raw_source=SourceLocation(block_index=0, context_type="text", context_ref="", text_snippet="c.5266dupC"),
                ),
                EvidenceItem(
                    field_id="B.disease_diagnosis",
                    category="B",
                    field_name="Disease diagnosis",
                    status=EvidenceStatus.FOUND,
                    value="Breast cancer",
                    confidence=0.9,
                    raw_source=SourceLocation(block_index=0, context_type="text", context_ref="", text_snippet="Breast cancer"),
                ),
            ]
        if stage == "special_evidence":
            return SpecialEvidenceResponse(records=[])
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

    assert provider.stages == ["relevance_scan", "catalog_extraction", "special_evidence"]
    assert state.evidence_items
    assert [item.group_id for item in state.evidence_items]
    assert state.evidence_chains == []
    assert all(item.group_id for item in state.evidence_items)
    assert state.quality_report is not None
    assert state.quality_report.human_review_required is True
