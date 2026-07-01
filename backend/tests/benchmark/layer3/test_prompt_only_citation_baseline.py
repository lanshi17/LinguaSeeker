"""Tests for prompt-only citation-required LLM baseline behavior."""

from __future__ import annotations

from benchmark.analysis.baselines.llm_common import (
    BaselineLLMEvidenceItem,
    RawOpenAICompatibleClient,
    _build_extraction_prompt,
    _extract_chat_content,
    quote_to_source_span,
)
from benchmark.analysis.baselines.runner import BaselineEntry


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


def test_citation_required_prompt_requests_source_quote() -> None:
    prompt = _build_extraction_prompt(
        "citation_required",
        BaselineEntry(entry_id="clingen_000", gene_symbol="MECP2", disease_label="Rett syndrome"),
        "Mutations in MECP2 cause Rett syndrome.",
    )

    assert "source_quote" in prompt
    assert "verbatim contiguous excerpt" in prompt


def test_direct_prompt_does_not_request_source_quote() -> None:
    prompt = _build_extraction_prompt(
        "naive",
        BaselineEntry(entry_id="clingen_000", gene_symbol="MECP2", disease_label="Rett syndrome"),
        "Mutations in MECP2 cause Rett syndrome.",
    )

    assert "source_quote" not in prompt


def test_extract_chat_content_reads_openai_message_content() -> None:
    content = _extract_chat_content(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": '{"evidence_items": []}',
                    }
                }
            ]
        }
    )

    assert content == '{"evidence_items": []}'


def test_raw_openai_client_builds_openai_compatible_payload() -> None:
    client = RawOpenAICompatibleClient(
        model="qwen-max-latest",
        base_url="https://provider.example",
        api_keys=["test-key"],
        temperature=0.0,
        max_tokens=4096,
        timeout=60,
    )

    payload = client.request_payload("Extract JSON only.")

    assert payload == {
        "model": "qwen-max-latest",
        "messages": [{"role": "user", "content": "Extract JSON only."}],
        "temperature": 0.0,
        "max_tokens": 4096,
    }
