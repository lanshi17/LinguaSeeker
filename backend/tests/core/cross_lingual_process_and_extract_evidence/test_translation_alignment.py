"""Tests for original-English semantic span alignment contracts and helpers."""
from __future__ import annotations

import pytest

from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    TranslationAlignmentChunk,
    TranslationSegment,
    TranslationSpanPair,
)
from src.core.cross_lingual_process_and_extract_evidence.config_context import TranslationConfigContext
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.alignment import (
    RawAlignmentPair,
    build_fallback_span_pairs,
    generate_chunk_span_pairs,
    validate_span_pairs,
)
from src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator import (
    MultiStageTranslator,
)


def test_translation_span_pair_serializes_semantic_method() -> None:
    pair = TranslationSpanPair(
        pair_id="c_0001-p_0001",
        original_text="MECP2基因",
        english_text="MECP2 gene",
        original_start_offset=10,
        original_end_offset=17,
        english_start_offset=20,
        english_end_offset=29,
        confidence=0.91,
        method="semantic_llm",
    )

    payload = pair.model_dump()

    assert payload["pair_id"] == "c_0001-p_0001"
    assert payload["method"] == "semantic_llm"
    assert payload["confidence"] == 0.91


def test_translation_alignment_chunk_accepts_legacy_payload_without_span_pairs() -> None:
    chunk = TranslationAlignmentChunk.model_validate({
        "chunk_id": "c_0001",
        "original_text": "患儿存在MECP2基因突变。",
        "english_text": "The child had an MECP2 gene mutation.",
        "original_start_offset": 0,
        "original_end_offset": 14,
        "english_start_offset": 0,
        "english_end_offset": 39,
    })

    assert chunk.span_pairs == []


def test_translation_span_pair_rejects_unknown_method() -> None:
    with pytest.raises(ValueError):
        TranslationSpanPair(
            pair_id="c_0001-p_0001",
            original_text="突变",
            english_text="mutation",
            original_start_offset=0,
            original_end_offset=2,
            english_start_offset=0,
            english_end_offset=8,
            method="approximate",
        )


def test_validate_span_pairs_builds_full_document_offsets() -> None:
    chunk = TranslationAlignmentChunk(
        chunk_id="c_0001",
        original_text="患儿存在MECP2基因c.194delC突变。",
        english_text="The child had an MECP2 gene c.194delC mutation.",
        original_start_offset=100,
        original_end_offset=124,
        english_start_offset=200,
        english_end_offset=249,
    )

    pairs = validate_span_pairs(
        chunk,
        [
            RawAlignmentPair(
                original_text="MECP2基因",
                english_text="MECP2 gene",
                confidence=0.91,
            ),
            RawAlignmentPair(
                original_text="c.194delC",
                english_text="c.194delC",
                confidence=0.97,
            ),
        ],
    )

    assert [pair.method for pair in pairs] == ["semantic_llm", "semantic_llm"]
    assert pairs[0].original_start_offset == 100 + chunk.original_text.index("MECP2基因")
    assert pairs[0].english_start_offset == 200 + chunk.english_text.index("MECP2 gene")
    assert pairs[1].original_text == "c.194delC"
    assert pairs[1].english_text == "c.194delC"


def test_validate_span_pairs_drops_missing_and_overlapping_pairs() -> None:
    chunk = TranslationAlignmentChunk(
        chunk_id="c_0002",
        original_text="MECP2基因突变导致Rett综合征。",
        english_text="An MECP2 gene mutation causes Rett syndrome.",
        original_start_offset=0,
        original_end_offset=18,
        english_start_offset=0,
        english_end_offset=43,
    )

    pairs = validate_span_pairs(
        chunk,
        [
            RawAlignmentPair(
                original_text="MECP2基因",
                english_text="MECP2 gene",
                confidence=0.91,
            ),
            RawAlignmentPair(
                original_text="基因突变",
                english_text="gene mutation",
                confidence=0.85,
            ),
            RawAlignmentPair(
                original_text="不存在文本",
                english_text="missing text",
                confidence=0.70,
            ),
        ],
    )

    assert len(pairs) == 1
    assert pairs[0].original_text == "MECP2基因"
    assert pairs[0].english_text == "MECP2 gene"


def test_build_fallback_span_pairs_emits_monotonic_pairs_for_rett_text() -> None:
    chunk = TranslationAlignmentChunk(
        chunk_id="c_0003",
        original_text="患儿存在MECP2基因c.194delC突变，最终确诊为Rett综合征。",
        english_text=(
            "The child had an MECP2 gene c.194delC mutation and was finally "
            "diagnosed with Rett syndrome."
        ),
        original_start_offset=50,
        original_end_offset=84,
        english_start_offset=120,
        english_end_offset=215,
    )

    pairs = build_fallback_span_pairs(chunk)

    assert pairs
    assert all(pair.method == "deterministic_token" for pair in pairs)
    assert pairs == sorted(pairs, key=lambda pair: pair.original_start_offset)
    assert pairs == sorted(pairs, key=lambda pair: pair.english_start_offset)
    assert any(pair.original_text == "c.194delC" and pair.english_text == "c.194delC" for pair in pairs)


@pytest.mark.asyncio
async def test_generate_chunk_span_pairs_uses_semantic_json(monkeypatch) -> None:
    chunk = TranslationAlignmentChunk(
        chunk_id="c_0004",
        original_text="MECP2基因突变导致Rett综合征。",
        english_text="An MECP2 gene mutation causes Rett syndrome.",
        original_start_offset=10,
        original_end_offset=28,
        english_start_offset=40,
        english_end_offset=83,
    )

    async def fake_invoke_json(llm, prompt, stage, system_prompt=""):
        return (
            '{"pairs": ['
            '{"original_text": "MECP2基因", "english_text": "MECP2 gene", "confidence": 0.92},'
            '{"original_text": "Rett综合征", "english_text": "Rett syndrome", "confidence": 0.94}'
            ']}'
        )

    monkeypatch.setattr(
        "src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.alignment.invoke_json_with_retry",
        fake_invoke_json,
    )

    pairs = await generate_chunk_span_pairs(object(), chunk, "zh", "align/c_0004")

    assert [pair.method for pair in pairs] == ["semantic_llm", "semantic_llm"]
    assert pairs[0].original_text == "MECP2基因"
    assert pairs[1].english_text == "Rett syndrome"


@pytest.mark.asyncio
async def test_generate_chunk_span_pairs_falls_back_on_invalid_json(monkeypatch) -> None:
    chunk = TranslationAlignmentChunk(
        chunk_id="c_0005",
        original_text="患儿存在MECP2基因c.194delC突变。",
        english_text="The child had an MECP2 gene c.194delC mutation.",
        original_start_offset=0,
        original_end_offset=24,
        english_start_offset=0,
        english_end_offset=49,
    )

    async def fake_invoke_json(llm, prompt, stage, system_prompt=""):
        return '{"pairs": "not-a-list"}'

    monkeypatch.setattr(
        "src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.alignment.invoke_json_with_retry",
        fake_invoke_json,
    )

    pairs = await generate_chunk_span_pairs(object(), chunk, "zh", "align/c_0005")

    assert pairs
    assert all(pair.method == "deterministic_token" for pair in pairs)


@pytest.mark.asyncio
async def test_generate_chunk_span_pairs_falls_back_on_provider_error(monkeypatch) -> None:
    chunk = TranslationAlignmentChunk(
        chunk_id="c_0006",
        original_text="最终确诊为Rett综合征。",
        english_text="The final diagnosis was Rett syndrome.",
        original_start_offset=0,
        original_end_offset=12,
        english_start_offset=0,
        english_end_offset=38,
    )

    async def fake_invoke_json(llm, prompt, stage, system_prompt=""):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        "src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.alignment.invoke_json_with_retry",
        fake_invoke_json,
    )

    pairs = await generate_chunk_span_pairs(object(), chunk, "zh", "align/c_0006")

    assert pairs
    assert all(pair.method == "deterministic_token" for pair in pairs)


@pytest.mark.asyncio
async def test_translator_attaches_span_pairs_to_segments(monkeypatch) -> None:
    translator = MultiStageTranslator(
        TranslationConfigContext(
            model="test-model",
            api_key="test-key",
            base_url="http://localhost:8001/v1",
        )
    )
    segment = TranslationSegment(
        index=0,
        source_text="MECP2基因突变导致Rett综合征。",
        translated_text="An MECP2 gene mutation causes Rett syndrome.",
        source_start_offset=10,
        source_end_offset=28,
        translated_start_offset=40,
        translated_end_offset=83,
    )
    expected_pair = TranslationSpanPair(
        pair_id="c_0001-p_0001",
        original_text="MECP2基因",
        english_text="MECP2 gene",
        original_start_offset=10,
        original_end_offset=17,
        english_start_offset=43,
        english_end_offset=53,
        confidence=0.9,
        method="semantic_llm",
    )

    async def fake_generate(json_llm, chunk, source_language, stage):
        return [expected_pair]

    monkeypatch.setattr(
        "src.core.cross_lingual_process_and_extract_evidence.cross_lingual.translate.translator.generate_chunk_span_pairs",
        fake_generate,
    )

    await translator._attach_span_pairs_to_segments([segment], "zh")

    assert segment.span_pairs == [expected_pair]
