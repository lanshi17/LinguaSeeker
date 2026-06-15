"""Tests for prompt-only citation-required LLM baseline behavior."""
from __future__ import annotations

from benchmark.layer3.baselines.llm_common import (
    BaselineLLMEvidenceItem,
    quote_to_source_span,
)


def test_baseline_llm_evidence_item_accepts_source_quote() -> None:
    item = BaselineLLMEvidenceItem.model_validate(
        {
            "field_id": "A.gene_symbol",
            "status": "found",
            "value": "MECP2",
            "confidence": "high",
            "source_quote": "Mutations in MECP2 cause Rett syndrome.",
        }
    )

    assert item.confidence == 0.9
    assert item.source_quote == "Mutations in MECP2 cause Rett syndrome."


def test_quote_to_source_span_maps_exact_quote() -> None:
    source_text = "Intro.\nMutations in MECP2 cause Rett syndrome.\nDiscussion."

    span = quote_to_source_span("Mutations in MECP2 cause Rett syndrome.", source_text)

    assert span == {
        "span_id": "llm-quote",
        "start_offset": 7,
        "end_offset": 46,
        "text_snippet": "Mutations in MECP2 cause Rett syndrome.",
        "source_precision": "llm_quote_exact",
    }


def test_quote_to_source_span_preserves_unmapped_quote_for_hcr() -> None:
    span = quote_to_source_span("This quote is not present.", "MECP2 source text.")

    assert span["start_offset"] == -1
    assert span["end_offset"] == -1
    assert span["text_snippet"] == "This quote is not present."
    assert span["source_precision"] == "llm_quote_unmapped"
