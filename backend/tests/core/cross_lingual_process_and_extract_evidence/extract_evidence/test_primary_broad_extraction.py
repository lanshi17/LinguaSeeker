"""Tests for the B8 primary broad extraction stage."""
from __future__ import annotations

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceStatus,
    ExtractionTarget,
    PrimaryBroadEvidenceCandidate,
    PrimaryBroadExtractionResponse,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.providers import EvidenceModelTier
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.primary_broad_extraction import (
    PrimaryBroadExtractionStage,
)


class BroadProvider:
    """Provider that captures prompts and returns one broad candidate."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.stages: list[str] = []

    def invoke_structured(self, prompt, output_schema, tier, stage, response_method="json_schema"):
        del response_method
        self.prompts.append(prompt)
        self.stages.append(stage)
        assert output_schema is PrimaryBroadExtractionResponse
        assert tier == EvidenceModelTier.STRONG
        return PrimaryBroadExtractionResponse(
            evidence_items=[
                PrimaryBroadEvidenceCandidate(
                    field_id="A.gene_symbol",
                    status=EvidenceStatus.FOUND,
                    value="BRCA1",
                    confidence=0.91,
                    source_quote="BRCA1 c.5266dupC was identified",
                )
            ]
        )

    async def ainvoke_structured(self, prompt, output_schema, tier, stage, response_method="json_schema"):
        return self.invoke_structured(prompt, output_schema, tier, stage, response_method)


def _document() -> TrackDocument:
    return TrackDocument(
        document_id="doc-b8",
        track=Track.ORIGINAL,
        formatted_text="BRCA1 c.5266dupC was identified in a family with breast cancer.",
        page_spans=[],
        extraction_target=ExtractionTarget(gene_symbol="BRCA1", disease_name="Breast cancer"),
    )


def test_primary_broad_stage_prompts_for_b8_fields_and_source_quote() -> None:
    provider = BroadProvider()
    stage = PrimaryBroadExtractionStage(provider)

    items = stage.run(_document())

    assert provider.stages == ["primary_broad_extraction"]
    prompt = provider.prompts[0]
    assert "single high-recall primary extraction pass" in prompt
    assert "source_quote" in prompt
    assert "A.gene_symbol" in prompt
    assert "C.functional_assay" in prompt
    assert "J.clinvar_assertion" in prompt
    assert items[0].field_id == "A.gene_symbol"
    assert items[0].category == "A"
    assert items[0].field_name == "Gene symbol"
    assert items[0].raw_source is not None
    assert items[0].raw_source.text_snippet == "BRCA1 c.5266dupC was identified"
    assert items[0].raw_source.context_ref == "primary_broad_extraction"
    assert items[0].raw_source.block_index == -1


@pytest.mark.asyncio
async def test_primary_broad_stage_supports_async_provider() -> None:
    provider = BroadProvider()
    stage = PrimaryBroadExtractionStage(provider)

    items = await stage.run_async(_document())

    assert provider.stages == ["primary_broad_extraction"]
    assert items[0].field_id == "A.gene_symbol"
