"""Regression tests for English-to-original translation traceback."""

from __future__ import annotations

from src.core.cross_lingual_process_and_extract_evidence.contracts import (
    TranslationAlignmentChunk,
    TranslationSpanPair,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.contracts import (
    ContentBlock,
    PageSpan,
    SourceLocation,
    SourcePrecision,
    Track,
    TrackDocument,
)
from src.core.cross_lingual_process_and_extract_evidence.extract_evidence.translation_traceback import (
    _map_source_to_original,
)


def test_map_source_to_original_uses_nested_span_pair_for_precise_traceback() -> None:
    original_text = "基因检测提示ABCA3缺陷引起的间质性肺病。"
    english_text = "Genetic testing suggested interstitial lung disease due to ABCA3 deficiency."
    original_pair_start = original_text.index("ABCA3缺陷")
    english_pair_start = english_text.index("ABCA3 deficiency")
    chunk = TranslationAlignmentChunk(
        chunk_id="c_0001",
        original_text=original_text,
        english_text=english_text,
        original_start_offset=0,
        original_end_offset=len(original_text),
        english_start_offset=0,
        english_end_offset=len(english_text),
        page=1,
        block_index=0,
        span_pairs=[
            TranslationSpanPair(
                pair_id="c_0001-p_0001",
                original_text="ABCA3缺陷",
                english_text="ABCA3 deficiency",
                original_start_offset=original_pair_start,
                original_end_offset=original_pair_start + len("ABCA3缺陷"),
                english_start_offset=english_pair_start,
                english_end_offset=english_pair_start + len("ABCA3 deficiency"),
                confidence=0.94,
                method="semantic_llm",
            )
        ],
    )
    original_document = TrackDocument(
        document_id="doc-1",
        track=Track.ORIGINAL,
        formatted_text=original_text,
        page_spans=[
            PageSpan(
                span_id="original-p1",
                page=1,
                start_offset=0,
                end_offset=len(original_text),
            )
        ],
        blocks=[ContentBlock(type="text", page_idx=0, text=original_text, bbox=[1, 2, 3, 4])],
    )
    english_source = SourceLocation(
        span_id="translated-p1",
        page=1,
        start_offset=english_pair_start,
        end_offset=english_pair_start + len("ABCA3 deficiency"),
        context_type="results",
        context_ref="Results",
        text_snippet="ABCA3 deficiency",
        block_index=0,
    )

    mapped = _map_source_to_original(original_document, [chunk], english_source)

    assert mapped is not None
    assert mapped.text_snippet == "ABCA3缺陷"
    assert mapped.start_offset == original_pair_start
    assert mapped.end_offset == original_pair_start + len("ABCA3缺陷")
    assert mapped.source_precision == SourcePrecision.EXACT
    assert mapped.bbox == [1, 2, 3, 4]
