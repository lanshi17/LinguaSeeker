"""Tests for primary-candidate review validation stage."""
from __future__ import annotations

import pytest

from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    EvidenceItem,
    EvidenceStatus,
    SourceLocation,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.stages.review_validation import (
    EvidenceReviewDecision,
    EvidenceReviewResponse,
    ReviewValidationStage,
)


class StaticReviewProvider:
    def __init__(self, response: EvidenceReviewResponse):
        self.response = response
        self.stages: list[str] = []

    def invoke_structured(self, prompt, output_schema, tier, stage, response_method="json_schema"):
        del prompt, output_schema, tier, response_method
        self.stages.append(stage)
        return self.response

    async def ainvoke_structured(self, prompt, output_schema, tier, stage, response_method="json_schema"):
        del prompt, output_schema, tier, response_method
        self.stages.append(stage)
        return self.response


class FailingReviewProvider:
    def invoke_structured(self, prompt, output_schema, tier, stage, response_method="json_schema"):
        del prompt, output_schema, tier, stage, response_method
        raise RuntimeError("review unavailable")


def _item(field_id: str, value: str) -> EvidenceItem:
    return EvidenceItem(
        field_id=field_id,
        category=field_id[0],
        field_name=field_id,
        status=EvidenceStatus.FOUND,
        value=value,
        confidence=0.7,
        raw_source=SourceLocation(
            context_type="text",
            context_ref="",
            text_snippet=value,
            block_index=0,
        ),
    )


def _document() -> TrackDocument:
    return TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text="MECP2 causes Rett syndrome.",
        page_spans=[],
    )


def test_review_validation_cannot_add_new_field_ids() -> None:
    provider = StaticReviewProvider(
        EvidenceReviewResponse(
            decisions=[
                EvidenceReviewDecision(
                    field_id="B.disease_diagnosis",
                    action="correct",
                    value="Rett syndrome",
                    confidence=0.9,
                    source_quote="Rett syndrome",
                )
            ]
        )
    )

    reviewed = ReviewValidationStage(provider).run(_document(), [_item("A.gene_symbol", "MECP2")])

    assert [item.field_id for item in reviewed] == ["A.gene_symbol"]
    assert reviewed[0].value == "MECP2"


def test_review_validation_corrects_existing_candidate_raw_source() -> None:
    provider = StaticReviewProvider(
        EvidenceReviewResponse(
            decisions=[
                EvidenceReviewDecision(
                    candidate_index=0,
                    field_id="B.disease_diagnosis",
                    action="correct",
                    value="Rett syndrome",
                    confidence=0.9,
                    source_quote="Rett syndrome",
                )
            ]
        )
    )

    reviewed = ReviewValidationStage(provider).run(
        _document(),
        [_item("B.disease_diagnosis", "neurodevelopmental disease")],
    )

    assert reviewed[0].status == EvidenceStatus.FOUND
    assert reviewed[0].value == "Rett syndrome"
    assert reviewed[0].confidence == 0.9
    assert reviewed[0].raw_source is not None
    assert reviewed[0].raw_source.text_snippet == "Rett syndrome"
    assert "review_track: corrected" in reviewed[0].notes


def test_review_validation_rejects_existing_candidate() -> None:
    provider = StaticReviewProvider(
        EvidenceReviewResponse(
            decisions=[
                EvidenceReviewDecision(
                    candidate_index=0,
                    field_id="A.variant_hgvs_p",
                    action="reject",
                    reason="not present in article",
                )
            ]
        )
    )

    reviewed = ReviewValidationStage(provider).run(_document(), [_item("A.variant_hgvs_p", "p.Bad")])

    assert reviewed[0].status == EvidenceStatus.NOT_FOUND
    assert reviewed[0].value is None
    assert reviewed[0].confidence == 0.0
    assert "review_track: rejected" in reviewed[0].notes


def test_review_validation_fails_open_to_primary_candidates() -> None:
    item = _item("A.gene_symbol", "MECP2")

    reviewed = ReviewValidationStage(FailingReviewProvider()).run(_document(), [item])

    assert reviewed == [item]


@pytest.mark.asyncio
async def test_review_validation_async_uses_async_provider() -> None:
    provider = StaticReviewProvider(
        EvidenceReviewResponse(
            decisions=[
                EvidenceReviewDecision(
                    candidate_index=0,
                    field_id="A.gene_symbol",
                    action="approve",
                    reason="directly supported",
                )
            ]
        )
    )

    reviewed = await ReviewValidationStage(provider).run_async(_document(), [_item("A.gene_symbol", "MECP2")])

    assert provider.stages == ["review_validation"]
    assert reviewed[0].status == EvidenceStatus.FOUND
    assert "review_track: approved" in reviewed[0].notes
