"""Tests for Phase 4 contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from uuid import uuid4

from src.core.visualize_evidence_with_expert_in_loop.contracts import (
    DeltaEntry,
    EvidenceCardPayload,
    ReviewStatus,
    SourceSpanDict,
    TargetType,
    TrackSpan,
)


class TestEvidenceCardPayload:
    """EvidenceCardPayload has a fixed schema for diff operations."""

    def test_minimal_payload(self) -> None:
        """All fields are optional."""
        payload = EvidenceCardPayload()
        assert payload.gene is None
        assert payload.references == []

    def test_full_payload(self) -> None:
        """All fields can be populated."""
        payload = EvidenceCardPayload(
            gene="GLA",
            variant="p.R227X",
            phenotype="Fabry disease",
            disease="Fabry disease",
            classification="Pathogenic",
            evidence_strength="PS3",
            evidence_type="Functional",
            functional_impact="Loss of function",
            inheritance_pattern="X-linked",
            zygosity="Hemizygous",
            references=["PMID:12345678"],
            summary="Test summary",
        )
        assert payload.gene == "GLA"
        assert payload.references == ["PMID:12345678"]

    def test_diff_fields_constant(self) -> None:
        """DIFF_FIELDS contains exactly the expected field names."""
        expected = {
            "gene",
            "variant",
            "phenotype",
            "disease",
            "classification",
            "evidence_strength",
            "evidence_type",
            "functional_impact",
            "inheritance_pattern",
            "zygosity",
            "references",
            "summary",
        }
        assert set(EvidenceCardPayload.DIFF_FIELDS) == expected


class TestReviewStatus:
    """ReviewStatus defines the state machine for evidence review."""

    def test_provisional_is_initial(self) -> None:
        assert ReviewStatus.PROVISIONAL.value == "provisional"

    def test_all_states(self) -> None:
        assert set(ReviewStatus) == {
            ReviewStatus.PROVISIONAL,
            ReviewStatus.APPROVED,
            ReviewStatus.CORRECTED,
            ReviewStatus.REJECTED,
        }


class TestTargetType:
    """TargetType enumerates review feedback targets."""

    def test_implemented_types(self) -> None:
        """Three target types are implemented in P0."""
        implemented = {
            TargetType.EVIDENCE_ITEM,
            TargetType.ENTITY,
            TargetType.MISSED_EVIDENCE,
        }
        assert implemented <= set(TargetType)

    def test_declared_but_not_implemented(self) -> None:
        """Other target types are declared but not implemented."""
        assert TargetType.TASK in set(TargetType)
        assert TargetType.NATIVE_EXTRACTION in set(TargetType)


class TestDeltaEntry:
    """DeltaEntry represents a single field change."""

    def test_valid_delta(self) -> None:
        delta = DeltaEntry(
            field="phenotype",
            old_value="Fabry disease",
            new_value="Fabry 病",
        )
        assert delta.field == "phenotype"
        assert delta.field in EvidenceCardPayload.DIFF_FIELDS

    def test_invalid_field_rejected(self) -> None:
        """Arbitrary field paths are rejected to prevent injection."""
        with pytest.raises(ValidationError):
            DeltaEntry(
                field="__class__.__dict__",
                old_value="x",
                new_value="y",
            )


class TestSourceSpanDict:
    """SourceSpanDict replaces bare dict on TrackSpan.source_span."""

    def test_track_span_source_span_is_typed(self) -> None:
        """TrackSpan.source_span should use SourceSpanDict, not bare dict."""
        import inspect

        sig = inspect.signature(TrackSpan)
        source_span_type = sig.parameters["source_span"].annotation
        assert source_span_type is not dict

    def test_source_span_dict_fields(self) -> None:
        """SourceSpanDict should accept known source span keys."""
        span = SourceSpanDict(
            text_snippet="some text",
            start_offset=0,
            end_offset=10,
            page=1,
        )
        assert span["text_snippet"] == "some text"
        assert span["page"] == 1


def test_evidence_group_detail_contract_accepts_traceability_payload():
    """Evidence group detail response should carry distribution and trace spans."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import (
        EvidenceChainHighlight,
        EvidenceFieldDistribution,
        EvidenceGroupDetailResponse,
        EvidenceGroupItem,
        EvidenceTrackTrace,
    )

    evidence_id = uuid4()
    source_document_id = uuid4()

    detail = EvidenceGroupDetailResponse(
        group_id="gene=['BRCA1']|variant=['c.68_69delAG']",
        source_document_id=source_document_id,
        title="BRCA1 clinical evidence paper",
        pmid="12345678",
        doi="10.1000/example",
        gene="BRCA1",
        variant="c.68_69delAG",
        disease="Hereditary breast and ovarian cancer",
        classification="Pathogenic",
        item_count=1,
        avg_confidence=0.95,
        distribution=EvidenceFieldDistribution(
            by_category={"A": 1},
            by_field={"A.gene_symbol": 1},
            by_status={"provisional": 1},
            by_track={"original": 1},
        ),
        items=[
            EvidenceGroupItem(
                canonical_evidence_id=evidence_id,
                field_id="A.gene_symbol",
                field_name="Gene symbol",
                category="A",
                value="BRCA1",
                review_status="provisional",
                confidence=0.95,
                track="original",
            )
        ],
        traces=[
            EvidenceTrackTrace(
                canonical_evidence_id=evidence_id,
                field_id="A.gene_symbol",
                field_name="Gene symbol",
                original=EvidenceChainHighlight(
                    text="BRCA1 was detected.",
                    highlight_start=0,
                    highlight_end=5,
                    page=1,
                    source_span={"text_snippet": "BRCA1 was detected."},
                ),
                translated=None,
                alignment_confidence=None,
            )
        ],
    )

    dumped = detail.model_dump()
    assert dumped["group_id"].startswith("gene=")
    assert dumped["title"] == "BRCA1 clinical evidence paper"
    assert dumped["distribution"]["by_category"] == {"A": 1}
    assert dumped["traces"][0]["original"]["highlight_start"] == 0


def test_evidence_track_trace_carries_value_anchors():
    """Evidence track traces expose original/translated extracted values."""
    from src.core.visualize_evidence_with_expert_in_loop.contracts import (
        EvidenceChainHighlight,
        EvidenceTrackTrace,
    )

    trace = EvidenceTrackTrace(
        canonical_evidence_id=uuid4(),
        field_id="A.gene_symbol",
        original_value="BRCA1",
        translated_value="BRCA1",
        original=EvidenceChainHighlight(
            text="BRCA1 was detected in the proband.",
            highlight_start=0,
            highlight_end=5,
        ),
        translated=EvidenceChainHighlight(
            text="在先证者中检测到 BRCA1。",
            highlight_start=7,
            highlight_end=12,
        ),
    )

    assert trace.original_value == "BRCA1"
    assert trace.translated_value == "BRCA1"
