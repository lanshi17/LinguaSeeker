import { describe, expect, it } from "vitest";

import type { EvidenceGroupDetailResponse } from "../../src/features/evidence-search/types/evidenceSearch";
import {
  activeAlignmentPairId,
  buildAlignmentHighlightMap,
  buildAlignmentHighlights,
  buildAlignmentHighlightsForBlocks,
} from "../../src/features/evidence-search/utils/translationAlignment";

function makeDetail(): EvidenceGroupDetailResponse {
  return {
    group_id: "gene=['MECP2']|variant=['c.194delC']",
    source_document_id: "doc-1",
    title: "MECP2 case report",
    pmid: null,
    doi: null,
    gene: "MECP2",
    variant: "c.194delC",
    disease: "Rett syndrome",
    classification: null,
    item_count: 1,
    avg_confidence: 0.92,
    distribution: {
      by_category: {},
      by_field: {},
      by_status: {},
      by_track: {},
    },
    items: [],
    traces: [],
    translation_alignment: [
      {
        chunk_id: "c_0001",
        original_text: "摘要：MECP2基因存在c.194delC致病性突变。",
        english_text: "Abstract: A pathogenic c.194delC mutation was found in MECP2.",
        original_start_offset: 0,
        original_end_offset: 30,
        english_start_offset: 0,
        english_end_offset: 64,
        page: 1,
        block_index: 0,
        span_pairs: [
          {
            pair_id: "c_0001-p_0001",
            original_text: "c.194delC",
            english_text: "c.194delC",
            original_start_offset: 11,
            original_end_offset: 20,
            english_start_offset: 24,
            english_end_offset: 33,
            confidence: 0.96,
            method: "semantic_llm",
          },
        ],
      },
    ],
  };
}

describe("translation alignment highlights", () => {
  it("uses hovered pair id before pinned pair id", () => {
    expect(activeAlignmentPairId({
      hoveredPairId: "hovered",
      pinnedPairId: "pinned",
    })).toBe("hovered");
    expect(activeAlignmentPairId({
      hoveredPairId: null,
      pinnedPairId: "pinned",
    })).toBe("pinned");
  });

  it("maps span pairs to the displayed original and translated text", () => {
    const detail = makeDetail();
    const originalText = "MECP2基因存在c.194delC致病性突变。";
    const translatedText = "A pathogenic c.194delC mutation was found in MECP2.";

    const original = buildAlignmentHighlights(
      detail,
      "original",
      originalText,
      { hoveredPairId: "c_0001-p_0001", pinnedPairId: null },
    );
    const translated = buildAlignmentHighlights(
      detail,
      "translated",
      translatedText,
      { hoveredPairId: "c_0001-p_0001", pinnedPairId: null },
    );

    expect(original).toEqual([
      expect.objectContaining({
        pairId: "c_0001-p_0001",
        start: originalText.indexOf("c.194delC"),
        end: originalText.indexOf("c.194delC") + "c.194delC".length,
        active: true,
      }),
    ]);
    expect(translated).toEqual([
      expect.objectContaining({
        pairId: "c_0001-p_0001",
        start: translatedText.indexOf("c.194delC"),
        end: translatedText.indexOf("c.194delC") + "c.194delC".length,
        active: true,
      }),
    ]);
  });

  it("returns no highlights when no span pairs are present", () => {
    expect(buildAlignmentHighlights(
      { ...makeDetail(), translation_alignment: [] },
      "original",
      "MECP2基因存在c.194delC致病性突变。",
      { hoveredPairId: null, pinnedPairId: null },
    )).toEqual([]);
  });

  it("builds paragraph highlight maps from evidence documents", () => {
    const detail = makeDetail();
    const text = "A pathogenic c.194delC mutation was found in MECP2.";
    const map = buildAlignmentHighlightMap(
      detail,
      {
        track: "translated",
        paragraphs: [{ id: "translated-full-text", text, highlights: [] }],
      },
      "translated",
      { hoveredPairId: "c_0001-p_0001", pinnedPairId: null },
    );

    expect(map["translated-full-text"]).toEqual([
      expect.objectContaining({
        pairId: "c_0001-p_0001",
        start: text.indexOf("c.194delC"),
        active: true,
      }),
    ]);
  });

  it("builds structured block alignment highlights in renderer coordinates", () => {
    const detail = makeDetail();
    const highlights = buildAlignmentHighlightsForBlocks(
      [{ type: "text", text: "A pathogenic c.194delC mutation was found in MECP2." }],
      detail,
      "translated",
      { hoveredPairId: "c_0001-p_0001", pinnedPairId: null },
    );

    expect(highlights).toEqual([
      expect.objectContaining({
        pairId: "c_0001-p_0001",
        start: "A pathogenic ".length,
        active: true,
      }),
    ]);
  });
});
