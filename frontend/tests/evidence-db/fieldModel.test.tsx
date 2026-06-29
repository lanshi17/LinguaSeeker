import { describe, expect, it } from "vitest";

import type {
  EvidenceFieldDistribution,
  EvidenceGroupDetailResponse,
  EvidenceGroupItem,
} from "../../src/features/evidence-search/types/evidenceSearch";
import {
  computeConflictCount,
  computeCoverage,
  computeLiteratureQuality,
  computeReviewProgress,
  computeVariantQuality,
  hasFullText,
  hasTranslation,
} from "../../src/features/evidence-db/utils/fieldModel";

function item(overrides: Partial<EvidenceGroupItem>): EvidenceGroupItem {
  return {
    canonical_evidence_id: overrides.canonical_evidence_id ?? "evidence-1",
    field_id: overrides.field_id ?? "A.gene_symbol",
    field_name: overrides.field_name ?? "Gene symbol",
    category: overrides.category ?? "A",
    value: overrides.value ?? "FLCN",
    review_status: overrides.review_status ?? "provisional",
    confidence: overrides.confidence ?? 0.8,
    track: overrides.track ?? "reconciled",
    page: overrides.page ?? null,
  };
}

function distribution(
  overrides: Partial<EvidenceFieldDistribution> = {},
): EvidenceFieldDistribution {
  return {
    by_category: {},
    by_field: {},
    by_status: {},
    by_track: {},
    ...overrides,
  };
}

function detail(
  overrides: Partial<EvidenceGroupDetailResponse> = {},
): EvidenceGroupDetailResponse {
  return {
    group_id: "group-1",
    source_document_id: "doc-1",
    title: "Evidence document",
    pmid: null,
    doi: null,
    original_document_text: null,
    translated_document_text: null,
    original_blocks: null,
    translated_blocks: null,
    gene: "FLCN",
    variant: "c.1177-5_-3delCTC",
    disease: "Birt-Hogg-Dube syndrome",
    classification: null,
    item_count: 0,
    avg_confidence: null,
    distribution: distribution(),
    items: [],
    traces: [],
    ...overrides,
  };
}

describe("fieldModel", () => {
  it("computes review progress from evidence item statuses", () => {
    const progress = computeReviewProgress([
      item({ canonical_evidence_id: "approved", review_status: "approved" }),
      item({ canonical_evidence_id: "corrected", review_status: "corrected" }),
      item({ canonical_evidence_id: "rejected", review_status: "rejected" }),
      item({ canonical_evidence_id: "provisional", review_status: "provisional" }),
    ]);

    expect(progress).toEqual({
      total: 4,
      reviewed: 3,
      approved: 1,
      corrected: 1,
      rejected: 1,
      provisional: 1,
      reviewedPercent: 0.75,
    });
  });

  it("computes category coverage over the known evidence categories", () => {
    const coverage = computeCoverage(
      distribution({
        by_category: {
          A: 2,
          B: 1,
          H: 0,
          J: 1,
        },
      }),
    );

    expect(coverage.coveredCategories).toBe(3);
    expect(coverage.totalCategories).toBe(10);
    expect(coverage.coveragePercent).toBe(0.3);
  });

  it("counts contradiction evidence from category and field id", () => {
    const count = computeConflictCount([
      item({ canonical_evidence_id: "category-h", category: "H", field_id: "H.contradiction" }),
      item({ canonical_evidence_id: "field-h", category: null, field_id: "H.other_conflict" }),
      item({ canonical_evidence_id: "normal", category: "A", field_id: "A.gene_symbol" }),
    ]);

    expect(count).toBe(2);
  });

  it("detects full-text availability from text or structured blocks", () => {
    expect(hasFullText(detail({ original_document_text: "full text" }))).toBe(true);
    expect(hasFullText(detail({ original_blocks: [{ type: "text", text: "full text" }] }))).toBe(true);
    expect(hasFullText(detail())).toBe(false);
  });

  it("detects translation availability from text, blocks, or trace snippets", () => {
    expect(hasTranslation(detail({ translated_document_text: "translated text" }))).toBe(true);
    expect(hasTranslation(detail({ translated_blocks: [{ type: "text", text: "translated text" }] }))).toBe(true);
    expect(
      hasTranslation(
        detail({
          traces: [
            {
              canonical_evidence_id: "evidence-1",
              field_id: "A.gene_symbol",
              translated: {
                text: "translated snippet",
                highlight_start: 0,
                highlight_end: 10,
                page: null,
                source_span: {},
              },
            },
          ],
        }),
      ),
    ).toBe(true);
    expect(hasTranslation(detail())).toBe(false);
  });

  it("computes variant quality from evidence group details", () => {
    const quality = computeVariantQuality([
      detail({
        distribution: distribution({ by_category: { A: 2, B: 1 } }),
        items: [
          item({ canonical_evidence_id: "approved", review_status: "approved", category: "A" }),
          item({ canonical_evidence_id: "conflict", review_status: "provisional", category: "H", field_id: "H.contradiction" }),
        ],
      }),
      detail({
        distribution: distribution({ by_category: { F: 1 } }),
        items: [
          item({ canonical_evidence_id: "corrected", review_status: "corrected", category: "F", field_id: "F.functional" }),
        ],
      }),
    ]);

    expect(quality.coverage.coveredCategories).toBe(3);
    expect(quality.coverage.coveragePercent).toBe(0.3);
    expect(quality.reviewProgress.reviewed).toBe(2);
    expect(quality.reviewProgress.reviewedPercent).toBe(2 / 3);
    expect(quality.conflictCount).toBe(1);
  });

  it("computes empty variant quality safely", () => {
    const quality = computeVariantQuality([]);

    expect(quality.coverage.coveredCategories).toBe(0);
    expect(quality.reviewProgress.reviewedPercent).toBe(0);
    expect(quality.conflictCount).toBe(0);
  });

  it("computes literature quality for one evidence group", () => {
    const quality = computeLiteratureQuality(
      detail({
        original_document_text: "source text",
        translated_document_text: "translated text",
        items: [
          item({ canonical_evidence_id: "approved", review_status: "approved", category: "A" }),
          item({ canonical_evidence_id: "conflict", review_status: "rejected", category: "H", field_id: "H.contradiction" }),
        ],
      }),
    );

    expect(quality.hasFullText).toBe(true);
    expect(quality.hasTranslation).toBe(true);
    expect(quality.reviewProgress.reviewed).toBe(2);
    expect(quality.reviewProgress.total).toBe(2);
    expect(quality.conflictCount).toBe(1);
  });
});
