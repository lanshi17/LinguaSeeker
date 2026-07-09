import { describe, expect, it } from "vitest";

import type { UserAnnotation } from "../../src/features/evidence-search/types/annotations";
import type { EvidenceGroupDetailResponse } from "../../src/features/evidence-search/types/evidenceSearch";
import {
  buildSynchronizedAnnotations,
  sourceAnnotationIdForMutation,
} from "../../src/features/evidence-search/utils/annotationSync";

function detail(
  overrides: Partial<EvidenceGroupDetailResponse> = {},
): EvidenceGroupDetailResponse {
  return {
    group_id: "group-1",
    source_document_id: "source-1",
    title: "Evidence paper",
    original_document_text: "BRCA1 was detected.",
    translated_document_text: "BRCA1 was detected.",
    gene: "BRCA1",
    variant: null,
    disease: null,
    classification: null,
    item_count: 1,
    distribution: {
      by_category: {},
      by_field: {},
      by_status: {},
      by_track: {},
    },
    items: [],
    traces: [],
    translation_alignment: [{
      chunk_id: "chunk-1",
      original_text: "BRCA1 was detected.",
      english_text: "BRCA1 was detected.",
      original_start_offset: 0,
      original_end_offset: 19,
      english_start_offset: 0,
      english_end_offset: 19,
      page: 1,
      block_index: 0,
      span_pairs: [{
        pair_id: "pair-1",
        original_text: "BRCA1",
        english_text: "BRCA1",
        original_start_offset: 0,
        original_end_offset: 5,
        english_start_offset: 0,
        english_end_offset: 5,
        confidence: 0.99,
        method: "deterministic_token",
      }],
    }],
    ...overrides,
  };
}

function annotation(overrides: Partial<UserAnnotation> = {}): UserAnnotation {
  return {
    id: "annotation-1",
    source_document_id: "source-1",
    track: "original",
    paragraph_id: "original-full-text",
    start_offset: 0,
    end_offset: 5,
    color: "#fde68a",
    note: "note",
    author: "tester",
    created_at: "2026-07-09T00:00:00Z",
    updated_at: "2026-07-09T00:00:00Z",
    ...overrides,
  };
}

describe("annotation bilingual synchronization", () => {
  it("mirrors a full-text annotation to the aligned translated span", () => {
    const synchronized = buildSynchronizedAnnotations(detail(), [annotation()]);
    const mirrored = synchronized.find((item) => item.id !== "annotation-1");

    expect(mirrored).toMatchObject({
      track: "translated",
      paragraph_id: "translated-full-text",
      start_offset: 0,
      end_offset: 5,
      color: "#fde68a",
      note: "note",
    });
    expect(sourceAnnotationIdForMutation(mirrored!.id)).toBe("annotation-1");
  });

  it("does not create a mirror when the target span already has a real annotation", () => {
    const synchronized = buildSynchronizedAnnotations(detail(), [
      annotation(),
      annotation({
        id: "annotation-2",
        track: "translated",
        paragraph_id: "translated-full-text",
      }),
    ]);

    expect(synchronized).toHaveLength(2);
  });
});
